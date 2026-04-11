"""Per-heater temperature chart with a target-setpoint reference line.

TUI cells can't anti-alias overlapping series the way Mainsail's SVG
chart does, so instead of one combined graph we render one compact
chart per heater. Each chart draws:

- A history of the current temperature as a block-character line
  (newest sample on the right, right-aligned when history is shorter
  than the chart width).
- The current target temperature as a horizontal magenta reference
  line spanning the full chart width.
- A header row above the chart showing the friendly heater name,
  the current reading, the target reading, and the autoscaled Y-axis
  range so the reader can interpret the chart without axis labels.

The Y-axis is autoscaled to always include both the history min/max
AND the target so the target line is never clipped. A minimum range
of 10 °C is enforced so tiny fluctuations don't look dramatic.
"""

from __future__ import annotations

import math
from collections import deque

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

#: Default number of samples kept in history. At a 2 s poll interval this
#: is 2 minutes of data, enough to see a heat-up cycle complete.
DEFAULT_MAX_HISTORY = 120

#: Height of the chart body in rows (excludes the header line).
DEFAULT_CHART_HEIGHT = 6

#: Minimum Y-axis span in degrees. Without this, a stable printer with
#: sub-degree noise would render as a single row with huge swings.
_MIN_RANGE = 10.0

#: Padding above/below the min/max so the line isn't right at the edge.
_PAD = 2.0


def _compute_bounds(history: list[float], target: float) -> tuple[float, float]:
    """Return ``(lo, hi)`` bounds that include all history plus the target.

    - Empty history with no target: ``(0, _MIN_RANGE)`` so the chart has
      something to draw against.
    - Empty history with a target: center on the target.
    - Otherwise: min/max over history + target, padded by ``_PAD`` on
      each side, with a minimum span of ``_MIN_RANGE``.
    """
    values = [v for v in history if v is not None and not math.isnan(v)]
    if target > 0:
        values.append(target)

    if not values:
        return 0.0, _MIN_RANGE

    lo = min(values) - _PAD
    hi = max(values) + _PAD

    span = hi - lo
    if span < _MIN_RANGE:
        mid = (lo + hi) / 2
        lo = mid - _MIN_RANGE / 2
        hi = mid + _MIN_RANGE / 2

    # Never let the low bound drop below 0 — negative temperatures
    # confuse the header readout and the chart cells don't care.
    if lo < 0:
        shift = -lo
        lo = 0.0
        hi += shift

    return lo, hi


def _temp_to_row(temp: float, lo: float, hi: float, height: int) -> int:
    """Map a temperature to a row index (0 = top, height-1 = bottom).

    Clamps out-of-range temperatures to the chart edges.
    """
    if height <= 0:
        return 0
    if hi <= lo:
        return height - 1
    frac = (temp - lo) / (hi - lo)
    row = round((height - 1) * (1 - frac))
    return max(0, min(height - 1, row))


def _current_style(current: float, target: float) -> str:
    """Color code the current-temperature line relative to the target."""
    if target <= 0:
        return "dim"
    if abs(current - target) < 3:
        return "bold green"
    return "bold yellow"


def _friendly_heater(name: str) -> str:
    """Short, friendly display label for a Klipper heater name."""
    mapping = {
        "extruder": "Hotend",
        "heater_bed": "Bed",
    }
    if name in mapping:
        return mapping[name]
    if name.startswith("extruder") and name[len("extruder") :].strip().isdigit():
        return f"Hotend ({name[len('extruder') :].strip()})"
    if name.startswith("heater_generic "):
        return f"Heater ({name[len('heater_generic ') :]})"
    if name.startswith("temperature_sensor "):
        return name[len("temperature_sensor ") :]
    if name.startswith("temperature_fan "):
        return f"Fan ({name[len('temperature_fan ') :]})"
    return name


