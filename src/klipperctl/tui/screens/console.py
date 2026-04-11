"""Full-screen GCode console: backfill + live streaming + input.

The full console is a thin wrapper around
:class:`DashboardConsoleWidget`. Both the dashboard-embedded console
and this full-screen console share the same widget implementation,
which gives them:

- A one-shot backfill of the last ~25 entries from Moonraker's
  gcode store on mount.
- An async live-tail poll loop that streams new entries as they
  appear — commands from other clients, running macros, slicer
  uploads, another TUI session.
- An input field with Up/Down command history recall.
- A local-echo dedupe heuristic so submissions through our own
  input don't render twice (once from the instant echo, once from
  the tail poll picking up the same entry a moment later).

The only differences between the dashboard embed and the full
console are:

1. Height — the dashboard embed is fixed at 14 rows; the full
   console fills the whole screen below the header.
2. Escape semantics — on the dashboard, escape releases focus from
   the input so the dashboard's single-key bindings work again.
   Here, escape bubbles to the screen's ``pop_screen`` binding so
   one press exits the full console back to the previous screen,
   matching the prior behavior of this screen before Phase 4c.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header

from klipperctl.filtering import MessageFilter
from klipperctl.tui.widgets.dashboard_console import DashboardConsoleWidget


class ConsoleScreen(Screen):
    """Full-screen interactive GCode console.

    Embeds a :class:`DashboardConsoleWidget` configured for the
    full-screen use case: no focus-release on escape (so a single
    escape press pops the screen), and an optional
    :class:`MessageFilter` applied to both backfill and live-tail
    entries.
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
    ]

    DEFAULT_CSS = """
    ConsoleScreen {
        layout: vertical;
    }
    ConsoleScreen DashboardConsoleWidget {
        /* Override the widget's default fixed height so the console
           expands to fill the whole screen below the header/footer. */
        height: 1fr;
    }
    """

    def __init__(self, msg_filter: MessageFilter | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._filter = msg_filter or MessageFilter()

    def compose(self) -> ComposeResult:
        yield Header()
        yield DashboardConsoleWidget(
            id="full-console",
            release_focus_on_escape=False,
            msg_filter=self._filter,
        )
        yield Footer()

    def on_dashboard_console_widget_submitted(
        self, message: DashboardConsoleWidget.Submitted
    ) -> None:
        """Forward a gcode submission to the app, wiring the reply back.

        Mirrors :meth:`DashboardScreen.on_dashboard_console_widget_submitted`
        so the full console gets the same request-response rendering
        as the dashboard-embedded one.
        """
        from klipperctl.tui.app import KlipperApp

        app = self.app
        if not isinstance(app, KlipperApp):
            return
        try:
            widget = self.query_one("#full-console", DashboardConsoleWidget)
        except Exception:
            return

        def _on_result(text: str, is_error: bool) -> None:
            widget.append_result(text, is_error=is_error)

        app.send_gcode(message.command, on_result=_on_result)

    def append_message(self, message: str) -> None:
        """Append a free-form message to the console log.

        Retained as a thin forwarder for backward compatibility with
        code (and tests) that called the old inline-RichLog-based
        ConsoleScreen. Honors the configured :class:`MessageFilter`.
        """
        if not self._filter.matches(message):
            return
        try:
            widget = self.query_one("#full-console", DashboardConsoleWidget)
        except Exception:
            return
        widget.append_info(message)
