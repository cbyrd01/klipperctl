"""Root CLI group for klipperctl.

Defines global options, top-level aliases, and lazy command group loading.
"""

from __future__ import annotations

import importlib
import sys

import click

from klipperctl import __version__
from klipperctl.output import output_error

# Top-level aliases: map shortcut names to (group, command, extra_args)
ALIASES: dict[str, tuple[str, str, list[str]]] = {
    "status": ("printer", "status", []),
    "temps": ("printer", "temps", ["--all"]),
    "progress": ("print", "progress", []),
    "gcode": ("printer", "gcode", []),
}

# Lazy-loaded command groups: name -> (module_path, attribute_name)
COMMAND_GROUPS: dict[str, tuple[str, str]] = {
    "printer": ("klipperctl.commands.printer", "printer"),
    "print": ("klipperctl.commands.print_cmd", "print_cmd"),
    "files": ("klipperctl.commands.files", "files"),
    "history": ("klipperctl.commands.history", "history"),
    "queue": ("klipperctl.commands.queue", "queue"),
    "server": ("klipperctl.commands.server", "server"),
    "system": ("klipperctl.commands.system", "system"),
    "update": ("klipperctl.commands.update", "update"),
    "power": ("klipperctl.commands.power", "power"),
    "auth": ("klipperctl.commands.auth", "auth"),
    "config": ("klipperctl.commands.config_cmd", "config_cmd"),
}


class AliasGroup(click.Group):
    """Click Group with top-level aliases and lazy command loading."""

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        """Expand aliases before resolving the command."""
        if args and args[0] in ALIASES:
            alias = args[0]
            group_name, cmd_name, extra = ALIASES[alias]
            args = [group_name, cmd_name, *extra, *args[1:]]
        return super().resolve_command(ctx, args)

    def list_commands(self, ctx: click.Context) -> list[str]:
        """Return sorted list of all command groups."""
        builtin = super().list_commands(ctx)
        return sorted(set(builtin) | set(COMMAND_GROUPS.keys()))

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """Lazy-load command groups on demand."""
        # Check already-registered commands first
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd
        # Lazy-load from COMMAND_GROUPS
        if cmd_name in COMMAND_GROUPS:
            module_path, attr_name = COMMAND_GROUPS[cmd_name]
            module = importlib.import_module(module_path)
            cmd_obj: click.Command = getattr(module, attr_name)
            return cmd_obj
        return None


def _handle_error(ctx: click.Context, error: Exception) -> None:
    """Map exceptions to exit codes and error messages."""
    from moonraker_client.exceptions import (
        MoonrakerAPIError,
        MoonrakerAuthError,
        MoonrakerConnectionError,
        MoonrakerTimeoutError,
    )

    if isinstance(error, MoonrakerConnectionError):
        url = ctx.find_root().params.get("url", "")
        output_error(
            f"Cannot connect to Moonraker at {url}. "
            "Is the printer on? Set --url or MOONRAKER_URL.",
            code=2,
        )
        sys.exit(2)
    elif isinstance(error, MoonrakerAuthError):
        output_error(
            "Authentication required. Run 'klipperctl auth login' or set --api-key.",
            code=2,
        )
        sys.exit(2)
    elif isinstance(error, MoonrakerTimeoutError):
        output_error("Request timed out. Try increasing --timeout.", code=2)
        sys.exit(2)
    elif isinstance(error, MoonrakerAPIError):
        output_error(str(error), code=1)
        sys.exit(1)
    elif isinstance(error, FileNotFoundError):
        output_error(str(error), code=3)
        sys.exit(3)
    elif isinstance(error, click.Abort):
        sys.exit(130)
    else:
        output_error(f"Unexpected error: {error}", code=1)
        sys.exit(1)


@click.group(cls=AliasGroup)
@click.option("--url", envvar="MOONRAKER_URL", help="Moonraker server URL.")
@click.option("--api-key", envvar="MOONRAKER_API_KEY", help="API key for authentication.")
@click.option("--json", "json_output", is_flag=True, help="Output raw JSON (machine-readable).")
@click.option("--no-color", is_flag=True, help="Disable colored output.")
@click.option(
    "--timeout", type=float, default=30.0, show_default=True, help="Request timeout in seconds."
)
@click.version_option(version=__version__, prog_name="klipperctl")
@click.pass_context
def cli(
    ctx: click.Context,
    url: str | None,
    api_key: str | None,
    json_output: bool,
    no_color: bool,
    timeout: float,
) -> None:
    """Command line interface for 3D printers using Moonraker and Klipper."""
    ctx.ensure_object(dict)
    if no_color:
        from klipperctl.output import console

        console.no_color = True
