"""Temperature display widget for the TUI dashboard.

Shows one :class:`HeaterChart` per heater that has a target setpoint
(normally the extruder and heater_bed), plus a text-only row for any
other temperature sensors/fans that don't have a target. Each chart
draws the current-temperature history and the target reference line
so the user can see, at a glance, how close the printer is to the
requested setpoint.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from klipperctl.tui.widgets.heater_chart import HeaterChart

#: Heaters we always want to give a dedicated chart to, in display order.
#: Any other heater with a non-zero target gets a chart appended after.
_PINNED_HEATERS = ("extruder", "heater_bed")


class TemperatureWidget(Widget):
    """Container that composes per-heater charts and a text readings row."""

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
    TemperatureWidget #temp-extras {
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._heater_data: dict[str, tuple[float, float]] = {}
        # Charts for heaters we've seen. Built lazily on first update so
        # the widget stays empty (no chart slots) until real data arrives.
        self._charts: dict[str, HeaterChart] = {}

    def compose(self) -> ComposeResult:
        yield Static("Temperatures", id="temp-title")
        # Charts are appended here when update_temperatures first sees a
        # heater with a target setpoint.
        yield Static("Waiting for data...", id="temp-placeholder")
        # Extras row for text-only sensors (temperature_sensor, fans).
        yield Label("", id="temp-extras")

    def update_temperatures(self, heaters: dict[str, tuple[float, float]]) -> None:
        """Update temperature readings.

        Args:
            heaters: Dict of ``heater_name -> (current_temp, target_temp)``.
                A ``target_temp`` of ``0`` is treated as "no target set"
                and the heater is rendered as a text row rather than a
                dedicated chart.
        """
        self._heater_data = dict(heaters)

        # Hide the placeholder the first time we see real data.
        if heaters:
            try:
                placeholder = self.query_one("#temp-placeholder", Static)
            except Exception:  # widget not yet mounted, skip silently
                placeholder = None
            if placeholder is not None:
                placeholder.display = False

        # Determine which heaters get charts. Pinned heaters (extruder,
        # bed) always get one if they're present in the data, even with
        # a zero target, so the user sees the chart from the moment the
        # dashboard opens. Other heaters get a chart only if they have
        # an active target.
        charted_order = [h for h in _PINNED_HEATERS if h in heaters]
        charted_set = set(charted_order)
        for name, (_current, target) in heaters.items():
            if name not in charted_set and target > 0:
                charted_order.append(name)
                charted_set.add(name)

        # Mount any newly-seen charts. Charts are added after the title
        # but before the extras row so the visual order stays consistent.
        extras_anchor: Widget | None
        try:
            extras_anchor = self.query_one("#temp-extras", Label)
        except Exception:  # not yet mounted
            extras_anchor = None

        for name in charted_order:
            if name not in self._charts:
                chart = HeaterChart(name, id=f"chart-{_safe_id(name)}")
                self._charts[name] = chart
                if extras_anchor is not None:
                    try:
                        self.mount(chart, before=extras_anchor)
                    except Exception:  # fall back to append
                        self.mount(chart)

        # Push data into each chart.
        for name in charted_order:
            chart = self._charts.get(name)
            if chart is None:
                continue
            current, target = heaters[name]
            chart.update_data(current, target)

        # Any heater that used to have a chart but is now missing from
        # the data: leave the chart in place with its last value so the
        # user doesn't see flapping UI. Removing widgets on every poll
        # would be visually noisy.

        # Render the extras line (text-only sensors without targets).
        extras_lines: list[str] = []
        for name, (current, target) in sorted(heaters.items()):
            if name in charted_set:
                continue
            display = _friendly_name(name)
            if target > 0:
                # Shouldn't happen since we charted everything with a
                # target, but be defensive.
                extras_lines.append(f"  {display}: {current:.1f}/{target:.0f}\u00b0C")
            else:
                extras_lines.append(f"  [dim]{display}: {current:.1f}\u00b0C[/dim]")

        if extras_anchor is not None:
            extras_anchor.update("\n".join(extras_lines))


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


def _safe_id(name: str) -> str:
    """Convert a Klipper heater name into a Textual-safe widget ID.

    Textual IDs must be valid CSS identifiers — letters, digits,
    hyphens, underscores — so replace spaces and other punctuation.
    """
    return "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in name)
