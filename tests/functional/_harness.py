"""Tri-modality test harness runners for functional workflows.

Each runner implements the same ``WorkflowRunner`` interface so a single
multi-step test body can exercise the library, CLI, and TUI layers with
identical assertions. Runners re-use existing code wherever possible:

- ``LibraryRunner`` calls ``moonraker_client.helpers`` directly — this is
  the shortest path to the wire and catches library-level regressions.
- ``CliModalityRunner`` invokes the Click CLI through ``CliRunner`` with
  ``--json`` and parses the structured output. This catches CLI wiring
  regressions (argument parsing, JSON shape, exit codes).
- ``TuiRunner`` drives the TUI via the Textual ``Pilot`` and re-uses
  ``KlipperApp.run_cli_command``, which itself runs the same Click CLI
  inside a worker. This catches TUI-specific regressions (worker error
  surfacing, modal flow) without re-implementing any of the underlying
  command logic.

All runner methods are ``async`` because the TUI modality must drive a
live Textual Pilot, and Pilot operations must be awaited. The library
and CLI runners wrap their sync calls in ``asyncio.to_thread`` so the
three modalities share an identical async signature and tests can be
written once against the abstract interface.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from click.testing import CliRunner

if TYPE_CHECKING:
    from moonraker_client import MoonrakerClient
    from textual.pilot import Pilot

    from klipperctl.tui.app import KlipperApp


# --------------------------------------------------------------------------- #
# Common interface
# --------------------------------------------------------------------------- #


class WorkflowRunner(ABC):
    """Shared async interface implemented by all three modality runners.

    The interface maps 1:1 onto the verbs used by multi-step workflows in
    ``test_workflows.py``. Keep it narrow — every method added here has to
    be implemented three times.
    """

    modality: str

    @abstractmethod
    async def get_state(self) -> str:
        """Return the current ``print_stats.state`` (standby/printing/...)."""

    @abstractmethod
    async def set_hotend_temp(self, target: float) -> None:
        """Set the extruder target temperature."""

    @abstractmethod
    async def set_bed_temp(self, target: float) -> None:
        """Set the bed target temperature."""

    @abstractmethod
    async def get_hotend_target(self) -> float:
        """Return the currently programmed extruder target."""

    @abstractmethod
    async def wait_until_temp(
        self, heater: str, target: float, tol: float = 3.0, timeout: float = 180.0
    ) -> bool:
        """Block until ``heater`` is within ``tol`` of ``target``."""

    @abstractmethod
    async def upload_sentinel_gcode(self) -> str:
        """Upload a tiny dwell-only gcode file and return its remote filename."""

    @abstractmethod
    async def start_print(self, filename: str) -> None:
        """Start printing a remote file."""

    @abstractmethod
    async def cancel_print(self) -> None:
        """Cancel the current print."""

    @abstractmethod
    async def send_gcode(self, command: str) -> None:
        """Send a raw gcode command."""

    @abstractmethod
    async def tail_logs_for(self, marker: str, timeout: float = 10.0) -> bool:
        """Return True if ``marker`` is observed in the gcode store within ``timeout``."""

    # Shared helpers ----------------------------------------------------- #

    async def wait_for_state(
        self, target_states: set[str], timeout: float = 30.0, poll: float = 1.0
    ) -> str:
        """Poll ``get_state`` until it matches one of ``target_states``.

        Returns the matched state on success, or the last observed state
        on timeout (caller decides whether to assert or retry).
        """
        deadline = time.monotonic() + timeout
        state = ""
        while time.monotonic() < deadline:
            state = await self.get_state()
            if state in target_states:
                return state
            await asyncio.sleep(poll)
        return state


# --------------------------------------------------------------------------- #
# Sentinel gcode — small dwell-only file used by start-and-cancel workflows
# --------------------------------------------------------------------------- #

# Sentinel gcode for start-and-cancel workflows. Must:
# - put the printer in `printing` state long enough to observe (10-30s)
# - contain no heating, no motion, no filament
# - NOT use a single long `G4` dwell - the moonraker-virtual-printer's
#   simulated MCU crashes with "Rescheduled timer in the past" when
#   asked for a multi-second dwell, leaving Klipper in a shutdown state
#   that can only be cleared with FIRMWARE_RESTART. Many short dwells
#   interleaved with M117 messages give the host work to do without
#   tripping any MCU timer limits.
_SENTINEL_TICKS = 60  # 60 * 200ms ~= 12 seconds of print time
SENTINEL_GCODE = (
    "; klipperctl functional-test sentinel\n"
    "; Safe: short dwells + M117 only. No motion, no heating, no filament.\n"
    "M117 klipperctl sentinel start\n"
    + "".join(f"M117 tick {i}\nG4 P200\n" for i in range(_SENTINEL_TICKS))
    + "M117 klipperctl sentinel done\n"
)


def _sentinel_filename() -> str:
    """Generate a unique remote filename so parallel runs don't collide."""
    return f"klipperctl_test_sentinel_{uuid.uuid4().hex[:8]}.gcode"


