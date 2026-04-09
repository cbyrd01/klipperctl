"""Functional tests for printer commands against a live Moonraker server."""

from __future__ import annotations

import json
import os

import pytest
from click.testing import CliRunner

from klipperctl.cli import cli

MOONRAKER_URL = os.environ.get("MOONRAKER_URL", "http://localhost:7125")


@pytest.mark.functional
class TestPrinterStatus:
    def test_human_output(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "printer", "status"])
        assert result.exit_code == 0
        assert "State:" in result.output

    def test_json_output(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "--json", "printer", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "state" in data
        assert "temperatures" in data

    def test_status_alias(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "status"])
        assert result.exit_code == 0
        assert "State:" in result.output


@pytest.mark.functional
class TestPrinterInfo:
    def test_shows_info(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "printer", "info"])
        assert result.exit_code == 0
        assert "state" in result.output


@pytest.mark.functional
class TestPrinterTemps:
    def test_human_output(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "printer", "temps"])
        assert result.exit_code == 0
        assert "extruder" in result.output or "Heater" in result.output

    def test_all_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "printer", "temps", "--all"])
        assert result.exit_code == 0

    def test_temps_alias(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "temps"])
        assert result.exit_code == 0

    def test_json_output(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "--json", "printer", "temps"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)


@pytest.mark.functional
class TestPrinterObjects:
    def test_lists_objects(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "printer", "objects"])
        assert result.exit_code == 0
        assert "extruder" in result.output

    def test_json_output(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "--json", "printer", "objects"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert "extruder" in data


@pytest.mark.functional
class TestPrintProgress:
    def test_shows_progress_or_no_print(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "print", "progress"])
        assert result.exit_code == 0
        # Either shows progress or "No active print"
        assert "progress" in result.output.lower() or "No active print" in result.output

    def test_progress_alias(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "progress"])
        assert result.exit_code == 0


@pytest.mark.functional
class TestSetTemp:
    """Tests that set-temp actually changes heater targets."""

    def test_set_hotend_and_verify(self) -> None:
        runner = CliRunner()
        try:
            result = runner.invoke(
                cli, ["--url", MOONRAKER_URL, "printer", "set-temp", "--hotend", "50"]
            )
            assert result.exit_code == 0
            # Verify target was set via JSON temps
            result = runner.invoke(
                cli, ["--url", MOONRAKER_URL, "--json", "printer", "temps"]
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["extruder"]["target"] == pytest.approx(50.0, abs=0.1)
        finally:
            runner.invoke(
                cli, ["--url", MOONRAKER_URL, "printer", "set-temp", "--hotend", "0"]
            )

    def test_set_bed_and_verify(self) -> None:
        runner = CliRunner()
        try:
            result = runner.invoke(
                cli, ["--url", MOONRAKER_URL, "printer", "set-temp", "--bed", "40"]
            )
            assert result.exit_code == 0
            result = runner.invoke(
                cli, ["--url", MOONRAKER_URL, "--json", "printer", "temps"]
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["heater_bed"]["target"] == pytest.approx(40.0, abs=0.1)
        finally:
            runner.invoke(
                cli, ["--url", MOONRAKER_URL, "printer", "set-temp", "--bed", "0"]
            )

    def test_cooldown(self) -> None:
        runner = CliRunner()
        runner.invoke(
            cli, ["--url", MOONRAKER_URL, "printer", "set-temp", "--hotend", "0", "--bed", "0"]
        )
        result = runner.invoke(
            cli, ["--url", MOONRAKER_URL, "--json", "printer", "temps"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["extruder"]["target"] == pytest.approx(0.0, abs=0.1)
        assert data["heater_bed"]["target"] == pytest.approx(0.0, abs=0.1)


@pytest.mark.functional
class TestFilesList:
    def test_human_output(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "files", "list"])
        assert result.exit_code == 0

    def test_json_output_is_valid(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "--json", "files", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_long_format(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--url", MOONRAKER_URL, "files", "list", "--long"])
        assert result.exit_code == 0
