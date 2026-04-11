"""Unit tests for TUI widgets."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from klipperctl.tui.widgets.temperatures import _friendly_name


class TestFriendlyName:
    def test_extruder(self) -> None:
        assert _friendly_name("extruder") == "Hotend"

    def test_heater_bed(self) -> None:
        assert _friendly_name("heater_bed") == "Bed"

    def test_extruder_with_suffix(self) -> None:
        assert _friendly_name("extruder 1") == "Hotend (1)"

    def test_temperature_sensor(self) -> None:
        assert _friendly_name("temperature_sensor chamber") == "chamber"

    def test_temperature_fan(self) -> None:
        assert _friendly_name("temperature_fan exhaust") == "Fan (exhaust)"

    def test_heater_generic(self) -> None:
        assert _friendly_name("heater_generic chamber_heater") == "Heater (chamber_heater)"

    def test_unknown(self) -> None:
        assert _friendly_name("some_sensor") == "some_sensor"


class TestPrinterStatusWidget:
    def test_initial_reactive_values(self) -> None:
        from klipperctl.tui.widgets.status import PrinterStatusWidget

        widget = PrinterStatusWidget()
        assert widget.printer_state == "unknown"
        assert widget.progress == 0.0
        assert widget.elapsed == "--"
        assert widget.eta == "--"
        assert widget.filename == ""

    def test_state_color(self) -> None:
        from klipperctl.tui.widgets.status import PrinterStatusWidget

        widget = PrinterStatusWidget()
        assert widget._state_color("ready") == "green"
        assert widget._state_color("printing") == "cyan"
        assert widget._state_color("paused") == "yellow"
        assert widget._state_color("error") == "red"
        assert widget._state_color("standby") == "dim"
        assert widget._state_color("cancelled") == "red"
        assert widget._state_color("complete") == "green"
        assert widget._state_color("unknown_state") == "white"

    @pytest.mark.asyncio
    async def test_update_from_data_in_app(self) -> None:
        """Test update_from_data when widget is mounted in an app."""
        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.status import PrinterStatusWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as _pilot:
                widget = app.screen.query_one("#printer-status", PrinterStatusWidget)
                widget.update_from_data(
                    state="printing",
                    state_message="",
                    filename="benchy.gcode",
                    progress=0.5,
                    elapsed="30m 0s",
                    eta="30m 0s",
                )
                assert widget.printer_state == "printing"
                assert widget.filename == "benchy.gcode"
                assert widget.progress == 0.5


class TestTemperatureWidget:
    def test_init(self) -> None:
        from klipperctl.tui.widgets.temperatures import TemperatureWidget

        widget = TemperatureWidget()
        assert widget._heater_data == {}
        # Charts are created lazily when real data arrives, not at init.
        assert widget._charts == {}

    @pytest.mark.asyncio
    async def test_update_temperatures_mounts_pinned_charts(self) -> None:
        """Hotend + bed must each get a dedicated HeaterChart on first update."""
        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.heater_chart import HeaterChart
        from klipperctl.tui.widgets.temperatures import TemperatureWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as _pilot:
                widget = app.screen.query_one("#temperatures", TemperatureWidget)
                widget.update_temperatures(
                    {
                        "extruder": (210.5, 210.0),
                        "heater_bed": (60.1, 60.0),
                    }
                )
                assert "extruder" in widget._heater_data
                assert "extruder" in widget._charts
                assert "heater_bed" in widget._charts

                extruder_chart = widget._charts["extruder"]
                bed_chart = widget._charts["heater_bed"]
                assert isinstance(extruder_chart, HeaterChart)
                assert isinstance(bed_chart, HeaterChart)
                # Each chart must have recorded the sample.
                assert len(extruder_chart.history) == 1
                assert extruder_chart.history[-1] == pytest.approx(210.5)
                assert bed_chart.history[-1] == pytest.approx(60.1)
                # Chart reactive values reflect the latest push.
                assert extruder_chart.current == pytest.approx(210.5)
                assert extruder_chart.target == pytest.approx(210.0)

    @pytest.mark.asyncio
    async def test_extra_sensors_go_to_text_row(self) -> None:
        """temperature_sensor entries without a target render as text, not a chart."""
        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.temperatures import TemperatureWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as _pilot:
                widget = app.screen.query_one("#temperatures", TemperatureWidget)
                widget.update_temperatures(
                    {
                        "extruder": (25.0, 0.0),
                        "heater_bed": (23.0, 0.0),
                        "temperature_sensor chamber": (21.5, 0.0),
                    }
                )
                # Extruder + bed still get charts even at zero target.
                assert "extruder" in widget._charts
                assert "heater_bed" in widget._charts
                # The chamber sensor does not get a chart — it's a
                # passive temperature reading.
                assert "temperature_sensor chamber" not in widget._charts


class TestHeaterChartHelpers:
    """Pure-function unit tests for the chart helpers."""

    def test_compute_bounds_empty(self) -> None:
        from klipperctl.tui.widgets.heater_chart import _compute_bounds

        lo, hi = _compute_bounds([], 0.0)
        assert lo == 0.0
        assert hi > lo  # produces a non-degenerate range

    def test_compute_bounds_with_target_only(self) -> None:
        from klipperctl.tui.widgets.heater_chart import _compute_bounds

        lo, hi = _compute_bounds([], 210.0)
        assert lo <= 210.0 <= hi
        assert hi - lo >= 10.0  # minimum range enforced

    def test_compute_bounds_history_only(self) -> None:
        from klipperctl.tui.widgets.heater_chart import _compute_bounds

        lo, hi = _compute_bounds([100.0, 150.0, 200.0], 0.0)
        assert lo <= 100.0
        assert hi >= 200.0

    def test_compute_bounds_history_plus_target(self) -> None:
        from klipperctl.tui.widgets.heater_chart import _compute_bounds

        # Target above the history range must be included so the line
        # is visible.
        lo, hi = _compute_bounds([180.0, 185.0], 210.0)
        assert lo <= 180.0
        assert hi >= 210.0

    def test_compute_bounds_enforces_min_range(self) -> None:
        from klipperctl.tui.widgets.heater_chart import _compute_bounds

        # Tiny sub-degree variations should not render as a degenerate
        # chart — the autoscaler widens to at least 10 °C.
        lo, hi = _compute_bounds([60.1, 60.2, 60.3], 60.0)
        assert hi - lo >= 10.0

    def test_compute_bounds_never_goes_negative(self) -> None:
        from klipperctl.tui.widgets.heater_chart import _compute_bounds

        lo, _hi = _compute_bounds([1.0, 2.0], 0.0)
        assert lo >= 0.0

    def test_temp_to_row_top(self) -> None:
        from klipperctl.tui.widgets.heater_chart import _temp_to_row

        assert _temp_to_row(100.0, 0.0, 100.0, 6) == 0

    def test_temp_to_row_bottom(self) -> None:
        from klipperctl.tui.widgets.heater_chart import _temp_to_row

        assert _temp_to_row(0.0, 0.0, 100.0, 6) == 5

    def test_temp_to_row_middle(self) -> None:
        from klipperctl.tui.widgets.heater_chart import _temp_to_row

        # Midpoint of a 6-row chart should land somewhere in the middle
        # (2 or 3 depending on rounding).
        row = _temp_to_row(50.0, 0.0, 100.0, 6)
        assert 1 <= row <= 4

    def test_temp_to_row_clamps_out_of_range(self) -> None:
        from klipperctl.tui.widgets.heater_chart import _temp_to_row

        assert _temp_to_row(-10.0, 0.0, 100.0, 6) == 5
        assert _temp_to_row(250.0, 0.0, 100.0, 6) == 0

    def test_friendly_heater(self) -> None:
        from klipperctl.tui.widgets.heater_chart import _friendly_heater

        assert _friendly_heater("extruder") == "Hotend"
        assert _friendly_heater("heater_bed") == "Bed"
        assert _friendly_heater("extruder1") == "Hotend (1)"
        assert _friendly_heater("temperature_sensor chamber") == "chamber"
        assert _friendly_heater("mystery") == "mystery"


class TestRenderHeaterChart:
    """End-to-end tests for the renderer that produces the Rich Text body."""

    def test_header_contains_name_current_and_target(self) -> None:
        from klipperctl.tui.widgets.heater_chart import _render_heater_chart

        text = _render_heater_chart("extruder", 210.5, 210.0, [210.0, 210.5], width=30, height=6)
        plain = text.plain
        # Header line is the first line of the output.
        header = plain.split("\n", 1)[0]
        assert "Hotend" in header
        assert "210.5" in header
        assert "210" in header
        assert "°C" in header

    def test_body_has_expected_row_count(self) -> None:
        from klipperctl.tui.widgets.heater_chart import _render_heater_chart

        text = _render_heater_chart("extruder", 210.0, 210.0, [210.0] * 5, width=30, height=6)
        lines = text.plain.split("\n")
        # 1 header + 6 chart rows = 7 lines.
        assert len(lines) == 7

    def test_body_contains_target_reference_line(self) -> None:
        """Target line should be drawn as ─ across the chart body."""
        from klipperctl.tui.widgets.heater_chart import _render_heater_chart

        text = _render_heater_chart("extruder", 200.0, 210.0, [200.0], width=30, height=6)
        # At least one row should have a run of ─ characters.
        body = text.plain.split("\n", 1)[1]
        assert "─" in body
        # Runs of at least 5 target characters (sanity — should span width).
        assert "─" * 5 in body

    def test_body_contains_current_line_markers(self) -> None:
        """The current history should be drawn with █ block characters."""
        from klipperctl.tui.widgets.heater_chart import _render_heater_chart

        text = _render_heater_chart(
            "extruder", 210.0, 0.0, [200.0, 205.0, 210.0], width=30, height=6
        )
        body = text.plain.split("\n", 1)[1]
        assert "█" in body

    def test_no_target_skips_reference_line(self) -> None:
        """Zero target should skip the target reference line."""
        from klipperctl.tui.widgets.heater_chart import _render_heater_chart

        text = _render_heater_chart("heater_bed", 25.0, 0.0, [25.0, 25.0], width=20, height=5)
        body = text.plain.split("\n", 1)[1]
        # No target line, but current ticks should still be present.
        assert "█" in body
        assert "─" not in body

    def test_empty_history_does_not_crash(self) -> None:
        from klipperctl.tui.widgets.heater_chart import _render_heater_chart

        text = _render_heater_chart("extruder", 0.0, 0.0, [], width=20, height=5)
        # Still renders a header and an empty chart body.
        lines = text.plain.split("\n")
        assert len(lines) == 6  # 1 header + 5 chart rows

    def test_history_right_aligned(self) -> None:
        """Shorter-than-width history lands on the right side of the chart."""
        from klipperctl.tui.widgets.heater_chart import _render_heater_chart

        text = _render_heater_chart("extruder", 200.0, 0.0, [200.0], width=20, height=5)
        body = text.plain.split("\n", 1)[1]
        # The single sample should be in the rightmost few columns of
        # one of the rows. Split into rows and find the block char.
        rows = body.split("\n")
        found_col = None
        for row in rows:
            idx = row.find("█")
            if idx >= 0:
                found_col = idx
                break
        assert found_col is not None
        # With width=20 and a single sample, it should be at column 19.
        assert found_col == 19


class TestHeaterChartWidget:
    """Tests for the Textual HeaterChart widget itself."""

    @pytest.mark.asyncio
    async def test_update_data_records_history(self) -> None:
        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.heater_chart import HeaterChart
        from klipperctl.tui.widgets.temperatures import TemperatureWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(120, 40)) as _pilot:
                temps = app.screen.query_one("#temperatures", TemperatureWidget)
                temps.update_temperatures({"extruder": (100.0, 0.0)})
                temps.update_temperatures({"extruder": (150.0, 200.0)})
                temps.update_temperatures({"extruder": (199.0, 200.0)})

                chart = temps._charts["extruder"]
                assert isinstance(chart, HeaterChart)
                assert chart.history == [100.0, 150.0, 199.0]
                assert chart.target == pytest.approx(200.0)
                assert chart.current == pytest.approx(199.0)

    @pytest.mark.asyncio
    async def test_max_history_enforced(self) -> None:
        """Chart history must be bounded by max_history."""
        from klipperctl.tui.widgets.heater_chart import HeaterChart

        chart = HeaterChart("extruder", max_history=5)
        for i in range(10):
            chart._history.append(float(i))  # direct append to avoid refresh()
        assert len(chart.history) == 5
        assert chart.history == [5.0, 6.0, 7.0, 8.0, 9.0]


class TestNormalizeCommand:
    """Pure-function tests for _normalize_command."""

    def test_trims_surrounding_whitespace(self) -> None:
        from klipperctl.tui.widgets.dashboard_console import _normalize_command

        assert _normalize_command("  G28  \n") == "G28"

    def test_empty_input_returns_empty(self) -> None:
        from klipperctl.tui.widgets.dashboard_console import _normalize_command

        assert _normalize_command("") == ""
        assert _normalize_command("   ") == ""
        assert _normalize_command("\t\n") == ""

    def test_preserves_internal_spacing(self) -> None:
        from klipperctl.tui.widgets.dashboard_console import _normalize_command

        assert _normalize_command("M117 hello world") == "M117 hello world"

    def test_none_is_empty(self) -> None:
        from klipperctl.tui.widgets.dashboard_console import _normalize_command

        # Defensive: the widget shouldn't pass None, but the helper
        # handles it cleanly rather than crashing.
        assert _normalize_command(None) == ""  # type: ignore[arg-type]


class TestDashboardConsoleWidget:
    """Tests for the embedded dashboard gcode console widget."""

    @pytest.mark.asyncio
    async def test_mounts_on_dashboard(self) -> None:
        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as _pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                assert widget is not None

    @pytest.mark.asyncio
    async def test_submit_echoes_and_posts_message(self) -> None:
        """Enter on a non-empty line must echo + post Submitted."""
        from textual.widgets import Input, RichLog

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.gcode_script.return_value = "ok"
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                input_widget = widget.query_one("#dash-gcode-input", Input)
                input_widget.value = "G28"
                # Programmatically submit by posting the Input.Submitted event.
                widget.on_input_submitted(Input.Submitted(input_widget, "G28"))
                # Give the event loop a tick to process posted messages.
                await pilot.pause(delay=0.2)

                # Echo should be present in the RichLog.
                log = widget.query_one("#console-log", RichLog)
                rendered = "\n".join(str(line) for line in log.lines)
                assert "G28" in rendered

                # History should contain the command.
                assert widget.history == ["G28"]

    @pytest.mark.asyncio
    async def test_empty_submit_is_ignored(self) -> None:
        """Whitespace-only submission must not post or record history."""
        from textual.widgets import Input

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as _pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                input_widget = widget.query_one("#dash-gcode-input", Input)
                widget.on_input_submitted(Input.Submitted(input_widget, "   "))
                assert widget.history == []

    @pytest.mark.asyncio
    async def test_append_result_renders_success_and_error(self) -> None:
        """append_result must write success and error lines to the log."""
        from textual.widgets import RichLog

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as _pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                widget.append_result("FIRMWARE_NAME: Klipper v0.12", is_error=False)
                widget.append_result("Unknown command", is_error=True)
                log = widget.query_one("#console-log", RichLog)
                rendered = "\n".join(str(line) for line in log.lines)
                assert "FIRMWARE_NAME" in rendered
                assert "Unknown command" in rendered

    @pytest.mark.asyncio
    async def test_history_cycles_with_up_down(self) -> None:
        """Up walks back through history; Down walks forward and restores draft."""
        from textual.widgets import Input

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as _pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                # Seed history directly without going through the event path.
                widget._history.extend(["G28", "M115", "M117 hi"])
                input_widget = widget.query_one("#dash-gcode-input", Input)
                # User types a draft they haven't submitted yet.
                input_widget.value = "draft-in-progress"
                # First Up jumps to most recent history entry, remembering
                # the draft.
                widget.action_history_prev()
                assert input_widget.value == "M117 hi"
                # Another Up: one step older.
                widget.action_history_prev()
                assert input_widget.value == "M115"
                # And another.
                widget.action_history_prev()
                assert input_widget.value == "G28"
                # Clamp at oldest — another Up stays put.
                widget.action_history_prev()
                assert input_widget.value == "G28"
                # Now Down: M115
                widget.action_history_next()
                assert input_widget.value == "M115"
                # Down: M117 hi
                widget.action_history_next()
                assert input_widget.value == "M117 hi"
                # Down past the newest: restores the draft.
                widget.action_history_next()
                assert input_widget.value == "draft-in-progress"

    @pytest.mark.asyncio
    async def test_consecutive_duplicates_collapsed(self) -> None:
        """Submitting the same command twice should not record it twice."""
        from textual.widgets import Input

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as _pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                input_widget = widget.query_one("#dash-gcode-input", Input)
                widget.on_input_submitted(Input.Submitted(input_widget, "G28"))
                widget.on_input_submitted(Input.Submitted(input_widget, "G28"))
                widget.on_input_submitted(Input.Submitted(input_widget, "M115"))
                widget.on_input_submitted(Input.Submitted(input_widget, "G28"))
                # Adjacent duplicates collapse; non-adjacent repeats do not.
                assert widget.history == ["G28", "M115", "G28"]

    @pytest.mark.asyncio
    async def test_dashboard_forwards_submission_to_app(self) -> None:
        """DashboardScreen must wire Submitted → app.send_gcode with callback."""
        from textual.widgets import Input, RichLog

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.gcode_script.return_value = "ok"
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                input_widget = widget.query_one("#dash-gcode-input", Input)
                input_widget.value = "G28"
                widget.on_input_submitted(Input.Submitted(input_widget, "G28"))
                # The worker dispatches on_result back into the widget.
                # Give the event loop time for the worker + callback.
                await pilot.pause(delay=0.5)
                log = widget.query_one("#console-log", RichLog)
                rendered = "\n".join(str(line) for line in log.lines)
                # Echo of the command.
                assert "G28" in rendered
                # Result from the mocked printer — the green success text.
                assert "ok" in rendered
                # mock_client.gcode_script should have been called with
                # the exact command.
                mock_client.gcode_script.assert_called_with("G28")

    @pytest.mark.asyncio
    async def test_error_result_rendered_as_error(self) -> None:
        """A MoonrakerError from the worker must show as an error line."""
        from moonraker_client.exceptions import MoonrakerAPIError
        from textual.widgets import Input, RichLog

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.gcode_script.side_effect = MoonrakerAPIError(
                "Unknown command: NOT_A_COMMAND", status_code=400
            )
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                input_widget = widget.query_one("#dash-gcode-input", Input)
                input_widget.value = "NOT_A_COMMAND"
                widget.on_input_submitted(Input.Submitted(input_widget, "NOT_A_COMMAND"))
                await pilot.pause(delay=0.5)
                log = widget.query_one("#console-log", RichLog)
                rendered = "\n".join(str(line) for line in log.lines)
                assert "NOT_A_COMMAND" in rendered
                assert "Unknown command" in rendered


class TestDashboardConsoleBackfill:
    """Tests for the mount-time gcode store backfill (bug 1)."""

    @pytest.mark.asyncio
    async def test_backfills_gcode_store_on_mount(self) -> None:
        """The widget should call app.fetch_gcode_store on mount and
        render returned entries above the 'ready' line.
        """
        from textual.widgets import RichLog

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            # Pretend the virtual printer has three recent entries.
            mock_client.server_gcodestore.return_value = {
                "gcode_store": [
                    {"time": 1700000000.0, "type": "command", "message": "G28"},
                    {"time": 1700000001.0, "type": "response", "message": "ok"},
                    {"time": 1700000002.0, "type": "command", "message": "M115"},
                ]
            }
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                # Wait for the backfill worker + callback round trip.
                await pilot.pause(delay=0.5)
                log = widget.query_one("#console-log", RichLog)
                rendered = "\n".join(str(line) for line in log.lines)
                assert "G28" in rendered
                assert "ok" in rendered
                assert "M115" in rendered
                # Ready line still there.
                assert "Dashboard console ready" in rendered
                # Backfill was actually called.
                mock_client.server_gcodestore.assert_called()

    @pytest.mark.asyncio
    async def test_backfill_on_empty_store_is_clean(self) -> None:
        """If the store is empty, the widget just shows the ready line."""
        from textual.widgets import RichLog

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {"gcode_store": []}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                await pilot.pause(delay=0.5)
                log = widget.query_one("#console-log", RichLog)
                rendered = "\n".join(str(line) for line in log.lines)
                assert "Dashboard console ready" in rendered
                # No end-of-history separator when there's nothing to show.
                assert "end of recent history" not in rendered

    @pytest.mark.asyncio
    async def test_backfill_error_is_silent(self) -> None:
        """Errors during backfill must not crash the mount path."""
        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.side_effect = RuntimeError("boom")
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                # Should still mount cleanly.
                await pilot.pause(delay=0.5)
                assert widget is not None

    def test_append_history_entry_command(self) -> None:
        """append_history_entry handles command-type entries."""
        # Pure function-like test — no Textual app needed because we
        # hit _write indirectly through a minimal harness.
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        captured: list[str] = []

        class _Harness(DashboardConsoleWidget):
            def _write(self, markup: str) -> None:  # type: ignore[override]
                captured.append(markup)

        w = _Harness()
        w.append_history_entry({"time": 1700000000.0, "type": "command", "message": "G28"})
        assert any("G28" in c for c in captured)
        assert any("dim cyan" in c for c in captured)

    def test_append_history_entry_response(self) -> None:
        """append_history_entry handles response-type entries in plain dim."""
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        captured: list[str] = []

        class _Harness(DashboardConsoleWidget):
            def _write(self, markup: str) -> None:  # type: ignore[override]
                captured.append(markup)

        w = _Harness()
        w.append_history_entry({"time": 1700000000.0, "type": "response", "message": "ok"})
        assert any("ok" in c for c in captured)
        # Response entries use plain dim (not "dim cyan" which is for commands).
        assert not any("dim cyan" in c for c in captured)

    def test_append_history_entry_empty_message_skipped(self) -> None:
        """Empty messages should produce no output."""
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        captured: list[str] = []

        class _Harness(DashboardConsoleWidget):
            def _write(self, markup: str) -> None:  # type: ignore[override]
                captured.append(markup)

        w = _Harness()
        w.append_history_entry({"time": 1700000000.0, "type": "command", "message": ""})
        assert captured == []


class TestDashboardConsoleEscape:
    """Tests for the escape-releases-focus behavior (bug 3)."""

    def test_escape_noop_when_release_focus_disabled(self) -> None:
        """When release_focus_on_escape is False, on_key returns early
        so escape bubbles to the parent screen.

        This is the full-ConsoleScreen use case: one press of escape
        should pop the screen back, rather than being swallowed by
        the widget to release input focus.
        """
        from textual import events

        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        widget = DashboardConsoleWidget(release_focus_on_escape=False)
        fake_event = events.Key(key="escape", character=None)
        # Should be a no-op — no access to a focused input (the
        # widget isn't mounted), no raising. The early-return guard
        # protects against the unmounted-widget crash path too.
        widget.on_key(fake_event)

    @pytest.mark.asyncio
    async def test_escape_releases_focus_without_quitting(self) -> None:
        """Pressing Escape while the input is focused must release
        focus and NOT trigger app.quit.
        """
        from textual.widgets import Input

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {"gcode_store": []}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                input_widget = widget.query_one("#dash-gcode-input", Input)
                # Focus the input so escape's "release focus" path fires.
                input_widget.focus()
                await pilot.pause(delay=0.1)
                assert input_widget.has_focus
                # Press escape via the real pilot key path.
                await pilot.press("escape")
                await pilot.pause(delay=0.1)
                # Focus must have been released from the input.
                assert not input_widget.has_focus
                # And the app must still be alive (not quit).
                assert app.is_running

    def test_input_css_does_not_clip_to_one_row(self) -> None:
        """Regression guard for bug 2: the Input must not be clamped to
        a single row, which would hide typed text entirely.
        """
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        css = DashboardConsoleWidget.DEFAULT_CSS
        # The fix removes the `height: 1` line on #dash-gcode-input.
        # Guard against it creeping back in.
        assert "#dash-gcode-input" in css
        # No `height: 1` within the input rule.
        # (The outer widget has `height: 14`, so we look for the input
        # selector's block specifically.)
        input_block_start = css.find("#dash-gcode-input")
        input_block_end = css.find("}", input_block_start)
        input_block = css[input_block_start:input_block_end]
        assert "height: 1" not in input_block


class TestDashboardConsoleLiveTail:
    """Tests for the async streaming tail of the gcode store."""

    @pytest.mark.asyncio
    async def test_tail_renders_new_entries_above_watermark(self) -> None:
        """Tail must render entries whose time is newer than the watermark."""
        from textual.widgets import RichLog

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {
                "gcode_store": [
                    {"time": 1000.0, "type": "command", "message": "M104 S200"},
                ]
            }
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                await pilot.pause(delay=0.3)

                widget._on_tail_entries([{"time": 2000.0, "type": "command", "message": "G28"}])
                log = widget.query_one("#console-log", RichLog)
                rendered = "\n".join(str(line) for line in log.lines)
                assert "G28" in rendered
                assert widget._last_time == 2000.0

    @pytest.mark.asyncio
    async def test_tail_skips_entries_at_or_below_watermark(self) -> None:
        """Entries whose timestamp <= watermark must not be re-rendered."""
        from textual.widgets import RichLog

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {"gcode_store": []}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                await pilot.pause(delay=0.3)
                widget._last_time = 5000.0

                log = widget.query_one("#console-log", RichLog)
                baseline = len(log.lines)

                widget._on_tail_entries(
                    [
                        {"time": 4000.0, "type": "command", "message": "OLD"},
                        {"time": 5000.0, "type": "command", "message": "SAME"},
                    ]
                )

                assert len(log.lines) == baseline
                rendered = "\n".join(str(line) for line in log.lines)
                assert "OLD" not in rendered
                assert "SAME" not in rendered
                assert widget._last_time == 5000.0

    @pytest.mark.asyncio
    async def test_tail_dedupes_recent_local_command(self) -> None:
        """Tail entry matching a just-submitted local command must be skipped."""
        from textual.widgets import Input, RichLog

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {"gcode_store": []}
            mock_client.gcode_script.return_value = "ok"
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                await pilot.pause(delay=0.3)

                input_widget = widget.query_one("#dash-gcode-input", Input)
                widget.on_input_submitted(Input.Submitted(input_widget, "G28"))
                await pilot.pause(delay=0.2)

                log = widget.query_one("#console-log", RichLog)
                rendered = "\n".join(str(line) for line in log.lines)
                echoes_before = rendered.count("G28")
                assert echoes_before == 1

                widget._on_tail_entries([{"time": 9999.0, "type": "command", "message": "G28"}])
                rendered_after = "\n".join(str(line) for line in log.lines)
                assert rendered_after.count("G28") == echoes_before, (
                    "tail should have skipped the duplicate local command"
                )
                assert widget._last_time >= 9999.0

    @pytest.mark.asyncio
    async def test_tail_skips_responses_within_local_submit_window(self) -> None:
        """A response within 3s of a local submission is assumed local."""
        from textual.widgets import Input, RichLog

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {"gcode_store": []}
            mock_client.gcode_script.return_value = "FIRMWARE_NAME: Klipper"
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                await pilot.pause(delay=0.3)

                input_widget = widget.query_one("#dash-gcode-input", Input)
                widget.on_input_submitted(Input.Submitted(input_widget, "M115"))
                await pilot.pause(delay=0.3)

                log = widget.query_one("#console-log", RichLog)
                baseline = "\n".join(str(line) for line in log.lines)

                widget._on_tail_entries(
                    [
                        {
                            "time": 9999.0,
                            "type": "response",
                            "message": "FIRMWARE_NAME: Klipper",
                        }
                    ]
                )
                after = "\n".join(str(line) for line in log.lines)
                assert after.count("FIRMWARE_NAME") == baseline.count("FIRMWARE_NAME")

    @pytest.mark.asyncio
    async def test_tail_renders_entries_from_other_sources(self) -> None:
        """Entries that don't match any local echo must be rendered."""
        from textual.widgets import RichLog

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {"gcode_store": []}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                await pilot.pause(delay=0.3)

                widget._on_tail_entries(
                    [
                        {"time": 1.0, "type": "command", "message": "REMOTE_MACRO"},
                        {"time": 2.0, "type": "response", "message": "macro ok"},
                    ]
                )
                log = widget.query_one("#console-log", RichLog)
                rendered = "\n".join(str(line) for line in log.lines)
                assert "REMOTE_MACRO" in rendered
                assert "macro ok" in rendered
                assert widget._last_time == 2.0

    @pytest.mark.asyncio
    async def test_tail_timer_installed_on_mount(self) -> None:
        """The live-tail interval timer must be installed during on_mount."""
        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {"gcode_store": []}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                await pilot.pause(delay=0.2)
                assert widget._tail_timer is not None

    @pytest.mark.asyncio
    async def test_backfill_advances_watermark(self) -> None:
        """After backfill, _last_time must reflect the newest historical entry."""
        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {
                "gcode_store": [
                    {"time": 1000.0, "type": "command", "message": "A"},
                    {"time": 2000.0, "type": "response", "message": "B"},
                    {"time": 3000.0, "type": "command", "message": "C"},
                ]
            }
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                await pilot.pause(delay=0.5)
                assert widget._last_time == 3000.0

    def test_entry_time_handles_malformed_values(self) -> None:
        """_entry_time must coerce bad data to 0.0 rather than crash."""
        from klipperctl.tui.widgets.dashboard_console import _entry_time

        assert _entry_time({"time": 1.5}) == 1.5
        assert _entry_time({"time": "1.5"}) == 1.5
        assert _entry_time({}) == 0.0
        assert _entry_time({"time": None}) == 0.0
        assert _entry_time({"time": "garbage"}) == 0.0

    def test_append_live_entry_command_bold(self) -> None:
        """Live command entries render in bold cyan (not dim)."""
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        captured: list[str] = []

        class _Harness(DashboardConsoleWidget):
            def _write(self, markup: str) -> None:  # type: ignore[override]
                captured.append(markup)

        w = _Harness()
        w.append_live_entry({"type": "command", "message": "G28"})
        assert any("bold cyan" in c for c in captured)
        assert any("G28" in c for c in captured)

    def test_append_live_entry_response_green(self) -> None:
        """Live response entries render in green (visible, not dim)."""
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        captured: list[str] = []

        class _Harness(DashboardConsoleWidget):
            def _write(self, markup: str) -> None:  # type: ignore[override]
                captured.append(markup)

        w = _Harness()
        w.append_live_entry({"type": "response", "message": "ok"})
        assert any("green" in c for c in captured)
        assert any("ok" in c for c in captured)

    def test_append_live_entry_empty_skipped(self) -> None:
        """Empty live entries produce no output."""
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        captured: list[str] = []

        class _Harness(DashboardConsoleWidget):
            def _write(self, markup: str) -> None:  # type: ignore[override]
                captured.append(markup)

        w = _Harness()
        w.append_live_entry({"type": "command", "message": ""})
        assert captured == []

    @pytest.mark.asyncio
    async def test_tail_holds_watermark_when_modal_is_active(self) -> None:
        """Tail must not render (or advance the watermark) when a modal is on top.

        Writing to the RichLog on a covered dashboard causes Textual's
        incremental renderer to paint over the modal in real terminals,
        producing visible artifacts on the right side of modal dialogs
        (the same visible bug as
        ``TestKlipperAppUpdateDashboard.test_update_dashboard_skipped_when_modal_active``
        but for the live-tail path). Holding the watermark guarantees
        the entries are re-rendered the next time the tail fires after
        the modal closes, so no data is lost.
        """
        from textual.widgets import RichLog

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.screens.commands import ResultModal
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {"gcode_store": []}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(160, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                await pilot.pause(delay=0.3)
                log = widget.query_one("#console-log", RichLog)
                baseline = len(log.lines)
                watermark_before = widget._last_time

                app.push_screen(ResultModal("Test", "content"))
                await pilot.pause()
                assert isinstance(app.screen, ResultModal)

                widget._on_tail_entries([{"time": 9999.0, "type": "command", "message": "HIDDEN"}])
                await pilot.pause()
                assert len(log.lines) == baseline
                rendered = "\n".join(str(line) for line in log.lines)
                assert "HIDDEN" not in rendered
                assert widget._last_time == watermark_before

                app.pop_screen()
                await pilot.pause()
                widget._on_tail_entries([{"time": 9999.0, "type": "command", "message": "HIDDEN"}])
                await pilot.pause()
                rendered_after = "\n".join(str(line) for line in log.lines)
                assert "HIDDEN" in rendered_after
                assert widget._last_time == 9999.0

    @pytest.mark.asyncio
    async def test_write_drops_when_modal_covers_dashboard(self) -> None:
        """_write is the last line of defense — any path writing to the
        dashboard console while a modal is on top should be silently
        dropped so the modal stays free of paint artifacts."""
        from textual.widgets import RichLog

        from klipperctl.tui.app import KlipperApp
        from klipperctl.tui.screens.commands import ResultModal
        from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {"gcode_store": []}
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(160, 48)) as pilot:
                widget = app.screen.query_one("#dash-console", DashboardConsoleWidget)
                await pilot.pause(delay=0.3)
                log = widget.query_one("#console-log", RichLog)

                app.push_screen(ResultModal("Test", "content"))
                await pilot.pause()
                baseline = len(log.lines)

                widget.append_info("should-be-dropped")
                widget.append_command("G28")
                widget.append_result("ok")
                await pilot.pause()

                assert len(log.lines) == baseline
                rendered = "\n".join(str(line) for line in log.lines)
                assert "should-be-dropped" not in rendered
                assert "G28" not in rendered


