"""Files command group - file management."""

from __future__ import annotations

from pathlib import Path

import click
from moonraker_client.exceptions import MoonrakerError
from moonraker_client.helpers import list_gcode_files, upload_gcode

from klipperctl.cli import _handle_error
from klipperctl.client import get_client
from klipperctl.output import (
    console,
    format_bytes,
    format_duration,
    format_timestamp,
    is_json_mode,
    make_table,
    output,
    output_json,
    print_table,
)


def _validate_remote_path(name: str) -> str:
    """Reject remote filenames that contain path traversal sequences."""
    if ".." in name:
        raise click.BadParameter(f"Invalid remote path (contains '..'): {name}")
    return name


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
    except (MoonrakerError, click.Abort, OSError) as e:
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
    except (MoonrakerError, click.Abort, OSError) as e:
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
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    def _human(result: dict) -> None:
        item = result.get("item", {})
        console.print(f"Uploaded: {item.get('path', file)}")
        if start_print:
            console.print("Print started.")

    output(result, _human)


@files.command()
@click.argument("filename")
@click.option("--output", "output_path", type=click.Path(), help="Local output path.")
@click.option("--root", default="gcodes", show_default=True, help="Root directory.")
@click.pass_context
def download(ctx: click.Context, filename: str, output_path: str | None, root: str) -> None:
    """Download a file from the printer."""
    _validate_remote_path(filename)
    try:
        client = get_client(ctx)
        data = client.files_download(root, filename)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if output_path:
        # Reject path traversal sequences in the output path
        if ".." in Path(output_path).parts:
            raise click.BadParameter(
                f"Output path must not contain '..': {output_path}"
            )
        try:
            with open(output_path, "wb" if isinstance(data, bytes) else "w") as f:
                f.write(data)
        except OSError as e:
            raise click.ClickException(f"Failed to write file: {e}") from e
        if not is_json_mode():
            console.print(f"Downloaded to: {output_path}")
        else:
            output_json({"path": output_path, "filename": filename})
    else:
        if is_json_mode():
            output_json({"filename": filename, "size": len(data) if data else 0})
        else:
            click.echo(data)


@files.command()
@click.argument("filename")
@click.option("--root", default="gcodes", show_default=True, help="Root directory.")
@click.option("--yes", is_flag=True, help="Skip confirmation.")
@click.pass_context
def delete(ctx: click.Context, filename: str, root: str, yes: bool) -> None:
    """Delete a file."""
    if not yes:
        click.confirm(f"Delete '{filename}' from {root}?", abort=True)
    try:
        client = get_client(ctx)
        result = client.files_delete(root, filename)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print(f"Deleted: {filename}")


@files.command()
@click.argument("source")
@click.argument("dest")
@click.pass_context
def move(ctx: click.Context, source: str, dest: str) -> None:
    """Move or rename a file."""
    try:
        client = get_client(ctx)
        result = client.files_move(source, dest)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print(f"Moved: {source} -> {dest}")


@files.command()
@click.argument("source")
@click.argument("dest")
@click.pass_context
def copy(ctx: click.Context, source: str, dest: str) -> None:
    """Copy a file."""
    try:
        client = get_client(ctx)
        result = client.files_copy(source, dest)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print(f"Copied: {source} -> {dest}")


@files.command()
@click.argument("path")
@click.pass_context
def mkdir(ctx: click.Context, path: str) -> None:
    """Create a directory."""
    try:
        client = get_client(ctx)
        result = client.files_create_directory(path)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print(f"Created: {path}")


@files.command()
@click.argument("path")
@click.option("--force", is_flag=True, help="Force delete non-empty directory.")
@click.option("--yes", is_flag=True, help="Skip confirmation.")
@click.pass_context
def rmdir(ctx: click.Context, path: str, force: bool, yes: bool) -> None:
    """Delete a directory."""
    if not yes:
        click.confirm(f"Delete directory '{path}'?", abort=True)
    try:
        client = get_client(ctx)
        result = client.files_delete_directory(path, force=force)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print(f"Deleted: {path}")


@files.command()
@click.argument("filename")
@click.pass_context
def thumbnails(ctx: click.Context, filename: str) -> None:
    """List thumbnails for a gcode file."""
    try:
        client = get_client(ctx)
        data = client.files_thumbnails(filename)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    def _human(data: list) -> None:
        if not data:
            console.print("No thumbnails found.")
            return
        table = make_table("Width", "Height", "Size", "Type")
        for t in data:
            table.add_row(
                str(t.get("width", "?")),
                str(t.get("height", "?")),
                format_bytes(t.get("size", 0)),
                t.get("thumbnail_type", "?"),
            )
        print_table(table)

    output(data, _human)


@files.command()
@click.argument("filename")
@click.pass_context
def scan(ctx: click.Context, filename: str) -> None:
    """Trigger metadata rescan for a file."""
    try:
        client = get_client(ctx)
        result = client.files_metascan(filename)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print(f"Metadata scan initiated: {filename}")
