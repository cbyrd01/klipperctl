"""GCode console screen with real-time WebSocket streaming."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, RichLog

from klipperctl.filtering import MessageFilter


class ConsoleScreen(Screen):
    """Real-time GCode console with input field."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
    ]

    DEFAULT_CSS = """
    ConsoleScreen #console-log {
        height: 1fr;
        border: solid $primary;
        scrollbar-size: 1 1;
    }
    ConsoleScreen #gcode-input {
        dock: bottom;
        margin-top: 1;
    }
    """

    def __init__(self, msg_filter: MessageFilter | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._filter = msg_filter or MessageFilter()

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield RichLog(highlight=True, markup=True, id="console-log")
            yield Input(placeholder="Enter GCode command...", id="gcode-input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#console-log", RichLog)
        log.write("[dim]GCode console ready. Type commands below.[/dim]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Send GCode command when user presses Enter."""
        command = event.value.strip()
        if not command:
            return
        event.input.value = ""
        log = self.query_one("#console-log", RichLog)
        log.write(f"[bold cyan]> {command}[/bold cyan]")
        self._send_gcode(command)

    def _send_gcode(self, command: str) -> None:
        """Send GCode via the app's client."""
        from klipperctl.tui.app import KlipperApp

        app = self.app
        if isinstance(app, KlipperApp):
            app.send_gcode(command)

    def append_message(self, message: str) -> None:
        """Append a message to the console log, applying filters."""
        if self._filter.matches(message):
            try:
                log = self.query_one("#console-log", RichLog)
                log.write(message)
            except Exception:
                pass
