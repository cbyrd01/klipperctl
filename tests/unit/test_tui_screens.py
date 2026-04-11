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
        """The full ConsoleScreen embeds a DashboardConsoleWidget.

        After Phase 4c, the full ConsoleScreen no longer owns an
        inline RichLog + Input — it composes a
        ``DashboardConsoleWidget`` (ID ``full-console``) which itself
        contains the log (``#console-log``) and input
        (``#dash-gcode-input``). Both IDs are walked by
        ``query_one`` on the screen, so the existing smoke checks
        still find them — we just updated the input ID to match.
        """
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {"gcode_store": []}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("c")
                await pilot.pause()
                from klipperctl.tui.screens.console import ConsoleScreen
                from klipperctl.tui.widgets.dashboard_console import (
                    DashboardConsoleWidget,
                )

                assert isinstance(app.screen, ConsoleScreen)
                widget = app.screen.query_one("#full-console", DashboardConsoleWidget)
                assert widget is not None
                log = app.screen.query_one("#console-log")
                assert log is not None
                inp = app.screen.query_one("#dash-gcode-input")
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
            mock_client.server_gcodestore.return_value = {"gcode_store": []}
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

    @pytest.mark.asyncio
    async def test_console_backfill_renders_history(self) -> None:
        """Full console must render backfilled entries on mount — no
        blank screen with only a ready line.
        """
        from textual.widgets import RichLog

        from klipperctl.tui.screens.console import ConsoleScreen

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {
                "gcode_store": [
                    {"time": 1000.0, "type": "command", "message": "G28"},
                    {"time": 1001.0, "type": "response", "message": "ok"},
                    {"time": 1002.0, "type": "command", "message": "M115"},
                ]
            }
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("c")
                await pilot.pause(delay=0.5)
                assert isinstance(app.screen, ConsoleScreen)
                log = app.screen.query_one("#console-log", RichLog)
                rendered = "\n".join(str(line) for line in log.lines)
                assert "G28" in rendered
                assert "M115" in rendered
                # Ready line also still present.
                assert "Dashboard console ready" in rendered

    @pytest.mark.asyncio
    async def test_console_does_not_render_literal_markup(self) -> None:
        """Regression: the ready line and other info lines must NOT
        render as literal ``[dim]...[/dim]`` bracket text.

        This pins the bug where the old ConsoleScreen built its
        RichLog with ``markup=False`` so the ``[dim]GCode console
        ready. Type commands below.[/dim]`` string was shown
        verbatim instead of being styled.
        """
        from textual.widgets import RichLog

        from klipperctl.tui.screens.console import ConsoleScreen

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {"gcode_store": []}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("c")
                await pilot.pause(delay=0.3)
                assert isinstance(app.screen, ConsoleScreen)
                log = app.screen.query_one("#console-log", RichLog)
                rendered = "\n".join(str(line) for line in log.lines)
                # The ready line is present...
                assert "ready" in rendered.lower() or "Dashboard console ready" in rendered
                # ...but must not contain the literal bracket markup.
                assert "[dim]" not in rendered
                assert "[/dim]" not in rendered

    @pytest.mark.asyncio
    async def test_console_live_tail_timer_installed(self) -> None:
        """Full console must start the live-tail poll timer on mount."""
        from klipperctl.tui.screens.console import ConsoleScreen
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {"gcode_store": []}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("c")
                await pilot.pause(delay=0.3)
                assert isinstance(app.screen, ConsoleScreen)
                widget = app.screen.query_one("#full-console", DashboardConsoleWidget)
                assert widget._tail_timer is not None
                # Full-console uses the non-release escape path.
                assert widget._release_focus_on_escape is False

    @pytest.mark.asyncio
    async def test_console_submit_wires_to_send_gcode(self) -> None:
        """Enter in the full console's input must dispatch to send_gcode
        and render the reply through the widget's on_result callback.
        """
        from textual.widgets import Input, RichLog

        from klipperctl.tui.screens.console import ConsoleScreen
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {"gcode_store": []}
            mock_client.gcode_script.return_value = "ok"
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("c")
                await pilot.pause(delay=0.3)
                assert isinstance(app.screen, ConsoleScreen)
                widget = app.screen.query_one("#full-console", DashboardConsoleWidget)
                input_widget = widget.query_one("#dash-gcode-input", Input)
                widget.on_input_submitted(Input.Submitted(input_widget, "G28"))
                await pilot.pause(delay=0.5)
                log = widget.query_one("#console-log", RichLog)
                rendered = "\n".join(str(line) for line in log.lines)
                assert "G28" in rendered
                assert "ok" in rendered
                mock_client.gcode_script.assert_called_with("G28")

    @pytest.mark.asyncio
    async def test_console_filter_excludes_temp_backfill_entries(self) -> None:
        """A MessageFilter passed to ConsoleScreen must exclude matching
        backfill entries.
        """
        from textual.widgets import RichLog

        from klipperctl.filtering import MessageFilter
        from klipperctl.tui.screens.console import ConsoleScreen

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            # Mix of regular entries and a temperature report that
            # should be excluded by the filter.
            mock_client.server_gcodestore.return_value = {
                "gcode_store": [
                    {"time": 1.0, "type": "command", "message": "G28"},
                    {
                        "time": 2.0,
                        "type": "response",
                        "message": "B:25.0 /0.0 T0:23.0 /0.0",
                    },
                    {"time": 3.0, "type": "command", "message": "M115"},
                ]
            }
            mock_client.close.return_value = None
            mock_build.return_value = mock_client

            # Install a filtered ConsoleScreen as the known screen so
            # pilot.press('c') reaches it.
            filtered = ConsoleScreen(msg_filter=MessageFilter(exclude_temps=True))
            async with app.run_test(size=(120, 40)) as pilot:
                app.install_screen(filtered, "filtered-console")
                app.push_screen("filtered-console")
                await pilot.pause(delay=0.5)

                widget_log = filtered.query_one("#console-log", RichLog)
                rendered = "\n".join(str(line) for line in widget_log.lines)
                assert "G28" in rendered
                assert "M115" in rendered
                # The temperature report should be filtered out.
                assert "B:25.0" not in rendered


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


