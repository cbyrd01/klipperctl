"""Functional test fixtures: preflight, live client, and tri-modality runners.

These fixtures are the shared backbone for functional tests that exercise the
full stack against a real Moonraker + Klipper printer. They provide:

- A session-scoped skip if ``MOONRAKER_URL`` is unset so the suite is
  always runnable (locally and in CI) regardless of hardware availability.
- A session-scoped preflight that verifies the printer is reachable and in
  ``klippy_state == "ready"``. If the printer is not ready, a firmware
  restart is attempted once (bounded by ``KLIPPERCTL_TEST_READY_TIMEOUT``,
  default 60s). Tests are skipped — not failed — if the printer cannot be
  brought to ready state, so the suite stays green on a printer that is
  powered off or in an error state.
- A parametrized ``workflow_runner`` fixture that returns a runner
  exposing the same interface across three modalities: the library
  (direct ``moonraker-client`` helper calls), the CLI (Click ``CliRunner``
  against ``klipperctl``), and the TUI (Textual ``app.run_test``). This
  lets a single workflow test exercise all three user-facing layers
  with identical assertions.

Scopes:
- ``moonraker_url``, ``live_client``, ``printer_ready`` — session-scoped
  so the preflight and connectivity checks run at most once per session.
- ``fresh_client``, ``workflow_runner`` — function-scoped so each test
  gets a clean transport and a fresh TUI pilot.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING

import pytest

from tests.functional._harness import (
    CliModalityRunner,
    LibraryRunner,
    TuiRunner,
    WorkflowRunner,
)

if TYPE_CHECKING:
    from moonraker_client import MoonrakerClient

MOONRAKER_URL_ENV = "MOONRAKER_URL"
READY_TIMEOUT_ENV = "KLIPPERCTL_TEST_READY_TIMEOUT"


@pytest.fixture(scope="session")
def moonraker_url() -> str:
    """Session-scoped printer URL; skips the suite if unset."""
    url = os.environ.get(MOONRAKER_URL_ENV)
    if not url:
        pytest.skip(
            f"{MOONRAKER_URL_ENV} not set; skipping functional tests",
            allow_module_level=False,
        )
    return url


@pytest.fixture(scope="session")
def live_client(moonraker_url: str) -> Iterator[MoonrakerClient]:
    """A long-lived client used for session-scoped preflight checks only.

    Per-test tests should use ``fresh_client`` instead so they do not share
    transport state with the preflight fixture.
    """
    from moonraker_client import MoonrakerClient
    from moonraker_client.exceptions import MoonrakerConnectionError, MoonrakerTimeoutError

    client = MoonrakerClient(base_url=moonraker_url, timeout=15.0)
    try:
        # Verify reachability up front so downstream fixtures get a clean
        # skip instead of a noisy traceback.
        try:
            client.server_info()
        except (MoonrakerConnectionError, MoonrakerTimeoutError) as exc:
            pytest.skip(f"Cannot reach Moonraker at {moonraker_url}: {exc}")
        yield client
    finally:
        client.close()


@pytest.fixture(scope="session")
def printer_ready(live_client: MoonrakerClient) -> bool:
    """Guarantee the printer is in ``klippy_state == "ready"`` before tests run.

    If the printer is not ready, attempt one firmware restart and wait up to
    ``KLIPPERCTL_TEST_READY_TIMEOUT`` (default 60s) for recovery. If the
    printer still cannot be brought to ready state, the remaining functional
    tests are **skipped**, not failed — the suite should stay green on a
    powered-off printer.
    """
    from moonraker_client.exceptions import MoonrakerError
    from moonraker_client.helpers import get_printer_status, restart_firmware

    ready_timeout = float(os.environ.get(READY_TIMEOUT_ENV, "60"))

    try:
        status = get_printer_status(live_client)
    except MoonrakerError as exc:
        pytest.skip(f"Cannot query printer status: {exc}")

    if status.klippy_state == "ready":
        return True

    # Not ready — try one firmware restart to recover.
    try:
        recovered = restart_firmware(live_client, timeout=ready_timeout, poll_interval=2.0)
    except MoonrakerError as exc:
        pytest.skip(f"firmware_restart failed while preparing printer: {exc}")

    if not recovered:
        pytest.skip(
            f"Printer not ready after firmware restart "
            f"(waited {ready_timeout:.0f}s; klippy_state was {status.klippy_state!r})"
        )
    return True


@pytest.fixture
def fresh_client(moonraker_url: str, printer_ready: bool) -> Iterator[MoonrakerClient]:
    """Per-test client with its own transport, preflight-gated."""
    from moonraker_client import MoonrakerClient

    _ = printer_ready  # enforce preflight dependency
    client = MoonrakerClient(base_url=moonraker_url, timeout=15.0)
    try:
        yield client
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Tri-modality workflow runner
#
# Each test using `workflow_runner` runs three times — once per modality —
# via `params=["library", "cli", "tui"]`. The three runner classes all
# implement the same interface (see `_harness.WorkflowRunner`), so a single
# test body asserts identical behavior across the stack.
#
# The TUI runner is async-scoped because `app.run_test()` is an async
# context manager. pytest-asyncio handles the bridging automatically.
# ---------------------------------------------------------------------------


@pytest.fixture(params=["library", "cli", "tui"])
def modality(request: pytest.FixtureRequest) -> str:
    """Parametrization marker so tests can introspect their current modality."""
    return str(request.param)


@pytest.fixture
async def workflow_runner(
    modality: str,
    moonraker_url: str,
    printer_ready: bool,
) -> AsyncIterator[WorkflowRunner]:
    """Return a runner for the current modality.

    All three runners expose the same methods (see ``WorkflowRunner`` ABC in
    ``_harness.py``), so tests can be written once and exercised across the
    library, CLI, and TUI layers by parametrizing on ``modality``.
    """
    from moonraker_client import MoonrakerClient

    _ = printer_ready  # enforce preflight dependency

    if modality == "library":
        with MoonrakerClient(base_url=moonraker_url, timeout=15.0) as client:
            yield LibraryRunner(client)
    elif modality == "cli":
        yield CliModalityRunner(moonraker_url)
    elif modality == "tui":
        from klipperctl.tui.app import KlipperApp

        app = KlipperApp(printer_url=moonraker_url, poll_interval=1.0)
        async with app.run_test(size=(120, 40), notifications=True) as pilot:
            yield TuiRunner(app, pilot, moonraker_url)
    else:  # pragma: no cover - fixture param is closed-set
        raise ValueError(f"Unknown modality: {modality}")
