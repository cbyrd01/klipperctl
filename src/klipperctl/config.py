"""Configuration management for klipperctl.

Reads and writes a config.toml for persistent settings like printer profiles.

Config location by platform:
  - Linux:   $XDG_CONFIG_HOME/klipperctl/ or ~/.config/klipperctl/
  - macOS:   ~/Library/Application Support/klipperctl/
  - Windows: %APPDATA%/klipperctl/
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import IO, Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def _config_dir() -> Path:
    """Get the platform-appropriate configuration directory."""
    # Respect explicit XDG override on any platform
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "klipperctl"

    if sys.platform == "win32":
        # Windows: %APPDATA%\klipperctl
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "klipperctl"
        return Path.home() / "AppData" / "Roaming" / "klipperctl"

    if sys.platform == "darwin":
        # macOS: ~/Library/Application Support/klipperctl
        return Path.home() / "Library" / "Application Support" / "klipperctl"

    # Linux and other Unix: ~/.config/klipperctl
    return Path.home() / ".config" / "klipperctl"


def _config_path() -> Path:
    return _config_dir() / "config.toml"


def load_config() -> dict[str, Any]:
    """Load configuration from disk. Returns empty dict if no config exists."""
    path = _config_path()
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        result: dict[str, Any] = tomllib.load(f)
        return result


def _set_restrictive_permissions(path: Path) -> None:
    """Set restrictive file/dir permissions where supported (Unix only).

    On Windows, file permissions are managed by ACLs and os.chmod only
    affects the read-only flag, so we skip it.
    """
    if sys.platform == "win32":
        return
    if path.is_dir():
        os.chmod(path, 0o700)
    else:
        os.chmod(path, 0o600)


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to disk in TOML format.

    On Unix, sets restrictive permissions (0o600) since config may contain API keys.
    """
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _set_restrictive_permissions(path.parent)
    with open(path, "w") as f:
        _write_toml(f, config)
    _set_restrictive_permissions(path)


def _write_toml(f: IO[str], data: dict[str, Any], prefix: str = "") -> None:
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
    url: str | None = printer.get("url")
    return url


def get_printer_api_key(config: dict[str, Any]) -> str | None:
    """Get the default printer API key from config."""
    default_name = config.get("default_printer")
    if not default_name:
        return None
    printers = config.get("printers", {})
    printer = printers.get(default_name, {})
    key: str | None = printer.get("api_key")
    return key
