"""Auth command group - authentication management."""

from __future__ import annotations

import click

from klipperctl.cli import _handle_error
from klipperctl.client import get_client
from klipperctl.output import (
    console,
    is_json_mode,
    output,
    output_json,
)


@click.group()
def auth() -> None:
    """Authentication management."""


@auth.command()
@click.option("--username", prompt=True, help="Username.")
@click.option("--password", prompt=True, hide_input=True, help="Password.")
@click.pass_context
def login(ctx: click.Context, username: str, password: str) -> None:
    """Login to the Moonraker server."""
    try:
        client = get_client(ctx)
        result = client.access_login(username, password)
    except Exception as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json(result)
    else:
        console.print(f"Logged in as {username}.")
        token = result.get("token") if isinstance(result, dict) else None
        if token:
            console.print(f"[dim]Token: {token[:20]}...[/dim]")


@auth.command()
@click.pass_context
def logout(ctx: click.Context) -> None:
    """Logout from the Moonraker server."""
    try:
        client = get_client(ctx)
        client.access_logout()
    except Exception as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json({"result": "ok"})
    else:
        console.print("Logged out.")


@auth.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Show authorization module info."""
    try:
        client = get_client(ctx)
        data = client.access_info()
    except Exception as e:
        _handle_error(ctx, e)

    def _human(data: dict) -> None:
        for key, value in data.items():
            console.print(f"  {key}: {value}")

    output(data, _human)


@auth.command()
@click.pass_context
def whoami(ctx: click.Context) -> None:
    """Show current user."""
    try:
        client = get_client(ctx)
        data = client.access_user()
    except Exception as e:
        _handle_error(ctx, e)

    def _human(data: dict) -> None:
        console.print(f"  Username:  {data.get('username', '?')}")
        console.print(f"  Source:    {data.get('source', '?')}")
        created = data.get("created_on")
        if created:
            from klipperctl.output import format_timestamp

            console.print(f"  Created:   {format_timestamp(created)}")

    output(data, _human)


@auth.command("api-key")
@click.pass_context
def api_key(ctx: click.Context) -> None:
    """Show the current API key."""
    try:
        client = get_client(ctx)
        result = client.access_apikey()
    except Exception as e:
        _handle_error(ctx, e)

    if is_json_mode():
        output_json({"api_key": result})
    else:
        console.print(result)
