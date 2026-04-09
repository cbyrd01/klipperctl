"""Printer status widget for the TUI dashboard."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ProgressBar, Static


class PrinterStatusWidget(Widget):
    """Displays printer state, current file, progress, elapsed time, and ETA."""

    DEFAULT_CSS = """
    PrinterStatusWidget {
        height: auto;
        padding: 1;
        border: solid $primary;
    }
    PrinterStatusWidget #status-title {
        text-style: bold;
        margin-bottom: 1;
    }
    PrinterStatusWidget .status-row {
        height: 1;
    }
    PrinterStatusWidget #progress-bar {
        margin-top: 1;
        margin-bottom: 1;
    }
    """

    printer_state: reactive[str] = reactive("unknown")
    state_message: reactive[str] = reactive("")
    filename: reactive[str] = reactive("")
    progress: reactive[float] = reactive(0.0)
    elapsed: reactive[str] = reactive("--")
    eta: reactive[str] = reactive("--")

    def compose(self) -> ComposeResult:
        yield Static("Printer Status", id="status-title")
        yield Label("State: unknown", id="state-value", classes="status-row")
        yield Label("File: --", id="file-value", classes="status-row")
        yield ProgressBar(total=100, show_eta=False, id="progress-bar")
        yield Label("Elapsed: --  |  ETA: --", id="time-value", classes="status-row")

    def _state_color(self, state: str) -> str:
        colors = {
            "ready": "green",
            "printing": "cyan",
            "paused": "yellow",
            "complete": "green",
            "error": "red",
            "standby": "dim",
            "cancelled": "red",
        }
        return colors.get(state, "white")

    def watch_printer_state(self, value: str) -> None:
        try:
            color = self._state_color(value)
            label = self.query_one("#state-value", Label)
            msg = f" — {self.state_message}" if self.state_message else ""
            label.update(f"State: [{color}]{value}{msg}[/{color}]")
        except Exception:
            pass

    def watch_state_message(self, value: str) -> None:
        self.watch_printer_state(self.printer_state)

    def watch_filename(self, value: str) -> None:
        try:
            display = value if value else "--"
            self.query_one("#file-value", Label).update(f"File: {display}")
        except Exception:
            pass

    def watch_progress(self, value: float) -> None:
        try:
            bar = self.query_one("#progress-bar", ProgressBar)
            bar.update(progress=value * 100)
        except Exception:
            pass

    def watch_elapsed(self, value: str) -> None:
        self._update_time_label()

    def watch_eta(self, value: str) -> None:
        self._update_time_label()

    def _update_time_label(self) -> None:
        try:
            label = self.query_one("#time-value", Label)
            label.update(f"Elapsed: {self.elapsed}  |  ETA: {self.eta}")
        except Exception:
            pass

    def update_from_data(
        self,
        state: str,
        state_message: str,
        filename: str,
        progress: float,
        elapsed: str,
        eta: str,
    ) -> None:
        """Batch update all status fields."""
        self.printer_state = state
        self.state_message = state_message
        self.filename = filename
        self.progress = progress
        self.elapsed = elapsed
        self.eta = eta
