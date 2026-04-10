"""Printer command group - state and direct control."""

from __future__ import annotations

import logging
import sys

import click
from moonraker_client import MoonrakerClient
from moonraker_client.exceptions import MoonrakerError
from moonraker_client.helpers import (
    PrinterStatus,
    TemperatureReading,
    get_printer_status,
    get_temperatures,
    restart_firmware,
    send_gcode,
    set_bed_temp,
    set_hotend_temp,
    wait_for_temps,
)

from klipperctl.cli import _handle_error
from klipperctl.client import get_client
from klipperctl.output import (
    console,
    format_duration,
    format_percent,
    format_temp,
    is_json_mode,
    make_table,
    output,
    output_error,
    output_json,
    print_table,
    unwrap_result,
    watch_loop,
)

_logger = logging.getLogger(__name__)


@click.group()
def printer() -> None:
    """Printer state and direct control."""


@printer.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show comprehensive printer status dashboard."""
    try:
        client = get_client(ctx)
        st = get_printer_status(client)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    def _human(st: PrinterStatus) -> None:
        state_color = {"ready": "green", "error": "red", "shutdown": "red"}.get(st.state, "yellow")
        console.print("[bold]Printer Status[/bold]")
        console.print(f"  State:    [{state_color}]{st.state}[/{state_color}]")
        if st.state_message:
            console.print(f"  Message:  {st.state_message}")
        console.print(f"  Host:     {st.hostname}")
        console.print(f"  Klipper:  {st.software_version}")
        console.print(f"  Klippy:   {st.klippy_state}")
        console.print()

        if st.temperatures:
            table = make_table("Heater", "Current", "Target", "Power")
            for name, t in st.temperatures.items():
                table.add_row(
                    name,
                    format_temp(t.current),
                    format_temp(t.target),
                    f"{t.power * 100:.0f}%",
                )
            print_table(table)

        if st.filename:
            console.print()
            console.print(f"  Printing: {st.filename}")
            console.print(f"  Progress: {format_percent(st.progress)}")
            console.print(f"  Duration: {format_duration(st.print_duration)}")

    output(
        {
            "state": st.state,
            "state_message": st.state_message,
            "hostname": st.hostname,
            "software_version": st.software_version,
            "klippy_connected": st.klippy_connected,
            "klippy_state": st.klippy_state,
            "filename": st.filename,
            "progress": st.progress,
            "print_duration": st.print_duration,
            "temperatures": {
                name: {"current": t.current, "target": t.target, "power": t.power}
                for name, t in st.temperatures.items()
            },
        },
        lambda data: _human(st),
    )


@printer.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Show raw Klipper host information."""
    try:
        client = get_client(ctx)
        data = client.printer_info()
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    def _human(data: dict) -> None:
        for key, value in data.items():
            console.print(f"  {key}: {value}")

    output(data, _human)


@printer.command()
@click.option("--all", "show_all", is_flag=True, help="Include all heaters and sensors.")
@click.option("--watch", is_flag=True, help="Continuously poll temperatures.")
@click.option(
    "--interval", type=float, default=2.0, show_default=True, help="Poll interval in seconds."
)
@click.pass_context
def temps(ctx: click.Context, show_all: bool, watch: bool, interval: float) -> None:
    """Show extruder and bed temperatures."""
    try:
        client = get_client(ctx)
        _show_temps(client, show_all)
        if watch:
            watch_loop(lambda: _show_temps(client, show_all), interval)
    except KeyboardInterrupt:
        pass
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)


