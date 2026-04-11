"""Functional tests for the per-heater chart widgets against live Moonraker.

These mount the real ``KlipperApp`` via Textual's ``run_test`` pilot,
let the background poll worker run a cycle so the dashboard populates
from the live virtual printer, and then assert that:

- Both pinned heaters (extruder + heater_bed) have a mounted
  :class:`HeaterChart` widget.
- Each chart's history has at least one sample (the polling path
  actually reached the widgets).
- Setting the hotend target through the live CLI path reflects in
  the chart's ``target`` reactive within a reasonable window.

Teardown resets the hotend target to 0 and cancels any accidental
print so the printer is left in a clean state for subsequent tests.
"""

from __future__ import annotations

import asyncio
import contextlib

import pytest

pytestmark = [pytest.mark.functional, pytest.mark.asyncio]


async def _poll_and_wait(app, pilot, timeout: float = 8.0) -> None:
    """Trigger a fresh poll and give the worker time to complete."""
    app.poll_printer()
    # The sync client inside the worker blocks the thread; pause long
    # enough for it to come back and deliver data to the widgets.
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await pilot.pause(delay=0.5)
        try:
            from klipperctl.tui.screens.dashboard import DashboardScreen
            from klipperctl.tui.widgets.temperatures import TemperatureWidget

            if not isinstance(app.screen, DashboardScreen):
                continue
            temps = app.screen.query_one("#temperatures", TemperatureWidget)
            if "extruder" in temps._charts:
                return
        except Exception:
            pass


async def test_dashboard_populates_heater_charts(moonraker_url: str, printer_ready: bool) -> None:
    """After a poll cycle, the dashboard must have hotend + bed charts."""
    from klipperctl.tui.app import KlipperApp
    from klipperctl.tui.widgets.heater_chart import HeaterChart
    from klipperctl.tui.widgets.temperatures import TemperatureWidget

    _ = printer_ready

    app = KlipperApp(printer_url=moonraker_url, poll_interval=1.0)
    async with app.run_test(size=(120, 40)) as pilot:
        await _poll_and_wait(app, pilot, timeout=10.0)

        temps = app.screen.query_one("#temperatures", TemperatureWidget)
        assert "extruder" in temps._charts, (
            f"extruder chart not mounted; seen: {list(temps._charts)}"
        )
        assert "heater_bed" in temps._charts, (
            f"heater_bed chart not mounted; seen: {list(temps._charts)}"
        )

        extruder_chart = temps._charts["extruder"]
        bed_chart = temps._charts["heater_bed"]
        assert isinstance(extruder_chart, HeaterChart)
        assert isinstance(bed_chart, HeaterChart)
        assert len(extruder_chart.history) >= 1
        assert len(bed_chart.history) >= 1


async def test_setting_hotend_target_reflects_in_chart(
    moonraker_url: str, printer_ready: bool
) -> None:
    """Dispatching set-temp through the TUI must update the chart target.

    This end-to-end check proves the whole chain works on live hardware:
    CLI command → Moonraker → Klipper → next poll → widget reactive.
    """
    from moonraker_client import MoonrakerClient
    from moonraker_client.helpers import set_hotend_temp

    from klipperctl.tui.app import KlipperApp
    from klipperctl.tui.widgets.temperatures import TemperatureWidget

    _ = printer_ready

    target_temp = 35.0
    app = KlipperApp(printer_url=moonraker_url, poll_interval=1.0)
    try:
        async with app.run_test(size=(120, 40)) as pilot:
            await _poll_and_wait(app, pilot, timeout=10.0)

            # Set the hotend target through the library (same path the
            # TUI uses via its CLI worker). We don't go through the TUI
            # command menu here because we want the test to focus on
            # the chart-update path, not the command-menu navigation.
            with MoonrakerClient(base_url=moonraker_url, timeout=15.0) as client:
                set_hotend_temp(client, target_temp)

            # Give the poll loop at least one more cycle to observe the
            # updated target on the extruder object.
            deadline = asyncio.get_event_loop().time() + 10.0
            temps = app.screen.query_one("#temperatures", TemperatureWidget)
            while asyncio.get_event_loop().time() < deadline:
                app.poll_printer()
                await pilot.pause(delay=0.5)
                chart = temps._charts.get("extruder")
                if chart is not None and abs(chart.target - target_temp) < 0.5:
                    break

            chart = temps._charts["extruder"]
            assert chart.target == pytest.approx(target_temp, abs=0.5), (
                f"chart target never reached {target_temp}; last was {chart.target}"
            )
    finally:
        # Cool down so the next test starts from a clean baseline.
        with (
            contextlib.suppress(Exception),
            MoonrakerClient(base_url=moonraker_url, timeout=15.0) as client,
        ):
            set_hotend_temp(client, 0.0)


async def test_chart_renders_target_reference_line_content(
    moonraker_url: str, printer_ready: bool
) -> None:
    """A chart with a known target must include the magenta reference line.

    Rather than inspect the Textual rendered screen (which is brittle
    across Textual versions) we call the chart's ``render()`` method
    directly after setting its reactive target, and assert the
    returned ``Text`` contains the horizontal reference character.
    """
    from klipperctl.tui.app import KlipperApp
    from klipperctl.tui.widgets.temperatures import TemperatureWidget

    _ = printer_ready

    app = KlipperApp(printer_url=moonraker_url, poll_interval=1.0)
    async with app.run_test(size=(120, 40)) as pilot:
        await _poll_and_wait(app, pilot, timeout=10.0)

        temps = app.screen.query_one("#temperatures", TemperatureWidget)
        chart = temps._charts["extruder"]
        # Force a target so the reference line is drawn regardless of
        # whatever the printer reports.
        chart.update_data(current=25.0, target=60.0)
        rendered = chart.render()
        text = rendered.plain if hasattr(rendered, "plain") else str(rendered)
        assert "─" in text, "target reference line not rendered"
        assert "█" in text, "current temperature line not rendered"
        # Header must carry the friendly name and both values.
        header = text.split("\n", 1)[0]
        assert "Hotend" in header
        assert "25.0" in header
        assert "60" in header
