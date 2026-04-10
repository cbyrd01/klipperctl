"""Server command group - Moonraker server management."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import click
from moonraker_client.exceptions import MoonrakerError

from klipperctl.cli import _handle_error
from klipperctl.client import get_client
from klipperctl.filtering import MessageFilter, build_filter
from klipperctl.output import (
    console,
    format_timestamp,
    is_json_mode,
    output,
    output_json,
    unwrap_result,
)

if TYPE_CHECKING:
    from moonraker_client import MoonrakerClient

_logger = logging.getLogger(__name__)

_LOGS_TAIL_WARN_AFTER = 5


@click.group()
def server() -> None:
    """Moonraker server management."""


@server.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Show server info (version, components, plugins)."""
    try:
        client = get_client(ctx)
        data = client.server_info()
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    def _human(data: dict) -> None:
        console.print("[bold]Moonraker Server[/bold]")
        console.print(f"  Version:    {data.get('moonraker_version', '?')}")
        console.print(f"  API Version: {data.get('api_version_string', '?')}")
        console.print(f"  Klippy:     {data.get('klippy_state', '?')}")
        console.print(f"  Connected:  {data.get('klippy_connected', '?')}")
        components = data.get("components", [])
        if components:
            console.print(f"  Components: {len(components)}")
        failed = data.get("failed_components", [])
        if failed:
            console.print(f"  [red]Failed:    {', '.join(failed)}[/red]")

    output(data, _human)


@server.command()
@click.pass_context
def config(ctx: click.Context) -> None:
    """Show Moonraker configuration."""
    try:
        client = get_client(ctx)
        data = client.server_config()
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    def _human(data: dict) -> None:
        config_data = data.get("config", data)
        for section, values in config_data.items():
            console.print(f"[bold][{section}][/bold]")
            if isinstance(values, dict):
                for key, val in values.items():
                    console.print(f"  {key} = {val}")
            console.print()

    output(data, _human)


@server.command()
@click.pass_context
def restart(ctx: click.Context) -> None:
    """Restart the Moonraker server."""
    try:
        client = get_client(ctx)
        client.server_restart()
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json({"result": "ok"})
    else:
        console.print("Moonraker restart requested.")


@server.command()
@click.option("--count", type=int, help="Number of entries to return.")
@click.option("--watch", is_flag=True, help="Continuously tail new entries.")
@click.option(
    "--interval", type=float, default=2.0, show_default=True, help="Poll interval in seconds."
)
@click.option("--filter", "filter_pattern", help="Only show lines matching regex pattern.")
@click.option("--exclude", "exclude_pattern", help="Hide lines matching regex pattern.")
@click.option("--exclude-temps", is_flag=True, help="Hide temperature reports.")
@click.pass_context
def logs(
    ctx: click.Context,
    count: int | None,
    watch: bool,
    interval: float,
    filter_pattern: str | None,
    exclude_pattern: str | None,
    exclude_temps: bool,
) -> None:
    """Show cached GCode responses."""
    msg_filter = build_filter(filter_pattern, exclude_pattern, exclude_temps)

    try:
        client = get_client(ctx)
        result = client.server_gcodestore(count=count)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    entries = unwrap_result(result, "gcode_store")
    filtered = [e for e in entries if msg_filter.matches(e.get("message", ""))]

    def _human(items: list) -> None:
        if not items:
            console.print("No cached GCode responses.")
            return
        for entry in items:
            _print_log_entry(entry)

    output(filtered, _human)

    if watch:
        import contextlib

        with contextlib.suppress(KeyboardInterrupt):
            _logs_tail(client, msg_filter, interval, count)


def _print_log_entry(entry: dict) -> None:
    """Print a single gcode store entry with timestamp."""
    msg = entry.get("message", "")
    time_val = entry.get("time")
    ts = f"[dim]{format_timestamp(time_val)}[/dim] " if time_val else ""
    console.print(f"{ts}{msg}")


