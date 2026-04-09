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
