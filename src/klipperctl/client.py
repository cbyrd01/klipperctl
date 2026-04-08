"""Client construction for klipperctl.

Builds a MoonrakerClient from CLI flags, environment variables, and config file.
Priority: CLI flags > environment variables > config file > defaults.
"""

from __future__ import annotations

import os

import click
from moonraker_client import MoonrakerClient

from klipperctl.config import get_printer_api_key, get_printer_url, load_config


def build_client(ctx: click.Context) -> MoonrakerClient:
    """Build a MoonrakerClient from the current Click context.

    Resolution order for URL:
        1. --url flag
        2. MOONRAKER_URL env var
        3. Config file default printer
        4. http://localhost:7125

    Resolution order for API key:
        1. --api-key flag
        2. MOONRAKER_API_KEY env var
        3. Config file default printer
    """
    params = ctx.find_root().params
    config = load_config()

    url = (
        params.get("url")
        or os.environ.get("MOONRAKER_URL")
        or get_printer_url(config)
        or "http://localhost:7125"
    )
    api_key = (
        params.get("api_key") or os.environ.get("MOONRAKER_API_KEY") or get_printer_api_key(config)
    )
    timeout = params.get("timeout", 30.0)

    return MoonrakerClient(base_url=url, api_key=api_key, timeout=timeout)


def get_client(ctx: click.Context) -> MoonrakerClient:
    """Get or create the MoonrakerClient stored in the Click context.

    Creates the client on first call and caches it for reuse. Registers
    cleanup to close the client when the context tears down.
    """
    if "client" not in ctx.ensure_object(dict):
        client = build_client(ctx)
        ctx.obj["client"] = client
        ctx.call_on_close(client.close)
    return ctx.obj["client"]