def _logs_tail(
    client: MoonrakerClient,
    msg_filter: MessageFilter,
    interval: float,
    count: int | None,
) -> None:
    """Tail-follow gcode store, printing only new entries.

    Transient Moonraker errors (network blips, brief restarts) keep the loop
    alive; `KeyboardInterrupt` propagates so Ctrl+C still exits immediately.
    After ``_LOGS_TAIL_WARN_AFTER`` consecutive failures we print a warning
    so the user isn't staring at a dead tail.
    """
    last_time = time.time()
    consecutive_failures = 0

    while True:
        time.sleep(interval)
        try:
            result = client.server_gcodestore(count=count)
        except MoonrakerError as exc:
            _logger.debug("server_gcodestore transient failure: %s", exc)
            consecutive_failures += 1
            if consecutive_failures == _LOGS_TAIL_WARN_AFTER:
                console.print(
                    f"[yellow]warning:[/yellow] log tail has failed "
                    f"{consecutive_failures} times in a row: {exc}"
                )
            continue
        consecutive_failures = 0
        entries = unwrap_result(result, "gcode_store")
        new_entries = [e for e in entries if e.get("time", 0) > last_time]
        if new_entries:
            last_time = max(e.get("time", 0) for e in new_entries)
            for entry in new_entries:
                msg = entry.get("message", "")
                if not msg_filter.matches(msg):
                    continue
                if is_json_mode():
                    output_json(entry)
                else:
                    _print_log_entry(entry)


@server.command("console")
@click.option("--filter", "filter_pattern", help="Only show lines matching regex pattern.")
@click.option("--exclude", "exclude_pattern", help="Hide lines matching regex pattern.")
@click.option("--exclude-temps", is_flag=True, help="Hide temperature reports.")
@click.pass_context
def console_cmd(
    ctx: click.Context,
    filter_pattern: str | None,
    exclude_pattern: str | None,
    exclude_temps: bool,
) -> None:
    """Stream console messages in real-time via WebSocket."""
    msg_filter = build_filter(filter_pattern, exclude_pattern, exclude_temps)
    try:
        asyncio.run(_console_stream(ctx, msg_filter))
    except KeyboardInterrupt:
        pass
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)


async def _console_stream(ctx: click.Context, msg_filter: MessageFilter) -> None:
    """Connect via WebSocket and stream NOTIFY_GCODE_RESPONSE events."""
    from moonraker_client.api.notifications import NOTIFY_GCODE_RESPONSE

    from klipperctl import __version__
    from klipperctl.client import build_async_client

    async with build_async_client(ctx) as client:
        await client.connect_websocket(reconnect=True)
        await client.identify("klipperctl", __version__, client_type="agent")

        def on_gcode_response(params: list) -> None:
            message = params[0] if isinstance(params, list) and params else str(params)
            if not msg_filter.matches(message):
                return
            if is_json_mode():
                output_json({"message": message, "time": time.time()})
            else:
                console.print(message)

        client.on(NOTIFY_GCODE_RESPONSE, on_gcode_response)

        if not is_json_mode():
            console.print("[dim]Streaming console... Press Ctrl+C to stop.[/dim]")

        import contextlib

        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.Event().wait()


@server.command("logs-rollover")
@click.option("--app", "application", default="*all*", help="Application name.")
@click.pass_context
def logs_rollover(ctx: click.Context, application: str) -> None:
    """Rollover log files."""
    try:
        client = get_client(ctx)
        client.server_logs_rollover(application=application)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json({"result": "ok"})
    else:
        console.print("Log rollover requested.")


@server.command()
@click.option("--include-dismissed", is_flag=True, help="Include dismissed entries.")
@click.pass_context
def announcements(ctx: click.Context, include_dismissed: bool) -> None:
    """List announcements."""
    try:
        client = get_client(ctx)
        result = client.server_announcements_list(include_dismissed=include_dismissed)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    entries = unwrap_result(result, "entries")

    def _human(entries: list) -> None:
        if not entries:
            console.print("No announcements.")
            return
        for entry in entries:
            title = entry.get("title", "?")
            dismissed = entry.get("dismissed", False)
            prefix = "[dim][dismissed][/dim] " if dismissed else ""
            console.print(f"  {prefix}{title}")
            if entry.get("description"):
                console.print(f"    {entry['description'][:100]}")

    output(entries, _human)


@server.command()
@click.argument("entry_id")
@click.pass_context
def dismiss(ctx: click.Context, entry_id: str) -> None:
    """Dismiss an announcement."""
    try:
        client = get_client(ctx)
        result = client.server_announcements_dismiss(entry_id)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print("Announcement dismissed.")