def _upload_sentinel(client: MoonrakerClient) -> str:
    """Upload the sentinel file using the library; returns remote filename."""
    import io

    name = _sentinel_filename()
    buf = io.BytesIO(SENTINEL_GCODE.encode("utf-8"))
    buf.name = name  # type: ignore[attr-defined]
    client.files_upload(buf)
    return name


def _scan_gcode_store_for(client: MoonrakerClient, marker: str) -> bool:
    """Return True if ``marker`` appears in the recent gcode store."""
    result = client.server_gcodestore(count=50)
    if not isinstance(result, dict):
        return False
    # `server_gcodestore` already unwraps `result` on the client-side helper;
    # accept both shapes defensively for robustness against mock or real.
    entries = result.get("gcode_store") or result.get("result", {}).get("gcode_store", [])
    return any(marker in (e.get("message") or "") for e in entries)


def _read_print_state(client: MoonrakerClient) -> str:
    """Return ``print_stats.state`` (standby/printing/paused/...).

    ``PrinterStatus.state`` from the helpers is the *Klippy* state, which
    stays ``"ready"`` while a print is running. For workflow tests we care
    about the print_stats.state field, which actually transitions to
    ``"printing"`` and back. Query it directly so runners are unambiguous.
    """
    result = client.printer_objects_query({"print_stats": ["state"]})
    status = result.get("status", {}) if isinstance(result, dict) else {}
    print_stats = status.get("print_stats", {}) if isinstance(status, dict) else {}
    return str(print_stats.get("state", "") or "")


# --------------------------------------------------------------------------- #
# Library runner
# --------------------------------------------------------------------------- #


