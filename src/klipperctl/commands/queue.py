"""Queue command group - job queue management."""

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
def queue() -> None:
    """Job queue management."""


@queue.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show queue state and pending jobs."""
    try:
        client = get_client(ctx)
        result = client.server_jobqueue_status()
    except Exception as e:
        _handle_error(ctx, e)

    def _human(result: dict) -> None:
        state = result.get("queue_state", "unknown")
        jobs = result.get("queued_jobs", [])
        console.print("[bold]Job Queue[/bold]")
        console.print(f"  State: {state}")
        console.print(f"  Jobs:  {len(jobs)}")
        if jobs:
            console.print()
            table = make_table("ID", "Filename", "Added")
            for job in jobs:
                from klipperctl.output import format_timestamp

                table.add_row(
                    job.get("job_id", "?")[:8],
                    job.get("filename", "?"),
                    format_timestamp(job["time_added"]) if "time_added" in job else "?",
                )
            print_table(table)

    output(result, _human)


@queue.command()
@click.argument("files", nargs=-1, required=True)
@click.option("--reset", is_flag=True, help="Clear queue before adding.")
@click.pass_context
def add(ctx: click.Context, files: tuple[str, ...], reset: bool) -> None:
    """Enqueue one or more files for printing."""
    try:
        client = get_client(ctx)
        result = client.server_jobqueue_job(filenames=list(files), reset=reset)
    except Exception as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print(f"Enqueued {len(files)} job(s).")


@queue.command()
@click.pass_context
def start(ctx: click.Context) -> None:
    """Start processing the queue."""
    try:
        client = get_client(ctx)
        result = client.server_jobqueue_start()
    except Exception as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print("Job queue started.")


@queue.command()
@click.pass_context
def pause(ctx: click.Context) -> None:
    """Pause the queue."""
    try:
        client = get_client(ctx)
        result = client.server_jobqueue_pause()
    except Exception as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print("Job queue paused.")


@queue.command()
@click.argument("job_id")
@click.pass_context
def jump(ctx: click.Context, job_id: str) -> None:
    """Move a job to the front of the queue."""
    try:
        client = get_client(ctx)
        result = client.server_jobqueue_jump(job_id)
    except Exception as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print(f"Job {job_id[:8]} moved to front.")


@queue.command()
@click.argument("job_ids", nargs=-1, required=True)
@click.pass_context
def remove(ctx: click.Context, job_ids: tuple[str, ...]) -> None:
    """Remove job(s) from the queue."""
    try:
        client = get_client(ctx)
        client.server_jobqueue_delete(list(job_ids))
    except Exception as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json({"removed": list(job_ids)})
    else:
        console.print(f"Removed {len(job_ids)} job(s).")
