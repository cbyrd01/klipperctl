"""Output formatting for klipperctl.

Handles JSON mode, Rich tables, and unit conversions. All command output
should go through these helpers to ensure consistent behavior.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import click
from rich.console import Console
from rich.table import Table

# Shared consoles for human-readable output
console = Console(highlight=False)
error_console = Console(highlight=False, stderr=True)


def format_duration(seconds: float) -> str:
    """Convert seconds to human-readable duration.

    Examples:
        0 -> "0s"
        65 -> "1m 5s"
        3661 -> "1h 1m 1s"
        86461 -> "1d 0h 1m"
    """
    if seconds < 0:
        return "0s"
    total = int(seconds)
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def format_bytes(num_bytes: float) -> str:
    """Convert bytes to human-readable size.

    Examples:
        1024 -> "1.0 KB"
        1048576 -> "1.0 MB"
    """
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            if unit == "B":
                return f"{int(num_bytes)} {unit}"
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def format_temp(temp: float) -> str:
    """Format temperature with one decimal place."""
    return f"{temp:.1f}\u00b0C"


def format_timestamp(ts: float) -> str:
    """Convert unix timestamp to local time string."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_percent(value: float) -> str:
    """Format a 0-1 float as a percentage."""
    return f"{value * 100:.1f}%"


def output_json(data: Any) -> None:
    """Print data as JSON to stdout."""
    click.echo(json.dumps(data, default=str))


def output_error(message: str, code: int = 1) -> None:
    """Print error to stderr. In JSON mode, outputs JSON error object."""
    ctx = click.get_current_context(silent=True)
    json_mode = ctx and ctx.find_root().params.get("json_output")
    if json_mode:
        click.echo(json.dumps({"error": message, "code": code}), err=True)
    else:
        error_console.print(f"[red]Error:[/red] {message}")


def make_table(*columns: str, title: str | None = None) -> Table:
    """Create a Rich table with standard styling."""
    table = Table(title=title, show_header=True, header_style="bold")
    for col in columns:
        table.add_column(col)
    return table


def print_table(table: Table) -> None:
    """Print a Rich table to the console."""
    console.print(table)


def is_json_mode() -> bool:
    """Check if JSON output mode is active."""
    ctx = click.get_current_context(silent=True)
    return bool(ctx and ctx.find_root().params.get("json_output"))


def output(data: Any, human_fn: Any = None) -> None:
    """Output data in JSON or human-readable format.

    Args:
        data: The data to output.
        human_fn: Callable that produces human-readable output.
            If None, prints repr of data.
    """
    if is_json_mode():
        output_json(data)
    elif human_fn:
        human_fn(data)
    else:
        click.echo(data)
