"""Update command group - software update management."""

from __future__ import annotations

import click

from klipperctl.cli import _handle_error
from klipperctl.client import get_client
from klipperctl.output import (
    console,
    is_json_mode,
    make_table,
    output,
    output_json,
    print_table,
)


@click.group()
def update() -> None:
    """Software update management."""


@update.command()
@click.option("--refresh", is_flag=True, help="Force refresh check (CPU-intensive).")
@click.pass_context
def status(ctx: click.Context, refresh: bool) -> None:
    """Show update status for all components."""
    try:
        client = get_client(ctx)
        if refresh:
            client.machine_update_refresh()
        data = client.machine_update_status()
    except Exception as e:
        _handle_error(ctx, e)

    version_info = data.get("version_info", data) if isinstance(data, dict) else data

    def _human(vi: dict) -> None:
        table = make_table("Component", "Version", "Remote", "Status")
        for name, info in sorted(vi.items()):
            if not isinstance(info, dict):
                continue
            version = info.get("version", info.get("full_version_string", "?"))
            remote = info.get("remote_version", info.get("remote_version_string", ""))
            is_dirty = info.get("is_dirty", False)
            is_valid = info.get("is_valid", True)
            if not is_valid:
                status_str = "[red]invalid[/red]"
            elif is_dirty:
                status_str = "[yellow]dirty[/yellow]"
            elif version != remote and remote:
                status_str = "[cyan]update available[/cyan]"
            else:
                status_str = "[green]up to date[/green]"
            table.add_row(name, str(version), str(remote), status_str)
        print_table(table)

    output(version_info, _human)


@update.command()
@click.option("--name", help="Specific component to upgrade (default: all).")
@click.pass_context
def upgrade(ctx: click.Context, name: str | None) -> None:
    """Upgrade software."""
    try:
        client = get_client(ctx)
        if not is_json_mode():
            target = name or "all components"
            console.print(f"Upgrading {target}...")
        result = client.machine_update_upgrade(name=name)
    except Exception as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print("Upgrade initiated.")


@update.command()
@click.argument("name")
@click.pass_context
def rollback(ctx: click.Context, name: str) -> None:
    """Rollback to previous version."""
    try:
        client = get_client(ctx)
        result = client.machine_update_rollback()
    except Exception as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print(f"Rollback initiated for {name}.")


@update.command()
@click.argument("name")
@click.option("--hard", is_flag=True, help="Hard recovery mode.")
@click.pass_context
def recover(ctx: click.Context, name: str, hard: bool) -> None:
    """Recover a corrupt repo."""
    try:
        client = get_client(ctx)
        result = client.machine_update_recover(name, hard=hard)
    except Exception as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        mode = "hard" if hard else "soft"
        console.print(f"Recovery ({mode}) initiated for {name}.")
