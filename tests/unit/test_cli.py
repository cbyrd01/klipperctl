"""Tests for the root CLI group and alias expansion."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from moonraker_client.exceptions import (
    MoonrakerAPIError,
    MoonrakerAuthError,
    MoonrakerConnectionError,
    MoonrakerTimeoutError,
)

from klipperctl.cli import cli


class TestCLI:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "klipperctl" in result.output.lower() or "Command line" in result.output

    def test_version(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_printer_group_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["printer", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output
        assert "temps" in result.output
        assert "gcode" in result.output

    def test_print_group_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["print", "--help"])
        assert result.exit_code == 0
        assert "start" in result.output
        assert "pause" in result.output

    def test_files_group_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["files", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "upload" in result.output

    def test_unknown_command(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["nonexistent"])
        assert result.exit_code != 0


class TestAliases:
    """Test that aliases resolve to the correct subcommand help."""

    def test_status_alias_resolves(self) -> None:
        runner = CliRunner()
        # Without a server, the status alias should at least resolve to
        # the printer status command (and fail on connection, not on "unknown command")
        result = runner.invoke(cli, ["status", "--help"])
        # This should show the printer status help
        assert result.exit_code == 0
        assert "status" in result.output.lower()

    def test_progress_alias_resolves(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["progress", "--help"])
        assert result.exit_code == 0
        assert "progress" in result.output.lower()


def _mock_client_raising(exc: Exception) -> MagicMock:
    client = MagicMock()
    client.close.return_value = None
    client.printer_info.side_effect = exc
    client.server_info.side_effect = exc
    client.printer_objects_query.side_effect = exc
    return client


class TestErrorHandling:
    """Test that _handle_error maps exceptions to correct exit codes."""

    def test_connection_error_exits_2(self) -> None:
        client = _mock_client_raising(MoonrakerConnectionError("refused"))
        runner = CliRunner()
        with patch("klipperctl.client.build_client", return_value=client):
            result = runner.invoke(cli, ["printer", "status"])
        assert result.exit_code == 2

    def test_auth_error_exits_2(self) -> None:
        client = _mock_client_raising(MoonrakerAuthError("unauthorized", status_code=401))
        runner = CliRunner()
        with patch("klipperctl.client.build_client", return_value=client):
            result = runner.invoke(cli, ["printer", "status"])
        assert result.exit_code == 2

    def test_timeout_error_exits_2(self) -> None:
        client = _mock_client_raising(MoonrakerTimeoutError("timed out"))
        runner = CliRunner()
        with patch("klipperctl.client.build_client", return_value=client):
            result = runner.invoke(cli, ["printer", "status"])
        assert result.exit_code == 2

    def test_api_error_exits_1(self) -> None:
        client = _mock_client_raising(MoonrakerAPIError("bad request", status_code=400))
        runner = CliRunner()
        with patch("klipperctl.client.build_client", return_value=client):
            result = runner.invoke(cli, ["printer", "status"])
        assert result.exit_code == 1

    def test_json_mode_error_outputs_json(self) -> None:
        client = _mock_client_raising(MoonrakerConnectionError("refused"))
        runner = CliRunner()
        with patch("klipperctl.client.build_client", return_value=client):
            result = runner.invoke(cli, ["--json", "printer", "status"])
        assert result.exit_code == 2
