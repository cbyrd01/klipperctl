"""Print command group - active print job control."""

from __future__ import annotations

import time

import click
from moonraker_client.exceptions import MoonrakerError
from moonraker_client.helpers import (
    get_print_progress,
    start_print,
)

from klipperctl.cli import _handle_error
from klipperctl.client import get_client
from klipperctl.output import (
    console,
    format_duration,
    is_json_mode,
    output,
    output_json,
)


@click.group("print")
def print_cmd() -> None:
    """Active print job control."""


@print_cmd.command()
@click.argument("filename")
@click.pass_context
def start(ctx: click.Context, filename: str) -> None:
    """Start printing a file."""
    try:
        client = get_client(ctx)
        result = start_print(client, filename)
        if is_json_mode():
            output_json({"result": result, "filename": filename})
        else:
            console.print(f"Print started: {filename}")
    except FileNotFoundError as e:
        _handle_error(ctx, e)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)


@print_cmd.command()
@click.pass_context
def pause(ctx: click.Context) -> None:
    """Pause the current print."""
    try:
        client = get_client(ctx)
        client.print_pause()
        if is_json_mode():
            output_json({"result": "ok"})
        else:
            console.print("Print paused.")
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)


@print_cmd.command()
@click.pass_context
def resume(ctx: click.Context) -> None:
    """Resume the paused print."""
    try:
        client = get_client(ctx)
        client.print_resume()
        if is_json_mode():
            output_json({"result": "ok"})
        else:
            console.print("Print resumed.")
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)


@print_cmd.command()
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def cancel(ctx: click.Context, yes: bool) -> None:
    """Cancel the current print."""
    try:
        client = get_client(ctx)

        if not yes:
            progress = get_print_progress(client)
            if progress:
                msg = (
                    f"Cancel print of '{progress.filename}' at {progress.progress_pct}% progress?"
                )
            else:
                msg = "Cancel the current print?"
            click.confirm(msg, abort=True)

        client.print_cancel()
        if is_json_mode():
            output_json({"result": "ok"})
        else:
            console.print("Print cancelled.")
    except click.Abort:
        raise
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)


@print_cmd.command()
@click.option("--watch", is_flag=True, help="Continuously update progress.")
@click.option(
    "--interval", type=float, default=2.0, show_default=True, help="Poll interval in seconds."
)
@click.pass_context
def progress(ctx: click.Context, watch: bool, interval: float) -> None:
    """Show current print progress."""
    try:
        client = get_client(ctx)
        _show_progress(client)
        if watch:
            while True:
                time.sleep(interval)
                if not is_json_mode():
                    click.clear()
                _show_progress(client)
    except KeyboardInterrupt:
        pass
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)


def _show_progress(client: object) -> None:
    """Fetch and display print progress."""
    prog = get_print_progress(client)  # type: ignore[arg-type]

    if prog is None:
        if is_json_mode():
            output_json(None)
        else:
            console.print("No active print.")
        return

    data = {
        "filename": prog.filename,
        "progress_pct": prog.progress_pct,
        "elapsed": prog.elapsed,
        "state": prog.state,
        "message": prog.message,
    }

    def _human(data: dict) -> None:
        state_color = {
            "printing": "green",
            "paused": "yellow",
            "complete": "blue",
            "error": "red",
            "cancelled": "red",
        }.get(data["state"], "white")
        console.print("[bold]Print Progress[/bold]")
        console.print(f"  File:     {data['filename']}")
        console.print(f"  State:    [{state_color}]{data['state']}[/{state_color}]")
        console.print(f"  Progress: {data['progress_pct']:.1f}%")
        console.print(f"  Elapsed:  {format_duration(data['elapsed'])}")
        if data["message"]:
            console.print(f"  Message:  {data['message']}")

    output(data, _human)