class LibraryRunner(WorkflowRunner):
    """Direct ``moonraker-client`` helper calls — shortest path to the wire."""

    modality = "library"

    def __init__(self, client: MoonrakerClient) -> None:
        self._client = client

    async def get_state(self) -> str:
        def _call() -> str:
            return _read_print_state(self._client)

        return await asyncio.to_thread(_call)

    async def set_hotend_temp(self, target: float) -> None:
        from moonraker_client.helpers import set_hotend_temp

        await asyncio.to_thread(set_hotend_temp, self._client, target)

    async def set_bed_temp(self, target: float) -> None:
        from moonraker_client.helpers import set_bed_temp

        await asyncio.to_thread(set_bed_temp, self._client, target)

    async def get_hotend_target(self) -> float:
        from moonraker_client.helpers import get_temperatures

        def _call() -> float:
            reading = get_temperatures(self._client).get("extruder")
            return float(reading.target) if reading else 0.0

        return await asyncio.to_thread(_call)

    async def wait_until_temp(
        self, heater: str, target: float, tol: float = 3.0, timeout: float = 180.0
    ) -> bool:
        from moonraker_client.helpers import wait_for_temps

        return await asyncio.to_thread(
            wait_for_temps,
            self._client,
            {heater: target},
            tol,
            timeout,
            2.0,
        )

    async def upload_sentinel_gcode(self) -> str:
        return await asyncio.to_thread(_upload_sentinel, self._client)

    async def start_print(self, filename: str) -> None:
        from moonraker_client.helpers import start_print

        await asyncio.to_thread(start_print, self._client, filename)

    async def cancel_print(self) -> None:
        await asyncio.to_thread(self._client.print_cancel)

    async def send_gcode(self, command: str) -> None:
        from moonraker_client.helpers import send_gcode

        await asyncio.to_thread(send_gcode, self._client, command)

    async def tail_logs_for(self, marker: str, timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = await asyncio.to_thread(_scan_gcode_store_for, self._client, marker)
            if found:
                return True
            await asyncio.sleep(0.5)
        return False


# --------------------------------------------------------------------------- #
# CLI runner
# --------------------------------------------------------------------------- #


class CliModalityRunner(WorkflowRunner):
    """Drive the public CLI via Click's ``CliRunner`` with ``--json`` parsing."""

    modality = "cli"

    def __init__(self, url: str) -> None:
        self._url = url
        self._runner = CliRunner()

    def _invoke(self, *args: str, json_output: bool = False) -> tuple[int, str, str]:
        from klipperctl.cli import cli

        cli_args = ["--url", self._url]
        if json_output:
            cli_args.append("--json")
        cli_args.extend(args)
        result = self._runner.invoke(cli, cli_args)
        return result.exit_code, result.output or "", result.stderr or ""

    def _invoke_json_sync(self, *args: str) -> object:
        code, out, err = self._invoke(*args, json_output=True)
        if code != 0:
            raise RuntimeError(f"CLI {' '.join(args)} exited {code}: {err.strip() or out.strip()}")
        return json.loads(out)

    async def _invoke_json(self, *args: str) -> object:
        return await asyncio.to_thread(self._invoke_json_sync, *args)

    async def _invoke_ok(self, *args: str) -> None:
        def _run() -> None:
            code, _out, err = self._invoke(*args)
            if code != 0:
                raise RuntimeError(f"CLI {' '.join(args)} failed: {err}")

        await asyncio.to_thread(_run)

    async def get_state(self) -> str:
        # `klipperctl printer status` surfaces the *klippy* state (stays
        # "ready" during a print). Workflows care about `print_stats.state`
        # — the actual print-lifecycle field — which the CLI doesn't expose
        # at the top level. Drop to a direct library client just for this
        # read; the CLI modality's job is to verify commands *reach* the
        # printer through the CLI, not to reimplement every query path.
        from moonraker_client import MoonrakerClient

        def _call() -> str:
            with MoonrakerClient(base_url=self._url, timeout=15.0) as c:
                return _read_print_state(c)

        return await asyncio.to_thread(_call)

    async def set_hotend_temp(self, target: float) -> None:
        await self._invoke_ok("printer", "set-temp", "--hotend", str(target))

    async def set_bed_temp(self, target: float) -> None:
        await self._invoke_ok("printer", "set-temp", "--bed", str(target))

    async def get_hotend_target(self) -> float:
        data = await self._invoke_json("printer", "temps")
        if isinstance(data, dict):
            extruder = data.get("extruder", {})
            if isinstance(extruder, dict):
                return float(extruder.get("target", 0.0))
        return 0.0

    async def wait_until_temp(
        self, heater: str, target: float, tol: float = 3.0, timeout: float = 180.0
    ) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data = await self._invoke_json("printer", "temps")
            if isinstance(data, dict):
                reading = data.get(heater)
                if isinstance(reading, dict):
                    current = float(reading.get("current", 0.0))
                    if abs(current - target) <= tol:
                        return True
            await asyncio.sleep(2.0)
        return False

    async def upload_sentinel_gcode(self) -> str:
        # Uploading via the library keeps the test deterministic — the CLI
        # upload path expects a real local file, which is orthogonal to what
        # the start-and-cancel workflow is trying to verify.
        from moonraker_client import MoonrakerClient

        def _do() -> str:
            with MoonrakerClient(base_url=self._url, timeout=15.0) as c:
                return _upload_sentinel(c)

        return await asyncio.to_thread(_do)

    async def start_print(self, filename: str) -> None:
        await self._invoke_ok("print", "start", filename)

    async def cancel_print(self) -> None:
        await self._invoke_ok("print", "cancel", "--yes")

    async def send_gcode(self, command: str) -> None:
        await self._invoke_ok("printer", "gcode", command)

    async def tail_logs_for(self, marker: str, timeout: float = 10.0) -> bool:
        from moonraker_client import MoonrakerClient

        def _scan_once() -> bool:
            with MoonrakerClient(base_url=self._url, timeout=15.0) as c:
                return _scan_gcode_store_for(c, marker)

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if await asyncio.to_thread(_scan_once):
                return True
            await asyncio.sleep(0.5)
        return False


# --------------------------------------------------------------------------- #
# TUI runner
# --------------------------------------------------------------------------- #


class TuiRunner(WorkflowRunner):
    """Drive the TUI through its real command path.

    The TUI re-uses the public CLI internally via ``KlipperApp.run_cli_command``,
    so this runner exercises the same command logic as the CLI modality but
    through the TUI's worker/modal layer. That catches TUI-specific regressions
    (worker error surfacing, modal flow) without re-implementing command logic.
    """

    modality = "tui"

    def __init__(self, app: KlipperApp, pilot: Pilot, url: str) -> None:
        self._app = app
        self._pilot = pilot
        self._url = url

    # Internal helpers --------------------------------------------------- #

    async def _run_cli_via_tui(self, args: list[str]) -> None:
        """Dispatch a CLI command through the TUI worker and await completion."""
        self._app.run_cli_command(args, title="Workflow")
        # Give the worker generous time: its own timeout is `self._timeout + 5`,
        # but for dispatch-only commands (set-temp, cancel) 3s is plenty.
        await self._pilot.pause(delay=2.5)

    def _lib_client(self) -> MoonrakerClient:
        from moonraker_client import MoonrakerClient

        return MoonrakerClient(base_url=self._url, timeout=15.0)

    # Interface ---------------------------------------------------------- #

    async def get_state(self) -> str:
        # State verification uses a direct library client: the TUI itself
        # has no public "what state are you in *right now*" API, only
        # asynchronously-updating widgets. Asserting on widget text would
        # be brittle across Textual versions. The TUI modality's job is
        # to prove commands reach the printer *through* the TUI worker
        # path; independent verification stays orthogonal.
        def _call() -> str:
            with self._lib_client() as c:
                return _read_print_state(c)

        return await asyncio.to_thread(_call)

    async def set_hotend_temp(self, target: float) -> None:
        await self._run_cli_via_tui(["printer", "set-temp", "--hotend", str(target)])

    async def set_bed_temp(self, target: float) -> None:
        await self._run_cli_via_tui(["printer", "set-temp", "--bed", str(target)])

    async def get_hotend_target(self) -> float:
        from moonraker_client.helpers import get_temperatures

        def _call() -> float:
            with self._lib_client() as c:
                reading = get_temperatures(c).get("extruder")
                return float(reading.target) if reading else 0.0

        return await asyncio.to_thread(_call)

    async def wait_until_temp(
        self, heater: str, target: float, tol: float = 3.0, timeout: float = 180.0
    ) -> bool:
        from moonraker_client.helpers import wait_for_temps

        def _call() -> bool:
            with self._lib_client() as c:
                return wait_for_temps(
                    c,
                    {heater: target},
                    tolerance=tol,
                    timeout=timeout,
                    poll_interval=2.0,
                )

        return await asyncio.to_thread(_call)

    async def upload_sentinel_gcode(self) -> str:
        def _do() -> str:
            with self._lib_client() as c:
                return _upload_sentinel(c)

        return await asyncio.to_thread(_do)

    async def start_print(self, filename: str) -> None:
        await self._run_cli_via_tui(["print", "start", filename])

    async def cancel_print(self) -> None:
        await self._run_cli_via_tui(["print", "cancel", "--yes"])

    async def send_gcode(self, command: str) -> None:
        # KlipperApp has a first-class `send_gcode` worker path; use it
        # directly to exercise the TUI's gcode dispatch rather than
        # routing through the CLI.
        self._app.send_gcode(command)
        await self._pilot.pause(delay=1.0)

    async def tail_logs_for(self, marker: str, timeout: float = 10.0) -> bool:
        def _scan_once() -> bool:
            with self._lib_client() as c:
                return _scan_gcode_store_for(c, marker)

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if await asyncio.to_thread(_scan_once):
                return True
            await asyncio.sleep(0.5)
        return False
