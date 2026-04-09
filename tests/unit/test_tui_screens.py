"""Unit tests for TUI screens."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from klipperctl.tui.app import KlipperApp


class TestDashboardScreen:
    @pytest.mark.asyncio
    async def test_dashboard_update_status(self) -> None:
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as _pilot:
                from klipperctl.tui.screens.dashboard import DashboardScreen
                from klipperctl.tui.widgets.status import PrinterStatusWidget

                assert isinstance(app.screen, DashboardScreen)
                app.screen.update_status(
                    {
                        "print_stats": {
                            "state": "printing",
                            "filename": "test.gcode",
                            "print_duration": 3600.0,
                            "message": "",
                        },
                        "virtual_sdcard": {"progress": 0.75},
                    }
                )
                widget = app.screen.query_one("#printer-status", PrinterStatusWidget)
                assert widget.printer_state == "printing"
                assert widget.filename == "test.gcode"
                assert widget.progress == 0.75

    @pytest.mark.asyncio
    async def test_dashboard_update_temperatures(self) -> None:
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as _pilot:
                from klipperctl.tui.screens.dashboard import DashboardScreen
                from klipperctl.tui.widgets.temperatures import TemperatureWidget

                assert isinstance(app.screen, DashboardScreen)
                app.screen.update_temperatures(
                    {
                        "extruder": (210.5, 210.0),
                        "heater_bed": (60.1, 60.0),
                    }
                )
                widget = app.screen.query_one("#temperatures", TemperatureWidget)
                assert "extruder" in widget._heater_data
                assert widget._heater_data["extruder"] == (210.5, 210.0)

    @pytest.mark.asyncio
    async def test_dashboard_connection_bar(self) -> None:
        app = KlipperApp(printer_url="http://myprinter:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as _pilot:
                from textual.widgets import Static

                bar = app.screen.query_one("#connection-bar", Static)
                # The connection bar should show the printer URL
                assert "myprinter" in bar.content


class TestConsoleScreen:
    @pytest.mark.asyncio
    async def test_console_screen_renders(self) -> None:
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
                log = app.screen.query_one("#console-log")
                assert log is not None
                inp = app.screen.query_one("#gcode-input")
                assert inp is not None

    @pytest.mark.asyncio
    async def test_console_append_message(self) -> None:
        from klipperctl.tui.screens.console import ConsoleScreen

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("c")
                await pilot.pause()
                screen = app.screen
                assert isinstance(screen, ConsoleScreen)
                # Should not raise
                screen.append_message("Test message")

    @pytest.mark.asyncio
    async def test_console_filter(self) -> None:
        from klipperctl.filtering import MessageFilter
        from klipperctl.tui.screens.console import ConsoleScreen

        msg_filter = MessageFilter(exclude_temps=True)
        screen = ConsoleScreen(msg_filter=msg_filter)
        assert screen._filter.exclude_temps is True

    @pytest.mark.asyncio
    async def test_console_back_navigation(self) -> None:
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
                await pilot.press("escape")
                await pilot.pause()
                from klipperctl.tui.screens.dashboard import DashboardScreen

                assert isinstance(app.screen, DashboardScreen)


class TestCommandMenuScreen:
    @pytest.mark.asyncio
    async def test_command_menu_lists_all_groups(self) -> None:
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

                screen = app.screen
                assert isinstance(screen, CommandMenuScreen)
                # Verify all 11 command groups are listed
                expected_groups = [
                    "printer",
                    "print",
                    "files",
                    "history",
                    "queue",
                    "server",
                    "system",
                    "update",
                    "power",
                    "auth",
                    "config",
                ]
                from textual.widgets import ListView

                list_view = screen.query_one(ListView)
                assert len(list(list_view.children)) == len(expected_groups)

    @pytest.mark.asyncio
    async def test_command_menu_back(self) -> None:
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


class TestConfirmModal:
    @pytest.mark.asyncio
    async def test_confirm_modal_renders(self) -> None:
        from klipperctl.tui.screens.commands import ConfirmModal

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                app.push_screen(ConfirmModal("Test confirmation?"))
                await pilot.pause()
                from textual.widgets import Button

                # Should have confirm and cancel buttons
                buttons = app.screen.query(Button)
                assert len(list(buttons)) == 2

    @pytest.mark.asyncio
    async def test_confirm_modal_cancel(self) -> None:
        from klipperctl.tui.screens.commands import ConfirmModal

        results: list[bool] = []
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                app.push_screen(ConfirmModal("Test?"), lambda r: results.append(r))
                await pilot.pause()
                await pilot.click("#confirm-no")
                await pilot.pause()
                assert results == [False]


class TestResultModal:
    @pytest.mark.asyncio
    async def test_result_modal_renders(self) -> None:
        from klipperctl.tui.screens.commands import ResultModal

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                app.push_screen(ResultModal("Test Title", "Test content"))
                await pilot.pause()
                from textual.widgets import Button

                close_btn = app.screen.query_one("#result-close", Button)
                assert close_btn is not None

    @pytest.mark.asyncio
    async def test_result_modal_close(self) -> None:
        from klipperctl.tui.screens.commands import ResultModal

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                app.push_screen(ResultModal("Test", "Content"))
                await pilot.pause()
                await pilot.click("#result-close")
                await pilot.pause()
                # Should return to dashboard
                from klipperctl.tui.screens.dashboard import DashboardScreen

                assert isinstance(app.screen, DashboardScreen)


class TestInputFormScreen:
    @pytest.mark.asyncio
    async def test_input_form_renders_fields(self) -> None:
        from klipperctl.tui.screens.commands import InputFormScreen

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                app.push_screen(
                    InputFormScreen(
                        title="Test Form",
                        fields=[
                            ("Field1", "placeholder1", True),
                            ("Field2", "placeholder2", False),
                        ],
                        callback=lambda v: ["test"],
                    )
                )
                await pilot.pause()
                from textual.widgets import Input

                inputs = app.screen.query(Input)
                assert len(list(inputs)) == 2

    @pytest.mark.asyncio
    async def test_input_form_cancel(self) -> None:
        from klipperctl.tui.screens.commands import InputFormScreen

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                app.push_screen(
                    InputFormScreen(
                        title="Test",
                        fields=[("Name", "enter name", True)],
                        callback=lambda v: ["test"],
                    )
                )
                await pilot.pause()
                await pilot.click("#form-cancel")
                await pilot.pause()
                from klipperctl.tui.screens.dashboard import DashboardScreen

                assert isinstance(app.screen, DashboardScreen)
