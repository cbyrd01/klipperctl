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
import time
from collections import deque
from typing import Any, ClassVar

from textual import events
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, RichLog

from klipperctl.filtering import MessageFilter
from klipperctl.output import format_timestamp

#: Maximum number of recently submitted commands remembered for Up/Down recall.
MAX_HISTORY = 50

#: Maximum number of lines retained in the scrolling log. RichLog uses
#: a ring buffer internally, so this is just the cap passed at construction.
MAX_LOG_LINES = 500

#: Default poll interval (seconds) for the live gcode-store tail loop.
#: Slightly slower than the main printer-status poll so we don't double
#: the HTTP load on slow networks; real-world printer activity doesn't
#: change much faster than this anyway.
DEFAULT_TAIL_INTERVAL = 2.0

#: Max number of entries requested per live-tail poll. Anything
#: older than the watermark is discarded, so this only caps the
#: burst size if many events happened between polls.
DEFAULT_TAIL_COUNT = 50

#: Window within which a live-tail command entry is considered a
#: duplicate of a recent local submission and skipped.
_LOCAL_ECHO_DEDUPE_WINDOW = 5.0

#: Window within which a live-tail response entry is assumed to belong
#: to a just-submitted local command (since the ``send_gcode`` worker's
#: ``on_result`` callback already rendered the reply).
_LOCAL_RESPONSE_DEDUPE_WINDOW = 3.0


def _normalize_command(raw: str) -> str:
    """Trim surrounding whitespace from a submitted command line.

    Returns an empty string for whitespace-only input, which callers
    treat as "do nothing".
    """
    return (raw or "").strip()


