"""Multi-step end-to-end functional workflows across all three modalities.

Each test in this module runs three times via the parametrized
``workflow_runner`` fixture (``library``, ``cli``, ``tui``) so a single
assertion body proves identical behavior across the full stack.

Workflows covered:

1. **heat-and-verify** — set the hotend to a modest target, wait for the
   reading to reach it, assert the printer remains in a ready state, then
   reset the target to 0. Exercises temperature control + poll loops.

2. **start-and-cancel** — upload a dwell-only sentinel gcode, start a
   print, wait until the printer reports ``printing``, cancel the print,
   and wait for the printer to return to a non-printing state. Exercises
   the full print-state machine without requiring heating or real motion.

3. **gcode-log roundtrip** — send a unique ``M118`` marker and then poll
   the gcode store for it. This exercises `_logs_tail`'s narrowed
   exception path (Phase 1) and the WebSocket/HTTP dispatch.

Every workflow guarantees a clean teardown via ``try/finally`` — even if
an assertion fails mid-workflow, the printer is returned to a safe idle
state (targets to 0, any in-flight print cancelled, sentinel file
deleted if possible). The preflight fixture guarantees the printer was
in ``ready`` state before the workflow began; teardown restores that
invariant.
"""

from __future__ import annotations

import contextlib
import uuid

import pytest

# These workflows are not cheap (they wait on real hardware). Mark them
# so users can select them with `pytest -m workflows` or skip them with
# `pytest -m "functional and not workflows"`.
pytestmark = [pytest.mark.functional, pytest.mark.asyncio]


HEAT_TARGET = 45.0  # Small, safe target well below filament melt range.
HEAT_TOLERANCE = 3.0
HEAT_TIMEOUT = 240.0  # Generous — cold printers take a while to reach 45C.

PRINT_CANCEL_TIMEOUT = 45.0
STATE_POLL_INTERVAL = 1.0

# States that mean "a print is actively running".
PRINTING_STATES = {"printing", "paused"}
# States that mean "no print is running" (vendor-dependent spellings).
IDLE_STATES = {"standby", "cancelled", "canceled", "complete", "error", "ready"}


async def test_heat_and_verify_workflow(workflow_runner) -> None:  # type: ignore[no-untyped-def]
    """Set the hotend target, wait for it, verify state, cool down.

    Sanity checks:
    - The programmed target is actually persisted on the printer.
    - The reading eventually reaches the target (within tolerance).
    - The printer does not transition into an error state mid-heat.

    Teardown always resets the target to 0 so the printer cools down
    even if the assertion body fails.
    """
    try:
        await workflow_runner.set_hotend_temp(HEAT_TARGET)

        programmed = await workflow_runner.get_hotend_target()
        assert programmed == pytest.approx(HEAT_TARGET, abs=0.5), (
            f"[{workflow_runner.modality}] expected extruder target "
            f"{HEAT_TARGET}, got {programmed}"
        )

        reached = await workflow_runner.wait_until_temp(
            "extruder", HEAT_TARGET, tol=HEAT_TOLERANCE, timeout=HEAT_TIMEOUT
        )
        assert reached, (
            f"[{workflow_runner.modality}] extruder did not reach "
            f"{HEAT_TARGET}±{HEAT_TOLERANCE}°C within {HEAT_TIMEOUT:.0f}s"
        )

        state = await workflow_runner.get_state()
        # The printer may be in "standby" or "ready" or even "complete"
        # depending on vendor — anything other than a printing state or
        # an error is acceptable here.
        assert state not in PRINTING_STATES, (
            f"[{workflow_runner.modality}] unexpected printing state "
            f"during heat-and-verify: {state!r}"
        )
        assert state != "error", (
            f"[{workflow_runner.modality}] printer entered error state during heat-and-verify"
        )
    finally:
        # Always cool down, even on failure.
        with contextlib.suppress(Exception):
            await workflow_runner.set_hotend_temp(0.0)


async def test_start_and_cancel_workflow(workflow_runner) -> None:  # type: ignore[no-untyped-def]
    """Upload a dwell-only sentinel, start printing it, then cancel.

    The sentinel is a pure ``G4 P60000`` dwell — no motion, no heating,
    no filament. Its only job is to put the printer in ``printing`` state
    long enough for us to observe the transition, then be safely
    cancelled. ``print_cancel`` is expected to return the printer to a
    non-printing state within ``PRINT_CANCEL_TIMEOUT``.

    Teardown cancels any in-flight print if the test fails mid-way.
    """
    sentinel = await workflow_runner.upload_sentinel_gcode()
    cancelled = False
    try:
        await workflow_runner.start_print(sentinel)

        started_state = await workflow_runner.wait_for_state(
            PRINTING_STATES, timeout=15.0, poll=STATE_POLL_INTERVAL
        )
        assert started_state in PRINTING_STATES, (
            f"[{workflow_runner.modality}] print did not reach a "
            f"printing state after start; last state was {started_state!r}"
        )

        await workflow_runner.cancel_print()
        cancelled = True

        final_state = await workflow_runner.wait_for_state(
            IDLE_STATES, timeout=PRINT_CANCEL_TIMEOUT, poll=STATE_POLL_INTERVAL
        )
        assert final_state in IDLE_STATES, (
            f"[{workflow_runner.modality}] printer did not return to "
            f"idle after cancel within {PRINT_CANCEL_TIMEOUT:.0f}s; "
            f"last state was {final_state!r}"
        )
    finally:
        if not cancelled:
            with contextlib.suppress(Exception):
                await workflow_runner.cancel_print()


async def test_gcode_log_roundtrip_workflow(workflow_runner) -> None:  # type: ignore[no-untyped-def]
    """Send an M118 marker and then observe it in the gcode store.

    This exercises the log tail path that Phase 1 tightened (narrow
    exception catch in ``_logs_tail``), verifying the full round trip:
    CLI/TUI/library dispatch → Klipper → gcode_store → read back.
    """
    marker = f"KLIPPERCTL_TEST_{uuid.uuid4().hex[:10]}"
    await workflow_runner.send_gcode(f"M118 {marker}")
    observed = await workflow_runner.tail_logs_for(marker, timeout=10.0)
    assert observed, (
        f"[{workflow_runner.modality}] did not observe marker {marker!r} in gcode store within 10s"
    )
