"""Files command group - file management."""

from __future__ import annotations

import click
from moonraker_client.helpers import list_gcode_files, upload_gcode

from klipperctl.cli import _handle_error
from klipperctl.client import get_client
from klipperctl.output import (
    console,
    format_bytes,
    format_timestamp,
    make_table,
    output,
    print_table,
)


@click.group()
def files() -> None:
    """File management."""


@files.command("list")
@click.option("--root", default="gcodes", show_default=True, help="Root directory.")
@click.option(
    "--sort",
    type=click.Choice(["modified", "size", "path"]),
    default="modified",
    show_default=True,
    help="Sort field.",
)
@click.option("--long", "long_format", is_flag=True, help="Show extended metadata.")
@click.pass_context
def list_files(ctx: click.Context, root: str, sort: str, long_format: bool) -> None:
    """List gcode files."""
    try:
        client = get_client(ctx)
        if root == "gcodes":
            file_list = list_gcode_files(client, sort_by=sort)
        else:
            file_list = client.files_list(root=root)
            reverse = sort == "modified"
            file_list = sorted(file_list, key=lambda f: f.get(sort, 0), reverse=reverse)
    except Exception as e:
        _handle_error(ctx, e)

    def _human(file_list: list) -> None:
        if not file_list:
            console.print("No files found.")
            return
        if long_format:
            table = make_table("Path", "Size", "Modified")
            for f in file_list:
                table.add_row(
                    f.get("path", f.get("filename", "?")),
                    format_bytes(f.get("size", 0)),
                    format_timestamp(f["modified"]) if "modified" in f else "?",
                )
        else:
            table = make_table("Path", "Size")
            for f in file_list:
                table.add_row(
                    f.get("path", f.get("filename", "?")),
                    format_bytes(f.get("size", 0)),
                )
        print_table(table)

    output(file_list, _human)


@files.command()
@click.argument("filename")
@click.pass_context
def info(ctx: click.Context, filename: str) -> None:
    """Show file metadata."""
    try:
        client = get_client(ctx)
        data = client.files_metadata(filename)
    except Exception as e:
        _handle_error(ctx, e)

    def _human(data: dict) -> None:
        console.print(f"[bold]{data.get('filename', filename)}[/bold]")
        if "size" in data:
            console.print(f"  Size:            {format_bytes(data['size'])}")
        if "modified" in data:
            console.print(f"  Modified:        {format_timestamp(data['modified'])}")
        if "slicer" in data:
            console.print(f"  Slicer:          {data['slicer']}")
        if "slicer_version" in data:
            console.print(f"  Slicer Version:  {data['slicer_version']}")
        if "estimated_time" in data:
            from klipperctl.output import format_duration

            console.print(f"  Estimated Time:  {format_duration(data['estimated_time'])}")
        if "filament_total" in data:
            filament_m = data["filament_total"] / 1000.0
            console.print(f"  Filament:        {filament_m:.1f}m")
        if "layer_height" in data:
            console.print(f"  Layer Height:    {data['layer_height']}mm")
        if "first_layer_height" in data:
            console.print(f"  First Layer:     {data['first_layer_height']}mm")
        if "first_layer_bed_temp" in data:
            console.print(f"  Bed Temp:        {data['first_layer_bed_temp']}\u00b0C")
        if "first_layer_extr_temp" in data:
            console.print(f"  Hotend Temp:     {data['first_layer_extr_temp']}\u00b0C")

    output(data, _human)


@files.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--path", "remote_path", help="Remote subdirectory.")
@click.option("--print", "start_print", is_flag=True, help="Start printing after upload.")
@click.pass_context
def upload(ctx: click.Context, file: str, remote_path: str | None, start_print: bool) -> None:
    """Upload a local gcode file."""
    try:
        client = get_client(ctx)
        result = upload_gcode(client, file, remote_path=remote_path, start=start_print)
    except Exception as e:
        _handle_error(ctx, e)

    def _human(result: dict) -> None:
        item = result.get("item", {})
        console.print(f"Uploaded: {item.get('path', file)}")
        if start_print:
            console.print("Print started.")

    output(result, _human)