def _entry_time(entry: dict[str, Any]) -> float:
    """Extract a float timestamp from a gcode store entry.

    Moonraker sends ``time`` as a float (epoch seconds). We coerce
    defensively so a malformed entry doesn't crash the poll loop.
    """
    value = entry.get("time", 0)
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


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

    def __init__(
        self,
        *,
        tail_interval: float = DEFAULT_TAIL_INTERVAL,
        release_focus_on_escape: bool = True,
        msg_filter: MessageFilter | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._history: deque[str] = deque(maxlen=MAX_HISTORY)
        self._history_index: int | None = None
        self._pending_draft: str = ""
        # Set by `on_mount` / `_request_backfill` to guard against
        # re-fetching on remount.
        self._backfill_requested: bool = False
        # Live-tail state: watermark is the server-side timestamp of
        # the newest entry we've already rendered (from backfill or a
        # prior poll). Entries with `time <= _last_time` are skipped.
        self._last_time: float = 0.0
        self._tail_interval: float = tail_interval
        self._tail_timer: Any = None
        # Recent user-submitted commands (with local wall time) used to
        # dedupe live-tail entries that come from the user's own
        # interaction with this widget, since the submit path already
        # echoes + renders the reply locally.
        self._local_echo_history: deque[tuple[str, float]] = deque(maxlen=20)
        # When True (the dashboard-embedded use case), escape while the
        # gcode input has focus releases focus and stops the event so
        # the dashboard's single-key bindings work again. When False
        # (the full ConsoleScreen use case), escape bubbles to the
        # parent screen, which typically binds it to pop_screen.
        self._release_focus_on_escape: bool = release_focus_on_escape
        # Optional filter applied to both backfill and live-tail
        # entries. Used by the full ConsoleScreen to honor its existing
        # `MessageFilter` constructor arg.
        self._msg_filter: MessageFilter | None = msg_filter

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
        # `_on_history_loaded`, which also seeds `_last_time` so the
        # live tail doesn't replay backfilled entries.
        self._backfill_requested = False
        self._request_backfill()
        self.append_info("Dashboard console ready. Type a gcode command.")
        # Start the live tail. Textual's set_interval is bound to the
        # widget lifecycle, so the timer is cleaned up automatically
        # when the dashboard is unmounted (app shutdown, screen pop).
        self._start_tail()

    def _start_tail(self) -> None:
        """Install the repeating tail-poll timer."""
        if self._tail_timer is not None or self._tail_interval <= 0:
            return
        try:
            self._tail_timer = self.set_interval(self._tail_interval, self._poll_tail)
        except Exception:
            # Widget not fully mounted yet — test harnesses may
            # instantiate the widget without a running app loop.
            self._tail_timer = None

    def _poll_tail(self) -> None:
        """Fire the live-tail worker. Runs on the timer's schedule."""
        app = self.app
        fetch = getattr(app, "fetch_gcode_store", None)
        if fetch is None:
            return
        with contextlib.suppress(Exception):
            fetch(count=DEFAULT_TAIL_COUNT, on_result=self._on_tail_entries)

    def _on_tail_entries(self, entries: list[dict[str, Any]]) -> None:
        """Render new gcode store entries that weren't seen before.

        Runs on the event-loop thread (the worker callback is invoked
        after ``asyncio.to_thread`` resumes). Filters by the watermark
        and by the local-echo dedupe heuristic, then advances the
        watermark.
        """
        if not entries:
            return
        newest = self._last_time
        for entry in entries:
            ts = _entry_time(entry)
            if ts <= self._last_time:
                continue
            if self._should_skip_local_duplicate(entry):
                if ts > newest:
                    newest = ts
                continue
            if not self._entry_matches_filter(entry):
                if ts > newest:
                    newest = ts
                continue
            self.append_live_entry(entry)
            if ts > newest:
                newest = ts
        if newest > self._last_time:
            self._last_time = newest

    def _should_skip_local_duplicate(self, entry: dict[str, Any]) -> bool:
        """Return True if this tail entry matches a recent local submission.

        The send-gcode path renders the echo + reply immediately when
        the user presses Enter, so if the same command (or a response
        within a tight window) also comes back via the tail poll, we
        skip it to avoid double rendering.
        """
        entry_type = entry.get("type", "response")
        msg = str(entry.get("message", ""))
        now = time.time()
        if entry_type == "command":
            return any(
                cmd == msg and now - ts < _LOCAL_ECHO_DEDUPE_WINDOW
                for cmd, ts in self._local_echo_history
            )
        # Response entries don't carry the command string, so we can't
        # content-match. Assume any response that arrives within a
        # tight window of a local submission is that submission's
        # reply — the on_result callback already rendered it.
        return any(
            now - ts < _LOCAL_RESPONSE_DEDUPE_WINDOW for _cmd, ts in self._local_echo_history
        )

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
        """Callback from the backfill worker.

        Appends historical entries to the log and advances the
        live-tail watermark past the newest one, so the tail loop
        doesn't re-render what the backfill already showed.
        """
        if not entries:
            return
        # Render entries oldest-first, matching chronological order on
        # screen. Moonraker returns them already in ascending time order.
        newest = self._last_time
        rendered_any = False
        for entry in entries:
            ts = _entry_time(entry)
            if ts > newest:
                newest = ts
            if not self._entry_matches_filter(entry):
                continue
            self.append_history_entry(entry)
            rendered_any = True
        if newest > self._last_time:
            self._last_time = newest
        # Add a visual separator so the user sees where history ends and
        # the live session begins. Skip the separator when the filter
        # excluded everything — otherwise the user sees a lone
        # "end of history" line with nothing above it.
        if rendered_any:
            self.append_info("--- end of recent history ---")

    def _entry_matches_filter(self, entry: dict[str, Any]) -> bool:
        """Apply the optional MessageFilter to a gcode store entry."""
        if self._msg_filter is None:
            return True
        msg = str(entry.get("message", ""))
        return self._msg_filter.matches(msg)

    def on_key(self, event: events.Key) -> None:
        """Handle escape while the gcode input has focus.

        When ``release_focus_on_escape`` is True (dashboard-embedded
        use case), escape releases focus and stops event propagation
        so the DashboardScreen's ``("escape", "app.quit")`` binding
        does not fire. When False (full ConsoleScreen use case),
        escape bubbles to the parent screen so a single press pops
        the screen cleanly.
        """
        if event.key != "escape":
            return
        if not self._release_focus_on_escape:
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

    def append_live_entry(self, entry: dict[str, Any]) -> None:
        """Render a single gcode store entry that arrived via the live tail.

        Unlike :meth:`append_history_entry` (which renders in muted
        colors because the entries predate the TUI), live entries are
        rendered in normal colors — they're current activity the user
        should see clearly. Command entries look the same as a local
        echo (bold cyan); responses render green.
        """
        msg = str(entry.get("message", ""))
        if not msg:
            return
        entry_type = entry.get("type", "response")
        if entry_type == "command":
            self._write(f"[bold cyan]> {msg}[/bold cyan]")
        else:
            for line in msg.splitlines() or [""]:
                self._write(f"[green]  {line}[/green]")

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
        # Record the local echo so the live-tail poll can skip this
        # command (and its imminent response) when it shows up in the
        # gcode store a moment later. We trim to entries within the
        # longer of the two dedupe windows.
        self._record_local_echo(command)
        self.append_command(command)
        self.post_message(self.Submitted(command))

    def _record_local_echo(self, command: str) -> None:
        """Remember a just-submitted command so the tail can dedupe it."""
        now = time.time()
        self._local_echo_history.append((command, now))
        # Prune entries older than the longest dedupe window we care
        # about so the deque stays tight and the dedupe check is fast.
        cutoff = now - max(_LOCAL_ECHO_DEDUPE_WINDOW, _LOCAL_RESPONSE_DEDUPE_WINDOW)
        while self._local_echo_history and self._local_echo_history[0][1] < cutoff:
            self._local_echo_history.popleft()

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
