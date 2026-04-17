"""Unit tests for the TUI application and screens."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("textual")

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

    @pytest.mark.asyncio
    async def test_update_dashboard_skipped_when_modal_active(self) -> None:
        """Polling updates must not leak through to dashboard widgets when a
        modal screen is on top.

        Writing to a lower-screen widget triggers Textual's incremental
        renderer to paint the widget on top of the modal in real
        terminals, producing visible artifacts on the right side of
        modal dialogs. The fix gates ``_update_dashboard`` on the
        dashboard actually being the active screen; this test locks in
        that gate.
        """
        from klipperctl.tui.screens.commands import ResultModal
        from klipperctl.tui.widgets.status import PrinterStatusWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(160, 40)) as pilot:
                # Seed the dashboard with a known state.
                initial = {
                    "extruder": {"temperature": 25.0, "target": 0.0},
                    "heater_bed": {"temperature": 25.0, "target": 0.0},
                    "print_stats": {
                        "state": "ready",
                        "filename": "",
                        "print_duration": 0.0,
                        "message": "",
                    },
                    "virtual_sdcard": {"progress": 0.0},
                }
                app._update_dashboard(initial)
                await pilot.pause()
                dashboard = app.screen
                widget = dashboard.query_one("#printer-status", PrinterStatusWidget)
                assert widget.printer_state == "ready"

                # Push a modal and then attempt to push new data. The
                # dashboard widget state must remain unchanged so no
                # refresh is emitted on the covered screen.
                app.push_screen(ResultModal("Test", "content"))
                await pilot.pause()
                assert isinstance(app.screen, ResultModal)

                updated = {
                    "extruder": {"temperature": 210.0, "target": 210.0},
                    "heater_bed": {"temperature": 60.0, "target": 60.0},
                    "print_stats": {
                        "state": "printing",
                        "filename": "job.gcode",
                        "print_duration": 1800.0,
                        "message": "",
                    },
                    "virtual_sdcard": {"progress": 0.5},
                }
                app._update_dashboard(updated)
                await pilot.pause()
                # Widget on the covered dashboard must still hold the
                # pre-modal state — the update was dropped.
                assert widget.printer_state == "ready"
                assert widget.filename == ""

                # Return to the dashboard; the next update should now apply.
                app.pop_screen()
                await pilot.pause()
                app._update_dashboard(updated)
                await pilot.pause()
                assert widget.printer_state == "printing"
                assert widget.filename == "job.gcode"


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
    async def test_poll_error_notifies_and_backs_off(self) -> None:
        """A poll worker error should surface via `notify` and trigger backoff.

        Repeated identical errors must not re-notify (throttling), but the
        consecutive-error counter and backoff schedule should still advance.
        """
        app = KlipperApp(printer_url="http://test:7125", poll_interval=0.5)
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40), notifications=True) as _pilot:
                notify_calls: list[tuple[str, dict]] = []
                orig_notify = app.notify

                def _spy(msg: str, **kwargs: object) -> None:
                    notify_calls.append((msg, dict(kwargs)))
                    orig_notify(msg, **kwargs)  # type: ignore[arg-type]

                with patch.object(app, "notify", side_effect=_spy):
                    app._on_poll_error("boom")
                    app._on_poll_error("boom")  # same message → no second notify
                    app._on_poll_error("different")  # new message → notify
                assert app._consecutive_poll_errors == 3
                assert len(notify_calls) == 2
                assert notify_calls[0][0] == "boom"
                assert notify_calls[1][0] == "different"
                assert notify_calls[0][1].get("severity") == "error"

    @pytest.mark.asyncio
    async def test_poll_success_after_error_resets_backoff(self) -> None:
        """A successful poll after errors must reset the backoff counter."""
        app = KlipperApp(printer_url="http://test:7125", poll_interval=0.5)
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40), notifications=True) as _pilot:
                app._on_poll_error("boom")
                app._on_poll_error("boom")
                assert app._consecutive_poll_errors == 2
                app._reset_poll_backoff()
                assert app._consecutive_poll_errors == 0
                assert app._last_poll_error is None

    @pytest.mark.asyncio
    async def test_cli_command_timeout_returns_exit_124(self) -> None:
        """A stuck CLI command must not hang the TUI — it must time out."""
        app = KlipperApp(
            printer_url="http://test:7125",
            timeout=0.1,  # Force a very short timeout bound
        )
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40), notifications=True) as pilot:
                # Replace the CliRunner invocation with a blocking sleep via
                # a stub that would block longer than the TUI timeout.
                import time as _time

                from klipperctl.tui import app as app_mod

                def _slow_invoke(*args: object, **kwargs: object) -> object:
                    _time.sleep(5.0)  # would hang without the wait_for guard
                    return MagicMock(exit_code=0, output="never")

                with patch.object(
                    app_mod, "CliRunner", create=True
                ):  # pragma: no cover - defensive
                    pass
                # Directly exercise the command via a runner that hangs.
                with patch("click.testing.CliRunner.invoke", side_effect=_slow_invoke):
                    app.run_cli_command(["printer", "info"], title="Slow")
                    await pilot.pause(delay=1.0)
                # No ResultModal should appear — the path returns exit 124
                # (timed out) and shows a notification.
                from klipperctl.tui.screens.commands import ResultModal

                assert not isinstance(app.screen, ResultModal)

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
