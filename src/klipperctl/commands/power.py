"""Power command group - power device control."""

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
def power() -> None:
    """Power device control."""


@power.command("list")
@click.pass_context
def list_devices(ctx: click.Context) -> None:
    """List configured power devices."""
    try:
        client = get_client(ctx)
        data = client.power_devices_list()
    except Exception as e:
        _handle_error(ctx, e)

    devices = data.get("devices", data) if isinstance(data, dict) else data

    def _human(devices: list) -> None:
        if not devices:
            console.print("No power devices configured.")
            return
        table = make_table("Device", "Type", "State", "Locked While Printing")
        for dev in devices:
            state = dev.get("status", "?")
            color = "green" if state == "on" else "red" if state == "off" else "yellow"
            table.add_row(
                dev.get("device", "?"),
                dev.get("type", "?"),
                f"[{color}]{state}[/{color}]",
                str(dev.get("locked_while_printing", "?")),
            )
        print_table(table)

    output(devices, _human)


@power.command()
@click.argument("device", required=False)
@click.option("--all", "show_all", is_flag=True, help="Show all devices.")
@click.pass_context
def status(ctx: click.Context, device: str | None, show_all: bool) -> None:
    """Show power device status."""
    if not device and not show_all:
        raise click.UsageError("Specify a DEVICE name or use --all.")
    try:
        client = get_client(ctx)
        devices: list = []
        if show_all:
            raw = client.power_devices_list()
            devices = raw.get("devices", raw) if isinstance(raw, dict) else raw
        else:
            data = client.power_device_status(device)  # type: ignore[arg-type]
            devices = [data] if isinstance(data, dict) else []
    except Exception as e:
        _handle_error(ctx, e)

    def _human(devices: list) -> None:
        for dev in devices:
            name = dev.get("device", device or "?")
            state = dev.get("status", "?")
            color = "green" if state == "on" else "red" if state == "off" else "yellow"
            console.print(f"  {name}: [{color}]{state}[/{color}]")

    output(devices, _human)


@power.command()
@click.argument("device")
@click.pass_context
def on(ctx: click.Context, device: str) -> None:
    """Turn on a power device."""
    try:
        client = get_client(ctx)
        result = client.power_device_set(device, "on")
    except Exception as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print(f"[green]{device}: on[/green]")


@power.command()
@click.argument("device")
@click.pass_context
def off(ctx: click.Context, device: str) -> None:
    """Turn off a power device."""
    try:
        client = get_client(ctx)
        result = client.power_device_set(device, "off")
    except Exception as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print(f"[red]{device}: off[/red]")
