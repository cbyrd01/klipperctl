"""Tests for the TUI CLI command entry point."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from klipperctl.cli import cli


class TestTuiCommand:
    def test_tui_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["tui", "--help"])
        assert result.exit_code == 0
        assert "Launch the interactive terminal dashboard" in result.output

    def test_tui_listed_in_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "tui" in result.output

    def test_tui_missing_textual(self) -> None:
        runner = CliRunner()
        with patch.dict(
            sys.modules,
            {"klipperctl.tui": None, "klipperctl.tui.app": None},
        ):
            result = runner.invoke(cli, ["tui"])
            assert result.exit_code != 0

    def test_tui_printer_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["tui", "--help"])
        assert "--printer" in result.output

    def test_tui_resolves_config_printer(self) -> None:
        pytest.importorskip("textual")
        runner = CliRunner()
        mock_config = {
            "default_printer": "myprinter",
            "printers": {
                "myprinter": {
                    "url": "http://configured:7125",
                    "api_key": "configured-key",
                },
            },
        }
        with patch("klipperctl.commands.tui_cmd.load_config", return_value=mock_config), patch(
            "klipperctl.tui.app.KlipperApp"
        ) as mock_app_cls:
            mock_app = MagicMock()
            mock_app_cls.return_value = mock_app
            runner.invoke(cli, ["tui", "--printer", "myprinter"])
            mock_app_cls.assert_called_once_with(
                printer_url="http://configured:7125",
                api_key="configured-key",
                timeout=30.0,
            )
            mock_app.run.assert_called_once()

    def test_tui_uses_global_url(self) -> None:
        pytest.importorskip("textual")
        runner = CliRunner()
        with patch("klipperctl.commands.tui_cmd.load_config", return_value={}), patch(
            "klipperctl.tui.app.KlipperApp"
        ) as mock_app_cls:
            mock_app = MagicMock()
            mock_app_cls.return_value = mock_app
            runner.invoke(cli, ["--url", "http://flag:7125", "tui"])
            mock_app_cls.assert_called_once()
            call_kwargs = mock_app_cls.call_args[1]
            assert call_kwargs["printer_url"] == "http://flag:7125"

    def test_tui_uses_env_url(self) -> None:
        pytest.importorskip("textual")
        runner = CliRunner()
        with patch("klipperctl.commands.tui_cmd.load_config", return_value={}), patch(
            "klipperctl.tui.app.KlipperApp"
        ) as mock_app_cls, patch.dict("os.environ", {"MOONRAKER_URL": "http://env:7125"}):
            mock_app = MagicMock()
            mock_app_cls.return_value = mock_app
            runner.invoke(cli, ["tui"])
            call_kwargs = mock_app_cls.call_args[1]
            assert call_kwargs["printer_url"] == "http://env:7125"

    def test_tui_default_url(self) -> None:
        pytest.importorskip("textual")
        runner = CliRunner()
        env = os.environ.copy()
        env.pop("MOONRAKER_URL", None)
        env.pop("MOONRAKER_API_KEY", None)
        with patch("klipperctl.commands.tui_cmd.load_config", return_value={}), patch(
            "klipperctl.tui.app.KlipperApp"
        ) as mock_app_cls, patch.dict("os.environ", env, clear=True):
            mock_app = MagicMock()
            mock_app_cls.return_value = mock_app
            runner.invoke(cli, ["tui"])
            call_kwargs = mock_app_cls.call_args[1]
            assert call_kwargs["printer_url"] == "http://localhost:7125"
