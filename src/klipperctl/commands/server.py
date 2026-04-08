"""Server command group - Moonraker server management."""

from __future__ import annotations

import click
from moonraker_client.exceptions import MoonrakerError

from klipperctl.cli import _handle_error
from klipperctl.client import get_client
from klipperctl.output import (
    console,
    format_timestamp,
    is_json_mode,
    output,
    output_json,
    unwrap_result,
)


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
@click.pass_context
def logs(ctx: click.Context, count: int | None) -> None:
    """Show cached GCode responses."""
    try:
        client = get_client(ctx)
        result = client.server_gcodestore(count=count)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    entries = unwrap_result(result, "gcode_store")

    def _human(entries: list) -> None:
        if not entries:
            console.print("No cached GCode responses.")
            return
        for entry in entries:
            msg = entry.get("message", "")
            time_val = entry.get("time")
            ts = f"[dim]{format_timestamp(time_val)}[/dim] " if time_val else ""
            console.print(f"{ts}{msg}")

    output(entries, _human)


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
