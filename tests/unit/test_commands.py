"""Tests for CLI commands with mocked MoonrakerClient."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from klipperctl.cli import cli


def _mock_client(**overrides: object) -> MagicMock:
    """Create a mock MoonrakerClient with sensible defaults."""
    client = MagicMock()
    client.printer_info.return_value = {
        "state": "ready",
        "state_message": "",
        "hostname": "testhost",
        "software_version": "v0.12.0",
        "klipper_path": "/home/pi/klipper",
    }
    client.server_info.return_value = {
        "klippy_connected": True,
        "klippy_state": "ready",
        "moonraker_version": "v0.8.0",
    }
    client.printer_objects_query.return_value = {
        "status": {
            "extruder": {"temperature": 200.0, "target": 200.0, "power": 0.5},
            "heater_bed": {"temperature": 60.0, "target": 60.0, "power": 0.3},
            "print_stats": {
                "filename": "test.gcode",
                "state": "printing",
                "print_duration": 3600.0,
                "message": "",
            },
            "virtual_sdcard": {"progress": 0.45},
        }
    }
    client.printer_objects_list.return_value = {"objects": ["extruder", "heater_bed", "toolhead"]}
    client.gcode_help.return_value = {"G28": "Home all axes", "M104": "Set hotend temperature"}
    client.query_endstops.return_value = {"x": "open", "y": "open", "z": "TRIGGERED"}
    client.files_list.return_value = [
        {"path": "test.gcode", "size": 1024, "modified": 1700000000.0},
        {"path": "benchy.gcode", "size": 2048, "modified": 1700000100.0},
    ]
    client.files_metadata.return_value = {
        "filename": "test.gcode",
        "size": 1024,
        "modified": 1700000000.0,
        "slicer": "PrusaSlicer",
        "estimated_time": 3600,
        "filament_total": 5000.0,
    }
    client.files_upload.return_value = {"item": {"path": "test.gcode"}}
    client.gcode_script.return_value = "ok"
    client.print_start.return_value = "ok"
    client.print_pause.return_value = "ok"
    client.print_resume.return_value = "ok"
    client.print_cancel.return_value = "ok"
    client.emergency_stop.return_value = "ok"
    client.printer_restart.return_value = "ok"
    client.firmware_restart.return_value = "ok"
    client.close.return_value = None
    for key, value in overrides.items():
        setattr(client, key, value)
    return client


def _invoke(args: list[str], mock_client: MagicMock | None = None) -> object:
    """Invoke the CLI with a mocked client."""
    if mock_client is None:
        mock_client = _mock_client()
    runner = CliRunner()
    with patch("klipperctl.client.build_client", return_value=mock_client):
        return runner.invoke(cli, args, catch_exceptions=False)


class TestPrinterStatus:
    def test_human_output(self) -> None:
        result = _invoke(["printer", "status"])
        assert result.exit_code == 0
        assert "ready" in result.output
        assert "testhost" in result.output
        assert "extruder" in result.output

    def test_json_output(self) -> None:
        result = _invoke(["--json", "printer", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["state"] == "ready"
        assert data["hostname"] == "testhost"
        assert "temperatures" in data


class TestPrinterInfo:
    def test_human_output(self) -> None:
        result = _invoke(["printer", "info"])
        assert result.exit_code == 0
        assert "ready" in result.output

    def test_json_output(self) -> None:
        result = _invoke(["--json", "printer", "info"])
        data = json.loads(result.output)
        assert data["state"] == "ready"


class TestPrinterTemps:
    def test_human_output(self) -> None:
        result = _invoke(["printer", "temps"])
        assert result.exit_code == 0
        assert "extruder" in result.output

    def test_json_output(self) -> None:
        result = _invoke(["--json", "printer", "temps"])
        data = json.loads(result.output)
        assert "extruder" in data


class TestPrinterGcode:
    def test_send_gcode(self) -> None:
        mock = _mock_client()
        result = _invoke(["printer", "gcode", "G28"], mock)
        assert result.exit_code == 0

    def test_json_mode(self) -> None:
        mock = _mock_client()
        result = _invoke(["--json", "printer", "gcode", "G28"], mock)
        data = json.loads(result.output)
        assert data["result"] == "ok"

    def test_no_script_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["printer", "gcode"])
        assert result.exit_code != 0


class TestPrinterGcodeHelp:
    def test_human_output(self) -> None:
        result = _invoke(["printer", "gcode-help"])
        assert result.exit_code == 0
        assert "G28" in result.output

    def test_filter(self) -> None:
        result = _invoke(["printer", "gcode-help", "--filter", "G28"])
        assert result.exit_code == 0
        assert "G28" in result.output

    def test_json_output(self) -> None:
        result = _invoke(["--json", "printer", "gcode-help"])
        data = json.loads(result.output)
        assert "G28" in data


class TestPrinterObjects:
    def test_human_output(self) -> None:
        result = _invoke(["printer", "objects"])
        assert result.exit_code == 0
        assert "extruder" in result.output

    def test_json_output(self) -> None:
        result = _invoke(["--json", "printer", "objects"])
        data = json.loads(result.output)
        assert "extruder" in data


class TestPrinterEndstops:
    def test_human_output(self) -> None:
        result = _invoke(["printer", "endstops"])
        assert result.exit_code == 0
        assert "open" in result.output

    def test_json_output(self) -> None:
        result = _invoke(["--json", "printer", "endstops"])
        data = json.loads(result.output)
        assert data["x"] == "open"


class TestPrinterRestart:
    def test_restart(self) -> None:
        mock = _mock_client()
        result = _invoke(["printer", "restart"], mock)
        assert result.exit_code == 0
        mock.printer_restart.assert_called_once()


class TestPrinterEmergencyStop:
    def test_with_yes_flag(self) -> None:
        mock = _mock_client()
        result = _invoke(["printer", "emergency-stop", "--yes"], mock)
        assert result.exit_code == 0
        mock.emergency_stop.assert_called_once()


class TestPrintStart:
    def test_start_print(self) -> None:
        mock = _mock_client()
        result = _invoke(["print", "start", "test.gcode"], mock)
        assert result.exit_code == 0

    def test_json_output(self) -> None:
        mock = _mock_client()
        result = _invoke(["--json", "print", "start", "test.gcode"], mock)
        data = json.loads(result.output)
        assert data["filename"] == "test.gcode"


class TestPrintPause:
    def test_pause(self) -> None:
        mock = _mock_client()
        result = _invoke(["print", "pause"], mock)
        assert result.exit_code == 0
        mock.print_pause.assert_called_once()


class TestPrintResume:
    def test_resume(self) -> None:
        mock = _mock_client()
        result = _invoke(["print", "resume"], mock)
        assert result.exit_code == 0
        mock.print_resume.assert_called_once()


class TestPrintCancel:
    def test_cancel_with_yes(self) -> None:
        mock = _mock_client()
        result = _invoke(["print", "cancel", "--yes"], mock)
        assert result.exit_code == 0
        mock.print_cancel.assert_called_once()


class TestPrintProgress:
    def test_no_active_print(self) -> None:
        mock = _mock_client()
        mock.printer_objects_query.return_value = {
            "status": {
                "print_stats": {"filename": "", "state": "standby"},
                "virtual_sdcard": {"progress": 0.0},
            }
        }
        result = _invoke(["print", "progress"], mock)
        assert result.exit_code == 0
        assert "No active print" in result.output

    def test_active_print(self) -> None:
        mock = _mock_client()
        result = _invoke(["print", "progress"], mock)
        assert result.exit_code == 0
        assert "test.gcode" in result.output

    def test_json_output(self) -> None:
        mock = _mock_client()
        result = _invoke(["--json", "print", "progress"], mock)
        data = json.loads(result.output)
        assert data["filename"] == "test.gcode"
        assert data["progress_pct"] == 45.0


class TestFilesList:
    def test_human_output(self) -> None:
        result = _invoke(["files", "list"])
        assert result.exit_code == 0
        assert "test.gcode" in result.output

    def test_long_format(self) -> None:
        result = _invoke(["files", "list", "--long"])
        assert result.exit_code == 0
        assert "Modified" in result.output

    def test_json_output(self) -> None:
        result = _invoke(["--json", "files", "list"])
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["path"] == "benchy.gcode"  # sorted by modified desc


class TestFilesInfo:
    def test_human_output(self) -> None:
        result = _invoke(["files", "info", "test.gcode"])
        assert result.exit_code == 0
        assert "PrusaSlicer" in result.output

    def test_json_output(self) -> None:
        result = _invoke(["--json", "files", "info", "test.gcode"])
        data = json.loads(result.output)
        assert data["slicer"] == "PrusaSlicer"
