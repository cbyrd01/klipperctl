"""Dashboard screen — the main TUI view with printer status and temperatures."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from klipperctl.output import format_duration
from klipperctl.tui.widgets.status import PrinterStatusWidget
from klipperctl.tui.widgets.temperatures import TemperatureWidget


class DashboardScreen(Screen):
    """Main dashboard showing printer status, temperatures, and quick actions."""

    BINDINGS = [
        ("c", "app.push_screen('console')", "Console"),
        ("m", "app.push_screen('commands')", "Commands"),
        ("r", "refresh_data", "Refresh"),
        ("escape", "app.quit", "Quit"),
        ("q", "app.quit", "Quit"),
    ]

    DEFAULT_CSS = """
    DashboardScreen {
        layout: vertical;
    }
    #dashboard-panels {
        height: 1fr;
    }
    #left-panel {
        width: 1fr;
        height: 100%;
    }
    #right-panel {
        width: 1fr;
        height: 100%;
    }
    #connection-bar {
        height: 1;
        background: $primary-background;
        color: $text;
        padding: 0 1;
    }
    """

    def __init__(self, printer_url: str = "", **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._printer_url = printer_url

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"Connected: {self._printer_url}", id="connection-bar")
        with Horizontal(id="dashboard-panels"):
            with Vertical(id="left-panel"):
                yield PrinterStatusWidget(id="printer-status")
            with Vertical(id="right-panel"):
                yield TemperatureWidget(id="temperatures")
        yield Footer()

    def update_status(self, data: dict[str, Any]) -> None:
        """Update the status widget from printer data."""
        status_widget = self.query_one("#printer-status", PrinterStatusWidget)

        print_stats = data.get("print_stats", {})
        virtual_sdcard = data.get("virtual_sdcard", {})

        state = print_stats.get("state", data.get("state", "unknown"))
        state_message = print_stats.get("message", data.get("state_message", ""))
        filename = print_stats.get("filename", "")
        progress = virtual_sdcard.get("progress", 0.0)
        duration = print_stats.get("print_duration", 0.0)

        elapsed_str = format_duration(duration) if duration > 0 else "--"
        if progress > 0 and duration > 0:
            total_est = duration / progress
            remaining = total_est - duration
            eta_str = format_duration(remaining)
        else:
            eta_str = "--"

        status_widget.update_from_data(
            state=state,
            state_message=state_message,
            filename=filename,
            progress=progress,
            elapsed=elapsed_str,
            eta=eta_str,
        )

    def update_temperatures(self, heaters: dict[str, tuple[float, float]]) -> None:
        """Update the temperature widget."""
        temp_widget = self.query_one("#temperatures", TemperatureWidget)
        temp_widget.update_temperatures(heaters)

    def action_refresh_data(self) -> None:
        """Trigger a manual data refresh."""
        from klipperctl.tui.app import KlipperApp

        app = self.app
        if isinstance(app, KlipperApp):
            app.poll_printer()
