"""Tests for configuration management."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from klipperctl.config import (
    get_printer_api_key,
    get_printer_url,
    load_config,
    save_config,
)


class TestLoadConfig:
    def test_returns_empty_when_no_file(self, tmp_path: Path, monkeypatch: object) -> None:
        import klipperctl.config as cfg

        monkeypatch.setattr(cfg, "_config_path", lambda: tmp_path / "nonexistent" / "config.toml")  # type: ignore[attr-defined]
        assert load_config() == {}

    def test_loads_valid_toml(self, tmp_path: Path, monkeypatch: object) -> None:
        import klipperctl.config as cfg

        config_file = tmp_path / "config.toml"
        config_file.write_text('default_printer = "myprinter"\n')
        monkeypatch.setattr(cfg, "_config_path", lambda: config_file)  # type: ignore[attr-defined]
        result = load_config()
        assert result["default_printer"] == "myprinter"


class TestSaveConfig:
    def test_creates_directory_and_file(self, tmp_path: Path, monkeypatch: object) -> None:
        import klipperctl.config as cfg

        config_file = tmp_path / "subdir" / "config.toml"
        monkeypatch.setattr(cfg, "_config_path", lambda: config_file)  # type: ignore[attr-defined]
        save_config({"default_printer": "test", "timeout": 30})
        assert config_file.exists()
        content = config_file.read_text()
        assert 'default_printer = "test"' in content
        assert "timeout = 30" in content

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Unix permissions not available on Windows"
    )
    def test_sets_restrictive_permissions(self, tmp_path: Path, monkeypatch: object) -> None:
        import klipperctl.config as cfg

        config_file = tmp_path / "secdir" / "config.toml"
        monkeypatch.setattr(cfg, "_config_path", lambda: config_file)  # type: ignore[attr-defined]
        save_config({"default_printer": "test"})
        file_mode = stat.S_IMODE(os.stat(config_file).st_mode)
        dir_mode = stat.S_IMODE(os.stat(config_file.parent).st_mode)
        assert file_mode == 0o600, f"Expected 0o600, got {oct(file_mode)}"
        assert dir_mode == 0o700, f"Expected 0o700, got {oct(dir_mode)}"

    def test_roundtrip(self, tmp_path: Path, monkeypatch: object) -> None:
        import klipperctl.config as cfg

        config_file = tmp_path / "config.toml"
        monkeypatch.setattr(cfg, "_config_path", lambda: config_file)  # type: ignore[attr-defined]
        original = {
            "default_printer": "voron",
            "printers": {
                "voron": {
                    "url": "http://voron.local:7125",
                    "api_key": "abc123",
                },
            },
        }
        save_config(original)
        loaded = load_config()
        assert loaded["default_printer"] == "voron"
        assert loaded["printers"]["voron"]["url"] == "http://voron.local:7125"


class TestGetPrinterUrl:
    def test_returns_url_from_config(self) -> None:
        config = {
            "default_printer": "myprinter",
            "printers": {"myprinter": {"url": "http://printer:7125"}},
        }
        assert get_printer_url(config) == "http://printer:7125"

    def test_returns_none_when_no_default(self) -> None:
        assert get_printer_url({}) is None

    def test_returns_none_when_printer_missing(self) -> None:
        config = {"default_printer": "missing"}
        assert get_printer_url(config) is None


class TestConfigEdgeCases:
    def test_xdg_config_home(self, tmp_path: Path, monkeypatch: object) -> None:
        import klipperctl.config as cfg

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        config_file = tmp_path / "klipperctl" / "config.toml"
        monkeypatch.setattr(cfg, "_config_path", lambda: config_file)  # type: ignore[attr-defined]
        save_config({"default_printer": "test"})
        assert config_file.exists()
        loaded = load_config()
        assert loaded["default_printer"] == "test"

    def test_config_dir_respects_platform(self, monkeypatch: object) -> None:
        from klipperctl.config import _config_dir

        # XDG override should work on any platform
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        assert _config_dir() == Path("/custom/config/klipperctl")

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_config_dir_windows_appdata(self, monkeypatch: object) -> None:
        from klipperctl.config import _config_dir

        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("APPDATA", r"C:\Users\test\AppData\Roaming")
        result = _config_dir()
        assert "klipperctl" in str(result)
        assert "AppData" in str(result)

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only test")
    def test_config_dir_macos(self, monkeypatch: object) -> None:
        from klipperctl.config import _config_dir

        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        result = _config_dir()
        assert "Library" in str(result)
        assert "Application Support" in str(result)

    def test_empty_config_file(self, tmp_path: Path, monkeypatch: object) -> None:
        import klipperctl.config as cfg

        config_file = tmp_path / "config.toml"
        config_file.write_text("")
        monkeypatch.setattr(cfg, "_config_path", lambda: config_file)  # type: ignore[attr-defined]
        result = load_config()
        assert result == {}


class TestGetPrinterApiKey:
    def test_returns_key(self) -> None:
        config = {
            "default_printer": "p1",
            "printers": {"p1": {"api_key": "secret"}},
        }
        assert get_printer_api_key(config) == "secret"

    def test_returns_none_when_no_key(self) -> None:
        config = {
            "default_printer": "p1",
            "printers": {"p1": {"url": "http://x"}},
        }
        assert get_printer_api_key(config) is None
