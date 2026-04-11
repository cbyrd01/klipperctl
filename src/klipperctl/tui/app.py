"""Main Textual application for klipperctl TUI."""

from __future__ import annotations

from typing import Any, ClassVar

from textual.app import App
from textual.worker import Worker, WorkerState


class KlipperApp(App):
    """The klipperctl TUI application."""

    TITLE = "klipperctl"
    SUB_TITLE = "3D Printer Control"

    SCREENS: ClassVar[dict[str, object]] = {}

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("d", "switch_screen('dashboard')", "Dashboard"),
        ("c", "switch_screen('console')", "Console"),
        ("m", "switch_screen('commands')", "Commands"),
        ("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    Screen {
        background: $surface;
    }
    """

    # Polling backoff: on consecutive errors the interval grows 2→4→8→16→30s
    # and resets to the base interval on the next successful poll.
    _POLL_BACKOFF_MAX: ClassVar[float] = 30.0

    def __init__(
        self,
        printer_url: str = "http://localhost:7125",
        api_key: str | None = None,
        timeout: float = 30.0,
        poll_interval: float = 2.0,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._printer_url = printer_url
        self._api_key = api_key
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._poll_timer: Any = None
        self._last_poll_error: str | None = None
        self._consecutive_poll_errors = 0

    def on_mount(self) -> None:
        """Set up the dashboard and start polling."""
        from klipperctl.tui.screens.commands import CommandMenuScreen
        from klipperctl.tui.screens.console import ConsoleScreen
        from klipperctl.tui.screens.dashboard import DashboardScreen

        self.install_screen(DashboardScreen(printer_url=self._printer_url), "dashboard")
        self.install_screen(ConsoleScreen(), "console")
        self.install_screen(CommandMenuScreen(), "commands")
        self.push_screen("dashboard")
        self._poll_timer = self.set_interval(self._poll_interval, self.poll_printer)
        self.poll_printer()

    def _schedule_poll_backoff(self) -> None:
        """Reschedule the poll timer with exponential backoff after errors."""
        if self._poll_timer is None:
            return
        # 2s → 4 → 8 → 16 → 30s (capped)
        delay = min(
            self._poll_interval * (2 ** max(0, self._consecutive_poll_errors - 1)),
            self._POLL_BACKOFF_MAX,
        )
        self._poll_timer.stop()
        self._poll_timer = self.set_interval(delay, self.poll_printer)

    def _reset_poll_backoff(self) -> None:
        """Reset the poll interval back to the base after a successful poll."""
        if self._consecutive_poll_errors == 0 or self._poll_timer is None:
            self._consecutive_poll_errors = 0
            return
        self._consecutive_poll_errors = 0
        self._last_poll_error = None
        self._poll_timer.stop()
        self._poll_timer = self.set_interval(self._poll_interval, self.poll_printer)

    def action_switch_screen(self, screen_name: str) -> None:
        """Switch to a named screen."""
        current = self.screen.__class__.__name__.lower()
        if current.startswith(screen_name):
            return
        self.push_screen(screen_name)

    def _build_sync_client(self) -> Any:
        """Build a synchronous MoonrakerClient."""
        from moonraker_client import MoonrakerClient

        return MoonrakerClient(
            base_url=self._printer_url,
            api_key=self._api_key,
            timeout=self._timeout,
        )

    def poll_printer(self) -> None:
        """Poll printer status and temperatures in a worker thread."""
        self.run_worker(self._poll_worker, exclusive=True, group="poll")

    async def _poll_worker(self) -> dict[str, Any]:
        """Fetch printer data in a thread worker."""
        import asyncio

        def _fetch() -> dict[str, Any]:
            try:
                client = self._build_sync_client()
                try:
                    status = client.printer_objects_query(
                        objects={
                            "extruder": ["temperature", "target"],
                            "heater_bed": ["temperature", "target"],
                            "print_stats": None,
                            "virtual_sdcard": ["progress"],
                        }
                    )
                    return status.get("status", {})
                finally:
                    client.close()
            except Exception as exc:
                return {"_error": str(exc)}

        return await asyncio.to_thread(_fetch)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker completion."""
        if event.state != WorkerState.SUCCESS:
            return
        if event.worker.group == "poll":
            data = event.worker.result
            if data is None:
                return
            if "_error" in data:
                self._on_poll_error(str(data["_error"]))
                return
            self._reset_poll_backoff()
            self._update_dashboard(data)
        elif event.worker.group == "cli_command":
            self._on_cli_result(event)
        elif event.worker.group == "fetch_list":
            self._on_fetch_list_result(event)

    def _on_poll_error(self, message: str) -> None:
        """Surface a poll worker error to the user and apply backoff.

        Only notifies when the error message *changes*, so a persistently
        down printer does not spam the notification stack.
        """
        self._consecutive_poll_errors += 1
        if message != self._last_poll_error:
            self._last_poll_error = message
            self.notify(message, title="Polling error", severity="error", timeout=6)
        self._schedule_poll_backoff()

    def _on_fetch_list_result(self, event: Worker.StateChanged) -> None:
        result = event.worker.result
        if result is None:
            return
        callback, items = result
        if items and items[0][0] == "_error":
            self.notify(f"Error: {items[0][1]}", severity="error")
            return
        if not items:
            self.notify("No items found", severity="warning")
            return
        callback(items)

    def _update_dashboard(self, data: dict[str, Any]) -> None:
        """Push data to the dashboard screen."""
        from klipperctl.tui.screens.dashboard import DashboardScreen

        # Only update when the dashboard is the currently active screen.
        # Updating widgets on a screen that's been covered by a modal
        # causes Textual's incremental renderer to paint widget updates
        # over the modal in real terminals, leaving visible artifacts on
        # the right side of the modal (where the dashboard's
        # PrinterStatusWidget / temperature charts sit).
        screen = self.screen
        if not isinstance(screen, DashboardScreen):
            return

        screen.update_status(data)

        heaters: dict[str, tuple[float, float]] = {}
        for key, values in data.items():
            if isinstance(values, dict) and "temperature" in values:
                temp = float(values["temperature"])
                target = float(values.get("target", 0))
                heaters[key] = (temp, target)
        if heaters:
            screen.update_temperatures(heaters)

    def fetch_gcode_store(
        self,
        count: int = 25,
        on_result: Any = None,
    ) -> None:
        """Fetch the most recent gcode store entries in a background worker.

        Args:
            count: Maximum number of entries to request from Moonraker.
            on_result: Callback ``(entries: list[dict]) -> None`` invoked
                on completion. On failure the callback receives an empty
                list so the caller can render a clean "no history" state
                without needing a separate error path.

        Mirrors the :meth:`send_gcode` worker pattern: run sync I/O in a
        thread via ``asyncio.to_thread`` so the event loop stays free.
        """
        import asyncio
        import contextlib

        def _fetch() -> list[dict[str, Any]]:
            try:
                client = self._build_sync_client()
                try:
                    result = client.server_gcodestore(count=count)
                finally:
                    client.close()
            except Exception:
                return []
            # Moonraker's gcode store is delivered under "gcode_store" on
            # the unwrapped result; fall back gracefully if the shape is
            # unexpected.
            if isinstance(result, dict):
                entries = result.get("gcode_store")
                if isinstance(entries, list):
                    return [e for e in entries if isinstance(e, dict)]
            return []

        async def _worker() -> list[dict[str, Any]]:
            entries = await asyncio.to_thread(_fetch)
            if on_result is not None:
                with contextlib.suppress(Exception):
                    on_result(entries)
            return entries

        self.run_worker(_worker, group="gcode_store")

    def send_gcode(
        self,
        command: str,
        on_result: Any = None,
    ) -> None:
        """Send a GCode command via the sync client.

        Args:
            command: The gcode script to send (e.g. ``"G28"``).
            on_result: Optional callback ``(text: str, is_error: bool) -> None``
                invoked on the Textual main thread when the worker
                completes. If omitted, the result is discarded
                (preserving the old fire-and-forget behavior).
        """

        def _send() -> tuple[str, bool]:
            try:
                client = self._build_sync_client()
                try:
                    result = client.gcode_script(command)
                    text = str(result) if result else "ok"
                    return text, False
                finally:
                    client.close()
            except Exception as exc:
                return f"{exc}", True

        import asyncio

        async def _worker() -> tuple[str, bool]:
            import contextlib

            text, is_error = await asyncio.to_thread(_send)
            if on_result is not None:
                # `asyncio.to_thread` resumes us on the event loop thread,
                # so a direct call is safe. A broken callback must not
                # poison the worker, hence the suppression.
                with contextlib.suppress(Exception):
                    on_result(text, is_error)
            return text, is_error

        self.run_worker(_worker, group="gcode")

    def run_cli_command(self, args: list[str], title: str = "Result") -> None:
        """Execute a CLI command and display the result in a modal."""

        import asyncio

        def _run() -> tuple[str, int]:
            from click.testing import CliRunner

            from klipperctl.cli import cli

            runner = CliRunner()
            cli_args = ["--url", self._printer_url]
            if self._api_key:
                cli_args.extend(["--api-key", self._api_key])
            cli_args.extend(args)
            result = runner.invoke(cli, cli_args)
            if result.exit_code != 0:
                # Prefer stderr for errors, fall back to stdout
                error_text = (result.stderr or result.output or "").strip()
                if not error_text:
                    error_text = f"Command failed (exit code {result.exit_code})"
                return error_text, result.exit_code
            return result.output or "(no output)", 0

        # Give the CLI command a generous upper bound relative to the HTTP
        # timeout so a stuck Moonraker call (or runaway worker) cannot hang
        # the entire TUI. Exit code 124 matches coreutils `timeout`.
        cli_command_timeout = self._timeout + 5.0

        async def _worker() -> tuple[str, str, int]:
            try:
                output, exit_code = await asyncio.wait_for(
                    asyncio.to_thread(_run), timeout=cli_command_timeout
                )
            except TimeoutError:
                return (
                    title,
                    f"Command timed out after {cli_command_timeout:.0f}s",
                    124,
                )
            return title, output, exit_code

        self.run_worker(_worker, group="cli_command")

    def fetch_api_list(
        self,
        fetch_fn: Any,
        callback: Any,
    ) -> None:
        """Fetch a list from the API in a worker, then call callback with results."""
        import asyncio

        def _fetch() -> list[tuple[str, str]]:
            try:
                client = self._build_sync_client()
                try:
                    return fetch_fn(client)
                finally:
                    client.close()
            except Exception as exc:
                return [("_error", str(exc))]

        async def _worker() -> tuple[Any, list[tuple[str, str]]]:
            items = await asyncio.to_thread(_fetch)
            return callback, items

        self.run_worker(_worker, group="fetch_list")

    def _on_cli_result(self, event: Worker.StateChanged) -> None:
        if event.state != WorkerState.SUCCESS:
            return
        result = event.worker.result
        if result is None:
            return
        title, output, exit_code = result
        if exit_code != 0:
            self.notify(output, title=title, severity="error", timeout=8)
        else:
            from klipperctl.tui.screens.commands import ResultModal

            self.push_screen(ResultModal(title=title, content=output))
