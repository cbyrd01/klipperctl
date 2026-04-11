"""Functional tests for the full ConsoleScreen against a live printer.

The full console (``klipperctl tui`` then ``c``) now embeds a
``DashboardConsoleWidget``, so it should share the same backfill +
live-streaming + request-response behavior as the dashboard-embedded
console. These tests pin that the full console:

1. Backfills recent gcode store entries on mount (no literal
   ``[dim]`` markup visible).
2. Streams new entries from other clients while the user is on
   the full console screen.
3. Submits commands through its own input and renders the reply.

All three exercise the full chain against the live virtual printer.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid

import pytest

pytestmark = [pytest.mark.functional, pytest.mark.asyncio]


async def _open_full_console(app, pilot):  # type: ignore[no-untyped-def]
    """Helper: navigate from dashboard to the full console screen."""
    await pilot.press("c")
    await pilot.pause(delay=1.5)
    from klipperctl.tui.screens.console import ConsoleScreen

    assert isinstance(app.screen, ConsoleScreen), (
        f"expected ConsoleScreen, got {type(app.screen).__name__}"
    )


async def test_full_console_backfills_and_has_no_literal_markup(
    moonraker_url: str, printer_ready: bool
) -> None:
    """Full console must populate with recent gcode store on mount and
    must not render literal ``[dim]`` bracket markup (bug 1).
    """
    from moonraker_client import MoonrakerClient
    from moonraker_client.helpers import send_gcode
    from textual.widgets import RichLog

    from klipperctl.tui.app import KlipperApp
    from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

    _ = printer_ready

    marker = f"KLIPPERCTL_FULL_BACKFILL_{uuid.uuid4().hex[:10]}"
    with MoonrakerClient(base_url=moonraker_url, timeout=15.0) as client:
        send_gcode(client, f"M118 {marker}")
    await asyncio.sleep(0.5)

    app = KlipperApp(printer_url=moonraker_url, poll_interval=1.0)
    async with app.run_test(size=(140, 48)) as pilot:
        await _open_full_console(app, pilot)
        widget = app.screen.query_one("#full-console", DashboardConsoleWidget)
        log = widget.query_one("#console-log", RichLog)
        rendered = "\n".join(str(line) for line in log.lines)

        # Bug 2: backfill visible in the full console.
        assert marker in rendered, (
            f"pre-seeded marker {marker!r} not in full console; log was:\n{rendered}"
        )

        # Bug 1: no literal bracket markup — all [dim] should render
        # as styled text, not visible as bracket characters.
        assert "[dim]" not in rendered
        assert "[/dim]" not in rendered
        # And the ready line should still be present (styled, not literal).
        assert "Dashboard console ready" in rendered


async def test_full_console_streams_new_entries_live(
    moonraker_url: str, printer_ready: bool
) -> None:
    """New gcode store activity from another client must stream into
    the full console log in near real time.
    """
    from moonraker_client import MoonrakerClient
    from moonraker_client.helpers import send_gcode
    from textual.widgets import RichLog

    from klipperctl.tui.app import KlipperApp
    from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

    _ = printer_ready

    app = KlipperApp(printer_url=moonraker_url, poll_interval=1.0)
    async with app.run_test(size=(140, 48)) as pilot:
        await _open_full_console(app, pilot)
        widget = app.screen.query_one("#full-console", DashboardConsoleWidget)
        # Speed up the tail so we don't wait 2 s per poll.
        widget._tail_interval = 0.5
        if widget._tail_timer is not None:
            with contextlib.suppress(Exception):
                widget._tail_timer.stop()
            widget._tail_timer = None
        widget._start_tail()

        await pilot.pause(delay=1.0)
        post_backfill_watermark = widget._last_time

        marker = f"KLIPPERCTL_FULL_STREAM_{uuid.uuid4().hex[:10]}"
        with MoonrakerClient(base_url=moonraker_url, timeout=15.0) as client:
            send_gcode(client, f"M118 {marker}")

        log = widget.query_one("#console-log", RichLog)
        deadline = asyncio.get_event_loop().time() + 12.0
        seen = False
        while asyncio.get_event_loop().time() < deadline:
            await pilot.pause(delay=0.5)
            rendered = "\n".join(str(line) for line in log.lines)
            if marker in rendered:
                seen = True
                break

        assert seen, f"full console did not pick up live marker {marker!r} within 12s"
        assert widget._last_time > post_backfill_watermark


async def test_full_console_submit_renders_reply(moonraker_url: str, printer_ready: bool) -> None:
    """Pressing Enter on the full console's input dispatches to
    send_gcode and renders the reply through the widget's
    on_result callback path.
    """
    from textual.widgets import Input, RichLog

    from klipperctl.tui.app import KlipperApp
    from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

    _ = printer_ready

    app = KlipperApp(printer_url=moonraker_url, poll_interval=1.0)
    async with app.run_test(size=(140, 48)) as pilot:
        await _open_full_console(app, pilot)
        widget = app.screen.query_one("#full-console", DashboardConsoleWidget)
        input_widget = widget.query_one("#dash-gcode-input", Input)

        marker = f"KLIPPERCTL_FULL_SUBMIT_{uuid.uuid4().hex[:10]}"
        widget.on_input_submitted(Input.Submitted(input_widget, f"M118 {marker}"))

        # Wait for the send-gcode worker to finish and the callback
        # to land in the RichLog.
        log = widget.query_one("#console-log", RichLog)
        deadline = asyncio.get_event_loop().time() + 10.0
        echo_seen = False
        while asyncio.get_event_loop().time() < deadline:
            await pilot.pause(delay=0.3)
            rendered = "\n".join(str(line) for line in log.lines)
            if marker in rendered:
                echo_seen = True
                break
        assert echo_seen, f"full console did not show the submitted M118 marker {marker!r}"


async def test_full_console_escape_pops_screen_in_one_press(
    moonraker_url: str, printer_ready: bool
) -> None:
    """Pressing Escape on the full console must return to the
    dashboard in a single keypress, not two (because the full
    console sets ``release_focus_on_escape=False`` on the widget).
    """
    from klipperctl.tui.app import KlipperApp
    from klipperctl.tui.screens.console import ConsoleScreen
    from klipperctl.tui.screens.dashboard import DashboardScreen

    _ = printer_ready

    app = KlipperApp(printer_url=moonraker_url, poll_interval=1.0)
    async with app.run_test(size=(140, 48)) as pilot:
        await _open_full_console(app, pilot)
        assert isinstance(app.screen, ConsoleScreen)
        await pilot.press("escape")
        await pilot.pause(delay=0.3)
        assert isinstance(app.screen, DashboardScreen)