class TestDashboardEscapeQuit:
    @pytest.mark.asyncio
    async def test_escape_binding_exists_on_dashboard(self) -> None:
        from klipperctl.tui.screens.dashboard import DashboardScreen

        bindings = [b[0] for b in DashboardScreen.BINDINGS]
        assert "escape" in bindings

    @pytest.mark.asyncio
    async def test_escape_does_not_exist_on_command_screens(self) -> None:
        """Escape on sub-screens should go back, not quit."""
        from klipperctl.tui.screens.commands import CommandMenuScreen

        bindings = {b[0]: b[1] for b in CommandMenuScreen.BINDINGS}
        assert bindings.get("escape") == "app.pop_screen"


class TestSelectionScreen:
    @pytest.mark.asyncio
    async def test_selection_screen_renders_items(self) -> None:
        from klipperctl.tui.screens.commands import SelectionScreen

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                items = [
                    ("file1.gcode", "file1.gcode"),
                    ("file2.gcode", "file2.gcode"),
                    ("file3.gcode", "file3.gcode"),
                ]
                app.push_screen(SelectionScreen(title="Select File", items=items))
                await pilot.pause()
                assert isinstance(app.screen, SelectionScreen)
                from textual.widgets import ListView

                lv = app.screen.query_one("#selection-list", ListView)
                assert len(list(lv.children)) == 3

    @pytest.mark.asyncio
    async def test_selection_screen_dismiss_on_select(self) -> None:
        from klipperctl.tui.screens.commands import SelectionScreen

        results: list[str] = []
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                items = [("val1", "Option 1"), ("val2", "Option 2")]
                app.push_screen(
                    SelectionScreen(title="Test", items=items),
                    lambda r: results.append(r),
                )
                await pilot.pause()
                from textual.widgets import ListView

                lv = app.screen.query_one("#selection-list", ListView)
                lv.index = 0
                await pilot.press("enter")
                await pilot.pause()
                assert results == ["val1"]

    @pytest.mark.asyncio
    async def test_selection_screen_escape_dismisses_empty(self) -> None:
        from klipperctl.tui.screens.commands import SelectionScreen

        results: list[str] = []
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                items = [("val1", "Option 1")]
                app.push_screen(
                    SelectionScreen(title="Test", items=items),
                    lambda r: results.append(r),
                )
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                assert results == [""]


class TestFetchFunctions:
    def test_fetch_file_list(self) -> None:
        from klipperctl.tui.screens.commands import _fetch_file_list

        mock_client = MagicMock()
        mock_client.files_list.return_value = [
            {"path": "b.gcode", "modified": 100},
            {"path": "a.gcode", "modified": 200},
        ]
        result = _fetch_file_list(mock_client)
        assert result == [("a.gcode", "a.gcode"), ("b.gcode", "b.gcode")]

    def test_fetch_power_devices(self) -> None:
        from klipperctl.tui.screens.commands import _fetch_power_devices

        mock_client = MagicMock()
        mock_client.power_devices_list.return_value = {
            "devices": [{"device": "printer"}, {"device": "lights"}]
        }
        result = _fetch_power_devices(mock_client)
        assert result == [("printer", "printer"), ("lights", "lights")]

    def test_fetch_services(self) -> None:
        from klipperctl.tui.screens.commands import _fetch_services

        mock_client = MagicMock()
        mock_client.machine_systeminfo.return_value = {
            "system_info": {
                "service_state": {
                    "klipper": {"active_state": "active"},
                    "moonraker": {"active_state": "active"},
                }
            }
        }
        result = _fetch_services(mock_client)
        assert len(result) == 2
        assert result[0][0] == "klipper"
        assert result[1][0] == "moonraker"

    def test_fetch_update_components(self) -> None:
        from klipperctl.tui.screens.commands import _fetch_update_components

        mock_client = MagicMock()
        mock_client.machine_update_status.return_value = {
            "version_info": {
                "klipper": {"version": "v0.12.0"},
                "moonraker": {"version": "v0.8.0"},
            }
        }
        result = _fetch_update_components(mock_client)
        assert len(result) == 2
        assert result[0][0] == "klipper"

    def test_fetch_queue_jobs(self) -> None:
        from klipperctl.tui.screens.commands import _fetch_queue_jobs

        mock_client = MagicMock()
        mock_client.server_jobqueue_status.return_value = {
            "queued_jobs": [
                {"job_id": "abc123", "filename": "test.gcode"},
                {"job_id": "def456", "filename": "benchy.gcode"},
            ]
        }
        result = _fetch_queue_jobs(mock_client)
        assert len(result) == 2
        assert result[0][0] == "abc123"
        assert "test.gcode" in result[0][1]

    def test_fetch_printer_profiles(self) -> None:
        from klipperctl.tui.screens.commands import _fetch_printer_profiles

        mock_config = {
            "default_printer": "voron",
            "printers": {
                "voron": {"url": "http://voron:7125"},
                "ender": {"url": "http://ender:7125"},
            },
        }
        with patch("klipperctl.config.load_config", return_value=mock_config):
            result = _fetch_printer_profiles()
            assert len(result) == 2
            assert result[0][0] == "ender"
            assert result[1][0] == "voron"
            assert "default" in result[1][1]

    def test_fetch_printer_profiles_empty(self) -> None:
        from klipperctl.tui.screens.commands import _fetch_printer_profiles

        with patch("klipperctl.config.load_config", return_value={}):
            result = _fetch_printer_profiles()
            assert result == []


