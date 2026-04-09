"""Unit tests for the TUI application and screens."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from klipperctl.tui.app import KlipperApp


class TestKlipperAppInit:
    def test_default_params(self) -> None:
        app = KlipperApp()
        assert app._printer_url == "http://localhost:7125"
        assert app._api_key is None
        assert app._timeout == 30.0

    def test_custom_params(self) -> None:
        app = KlipperApp(
            printer_url="http://printer:7125",
            api_key="test-key",
            timeout=60.0,
        )
        assert app._printer_url == "http://printer:7125"
        assert app._api_key == "test-key"
        assert app._timeout == 60.0

    def test_title(self) -> None:
        app = KlipperApp()
        assert app.TITLE == "klipperctl"

    @pytest.mark.asyncio
    async def test_screens_installed_on_mount(self) -> None:
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as _pilot:
                assert "dashboard" in app._installed_screens
                assert "console" in app._installed_screens
                assert "commands" in app._installed_screens

    def test_bindings_defined(self) -> None:
        app = KlipperApp()
        binding_keys = [b[0] for b in app.BINDINGS]
        assert "d" in binding_keys
        assert "c" in binding_keys
        assert "m" in binding_keys
        assert "q" in binding_keys


class TestKlipperAppBuildClient:
    def test_build_sync_client(self) -> None:
        app = KlipperApp(
            printer_url="http://test:7125",
            api_key="key123",
            timeout=15.0,
        )
        with patch("moonraker_client.MoonrakerClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            app._build_sync_client()
            mock_cls.assert_called_once_with(
                base_url="http://test:7125",
                api_key="key123",
                timeout=15.0,
            )


class TestKlipperAppUpdateDashboard:
    @pytest.mark.asyncio
    async def test_update_dashboard_extracts_heaters(self) -> None:
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as _pilot:
                data = {
                    "extruder": {"temperature": 210.0, "target": 210.0},
                    "heater_bed": {"temperature": 60.0, "target": 60.0},
                    "print_stats": {
                        "state": "printing",
                        "filename": "test.gcode",
                        "print_duration": 1800.0,
                        "message": "",
                    },
                    "virtual_sdcard": {"progress": 0.5},
                }
                app._update_dashboard(data)
                from klipperctl.tui.widgets.status import PrinterStatusWidget

                widget = app.screen.query_one("#printer-status", PrinterStatusWidget)
                assert widget.printer_state == "printing"

    @pytest.mark.asyncio
    async def test_update_dashboard_with_empty_data(self) -> None:
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as _pilot:
                # Empty data should not crash
                app._update_dashboard({})


class TestKlipperAppMounted:
    @pytest.mark.asyncio
    async def test_app_starts_and_shows_dashboard(self) -> None:
        app = KlipperApp(printer_url="http://test:7125")
        # Mock the client to avoid real network calls
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {
                "status": {
                    "extruder": {"temperature": 25.0, "target": 0.0},
                    "heater_bed": {"temperature": 25.0, "target": 0.0},
                    "print_stats": {
                        "state": "standby",
                        "filename": "",
                        "print_duration": 0.0,
                        "message": "",
                    },
                    "virtual_sdcard": {"progress": 0.0},
                }
            }
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as _pilot:
                from klipperctl.tui.screens.dashboard import DashboardScreen

                assert isinstance(app.screen, DashboardScreen)

    @pytest.mark.asyncio
    async def test_app_dashboard_has_widgets(self) -> None:
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as _pilot:
                from klipperctl.tui.widgets.status import PrinterStatusWidget
                from klipperctl.tui.widgets.temperatures import TemperatureWidget

                status = app.screen.query_one("#printer-status", PrinterStatusWidget)
                temps = app.screen.query_one("#temperatures", TemperatureWidget)
                assert status is not None
                assert temps is not None

    @pytest.mark.asyncio
    async def test_navigate_to_commands(self) -> None:
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("m")
                await pilot.pause()
                from klipperctl.tui.screens.commands import CommandMenuScreen

                assert isinstance(app.screen, CommandMenuScreen)

    @pytest.mark.asyncio
    async def test_navigate_to_console(self) -> None:
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("c")
                await pilot.pause()
                from klipperctl.tui.screens.console import ConsoleScreen

                assert isinstance(app.screen, ConsoleScreen)

    @pytest.mark.asyncio
    async def test_navigate_back_from_commands(self) -> None:
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("m")
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                from klipperctl.tui.screens.dashboard import DashboardScreen

                assert isinstance(app.screen, DashboardScreen)

    @pytest.mark.asyncio
    async def test_run_cli_command_shows_result_modal(self) -> None:
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                # Execute a CLI command that doesn't need a real server
                app.run_cli_command(["--help"], title="Help")
                # Wait for worker to complete and modal to appear
                await pilot.pause(delay=1.0)
                from klipperctl.tui.screens.commands import ResultModal

                assert isinstance(app.screen, ResultModal)

    @pytest.mark.asyncio
    async def test_run_cli_command_error_shows_notification(self) -> None:
        """Failed CLI commands should show a notification, not a ResultModal."""
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40), notifications=True) as pilot:
                # Run a command that will fail (nonexistent subcommand)
                app.run_cli_command(["printer", "nonexistent"], title="Bad Command")
                await pilot.pause(delay=1.0)
                # Should NOT show ResultModal — should show notification
                from klipperctl.tui.screens.dashboard import DashboardScreen

                assert isinstance(app.screen, DashboardScreen)
