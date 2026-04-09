"""Temperature display widget for the TUI dashboard."""

from __future__ import annotations

from collections import deque

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Sparkline, Static


class TemperatureWidget(Widget):
    """Displays heater temperatures with sparkline history."""

    DEFAULT_CSS = """
    TemperatureWidget {
        height: auto;
        padding: 1;
        border: solid $primary;
    }
    TemperatureWidget #temp-title {
        text-style: bold;
        margin-bottom: 1;
    }
    TemperatureWidget .heater-row {
        height: 1;
    }
    TemperatureWidget Sparkline {
        height: 3;
        margin-top: 1;
    }
    """

    MAX_HISTORY = 60

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._heater_data: dict[str, tuple[float, float]] = {}
        self._history: dict[str, deque[float]] = {}

    def compose(self) -> ComposeResult:
        yield Static("Temperatures", id="temp-title")
        yield Label("No temperature data", id="temp-readings")
        yield Sparkline([], id="temp-sparkline")

    def update_temperatures(self, heaters: dict[str, tuple[float, float]]) -> None:
        """Update temperature readings.

        Args:
            heaters: Dict of heater_name -> (current_temp, target_temp).
        """
        self._heater_data = heaters
        lines = []
        primary_heater = None
        for name, (current, target) in sorted(heaters.items()):
            display_name = _friendly_name(name)
            if target > 0:
                color = "green" if abs(current - target) < 3 else "yellow"
                lines.append(
                    f"  [{color}]{display_name}: {current:.1f}/{target:.0f}\u00b0C[/{color}]"
                )
            else:
                lines.append(f"  [dim]{display_name}: {current:.1f}\u00b0C[/dim]")

            if name not in self._history:
                self._history[name] = deque(maxlen=self.MAX_HISTORY)
            self._history[name].append(current)

            if primary_heater is None:
                primary_heater = name

        if lines:
            self.query_one("#temp-readings", Label).update("\n".join(lines))
        else:
            self.query_one("#temp-readings", Label).update("No temperature data")

        if primary_heater and primary_heater in self._history:
            sparkline = self.query_one("#temp-sparkline", Sparkline)
            sparkline.data = list(self._history[primary_heater])


def _friendly_name(name: str) -> str:
    """Convert Klipper heater names to human-friendly labels."""
    name_map = {
        "extruder": "Hotend",
        "heater_bed": "Bed",
        "heater_generic": "Heater",
    }
    for prefix, label in name_map.items():
        if name == prefix:
            return label
        if name.startswith(prefix + " "):
            suffix = name[len(prefix) + 1 :]
            return f"{label} ({suffix})"
    if name.startswith("temperature_sensor "):
        return name[len("temperature_sensor ") :]
    if name.startswith("temperature_fan "):
        return f"Fan ({name[len('temperature_fan ') :]})"
    return name