class TestFetchGcodeStore:
    """Unit tests for KlipperApp.fetch_gcode_store (backfill helper)."""

    @pytest.mark.asyncio
    async def test_callback_invoked_with_entries(self) -> None:
        """The callback must receive the gcode_store list verbatim."""
        from klipperctl.tui.app import KlipperApp

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.return_value = {
                "gcode_store": [
                    {"time": 1.0, "type": "command", "message": "G28"},
                    {"time": 2.0, "type": "response", "message": "ok"},
                ]
            }
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                captured: list[list[dict]] = []

                def _on_result(entries: list[dict]) -> None:
                    captured.append(entries)

                app.fetch_gcode_store(count=10, on_result=_on_result)
                await pilot.pause(delay=0.5)
                assert captured, "fetch_gcode_store callback was not invoked"
                assert len(captured[0]) == 2
                assert captured[0][0]["message"] == "G28"

    @pytest.mark.asyncio
    async def test_callback_gets_empty_list_on_error(self) -> None:
        """When the sync call raises, the callback receives []."""
        from klipperctl.tui.app import KlipperApp

        app = KlipperApp(printer_url="http://test:7125")
        with patch.object(app, "_build_sync_client") as mock_build:
            mock_client = MagicMock()
            mock_client.printer_objects_query.return_value = {"status": {}}
            mock_client.server_gcodestore.side_effect = RuntimeError("boom")
            mock_client.close.return_value = None
            mock_build.return_value = mock_client
            async with app.run_test(size=(140, 48)) as pilot:
                captured: list[list[dict]] = []

                def _on_result(entries: list[dict]) -> None:
                    captured.append(entries)

                app.fetch_gcode_store(count=10, on_result=_on_result)
                await pilot.pause(delay=0.5)
                assert captured == [[]]