def _show_temps(client: MoonrakerClient, show_all: bool) -> None:
    """Fetch and display temperatures."""

    temps = get_temperatures(client)

    if show_all:
        # Query all temperature-related objects
        try:
            objects = client.printer_objects_list()
            temp_objects: dict[str, list[str] | None] = {}
            for obj in objects:
                if any(
                    obj.startswith(prefix)
                    for prefix in (
                        "extruder",
                        "heater_bed",
                        "temperature_sensor",
                        "temperature_fan",
                    )
                ):
                    temp_objects[obj] = ["temperature", "target", "power"]
            if temp_objects:
                result = client.printer_objects_query(temp_objects)
                status = result.get("status", {})
                for name, data in status.items():
                    if isinstance(data, dict) and "temperature" in data:
                        temps[name] = TemperatureReading(
                            current=data.get("temperature", 0.0),
                            target=data.get("target", 0.0),
                            power=data.get("power", 0.0),
                        )
        except MoonrakerError as exc:
            # Best-effort enrichment. Surface at debug so `--watch` keeps
            # rolling while still letting KeyboardInterrupt propagate.
            _logger.debug("printer_objects_list/query transient failure: %s", exc)

    data = {
        name: {"current": t.current, "target": t.target, "power": t.power}
        for name, t in temps.items()
    }

    def _human(data: dict) -> None:
        table = make_table("Heater", "Current", "Target", "Power")
        for name, values in data.items():
            table.add_row(
                name,
                format_temp(values["current"]),
                format_temp(values["target"]),
                f"{values['power'] * 100:.0f}%",
            )
        print_table(table)

    output(data, _human)


@printer.command("set-temp")
@click.option("--hotend", type=float, help="Hotend target temperature (\u00b0C).")
@click.option("--bed", type=float, help="Bed target temperature (\u00b0C).")
@click.option("--tool", type=int, default=0, show_default=True, help="Tool index.")
@click.option("--wait", is_flag=True, help="Wait until temperatures are reached.")
@click.option(
    "--tolerance", type=float, default=2.0, show_default=True, help="Degrees tolerance for --wait."
)
@click.option(
    "--timeout",
    "wait_timeout",
    type=float,
    default=300.0,
    show_default=True,
    help="Max wait time in seconds.",
)
@click.pass_context
def set_temp(
    ctx: click.Context,
    hotend: float | None,
    bed: float | None,
    tool: int,
    wait: bool,
    tolerance: float,
    wait_timeout: float,
) -> None:
    """Set heater target temperatures."""
    if hotend is None and bed is None:
        raise click.UsageError("Specify at least one of --hotend or --bed.")

    try:
        client = get_client(ctx)
        targets: dict[str, float] = {}

        if hotend is not None:
            set_hotend_temp(client, hotend, tool=tool)
            targets[f"extruder{'' if tool == 0 else tool}"] = hotend
            if not is_json_mode():
                console.print(f"Hotend target set to {format_temp(hotend)}")

        if bed is not None:
            set_bed_temp(client, bed)
            targets["heater_bed"] = bed
            if not is_json_mode():
                console.print(f"Bed target set to {format_temp(bed)}")

        if wait and targets:
            if not is_json_mode():
                console.print("Waiting for temperatures...")
            reached = wait_for_temps(client, targets, tolerance=tolerance, timeout=wait_timeout)
            if not reached:
                output_error("Timeout waiting for temperatures.", code=1)
                sys.exit(1)
            if not is_json_mode():
                console.print("[green]Temperatures reached.[/green]")

        if is_json_mode():
            output_json({"targets": targets, "wait": wait})
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)


@printer.command()
@click.argument("script", required=False)
@click.pass_context
def gcode(ctx: click.Context, script: str | None) -> None:
    """Send raw GCode command(s).

    Pass GCode as an argument or use - to read from stdin.
    """
    if script == "-" or (script is None and not sys.stdin.isatty()):
        script = sys.stdin.read().strip()
    if not script:
        raise click.UsageError("Provide a GCode command or pipe via stdin.")

    try:
        client = get_client(ctx)
        result = send_gcode(client, script)
        output({"result": result}, lambda d: console.print("OK"))
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)


@printer.command("gcode-help")
@click.option("--filter", "name_filter", help="Filter by command name substring.")
@click.pass_context
def gcode_help(ctx: click.Context, name_filter: str | None) -> None:
    """List registered GCode commands."""
    try:
        client = get_client(ctx)
        data = client.gcode_help()
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if name_filter:
        upper_filter = name_filter.upper()
        data = {k: v for k, v in data.items() if upper_filter in k.upper()}

    def _human(data: dict) -> None:
        table = make_table("Command", "Description")
        for cmd in sorted(data.keys()):
            table.add_row(cmd, data[cmd])
        print_table(table)

    output(data, _human)


