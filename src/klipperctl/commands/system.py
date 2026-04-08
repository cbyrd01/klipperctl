"""System command group - host machine management."""

from __future__ import annotations

import time

import click
from moonraker_client.exceptions import MoonrakerError
from moonraker_client.helpers import get_system_health

from klipperctl.cli import _handle_error
from klipperctl.client import get_client
from klipperctl.output import (
    console,
    format_bytes,
    format_duration,
    is_json_mode,
    make_table,
    output,
    output_json,
    print_table,
)


@click.group()
def system() -> None:
    """Host machine management."""


@system.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Show system info (OS, CPU, memory)."""
    try:
        client = get_client(ctx)
        data = client.machine_systeminfo()
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    sys_info = data.get("system_info", data) if isinstance(data, dict) else data

    def _human(si: dict) -> None:
        console.print("[bold]System Information[/bold]")
        cpu = si.get("cpu_info", {})
        if cpu:
            console.print(f"  CPU:        {cpu.get('model', '?')}")
            console.print(f"  Cores:      {cpu.get('cpu_count', '?')}")
        dist = si.get("distribution", {})
        if dist:
            console.print(f"  OS:         {dist.get('name', '?')} {dist.get('version', '')}")
        mem = si.get("memory", {})
        if mem:
            console.print(f"  Memory:     {format_bytes(mem.get('total', 0) * 1024)}")
        net = si.get("network", {})
        if net:
            for iface, details in net.items():
                if details.get("ip_addresses"):
                    ips = ", ".join(a.get("address", "") for a in details["ip_addresses"])
                    console.print(f"  Net ({iface}): {ips}")

    output(sys_info, _human)


@system.command()
@click.option("--watch", is_flag=True, help="Continuously poll.")
@click.option("--interval", type=float, default=5.0, show_default=True, help="Poll interval.")
@click.pass_context
def health(ctx: click.Context, watch: bool, interval: float) -> None:
    """Show system health summary."""
    try:
        client = get_client(ctx)
        _show_health(client)
        if watch:
            while True:
                time.sleep(interval)
                if not is_json_mode():
                    click.clear()
                _show_health(client)
    except KeyboardInterrupt:
        pass
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)


def _show_health(client: object) -> None:
    """Fetch and display system health."""
    data = get_system_health(client)  # type: ignore[arg-type]

    def _human(data: dict) -> None:
        console.print("[bold]System Health[/bold]")
        if data.get("cpu_temp") is not None:
            console.print(f"  CPU Temp:   {data['cpu_temp']:.1f}\u00b0C")
        if data.get("system_uptime") is not None:
            console.print(f"  Uptime:     {format_duration(data['system_uptime'])}")
        mem = data.get("system_memory")
        if mem:
            total = mem.get("total", 0)
            used = mem.get("used", 0)
            console.print(
                f"  Memory:     {format_bytes(used * 1024)} / {format_bytes(total * 1024)}"
            )
        cpu = data.get("system_cpu_usage")
        if cpu:
            total_pct = sum(cpu.values()) / len(cpu) if cpu else 0
            console.print(f"  CPU Usage:  {total_pct:.1f}%")
        if data.get("websocket_connections") is not None:
            console.print(f"  WS Conns:   {data['websocket_connections']}")

    output(data, _human)


@system.command()
@click.option("--yes", is_flag=True, help="Skip confirmation.")
@click.pass_context
def shutdown(ctx: click.Context, yes: bool) -> None:
    """Shutdown the host operating system."""
    if not yes:
        click.confirm(
            "This will shut down the printer's operating system. Continue?",
            abort=True,
        )
    try:
        client = get_client(ctx)
        client.machine_shutdown()
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json({"result": "ok"})
    else:
        console.print("Shutdown initiated.")


@system.command()
@click.option("--yes", is_flag=True, help="Skip confirmation.")
@click.pass_context
def reboot(ctx: click.Context, yes: bool) -> None:
    """Reboot the host operating system."""
    if not yes:
        click.confirm("This will reboot the printer's operating system. Continue?", abort=True)
    try:
        client = get_client(ctx)
        client.machine_reboot()
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json({"result": "ok"})
    else:
        console.print("Reboot initiated.")


@system.command()
@click.pass_context
def services(ctx: click.Context) -> None:
    """List system services."""
    try:
        client = get_client(ctx)
        data = client.machine_systeminfo()
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    si = data.get("system_info", data) if isinstance(data, dict) else data
    svc_state = si.get("service_state", {})

    def _human(svc_state: dict) -> None:
        if not svc_state:
            console.print("No service information available.")
            return
        table = make_table("Service", "State", "Sub-state")
        for name in sorted(svc_state.keys()):
            svc = svc_state[name]
            state = svc.get("active_state", "?")
            sub = svc.get("sub_state", "?")
            color = "green" if state == "active" else "red" if state == "failed" else "yellow"
            table.add_row(name, f"[{color}]{state}[/{color}]", sub)
        print_table(table)

    output(svc_state, _human)


@system.group("service")
def service_group() -> None:
    """Manage system services."""


@service_group.command()
@click.argument("service")
@click.pass_context
def restart(ctx: click.Context, service: str) -> None:
    """Restart a system service."""
    try:
        client = get_client(ctx)
        client.machine_services_restart(service)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json({"result": "ok", "service": service})
    else:
        console.print(f"Service '{service}' restart requested.")


@service_group.command()
@click.argument("service")
@click.pass_context
def stop(ctx: click.Context, service: str) -> None:
    """Stop a system service."""
    try:
        client = get_client(ctx)
        client.machine_services_stop(service)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json({"result": "ok", "service": service})
    else:
        console.print(f"Service '{service}' stop requested.")


@service_group.command()
@click.argument("service")
@click.pass_context
def start(ctx: click.Context, service: str) -> None:
    """Start a system service."""
    try:
        client = get_client(ctx)
        client.machine_services_start(service)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json({"result": "ok", "service": service})
    else:
        console.print(f"Service '{service}' start requested.")


@system.command()
@click.option(
    "--type",
    "device_type",
    type=click.Choice(["usb", "serial", "video", "canbus"]),
    help="Filter by device type.",
)
@click.pass_context
def peripherals(ctx: click.Context, device_type: str | None) -> None:
    """List USB, serial, video, and CAN devices."""
    try:
        client = get_client(ctx)
        result: dict = {}
        types = [device_type] if device_type else ["usb", "serial", "video", "canbus"]
        for dt in types:
            try:
                if dt == "usb":
                    result["usb"] = client.machine_peripherals_usb()
                elif dt == "serial":
                    result["serial"] = client.machine_peripherals_serial()
                elif dt == "video":
                    result["video"] = client.machine_peripherals_video()
                elif dt == "canbus":
                    result["canbus"] = client.machine_peripherals_canbus()
            except MoonrakerError:
                result[dt] = []
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    def _human(result: dict) -> None:
        for dt, devices in result.items():
            dev_list = devices if isinstance(devices, list) else devices.get("devices", [])
            console.print(f"[bold]{dt.upper()} Devices ({len(dev_list)})[/bold]")
            if not dev_list:
                console.print("  None found.")
            for dev in dev_list:
                if dt == "usb":
                    desc = dev.get("description", dev.get("product", "?"))
                    console.print(
                        f"  {dev.get('device_num', '?')}: {desc} "
                        f"[dim]{dev.get('vendor_id', '')}:{dev.get('product_id', '')}[/dim]"
                    )
                elif dt == "serial":
                    console.print(
                        f"  {dev.get('device_path', '?')} [dim]{dev.get('driver_name', '')}[/dim]"
                    )
                else:
                    console.print(f"  {dev}")
            console.print()

    output(result, _human)
