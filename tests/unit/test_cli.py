"""Tests for the root CLI group and alias expansion."""

from __future__ import annotations

from click.testing import CliRunner

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
