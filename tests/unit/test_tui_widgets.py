"""Unit tests for TUI widgets."""

from __future__ import annotations

from collections import deque
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
        assert widget._history == {}

    def test_history_tracking(self) -> None:
        from klipperctl.tui.widgets.temperatures import TemperatureWidget

        widget = TemperatureWidget()
        widget._history["extruder"] = deque(maxlen=widget.MAX_HISTORY)
        widget._history["extruder"].append(200.0)
        widget._history["extruder"].append(201.0)
        assert len(widget._history["extruder"]) == 2
        assert list(widget._history["extruder"]) == [200.0, 201.0]

    def test_max_history_limit(self) -> None:
        from klipperctl.tui.widgets.temperatures import TemperatureWidget

        widget = TemperatureWidget()
        widget._history["test"] = deque(maxlen=widget.MAX_HISTORY)
        for i in range(100):
            widget._history["test"].append(float(i))
        assert len(widget._history["test"]) == widget.MAX_HISTORY

    @pytest.mark.asyncio
    async def test_update_temperatures_in_app(self) -> None:
        """Test update_temperatures when widget is mounted."""
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
                        "extruder": (210.5, 210.0),
                        "heater_bed": (60.1, 60.0),
                    }
                )
                assert "extruder" in widget._heater_data
                assert len(widget._history["extruder"]) == 1
