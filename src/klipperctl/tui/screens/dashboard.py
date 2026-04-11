"""Dashboard screen — the main TUI view with printer status and temperatures."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from klipperctl.output import format_duration
from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget
from klipperctl.tui.widgets.status import PrinterStatusWidget
from klipperctl.tui.widgets.temperatures import TemperatureWidget


class DashboardScreen(Screen):
    """Main dashboard showing printer status, temperatures, and quick actions."""

    BINDINGS = [
        ("c", "app.push_screen('console')", "Full console"),
        ("m", "app.push_screen('commands')", "Commands"),
        ("r", "refresh_data", "Refresh"),
        ("g", "focus_gcode", "GCode"),
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
    #dash-console {
        height: 12;
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
        yield DashboardConsoleWidget(id="dash-console")
        yield Footer()

    def action_focus_gcode(self) -> None:
        """Jump focus into the embedded gcode input (bound to ``g``)."""
        try:
            widget = self.query_one("#dash-console", DashboardConsoleWidget)
        except Exception:
            return
        widget.focus_input()

    def on_dashboard_console_widget_submitted(
        self, message: DashboardConsoleWidget.Submitted
    ) -> None:
        """Forward a console submission to the app and wire the reply back.

        The widget is deliberately ignorant of the transport; the screen
        is the bridge between widget events and ``KlipperApp.send_gcode``.
        """
        from klipperctl.tui.app import KlipperApp

        app = self.app
        if not isinstance(app, KlipperApp):
            return

        try:
            widget = self.query_one("#dash-console", DashboardConsoleWidget)
        except Exception:
            return

        def _on_result(text: str, is_error: bool) -> None:
            widget.append_result(text, is_error=is_error)

        app.send_gcode(message.command, on_result=_on_result)

    def update_status(self, data: dict[str, Any]) -> None:
        """Update the status widget from printer data.

        The dashboard screen can briefly exist without the status widget
        mounted yet during the window between ``compose()`` starting and
        the first children being attached. Polling happens on a separate
        worker thread and can race ahead of compose; swallow the
        ``NoMatches`` so the TUI doesn't crash on its first poll.
        """
        try:
            status_widget = self.query_one("#printer-status", PrinterStatusWidget)
        except Exception:
            return

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
        """Update the temperature widget.

        Same mount-race guard as :meth:`update_status`.
        """
        try:
            temp_widget = self.query_one("#temperatures", TemperatureWidget)
        except Exception:
            return
        temp_widget.update_temperatures(heaters)

    def action_refresh_data(self) -> None:
        """Trigger a manual data refresh."""
        from klipperctl.tui.app import KlipperApp

        app = self.app
        if isinstance(app, KlipperApp):
            app.poll_printer()
