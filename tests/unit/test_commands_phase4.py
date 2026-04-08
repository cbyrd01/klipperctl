"""Tests for Phase 4 commands: auth, config."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from klipperctl.cli import cli


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.close.return_value = None
    client.access_login.return_value = {"token": "jwt-token-123456789", "username": "testuser"}
    client.access_logout.return_value = "ok"
    client.access_info.return_value = {"default_source": "moonraker", "api_key_enabled": True}
    client.access_user.return_value = {
        "username": "testuser",
        "source": "moonraker",
        "created_on": 1700000000.0,
    }
    client.access_apikey.return_value = "ABCDEF123456"
    return client


def _invoke(args: list[str], mock_client: MagicMock | None = None) -> object:
    if mock_client is None:
        mock_client = _mock_client()
    runner = CliRunner()
    with patch("klipperctl.client.build_client", return_value=mock_client):
        return runner.invoke(cli, args, catch_exceptions=False)


class TestAuthLogin:
    def test_login(self) -> None:
        mock = _mock_client()
        runner = CliRunner()
        with patch("klipperctl.client.build_client", return_value=mock):
            result = runner.invoke(
                cli,
                ["auth", "login", "--username", "test", "--password", "pass"],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert "Logged in" in result.output


class TestAuthLogout:
    def test_logout(self) -> None:
        result = _invoke(["auth", "logout"])
        assert result.exit_code == 0


class TestAuthInfo:
    def test_human(self) -> None:
        result = _invoke(["auth", "info"])
        assert result.exit_code == 0
        assert "moonraker" in result.output


class TestAuthWhoami:
    def test_human(self) -> None:
        result = _invoke(["auth", "whoami"])
        assert result.exit_code == 0
        assert "testuser" in result.output


class TestAuthApiKey:
    def test_human(self) -> None:
        result = _invoke(["auth", "api-key"])
        assert result.exit_code == 0
        assert "ABCDEF123456" in result.output

    def test_json(self) -> None:
        result = _invoke(["--json", "auth", "api-key"])
        data = json.loads(result.output)
        assert data["api_key"] == "ABCDEF123456"


class TestConfigShow:
    def test_empty_config(self, tmp_path: Path, monkeypatch: object) -> None:
        import klipperctl.config as cfg

        monkeypatch.setattr(cfg, "_config_path", lambda: tmp_path / "config.toml")  # type: ignore[attr-defined]
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert "No configuration" in result.output


class TestConfigAddPrinter:
    def test_add(self, tmp_path: Path, monkeypatch: object) -> None:
        import klipperctl.config as cfg

        monkeypatch.setattr(cfg, "_config_path", lambda: tmp_path / "config.toml")  # type: ignore[attr-defined]
        runner = CliRunner()
        result = runner.invoke(
            cli, ["config", "add-printer", "test", "http://test:7125", "--default"]
        )
        assert result.exit_code == 0
        assert "Added printer" in result.output


class TestConfigUse:
    def test_switch(self, tmp_path: Path, monkeypatch: object) -> None:
        import klipperctl.config as cfg

        config_file = tmp_path / "config.toml"
        monkeypatch.setattr(cfg, "_config_path", lambda: config_file)  # type: ignore[attr-defined]
        # First add a printer
        runner = CliRunner()
        runner.invoke(cli, ["config", "add-printer", "p1", "http://p1:7125"])
        runner.invoke(cli, ["config", "add-printer", "p2", "http://p2:7125"])
        result = runner.invoke(cli, ["config", "use", "p2"])
        assert result.exit_code == 0
        assert "p2" in result.output


class TestConfigRemovePrinter:
    def test_remove(self, tmp_path: Path, monkeypatch: object) -> None:
        import klipperctl.config as cfg

        monkeypatch.setattr(cfg, "_config_path", lambda: tmp_path / "config.toml")  # type: ignore[attr-defined]
        runner = CliRunner()
        runner.invoke(cli, ["config", "add-printer", "p1", "http://p1:7125"])
        result = runner.invoke(cli, ["config", "remove-printer", "p1"])
        assert result.exit_code == 0
        assert "Removed" in result.output
