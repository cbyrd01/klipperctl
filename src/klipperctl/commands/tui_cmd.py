"""TUI command — launch the interactive terminal dashboard."""

from __future__ import annotations

import click

from klipperctl.config import get_printer_api_key, get_printer_url, load_config


@click.command("tui")
@click.option("--printer", help="Printer profile name to connect to.")
@click.pass_context
def tui_cmd(ctx: click.Context, printer: str | None) -> None:
    """Launch the interactive terminal dashboard.

    Requires the 'tui' extra: pip install klipperctl[tui]
    """
    try:
        from klipperctl.tui.app import KlipperApp
    except ImportError:
        click.echo(
            "Error: TUI dependencies not installed. Install with: pip install klipperctl[tui]",
            err=True,
        )
        raise SystemExit(1) from None

    config = load_config()
    root_params = ctx.find_root().params

    # Resolve connection from --printer flag, global options, or config
    if printer:
        printers = config.get("printers", {})
        profile = printers.get(printer, {})
        url = profile.get("url", "http://localhost:7125")
        api_key = profile.get("api_key")
    else:
        import os

        url = (
            root_params.get("url")
            or os.environ.get("MOONRAKER_URL")
            or get_printer_url(config)
            or "http://localhost:7125"
        )
        api_key = (
            root_params.get("api_key")
            or os.environ.get("MOONRAKER_API_KEY")
            or get_printer_api_key(config)
        )

    timeout = root_params.get("timeout", 30.0)

    app = KlipperApp(printer_url=url, api_key=api_key, timeout=timeout)
    app.run()
