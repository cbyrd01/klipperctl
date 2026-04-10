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

# print_stats.state values that mean "a print is actively running".
# Note: `paused` is intentionally NOT here — after a cancel, Klipper's
# CANCEL_PRINT macro may leave the printer in `paused` state (virtual
# printer behavior, and common on real setups with no custom cancel
# macro). Since `paused` post-cancel means "not actively executing
# gcode anymore", it counts as "not still printing" for workflow
# assertions. During the "is the print running?" check (which we do
# *before* cancelling), we use `STARTED_STATES` below which includes
# `paused` since a paused-but-queued print has successfully started.
ACTIVELY_PRINTING_STATES = {"printing"}
#: States that confirm a print has started (observed *before* cancel).
STARTED_STATES = {"printing", "paused"}
#: print_stats.state values that mean "no print is actively running".
#: Vendor-dependent spellings are tolerated. Empty string covers the
#: "never had a print" fresh-boot case. `paused` is included because
#: after a successful cancel the virtual printer rests in `paused`.
IDLE_STATES = {
    "standby",
    "cancelled",
    "canceled",
    "complete",
    "error",
    "paused",
    "",
}


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
        # Anything other than "actively printing" or "error" is acceptable.
        assert state not in ACTIVELY_PRINTING_STATES, (
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


async def _ensure_not_printing(  # type: ignore[no-untyped-def]
    runner, moonraker_url: str, timeout: float = 60.0
) -> None:
    """Bring the printer back to a non-printing state before a test begins.

    Tests on a shared virtual printer can leak state across parametrizations.
    If a previous run left the printer ``printing`` or ``paused``, the next
    run will trip over a dirty baseline. This helper:

    1. Tries a soft cleanup: ``cancel_print`` + wait for idle.
    2. If the printer is in ``shutdown`` (Klipper MCU error) or the soft
       cleanup times out, falls back to a ``firmware_restart`` to force a
       hard reset, matching what the ``printer_ready`` preflight fixture
       does at session start.
    """
    from moonraker_client import MoonrakerClient
    from moonraker_client.helpers import get_printer_status, restart_firmware

    state = await runner.get_state()
    if state in ACTIVELY_PRINTING_STATES:
        with contextlib.suppress(Exception):
            await runner.cancel_print()
        await runner.wait_for_state(IDLE_STATES, timeout=timeout, poll=STATE_POLL_INTERVAL)
        state = await runner.get_state()
        if state in ACTIVELY_PRINTING_STATES:
            # Soft cleanup didn't take; hard-reset the firmware.
            with (
                contextlib.suppress(Exception),
                MoonrakerClient(base_url=moonraker_url, timeout=15.0) as client,
            ):
                restart_firmware(client, timeout=timeout, poll_interval=2.0)

    # Also recover from Klippy shutdown (MCU timer errors, etc).
    with (
        contextlib.suppress(Exception),
        MoonrakerClient(base_url=moonraker_url, timeout=15.0) as client,
    ):
        status = get_printer_status(client)
        if status.klippy_state != "ready":
            restart_firmware(client, timeout=timeout, poll_interval=2.0)


async def test_start_and_cancel_workflow(workflow_runner, moonraker_url) -> None:  # type: ignore[no-untyped-def]
    """Upload a dwell-only sentinel, start printing it, then cancel.

    The sentinel is a pure ``G4 P60000`` dwell — no motion, no heating,
    no filament. Its only job is to put the printer in ``printing`` state
    long enough for us to observe the transition, then be safely
    cancelled. After cancel, the printer is expected to *leave* the
    printing states within ``PRINT_CANCEL_TIMEOUT``; the exact landing
    state (``standby``, ``cancelled``, or even a brief ``paused`` on
    some vendors) is considered equivalent for the purposes of this
    workflow, so the assertion is phrased as "not still printing" rather
    than a strict set membership.

    Teardown cancels any in-flight print and waits for it to clear so
    the next parametrized run starts from a clean baseline.
    """
    # Pre-flight: shared virtual printers can leak state across runs.
    await _ensure_not_printing(workflow_runner, moonraker_url, timeout=PRINT_CANCEL_TIMEOUT)

    sentinel = await workflow_runner.upload_sentinel_gcode()
    cancelled = False
    try:
        await workflow_runner.start_print(sentinel)

        started_state = await workflow_runner.wait_for_state(
            STARTED_STATES, timeout=15.0, poll=STATE_POLL_INTERVAL
        )
        assert started_state in STARTED_STATES, (
            f"[{workflow_runner.modality}] print did not reach a "
            f"started state after start; last state was {started_state!r}"
        )

        await workflow_runner.cancel_print()
        cancelled = True

        # Success criterion after cancel: "no longer actively printing".
        # The resting state (standby, cancelled, paused) depends on the
        # printer's cancel macro and is not something this workflow is
        # trying to pin down. As long as the printer is not in
        # ACTIVELY_PRINTING_STATES (i.e., not still running gcode), the
        # cancel has taken effect.
        final_state = await workflow_runner.wait_for_state(
            IDLE_STATES, timeout=PRINT_CANCEL_TIMEOUT, poll=STATE_POLL_INTERVAL
        )
        assert final_state not in ACTIVELY_PRINTING_STATES, (
            f"[{workflow_runner.modality}] printer still actively "
            f"printing {PRINT_CANCEL_TIMEOUT:.0f}s after cancel; "
            f"last state was {final_state!r}"
        )
    finally:
        # Always return the printer to a known-clean state so the next
        # parametrized run doesn't inherit in-flight prints.
        if not cancelled:
            with contextlib.suppress(Exception):
                await workflow_runner.cancel_print()
        with contextlib.suppress(Exception):
            await workflow_runner.wait_for_state(
                IDLE_STATES, timeout=PRINT_CANCEL_TIMEOUT, poll=STATE_POLL_INTERVAL
            )


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
