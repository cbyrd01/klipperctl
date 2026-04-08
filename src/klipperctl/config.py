"""Configuration management for klipperctl.

Reads and writes ~/.config/klipperctl/config.toml for persistent settings
like printer profiles.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import tomllib


def _config_dir() -> Path:
    """Get the configuration directory, respecting XDG_CONFIG_HOME."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "klipperctl"
    return Path.home() / ".config" / "klipperctl"


def _config_path() -> Path:
    return _config_dir() / "config.toml"


def load_config() -> dict[str, Any]:
    """Load configuration from disk. Returns empty dict if no config exists."""
    path = _config_path()
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to disk in TOML format.

    Sets restrictive permissions (0o600) since config may contain API keys.
    """
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    with open(path, "w") as f:
        _write_toml(f, config)
    os.chmod(path, 0o600)


def _write_toml(f: Any, data: dict[str, Any], prefix: str = "") -> None:
    """Write a dict as TOML. Handles simple values and nested tables."""
    tables = {}
    for key, value in data.items():
        if isinstance(value, dict):
            tables[key] = value
        else:
            f.write(f"{key} = {_toml_value(value)}\n")
    for key, value in tables.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        f.write(f"\n[{full_key}]\n")
        _write_toml(f, value, full_key)


def _toml_value(value: Any) -> str:
    """Convert a Python value to a TOML value string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        items = ", ".join(_toml_value(v) for v in value)
        return f"[{items}]"
    return f'"{value}"'


def get_printer_url(config: dict[str, Any]) -> str | None:
    """Get the default printer URL from config."""
    default_name = config.get("default_printer")
    if not default_name:
        return None
    printers = config.get("printers", {})
    printer = printers.get(default_name, {})
    return printer.get("url")


def get_printer_api_key(config: dict[str, Any]) -> str | None:
    """Get the default printer API key from config."""
    default_name = config.get("default_printer")
    if not default_name:
        return None
    printers = config.get("printers", {})
    printer = printers.get(default_name, {})
    return printer.get("api_key")
