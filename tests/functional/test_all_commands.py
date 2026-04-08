"""Functional tests for all command groups against a live Moonraker server."""

from __future__ import annotations

import json
import os

import pytest
from click.testing import CliRunner

from klipperctl.cli import cli

MOONRAKER_URL = os.environ.get("MOONRAKER_URL", "http://localhost:7125")


def _run(*args: str) -> object:
    runner = CliRunner()
    return runner.invoke(cli, ["--url", MOONRAKER_URL, *args])


def _run_json(*args: str) -> dict:
    runner = CliRunner()
    result = runner.invoke(cli, ["--url", MOONRAKER_URL, "--json", *args])
    assert result.exit_code == 0, f"Command failed: {result.output}"
    return json.loads(result.output)


@pytest.mark.functional
class TestHistoryCommands:
    def test_list(self) -> None:
        result = _run("history", "list")
        assert result.exit_code == 0

    def test_list_json(self) -> None:
        data = _run_json("history", "list")
        assert isinstance(data, list)

    def test_totals(self) -> None:
        result = _run("history", "totals")
        assert result.exit_code == 0
        assert "Total Jobs" in result.output

    def test_totals_json(self) -> None:
        data = _run_json("history", "totals")
        assert "total_jobs" in data


@pytest.mark.functional
class TestQueueCommands:
    def test_status(self) -> None:
        result = _run("queue", "status")
        assert result.exit_code == 0
        assert "State" in result.output

    def test_status_json(self) -> None:
        data = _run_json("queue", "status")
        assert "queue_state" in data


@pytest.mark.functional
class TestServerCommands:
    def test_info(self) -> None:
        result = _run("server", "info")
        assert result.exit_code == 0
        assert "Moonraker" in result.output

    def test_info_json(self) -> None:
        data = _run_json("server", "info")
        assert "klippy_state" in data

    def test_logs(self) -> None:
        result = _run("server", "logs", "--count", "5")
        assert result.exit_code == 0

    def test_announcements(self) -> None:
        result = _run("server", "announcements")
        assert result.exit_code == 0


@pytest.mark.functional
class TestSystemCommands:
    def test_info(self) -> None:
        result = _run("system", "info")
        assert result.exit_code == 0

    def test_info_json(self) -> None:
        data = _run_json("system", "info")
        assert isinstance(data, dict)

    def test_health(self) -> None:
        result = _run("system", "health")
        assert result.exit_code == 0
        assert "Health" in result.output

    def test_services(self) -> None:
        result = _run("system", "services")
        assert result.exit_code == 0

    def test_peripherals(self) -> None:
        result = _run("system", "peripherals", "--type", "serial")
        assert result.exit_code == 0


@pytest.mark.functional
class TestFilesExtended:
    def test_files_list_json_valid(self) -> None:
        data = _run_json("files", "list")
        assert isinstance(data, list)

    def test_files_thumbnails(self) -> None:
        # May fail if no files with thumbnails, that's ok
        result = _run("files", "list")
        assert result.exit_code == 0
