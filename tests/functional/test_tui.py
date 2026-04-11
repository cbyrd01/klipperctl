"""Functional tests for the TUI against a live Moonraker server."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

MOONRAKER_URL = os.environ.get("MOONRAKER_URL", "http://localhost:7125")


@pytest.mark.functional
class TestTuiDashboard:
    """Test the TUI dashboard with a live Moonraker connection."""

    @pytest.mark.asyncio
    async def test_dashboard_loads_real_data(self) -> None:
        """Dashboard should display real printer data from the server."""
        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.screens.dashboard import DashboardScreen
        from klipperctl.tui.widgets.status import PrinterStatusWidget
        from klipperctl.tui.widgets.temperatures import TemperatureWidget

        app = KlipperApp(printer_url=MOONRAKER_URL)
        async with app.run_test(size=(120, 40)) as pilot:
            # Wait for initial poll to complete
            await pilot.pause(delay=3.0)
            assert isinstance(app.screen, DashboardScreen)

            # Status widget should have received data
            status = app.screen.query_one("#printer-status", PrinterStatusWidget)
            assert status.printer_state != "unknown"

            # Temperature widget should have heater data
            temps = app.screen.query_one("#temperatures", TemperatureWidget)
            assert len(temps._heater_data) > 0

    @pytest.mark.asyncio
    async def test_dashboard_navigation(self) -> None:
        """Navigate between dashboard, commands, and console screens."""
        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.screens.commands import CommandMenuScreen
        from klipperctl.tui.screens.console import ConsoleScreen
        from klipperctl.tui.screens.dashboard import DashboardScreen

        app = KlipperApp(printer_url=MOONRAKER_URL)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

            # Go to commands
            await pilot.press("m")
            await pilot.pause()
            assert isinstance(app.screen, CommandMenuScreen)

            # Back to dashboard
            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

            # Go to console
            await pilot.press("c")
            await pilot.pause()
            assert isinstance(app.screen, ConsoleScreen)

            # Back to dashboard
            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

    @pytest.mark.asyncio
    async def test_command_execution(self) -> None:
        """Execute a real command through the TUI command menu."""
        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.screens.commands import CommandMenuScreen

        app = KlipperApp(printer_url=MOONRAKER_URL)
        async with app.run_test(size=(120, 40)) as pilot:
            # Navigate to commands > Server > Info
            await pilot.press("m")
            await pilot.pause()
            assert isinstance(app.screen, CommandMenuScreen)

            from textual.widgets import ListView

            lv = app.screen.query_one(ListView)
            lv.index = 5  # Server
            await pilot.press("enter")
            await pilot.pause()

            from klipperctl.tui.screens.commands import ServerCommandScreen

            assert isinstance(app.screen, ServerCommandScreen)

    @pytest.mark.asyncio
    async def test_modal_blocks_dashboard_widget_updates(self) -> None:
        """Against a live Moonraker, a modal on top of the dashboard must
        freeze the dashboard's widget state until dismissed.

        This is the regression test for the right-side paint-artifact
        bug on modal dialogs: polling worker updates that fire while a
        modal is active were writing directly to dashboard widgets,
        causing Textual's incremental renderer to repaint them on top
        of the modal. The fix gates ``_update_dashboard`` on the
        dashboard being the active screen, so the widget state must be
        invariant while the modal is up.
        """
        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.screens.commands import ResultModal
        from klipperctl.tui.screens.dashboard import DashboardScreen
        from klipperctl.tui.widgets.status import PrinterStatusWidget

        app = KlipperApp(printer_url=MOONRAKER_URL, poll_interval=0.5)
        async with app.run_test(size=(160, 40)) as pilot:
            # Let at least one poll populate the dashboard with real data.
            await pilot.pause(delay=3.0)
            assert isinstance(app.screen, DashboardScreen)
            status = app.screen.query_one("#printer-status", PrinterStatusWidget)
            seeded_state = status.printer_state
            assert seeded_state != "unknown"

            app.push_screen(ResultModal("live-test", "modal body"))
            await pilot.pause()
            assert isinstance(app.screen, ResultModal)

            # Force the widget reactive to a sentinel value. The poll
            # worker keeps firing every 0.5s against the live server;
            # if the gate is broken, the next poll overwrites this.
            sentinel = "__modal_sentinel__"
            status.printer_state = sentinel

            # Wait long enough for several poll cycles to fire against
            # the live server — plenty of chances to clobber the state
            # if the fix regresses.
            await pilot.pause(delay=3.0)
            assert status.printer_state == sentinel, (
                "Dashboard widget was updated while a modal was active — "
                "this causes the right-side paint artifact on modal dialogs"
            )

            app.pop_screen()
            await pilot.pause(delay=2.0)
            # Once the dashboard is active again, polling should
            # overwrite the sentinel with a real state.
            assert status.printer_state != sentinel

    @pytest.mark.asyncio
    async def test_tui_cli_entry(self) -> None:
        """Test the `klipperctl tui` CLI entry point resolves connection."""
        from click.testing import CliRunner

        from klipperctl.cli import cli
        from klipperctl.tui.app import KlipperApp

        runner = CliRunner()
        # Mock run() to prevent blocking
        with patch.object(KlipperApp, "run") as mock_run:
            result = runner.invoke(cli, ["--url", MOONRAKER_URL, "tui"])
            assert result.exit_code == 0
            mock_run.assert_called_once()
