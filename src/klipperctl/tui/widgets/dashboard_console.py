"""Embedded gcode console widget for the dashboard screen.

Gives the dashboard a "quick command" panel: a small scrolling log
plus an Input field at the bottom. Lets the user fire off a gcode
command (``G28``, ``M115``, ``M117 hello``) without leaving the
dashboard to visit the full :class:`ConsoleScreen`. The widget is
intentionally simple and request/response in style — it does not
subscribe to WebSocket notifications. For real-time streaming use
the separate console screen (``c`` key).

Key behaviors:

- Up/Down arrow cycles a bounded command history so the user can
  re-run recent commands without retyping them.
- Enter submits the current line (ignored if empty or whitespace).
- Escape blurs the input so the dashboard's global single-key
  bindings (``q``, ``c``, ``m``, ``r``) work again.
- Success replies render in green, errors in red, info messages
  (echo of submitted commands, status lines) in dim.

The widget does not know how to talk to the printer. It exposes
``append_command``, ``append_result``, ``append_info`` and fires a
``DashboardConsoleWidget.Submitted`` message on Enter. The
DashboardScreen wires the message through to ``KlipperApp.send_gcode``
with an ``on_result`` callback that pipes the response back into
``append_result``.
"""

from __future__ import annotations

import contextlib
from collections import deque
from typing import Any, ClassVar

from textual import events
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, RichLog

from klipperctl.output import format_timestamp

#: Maximum number of recently submitted commands remembered for Up/Down recall.
MAX_HISTORY = 50

#: Maximum number of lines retained in the scrolling log. RichLog uses
#: a ring buffer internally, so this is just the cap passed at construction.
MAX_LOG_LINES = 500


def _normalize_command(raw: str) -> str:
    """Trim surrounding whitespace from a submitted command line.

    Returns an empty string for whitespace-only input, which callers
    treat as "do nothing".
    """
    return (raw or "").strip()