@printer.command()
@click.pass_context
def objects(ctx: click.Context) -> None:
    """List available Klipper printer objects."""
    try:
        client = get_client(ctx)
        result = client.printer_objects_list()
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    # API returns {"objects": [...]} — unwrap to the list
    obj_list = unwrap_result(result, "objects")

    def _human(data: list) -> None:
        for obj in sorted(data):
            console.print(f"  {obj}")

    output(obj_list, _human)


@printer.command()
@click.argument("object_names", nargs=-1, required=True)
@click.option("--attrs", help="Comma-separated attribute names.")
@click.pass_context
def query(ctx: click.Context, object_names: tuple[str, ...], attrs: str | None) -> None:
    """Query specific printer objects."""
    attr_list = attrs.split(",") if attrs else None
    objects_dict: dict[str, list[str] | None] = {name: attr_list for name in object_names}  # noqa: C420

    try:
        client = get_client(ctx)
        result = client.printer_objects_query(objects_dict)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    data = result.get("status", result)

    def _human(data: dict) -> None:
        for obj_name, obj_data in data.items():
            console.print(f"[bold]{obj_name}[/bold]")
            if isinstance(obj_data, dict):
                for key, value in obj_data.items():
                    console.print(f"  {key}: {value}")
            else:
                console.print(f"  {obj_data}")

    output(data, _human)


@printer.command()
@click.pass_context
def endstops(ctx: click.Context) -> None:
    """Query endstop states."""
    try:
        client = get_client(ctx)
        data = client.query_endstops()
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    def _human(data: dict) -> None:
        table = make_table("Endstop", "State")
        for name, state in sorted(data.items()):
            color = "green" if state == "open" else "red"
            table.add_row(name, f"[{color}]{state}[/{color}]")
        print_table(table)

    output(data, _human)


@printer.command()
@click.pass_context
def restart(ctx: click.Context) -> None:
    """Soft restart Klipper."""
    try:
        client = get_client(ctx)
        client.printer_restart()
        if not is_json_mode():
            console.print("Klipper restart requested.")
        else:
            output_json({"result": "ok"})
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)


@printer.command("firmware-restart")
@click.option("--wait/--no-wait", default=True, show_default=True, help="Wait for ready state.")
@click.option(
    "--timeout",
    "wait_timeout",
    type=float,
    default=30.0,
    show_default=True,
    help="Max wait time in seconds.",
)
@click.pass_context
def firmware_restart_cmd(ctx: click.Context, wait: bool, wait_timeout: float) -> None:
    """Full firmware restart (resets MCUs)."""
    try:
        client = get_client(ctx)
        if wait:
            if not is_json_mode():
                console.print("Restarting firmware...")
            reached = restart_firmware(client, timeout=wait_timeout)
            msg = "Firmware restarted successfully." if reached else "Firmware restart timed out."
            if is_json_mode():
                output_json({"result": "ok" if reached else "timeout"})
            else:
                color = "green" if reached else "yellow"
                console.print(f"[{color}]{msg}[/{color}]")
            if not reached:
                sys.exit(1)
        else:
            client.firmware_restart()
            if is_json_mode():
                output_json({"result": "ok"})
            else:
                console.print("Firmware restart requested.")
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)


@printer.command("emergency-stop")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def emergency_stop(ctx: click.Context, yes: bool) -> None:
    """Emergency stop the printer.

    This will IMMEDIATELY HALT the printer. All heaters will be disabled.
    """
    if not yes:
        click.confirm(
            "This will IMMEDIATELY HALT the printer. All heaters will be disabled. Continue?",
            abort=True,
        )
    try:
        client = get_client(ctx)
        client.emergency_stop()
        if is_json_mode():
            output_json({"result": "ok"})
        else:
            console.print("[red]Emergency stop executed.[/red]")
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)
