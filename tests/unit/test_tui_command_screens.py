"""Unit tests for individual command group screens in the TUI."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("textual")

from klipperctl.tui.app import KlipperApp


def _make_app() -> tuple[KlipperApp, MagicMock]:
    """Create an app with a mocked client."""
    app = KlipperApp(printer_url="http://test:7125")
    mock_client = MagicMock()
    mock_client.printer_objects_query.return_value = {"status": {}}
    mock_client.close.return_value = None
    return app, mock_client


class TestPrinterCommandScreen:
    @pytest.mark.asyncio
    async def test_printer_screen_lists_commands(self) -> None:
        app, mock_client = _make_app()
        with patch.object(app, "_build_sync_client", return_value=mock_client):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("m")
                await pilot.pause()
                # Select "Printer Control" (first item)
                from klipperctl.tui.screens.commands import CommandMenuScreen

                assert isinstance(app.screen, CommandMenuScreen)
                from textual.widgets import ListView

                lv = app.screen.query_one(ListView)
                lv.index = 0
                await pilot.press("enter")
                await pilot.pause()
                from klipperctl.tui.screens.commands import PrinterCommandScreen

                assert isinstance(app.screen, PrinterCommandScreen)

    @pytest.mark.asyncio
    async def test_printer_screen_back(self) -> None:
        app, mock_client = _make_app()
        with patch.object(app, "_build_sync_client", return_value=mock_client):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("m")
                await pilot.pause()
                from textual.widgets import ListView

                lv = app.screen.query_one(ListView)
                lv.index = 0
                await pilot.press("enter")
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                from klipperctl.tui.screens.commands import CommandMenuScreen

                assert isinstance(app.screen, CommandMenuScreen)


class TestPrintCommandScreen:
    @pytest.mark.asyncio
    async def test_print_screen_renders(self) -> None:
        app, mock_client = _make_app()
        with patch.object(app, "_build_sync_client", return_value=mock_client):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("m")
                await pilot.pause()
                from textual.widgets import ListView

                lv = app.screen.query_one(ListView)
                lv.index = 1  # "Print Jobs"
                await pilot.press("enter")
                await pilot.pause()
                from klipperctl.tui.screens.commands import PrintCommandScreen

                assert isinstance(app.screen, PrintCommandScreen)


class TestFilesCommandScreen:
    @pytest.mark.asyncio
    async def test_files_screen_renders(self) -> None:
        app, mock_client = _make_app()
        with patch.object(app, "_build_sync_client", return_value=mock_client):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("m")
                await pilot.pause()
                from textual.widgets import ListView

                lv = app.screen.query_one(ListView)
                lv.index = 2  # "File Management"
                await pilot.press("enter")
                await pilot.pause()
                from klipperctl.tui.screens.commands import FilesCommandScreen

                assert isinstance(app.screen, FilesCommandScreen)


class TestHistoryCommandScreen:
    @pytest.mark.asyncio
    async def test_history_screen_renders(self) -> None:
        app, mock_client = _make_app()
        with patch.object(app, "_build_sync_client", return_value=mock_client):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("m")
                await pilot.pause()
                from textual.widgets import ListView

                lv = app.screen.query_one(ListView)
                lv.index = 3
                await pilot.press("enter")
                await pilot.pause()
                from klipperctl.tui.screens.commands import HistoryCommandScreen

                assert isinstance(app.screen, HistoryCommandScreen)


class TestQueueCommandScreen:
    @pytest.mark.asyncio
    async def test_queue_screen_renders(self) -> None:
        app, mock_client = _make_app()
        with patch.object(app, "_build_sync_client", return_value=mock_client):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("m")
                await pilot.pause()
                from textual.widgets import ListView

                lv = app.screen.query_one(ListView)
                lv.index = 4
                await pilot.press("enter")
                await pilot.pause()
                from klipperctl.tui.screens.commands import QueueCommandScreen

                assert isinstance(app.screen, QueueCommandScreen)


class TestServerCommandScreen:
    @pytest.mark.asyncio
    async def test_server_screen_renders(self) -> None:
        app, mock_client = _make_app()
        with patch.object(app, "_build_sync_client", return_value=mock_client):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("m")
                await pilot.pause()
                from textual.widgets import ListView

                lv = app.screen.query_one(ListView)
                lv.index = 5
                await pilot.press("enter")
                await pilot.pause()
                from klipperctl.tui.screens.commands import ServerCommandScreen

                assert isinstance(app.screen, ServerCommandScreen)


class TestSystemCommandScreen:
    @pytest.mark.asyncio
    async def test_system_screen_renders(self) -> None:
        app, mock_client = _make_app()
        with patch.object(app, "_build_sync_client", return_value=mock_client):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("m")
                await pilot.pause()
                from textual.widgets import ListView

                lv = app.screen.query_one(ListView)
                lv.index = 6
                await pilot.press("enter")
                await pilot.pause()
                from klipperctl.tui.screens.commands import SystemCommandScreen

                assert isinstance(app.screen, SystemCommandScreen)


class TestUpdateCommandScreen:
    @pytest.mark.asyncio
    async def test_update_screen_renders(self) -> None:
        app, mock_client = _make_app()
        with patch.object(app, "_build_sync_client", return_value=mock_client):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("m")
                await pilot.pause()
                from textual.widgets import ListView

                lv = app.screen.query_one(ListView)
                lv.index = 7
                await pilot.press("enter")
                await pilot.pause()
                from klipperctl.tui.screens.commands import UpdateCommandScreen

                assert isinstance(app.screen, UpdateCommandScreen)


class TestPowerCommandScreen:
    @pytest.mark.asyncio
    async def test_power_screen_renders(self) -> None:
        app, mock_client = _make_app()
        with patch.object(app, "_build_sync_client", return_value=mock_client):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("m")
                await pilot.pause()
                from textual.widgets import ListView

                lv = app.screen.query_one(ListView)
                lv.index = 8
                await pilot.press("enter")
                await pilot.pause()
                from klipperctl.tui.screens.commands import PowerCommandScreen

                assert isinstance(app.screen, PowerCommandScreen)


class TestAuthCommandScreen:
    @pytest.mark.asyncio
    async def test_auth_screen_renders(self) -> None:
        app, mock_client = _make_app()
        with patch.object(app, "_build_sync_client", return_value=mock_client):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("m")
                await pilot.pause()
                from textual.widgets import ListView

                lv = app.screen.query_one(ListView)
                lv.index = 9
                await pilot.press("enter")
                await pilot.pause()
                from klipperctl.tui.screens.commands import AuthCommandScreen

                assert isinstance(app.screen, AuthCommandScreen)


class TestConfigCommandScreen:
    @pytest.mark.asyncio
    async def test_config_screen_renders(self) -> None:
        app, mock_client = _make_app()
        with patch.object(app, "_build_sync_client", return_value=mock_client):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("m")
                await pilot.pause()
                from textual.widgets import ListView

                lv = app.screen.query_one(ListView)
                lv.index = 10
                await pilot.press("enter")
                await pilot.pause()
                from klipperctl.tui.screens.commands import ConfigCommandScreen

                assert isinstance(app.screen, ConfigCommandScreen)


class TestBuildSetTempArgs:
    def test_hotend_only(self) -> None:
        from klipperctl.tui.screens.commands import _build_set_temp_args

        args = _build_set_temp_args({"Hotend": "210", "Bed": ""})
        assert args == ["printer", "set-temp", "--hotend", "210"]

    def test_bed_only(self) -> None:
        from klipperctl.tui.screens.commands import _build_set_temp_args

        args = _build_set_temp_args({"Hotend": "", "Bed": "60"})
        assert args == ["printer", "set-temp", "--bed", "60"]

    def test_both(self) -> None:
        from klipperctl.tui.screens.commands import _build_set_temp_args

        args = _build_set_temp_args({"Hotend": "210", "Bed": "60"})
        assert args == ["printer", "set-temp", "--hotend", "210", "--bed", "60"]

    def test_neither(self) -> None:
        from klipperctl.tui.screens.commands import _build_set_temp_args

        args = _build_set_temp_args({"Hotend": "", "Bed": ""})
        assert args is None
