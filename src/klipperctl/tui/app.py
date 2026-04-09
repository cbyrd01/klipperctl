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

    def __init__(
        self,
        printer_url: str = "http://localhost:7125",
        api_key: str | None = None,
        timeout: float = 30.0,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._printer_url = printer_url
        self._api_key = api_key
        self._timeout = timeout
        self._poll_timer: Any = None

    def on_mount(self) -> None:
        """Set up the dashboard and start polling."""
        from klipperctl.tui.screens.commands import CommandMenuScreen
        from klipperctl.tui.screens.console import ConsoleScreen
        from klipperctl.tui.screens.dashboard import DashboardScreen

        self.install_screen(DashboardScreen(printer_url=self._printer_url), "dashboard")
        self.install_screen(ConsoleScreen(), "console")
        self.install_screen(CommandMenuScreen(), "commands")
        self.push_screen("dashboard")
        self._poll_timer = self.set_interval(2.0, self.poll_printer)
        self.poll_printer()

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
            if data is None or "_error" in data:
                return
            self._update_dashboard(data)
        elif event.worker.group == "cli_command":
            self._on_cli_result(event)

    def _update_dashboard(self, data: dict[str, Any]) -> None:
        """Push data to the dashboard screen."""
        from klipperctl.tui.screens.dashboard import DashboardScreen

        screen = self.screen
        if not isinstance(screen, DashboardScreen):
            for s in self.screen_stack:
                if isinstance(s, DashboardScreen):
                    screen = s
                    break
            else:
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

    def send_gcode(self, command: str) -> None:
        """Send a GCode command via the sync client."""

        def _send() -> str:
            try:
                client = self._build_sync_client()
                try:
                    result = client.gcode_script(command)
                    return str(result) if result else "ok"
                finally:
                    client.close()
            except Exception as exc:
                return f"Error: {exc}"

        import asyncio

        async def _worker() -> str:
            return await asyncio.to_thread(_send)

        self.run_worker(_worker, group="gcode")

    def run_cli_command(self, args: list[str], title: str = "Result") -> None:
        """Execute a CLI command and display the result in a modal."""

        import asyncio

        def _run() -> str:
            from click.testing import CliRunner

            from klipperctl.cli import cli

            runner = CliRunner()
            cli_args = ["--url", self._printer_url]
            if self._api_key:
                cli_args.extend(["--api-key", self._api_key])
            cli_args.extend(args)
            result = runner.invoke(cli, cli_args)
            return result.output or "(no output)"

        async def _worker() -> tuple[str, str]:
            output = await asyncio.to_thread(_run)
            return title, output

        self.run_worker(_worker, group="cli_command")

    def _on_cli_result(self, event: Worker.StateChanged) -> None:
        if event.state != WorkerState.SUCCESS:
            return
        result = event.worker.result
        if result is None:
            return
        title, output = result
        from klipperctl.tui.screens.commands import ResultModal

        self.push_screen(ResultModal(title=title, content=output))