class TestFetchApiListWorker:
    @pytest.mark.asyncio
    async def test_fetch_api_list_success(self) -> None:
        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_client.files_list.return_value = [
                {"path": "test.gcode", "modified": 100},
            ]
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                from klipperctl.tui.screens.commands import _fetch_file_list

                callback_results: list[object] = []
                app.fetch_api_list(
                    _fetch_file_list,
                    lambda items: callback_results.append(items),
                )
                await pilot.pause(delay=1.0)
                assert len(callback_results) == 1
                assert callback_results[0] == [("test.gcode", "test.gcode")]


class TestMarkupSafety:
    """Verify that untrusted API data doesn't crash Rich markup parsing."""

    def test_fetch_file_list_escapes_markup_tags(self) -> None:
        from klipperctl.tui.screens.commands import _fetch_file_list

        mock_client = MagicMock()
        mock_client.files_list.return_value = [
            {"path": "[error] - Unknown.gcode", "modified": 100},
            {"path": "normal.gcode", "modified": 200},
        ]
        result = _fetch_file_list(mock_client)
        # Values should be raw (for CLI args)
        assert result[1][0] == "[error] - Unknown.gcode"
        # Display should have the bracket escaped so Rich doesn't crash
        assert "\\[error]" in result[1][1]

    def test_fetch_services_escapes_brackets(self) -> None:
        from klipperctl.tui.screens.commands import _fetch_services

        mock_client = MagicMock()
        mock_client.machine_systeminfo.return_value = {
            "system_info": {
                "service_state": {
                    "klipper [v1]": {"active_state": "active [ok]"},
                }
            }
        }
        result = _fetch_services(mock_client)
        assert result[0][0] == "klipper [v1]"
        # Display should be escaped so Rich doesn't crash
        assert "\\[" in result[0][1]

    def test_fetch_queue_jobs_escapes_brackets(self) -> None:
        from klipperctl.tui.screens.commands import _fetch_queue_jobs

        mock_client = MagicMock()
        mock_client.server_jobqueue_status.return_value = {
            "queued_jobs": [
                {"job_id": "abc", "filename": "[test] - Unknown.gcode"},
            ]
        }
        result = _fetch_queue_jobs(mock_client)
        assert result[0][0] == "abc"
        assert "\\[" in result[0][1]

    @pytest.mark.asyncio
    async def test_result_modal_with_brackets_in_content(self) -> None:
        """ResultModal should not crash on CLI output containing brackets."""
        from klipperctl.tui.screens.commands import ResultModal

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                # This content would crash with markup=True
                app.push_screen(ResultModal("Test", "Status: [error] - Unknown\nLine 2"))
                await pilot.pause()
                assert isinstance(app.screen, ResultModal)

    @pytest.mark.asyncio
    async def test_selection_screen_with_escaped_items(self) -> None:
        """SelectionScreen should render items with escaped markup safely."""
        from klipperctl.tui.screens.commands import SelectionScreen

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                items = [
                    ("file.gcode", "\\[test] - Unknown.gcode"),
                    ("other.gcode", "normal_file.gcode"),
                ]
                app.push_screen(SelectionScreen(title="Select", items=items))
                await pilot.pause()
                assert isinstance(app.screen, SelectionScreen)

    @pytest.mark.asyncio
    async def test_confirm_modal_with_brackets(self) -> None:
        """ConfirmModal should not crash with brackets in message."""
        from klipperctl.tui.screens.commands import ConfirmModal

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as pilot:
                app.push_screen(ConfirmModal("Delete '[test] - Unknown.gcode'?"))
                await pilot.pause()
                from textual.widgets import Button

                buttons = app.screen.query(Button)
                assert len(list(buttons)) == 2
