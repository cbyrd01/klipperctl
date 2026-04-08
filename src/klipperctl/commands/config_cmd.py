"""Config command group - local CLI configuration management."""

from __future__ import annotations

import click

from klipperctl.config import load_config, save_config
from klipperctl.output import (
    console,
    is_json_mode,
    make_table,
    output,
    output_json,
    print_table,
)


@click.group("config")
def config_cmd() -> None:
    """Local CLI configuration."""


@config_cmd.command()
def show() -> None:
    """Show current configuration."""
    config = load_config()

    def _human(config: dict) -> None:
        if not config:
            console.print(
                "No configuration found. Use 'klipperctl config add-printer' to get started."
            )
            return
        if "default_printer" in config:
            console.print(f"  Default printer: {config['default_printer']}")
        printers = config.get("printers", {})
        if printers:
            console.print()
            table = make_table("Name", "URL", "API Key", "Default")
            default = config.get("default_printer", "")
            for name, printer in printers.items():
                is_default = "yes" if name == default else ""
                key = printer.get("api_key", "")
                masked = f"{key[:4]}..." if key else ""
                table.add_row(name, printer.get("url", ""), masked, is_default)
            print_table(table)

    output(config, _human)


@config_cmd.command()
@click.argument("key")
@click.argument("value")
def set(key: str, value: str) -> None:
    """Set a configuration value."""
    config = load_config()
    config[key] = value
    save_config(config)

    if is_json_mode():
        output_json({"key": key, "value": value})
    else:
        console.print(f"Set {key} = {value}")


@config_cmd.command()
def printers() -> None:
    """List configured printers."""
    config = load_config()
    printer_list = config.get("printers", {})

    def _human(printers: dict) -> None:
        if not printers:
            console.print("No printers configured.")
            return
        default = config.get("default_printer", "")
        table = make_table("Name", "URL", "Default")
        for name, printer in printers.items():
            is_default = "[green]* active[/green]" if name == default else ""
            table.add_row(name, printer.get("url", ""), is_default)
        print_table(table)

    output(printer_list, _human)


@config_cmd.command("add-printer")
@click.argument("name")
@click.argument("url")
@click.option("--api-key", help="API key for this printer.")
@click.option("--default", "set_default", is_flag=True, help="Set as default printer.")
def add_printer(name: str, url: str, api_key: str | None, set_default: bool) -> None:
    """Add a printer profile."""
    config = load_config()
    printers = config.setdefault("printers", {})
    printers[name] = {"url": url}
    if api_key:
        printers[name]["api_key"] = api_key
    if set_default or not config.get("default_printer"):
        config["default_printer"] = name
    save_config(config)

    if is_json_mode():
        output_json({"name": name, "url": url, "default": set_default})
    else:
        console.print(f"Added printer '{name}' at {url}")
        if set_default or not config.get("default_printer"):
            console.print("Set as default printer.")


@config_cmd.command("remove-printer")
@click.argument("name")
def remove_printer(name: str) -> None:
    """Remove a printer profile."""
    config = load_config()
    printers = config.get("printers", {})
    if name not in printers:
        raise click.UsageError(f"Printer '{name}' not found.")
    del printers[name]
    if config.get("default_printer") == name:
        config["default_printer"] = next(iter(printers), "")
    save_config(config)

    if is_json_mode():
        output_json({"removed": name})
    else:
        console.print(f"Removed printer '{name}'.")


@config_cmd.command()
@click.argument("name")
def use(name: str) -> None:
    """Switch active printer."""
    config = load_config()
    printers = config.get("printers", {})
    if name not in printers:
        raise click.UsageError(
            f"Printer '{name}' not found. Available: {', '.join(printers.keys())}"
        )
    config["default_printer"] = name
    save_config(config)

    if is_json_mode():
        output_json({"active_printer": name})
    else:
        url = printers[name].get("url", "")
        console.print(f"Switched to '{name}' ({url})")