def _render_heater_chart(
    name: str,
    current: float,
    target: float,
    history: list[float],
    *,
    width: int,
    height: int = DEFAULT_CHART_HEIGHT,
) -> Text:
    """Build a Rich ``Text`` renderable for a single heater chart.

    Layout::

        Hotend                    210.3 / 210 °C   [200-220]
        ░░░░░░░░░░░░░░░░░░░░█████
        ------------------█------    (target line; magenta)
                      ████
                  ████

    The first row is the header. The following ``height`` rows are the
    chart body. The current-temperature line is drawn with full-block
    characters in a color that reflects proximity to target. The target
    line is drawn first so the current line visually overlays it.
    """
    display_name = _friendly_heater(name)
    lo, hi = _compute_bounds(history, target)

    # ------- Header -------
    text = Text()
    text.append(f" {display_name:<10}", style="bold")
    text.append(" " * 3)
    current_style = _current_style(current, target)
    if target > 0:
        text.append(f"{current:6.1f}", style=current_style)
        text.append(" / ", style="dim")
        text.append(f"{target:5.1f} °C", style="magenta")
    else:
        text.append(f"{current:6.1f} °C", style="dim")
    text.append(f"    [{lo:.0f}-{hi:.0f}]", style="dim")
    text.append("\n")

    if width <= 0 or height <= 0:
        return text

    # ------- Grid -------
    # Cells are (char, style). Background is a middle-dot so empty cells
    # are visibly distinct from the chart rows but don't compete with
    # the line or target reference.
    blank = (" ", "dim")
    grid: list[list[tuple[str, str]]] = [[blank for _ in range(width)] for _ in range(height)]

    # Draw target reference line first — a horizontal run of ─ cells.
    if target > 0 and lo <= target <= hi:
        target_row = _temp_to_row(target, lo, hi, height)
        for c in range(width):
            grid[target_row][c] = ("─", "magenta")

    # Draw the current-temperature line, right-aligned so the newest
    # sample sits in the rightmost column and older samples fall off
    # the left edge when history exceeds chart width.
    points: list[float] = list(history)[-width:]
    start_col = width - len(points)
    for i, temp in enumerate(points):
        col = start_col + i
        if 0 <= col < width:
            row = _temp_to_row(temp, lo, hi, height)
            grid[row][col] = ("█", current_style)

    # ------- Render grid -------
    for r, row in enumerate(grid):
        for ch, style in row:
            text.append(ch, style=style)
        if r < height - 1:
            text.append("\n")

    return text


class HeaterChart(Widget):
    """Textual widget wrapping a per-heater chart.

    The widget maintains its own history deque and re-renders on every
    ``update_data`` call. ``render()`` pulls the current terminal width
    from ``self.size`` so the chart grows with the terminal.
    """

    DEFAULT_CSS = """
    HeaterChart {
        height: auto;
        margin-bottom: 1;
    }
    """

    # Reactive triggers so Textual re-renders automatically when set.
    current = reactive(0.0)
    target = reactive(0.0)

    def __init__(
        self,
        heater_name: str,
        *,
        max_history: int = DEFAULT_MAX_HISTORY,
        chart_height: int = DEFAULT_CHART_HEIGHT,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._heater_name = heater_name
        self._max_history = max_history
        self._chart_height = chart_height
        self._history: deque[float] = deque(maxlen=max_history)

    @property
    def heater_name(self) -> str:
        return self._heater_name

    @property
    def history(self) -> list[float]:
        return list(self._history)

    def update_data(self, current: float, target: float) -> None:
        """Append a sample and redraw."""
        self._history.append(float(current))
        self.current = float(current)
        self.target = float(target)
        self.refresh()

    def render(self) -> Text:
        # `self.size.width` is valid once the widget is mounted. Fall back
        # to a sensible default so unit tests that render before mount
        # still get a reasonable chart.
        try:
            width = max(20, self.size.width - 1)
        except Exception:
            width = 40
        return _render_heater_chart(
            self._heater_name,
            float(self.current),
            float(self.target),
            list(self._history),
            width=width,
            height=self._chart_height,
        )
