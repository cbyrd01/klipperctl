"""Functional tests for the dashboard embedded gcode console.

Exercise the real ``DashboardConsoleWidget`` against the live
Moonraker virtual printer: submit a well-known safe gcode command
(``M118`` prints a message to the console/log, ``M115`` reports
firmware info), verify the echo lands in the RichLog, and verify
the printer's reply also lands via the ``on_result`` callback path.

These tests prove the full chain works end-to-end:

    user types → Input.Submitted → widget.post_message(Submitted)
      → DashboardScreen handler → KlipperApp.send_gcode
      → worker → moonraker-client HTTP → Klipper → ok/reply
      → worker callback → widget.append_result → RichLog

A per-test teardown resets any hotend target back to 0 as a
belt-and-braces guard.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid

import pytest

pytestmark = [pytest.mark.functional, pytest.mark.asyncio]


async def _wait_for_reply(widget, marker: str, timeout: float = 10.0) -> bool:
    """Poll the widget's RichLog until ``marker`` appears or timeout.

    Returns True if the marker was observed, False otherwise.
    """
    from textual.widgets import RichLog

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            log = widget.query_one("#console-log", RichLog)
            rendered = "\n".join(str(line) for line in log.lines)
            if marker in rendered:
                return True
        except Exception:
            pass
        await asyncio.sleep(0.2)
    return False


async def test_dashboard_console_roundtrip_safe_command(
    moonraker_url: str, printer_ready: bool
) -> None:
    """M115 is a read-only firmware-info query. Submit through the widget,
    assert the printer's reply lands in the dashboard console log.
    """
    from textual.widgets import Input

    from klipperctl.tui.app import KlipperApp
    from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

    _ = printer_ready

    app = KlipperApp(printer_url=moonraker_url, poll_interval=1.0)
    async with app.run_test(size=(140, 48)) as _pilot:
        widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)

        # Route through the widget's real event handler so the whole
        # chain is exercised, including the DashboardScreen message
        # forwarder and the app's worker dispatch.
        input_widget = widget.query_one("#dash-gcode-input", Input)
        input_widget.value = "M115"
        widget.on_input_submitted(Input.Submitted(input_widget, "M115"))

        # The worker fires on_result with the reply text. The printer
        # will either return "ok" or an info line starting with
        # "FIRMWARE_NAME". Either is an acceptable proof of life; we
        # assert on the command echo + presence of *some* reply.
        got_echo = await _wait_for_reply(widget, "M115", timeout=10.0)
        assert got_echo, "command echo never appeared in RichLog"

        # Wait up to 10 s for any reply (green line prefix " ").
        from textual.widgets import RichLog

        log = widget.query_one("#console-log", RichLog)
        deadline = asyncio.get_event_loop().time() + 10.0
        reply_seen = False
        while asyncio.get_event_loop().time() < deadline:
            rendered = "\n".join(str(line) for line in log.lines)
            lines = rendered.splitlines()
            # Count lines after the echo that start with " " (success
            # prefix) or "!" (error prefix).
            # Echo is bold-cyan "> M115" — skip it and look for
            # anything else that isn't "[dim]".
            reply_lines = [
                line
                for line in lines
                if ("> M115" not in line)
                and line.strip()
                and "Dashboard console ready" not in line
            ]
            if reply_lines:
                reply_seen = True
                break
            await asyncio.sleep(0.2)
        log_text = "\n".join(str(line) for line in log.lines)
        assert reply_seen, f"no reply line appeared after M115; log was:\n{log_text}"


async def test_dashboard_console_m118_marker_roundtrip(
    moonraker_url: str, printer_ready: bool
) -> None:
    """M118 <marker> is the canonical "print to host console" gcode.

    The reply from Klipper for M118 is typically ``ok`` (no payload),
    so to verify the command actually reached the printer we also
    check the gcode store via a direct library client afterwards.
    """
    from textual.widgets import Input

    from klipperctl.tui.app import KlipperApp
    from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

    _ = printer_ready

    marker = f"KLIPPERCTL_DASH_{uuid.uuid4().hex[:10]}"
    app = KlipperApp(printer_url=moonraker_url, poll_interval=1.0)
    async with app.run_test(size=(140, 48)) as _pilot:
        widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
        input_widget = widget.query_one("#dash-gcode-input", Input)
        input_widget.value = f"M118 {marker}"
        widget.on_input_submitted(Input.Submitted(input_widget, f"M118 {marker}"))

        # Echo check.
        assert await _wait_for_reply(widget, marker, timeout=5.0), (
            "echo of M118 command never appeared"
        )

        # Confirm the printer actually executed the command by reading
        # the gcode store directly. The ok reply comes back fast, but
        # the store write can lag a beat.
        from moonraker_client import MoonrakerClient

        observed = False
        deadline = asyncio.get_event_loop().time() + 10.0
        while asyncio.get_event_loop().time() < deadline:
            with MoonrakerClient(base_url=moonraker_url, timeout=15.0) as client:
                result = client.server_gcodestore(count=50)
            entries = []
            if isinstance(result, dict):
                entries = result.get("gcode_store") or result.get("result", {}).get(
                    "gcode_store", []
                )
            if any(marker in (e.get("message") or "") for e in entries):
                observed = True
                break
            await asyncio.sleep(0.3)

        assert observed, f"M118 marker {marker!r} never reached the gcode store"


async def test_backfill_shows_recent_store_entries(
    moonraker_url: str, printer_ready: bool
) -> None:
    """Dashboard console must prefill with recent gcode store on mount.

    Seed the virtual printer's gcode store by sending a unique M118
    marker via a direct library client *before* launching the TUI.
    Then start the app and assert the marker appears in the console
    log WITHOUT the user having to submit anything through the widget.
    This exercises the full ``KlipperApp.fetch_gcode_store`` →
    ``DashboardConsoleWidget._on_history_loaded`` →
    ``append_history_entry`` path against the live printer.
    """
    from textual.widgets import RichLog

    from klipperctl.tui.app import KlipperApp
    from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget
    from moonraker_client import MoonrakerClient
    from moonraker_client.helpers import send_gcode

    _ = printer_ready

    marker = f"KLIPPERCTL_BACKFILL_{uuid.uuid4().hex[:10]}"
    with MoonrakerClient(base_url=moonraker_url, timeout=15.0) as client:
        send_gcode(client, f"M118 {marker}")

    # Small delay so Moonraker's gcode store has a chance to record it.
    await asyncio.sleep(0.5)

    app = KlipperApp(printer_url=moonraker_url, poll_interval=1.0)
    async with app.run_test(size=(140, 48)) as pilot:
        # Wait for the backfill worker to complete.
        await pilot.pause(delay=1.5)
        widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
        log = widget.query_one("#console-log", RichLog)
        rendered = "\n".join(str(line) for line in log.lines)
        assert marker in rendered, (
            f"backfilled marker {marker!r} not visible in console log; "
            f"log was:\n{rendered}"
        )


async def test_dashboard_console_error_path(moonraker_url: str, printer_ready: bool) -> None:
    """A bogus command must be reported via the error-styled path."""
    from textual.widgets import Input

    from klipperctl.tui.app import KlipperApp
    from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

    _ = printer_ready

    app = KlipperApp(printer_url=moonraker_url, poll_interval=1.0)
    try:
        async with app.run_test(size=(140, 48)) as _pilot:
            widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
            input_widget = widget.query_one("#dash-gcode-input", Input)
            # `G1 X1000000` before a homing move reliably returns a
            # Moonraker 400 "Must home axis first" error on any Klipper
            # build, which is the path we want to exercise (worker
            # exception → on_result(is_error=True) → append_result
            # red-styled).
            bogus = "G1 X1000000"
            input_widget.value = bogus
            widget.on_input_submitted(Input.Submitted(input_widget, bogus))

            # Echo should appear.
            assert await _wait_for_reply(widget, bogus, timeout=5.0)

            # Wait for the error reply — "Must home axis first" is the
            # message Klipper returns for unhomed motion.
            from textual.widgets import RichLog

            log = widget.query_one("#console-log", RichLog)
            deadline = asyncio.get_event_loop().time() + 10.0
            err_seen = False
            while asyncio.get_event_loop().time() < deadline:
                rendered = "\n".join(str(line) for line in log.lines)
                # Accept any of the known error surfaces: Klipper's
                # "Must home axis first" message, Moonraker's wrapped
                # error phrasing, or our own worker error prefix.
                if (
                    "Must home axis" in rendered
                    or "HTTP 400" in rendered
                    or "Request failed" in rendered
                ):
                    err_seen = True
                    break
                await asyncio.sleep(0.3)
            assert err_seen, (
                "bogus command did not produce an error-styled line in the log; "
                f"log was:\n{' | '.join(str(line) for line in log.lines)}"
            )
    finally:
        # Belt and braces: make sure nothing got left heating up.
        from moonraker_client import MoonrakerClient
        from moonraker_client.helpers import set_hotend_temp

        with (
            contextlib.suppress(Exception),
            MoonrakerClient(base_url=moonraker_url, timeout=15.0) as client,
        ):
            set_hotend_temp(client, 0.0)