class DashboardConsoleWidget(Widget):
    """Compact embedded gcode console: log + input + history."""

    # NOTE on height: Textual's `Input` has a native height of 3 (border
    # top + content + border bottom). Do NOT override `#dash-gcode-input`
    # with a smaller height — clamping to 1 row leaves zero rows for the
    # content area and typed characters never render (regression from an
    # earlier iteration). The outer widget is `height: 14`, leaving
    # 11 rows for the RichLog after the 3-row Input.
    DEFAULT_CSS = """
    DashboardConsoleWidget {
        height: 14;
        border: solid $primary;
        padding: 0 1;
    }
    DashboardConsoleWidget #console-log {
        height: 1fr;
        scrollbar-size: 1 1;
    }
    DashboardConsoleWidget #dash-gcode-input {
        dock: bottom;
    }
    """

    class Submitted(Message):
        """Message emitted when the user submits a non-empty gcode line.

        Carries the normalized command string. The DashboardScreen
        listens for this and forwards to ``KlipperApp.send_gcode``.
        """

        def __init__(self, command: str) -> None:
            super().__init__()
            self.command = command

    # Bindings scoped to this widget. Up/Down cycle history when the
    # input has focus; Textual routes the events to the widget because
    # the Input is a child. Escape is handled via `on_key` instead of
    # a binding so we can both release focus *and* stop the event from
    # bubbling up to the DashboardScreen's `("escape", "app.quit")`
    # binding — using BINDINGS here would still let the screen's
    # quit action fire.
    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("up", "history_prev", "History prev"),
        ("down", "history_next", "History next"),
    ]

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._history: deque[str] = deque(maxlen=MAX_HISTORY)
        self._history_index: int | None = None
        self._pending_draft: str = ""
        # Set by `on_mount` / `_request_backfill` to guard against
        # re-fetching on remount.
        self._backfill_requested: bool = False

    def compose(self) -> ComposeResult:
        yield RichLog(
            highlight=False,
            markup=True,
            max_lines=MAX_LOG_LINES,
            id="console-log",
        )
        yield Input(
            placeholder="GCode (Enter to send, Up/Down for history)", id="dash-gcode-input"
        )

    def on_mount(self) -> None:
        # Kick off the backfill worker first so it starts while we render
        # the ready line. Entries are appended above the ready line by
        # `_on_history_loaded`.
        self._backfill_requested = False
        self._request_backfill()
        self.append_info("Dashboard console ready. Type a gcode command.")

    def _request_backfill(self) -> None:
        """Ask the app for the last ~25 gcode store entries."""
        if self._backfill_requested:
            return
        self._backfill_requested = True
        app = self.app
        fetch = getattr(app, "fetch_gcode_store", None)
        if fetch is None:
            return
        # App may not be ready yet (tests can mount the widget
        # directly); fail quietly — the ready line still renders.
        with contextlib.suppress(Exception):
            fetch(count=25, on_result=self._on_history_loaded)

    def _on_history_loaded(self, entries: list[dict[str, Any]]) -> None:
        """Callback from the backfill worker. Prepends entries to the log."""
        if not entries:
            return
        # Render entries oldest-first, matching chronological order on
        # screen. Moonraker returns them already in ascending time order.
        for entry in entries:
            self.append_history_entry(entry)
        # Add a visual separator so the user sees where history ends and
        # the live session begins.
        self.append_info("--- end of recent history ---")

    def on_key(self, event: events.Key) -> None:
        """Handle escape while the gcode input has focus.

        Using ``on_key`` (not ``BINDINGS``) lets us:

        1. Scope the behavior to the case where the Input is actually
           focused — escape from the dashboard proper should still
           fall through to the screen's quit binding.
        2. Call ``event.stop()`` + ``event.prevent_default()`` so the
           event does *not* bubble up to the DashboardScreen, which
           would otherwise trigger ``app.quit``.
        """
        if event.key != "escape":
            return
        try:
            input_widget = self.query_one("#dash-gcode-input", Input)
        except Exception:
            return
        if not input_widget.has_focus:
            return
        # Release focus back to the screen so the dashboard's single-key
        # bindings (q, c, m, r, g) work again.
        with contextlib.suppress(Exception):
            self.screen.set_focus(None)
        event.stop()
        event.prevent_default()

    # ------------------------------------------------------------------ #
    # Public API used by DashboardScreen
    # ------------------------------------------------------------------ #

    def append_command(self, command: str) -> None:
        """Echo a command the user just submitted."""
        self._write(f"[bold cyan]> {command}[/bold cyan]")

    def append_result(self, text: str, is_error: bool = False) -> None:
        """Render a response from the printer.

        Multi-line responses are split so each line gets its own styled
        entry, which prevents long replies from wrapping unreadably.
        """
        style = "red" if is_error else "green"
        prefix = "!" if is_error else " "
        for line in str(text or "").splitlines() or [""]:
            self._write(f"[{style}]{prefix} {line}[/{style}]")

    def append_info(self, text: str) -> None:
        """Render a dim informational line (not a command, not a reply)."""
        self._write(f"[dim]{text}[/dim]")

    def append_history_entry(self, entry: dict[str, Any]) -> None:
        """Render a single Moonraker gcode store entry as a prior-history line.

        Entries come from ``server.gcodestore`` with the shape
        ``{"time": float, "type": "command" | "response", "message": str}``.
        Commands render in dim cyan (still identifiable as user-submitted
        gcode), responses in plain dim. The timestamp prefix uses the
        same formatter as ``klipperctl server logs`` for consistency.
        """
        msg = str(entry.get("message", ""))
        if not msg:
            return
        ts_val = entry.get("time")
        ts_str = format_timestamp(ts_val) if ts_val else ""
        ts_prefix = f"[dim]{ts_str}[/dim] " if ts_str else ""
        entry_type = entry.get("type", "response")
        if entry_type == "command":
            # Historical commands echo with the same > prefix as live
            # ones, but in dim cyan so it's clear they aren't live.
            self._write(f"{ts_prefix}[dim cyan]> {msg}[/dim cyan]")
        else:
            self._write(f"{ts_prefix}[dim]{msg}[/dim]")

    # ------------------------------------------------------------------ #
    # Input handling
    # ------------------------------------------------------------------ #

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter in the gcode input."""
        command = _normalize_command(event.value)
        event.input.value = ""
        # Reset history navigation state so the next Up jumps to the
        # most recent entry again.
        self._history_index = None
        self._pending_draft = ""
        if not command:
            return
        # Avoid consecutive duplicates — repeatedly resubmitting the same
        # thing is almost always a mistake in a command history.
        if not self._history or self._history[-1] != command:
            self._history.append(command)
        self.append_command(command)
        self.post_message(self.Submitted(command))

    def action_history_prev(self) -> None:
        """Step one entry back in the command history (older)."""
        if not self._history:
            return
        try:
            input_widget = self.query_one("#dash-gcode-input", Input)
        except Exception:
            return
        if self._history_index is None:
            # First Up: remember whatever the user was typing so Down can
            # restore it later, then jump to the newest history entry.
            self._pending_draft = input_widget.value
            self._history_index = len(self._history) - 1
        else:
            self._history_index = max(0, self._history_index - 1)
        input_widget.value = self._history[self._history_index]
        # Keep the cursor at the end — Textual Input supports this via
        # `cursor_position`.
        input_widget.cursor_position = len(input_widget.value)

    def action_history_next(self) -> None:
        """Step one entry forward (newer). Past the end restores the draft."""
        if self._history_index is None:
            return
        try:
            input_widget = self.query_one("#dash-gcode-input", Input)
        except Exception:
            return
        if self._history_index >= len(self._history) - 1:
            # Walked past the newest entry — restore the draft the user
            # was typing before they pressed Up for the first time.
            self._history_index = None
            input_widget.value = self._pending_draft
            self._pending_draft = ""
        else:
            self._history_index += 1
            input_widget.value = self._history[self._history_index]
        input_widget.cursor_position = len(input_widget.value)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _write(self, markup: str) -> None:
        """Write a single line to the RichLog, tolerating early calls."""
        try:
            log = self.query_one("#console-log", RichLog)
        except Exception:
            return
        log.write(markup)

    def focus_input(self) -> None:
        """Move keyboard focus to the gcode input.

        Called by the DashboardScreen when a dedicated keybinding
        wants to jump the user into the console.
        """
        with contextlib.suppress(Exception):
            self.query_one("#dash-gcode-input", Input).focus()

    @property
    def history(self) -> list[str]:
        return list(self._history)
