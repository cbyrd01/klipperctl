"""History command group - print history."""

from __future__ import annotations

import click
from moonraker_client.exceptions import MoonrakerError

from klipperctl.cli import _handle_error
from klipperctl.client import get_client
from klipperctl.output import (
    console,
    format_duration,
    format_timestamp,
    is_json_mode,
    make_table,
    output,
    output_json,
    print_table,
)


@click.group()
def history() -> None:
    """Print history."""


@history.command("list")
@click.option("--limit", type=int, default=20, show_default=True, help="Max entries.")
@click.option("--since", type=float, help="Unix timestamp: jobs since this time.")
@click.option("--before", type=float, help="Unix timestamp: jobs before this time.")
@click.option(
    "--order",
    type=click.Choice(["asc", "desc"]),
    default="desc",
    show_default=True,
    help="Sort order.",
)
@click.pass_context
def list_jobs(
    ctx: click.Context,
    limit: int,
    since: float | None,
    before: float | None,
    order: str,
) -> None:
    """List past print jobs."""
    try:
        client = get_client(ctx)
        result = client.server_history_list(limit=limit, since=since, before=before, order=order)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    jobs = result.get("jobs", result) if isinstance(result, dict) else result

    def _human(jobs: list) -> None:
        if not jobs:
            console.print("No print history.")
            return
        table = make_table("Filename", "Status", "Duration", "Filament", "Date")
        for job in jobs:
            table.add_row(
                job.get("filename", "?"),
                job.get("status", "?"),
                format_duration(job.get("print_duration", 0)),
                f"{job.get('filament_used', 0) / 1000:.1f}m",
                format_timestamp(job["start_time"]) if "start_time" in job else "?",
            )
        print_table(table)

    output(jobs, _human)


@history.command()
@click.argument("job_id")
@click.pass_context
def show(ctx: click.Context, job_id: str) -> None:
    """Show details of a single job."""
    try:
        client = get_client(ctx)
        result = client.server_history_job(job_id)
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    job = result.get("job", result) if isinstance(result, dict) else result

    def _human(job: dict) -> None:
        console.print(f"[bold]{job.get('filename', '?')}[/bold]")
        console.print(f"  Status:     {job.get('status', '?')}")
        if "start_time" in job:
            console.print(f"  Started:    {format_timestamp(job['start_time'])}")
        if "end_time" in job and job["end_time"]:
            console.print(f"  Ended:      {format_timestamp(job['end_time'])}")
        console.print(f"  Duration:   {format_duration(job.get('print_duration', 0))}")
        console.print(f"  Total Time: {format_duration(job.get('total_duration', 0))}")
        filament = job.get("filament_used", 0) / 1000
        console.print(f"  Filament:   {filament:.1f}m")
        if "metadata" in job and job["metadata"]:
            meta = job["metadata"]
            if "slicer" in meta:
                console.print(f"  Slicer:     {meta['slicer']}")
            if "estimated_time" in meta:
                console.print(f"  Est. Time:  {format_duration(meta['estimated_time'])}")

    output(job, _human)


@history.command()
@click.pass_context
def totals(ctx: click.Context) -> None:
    """Show aggregate print totals."""
    try:
        client = get_client(ctx)
        result = client.server_history_totals()
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    data = result.get("job_totals", result) if isinstance(result, dict) else result

    def _human(data: dict) -> None:
        console.print("[bold]Print Totals[/bold]")
        console.print(f"  Total Jobs:     {data.get('total_jobs', 0)}")
        console.print(f"  Total Time:     {format_duration(data.get('total_time', 0))}")
        console.print(f"  Total Filament: {data.get('total_filament_used', 0) / 1000:.1f}m")
        console.print(f"  Longest Job:    {format_duration(data.get('longest_job', 0))}")
        console.print(f"  Longest Print:  {format_duration(data.get('longest_print', 0))}")

    output(data, _human)


@history.command("reset-totals")
@click.option("--yes", is_flag=True, help="Skip confirmation.")
@click.pass_context
def reset_totals(ctx: click.Context, yes: bool) -> None:
    """Reset print totals to zero."""
    if not yes:
        click.confirm("Reset all print history totals to zero?", abort=True)
    try:
        client = get_client(ctx)
        result = client.server_history_resettotals()
    except (MoonrakerError, click.Abort, OSError) as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print("Print totals reset.")
