"""Tests for Phase 3 commands: server, system, update, power."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from klipperctl.cli import cli


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.close.return_value = None
    # Server
    client.server_info.return_value = {
        "moonraker_version": "v0.8.0",
        "api_version_string": "1.5.0",
        "klippy_state": "ready",
        "klippy_connected": True,
        "components": ["file_manager", "machine", "history"],
        "failed_components": [],
    }
    client.server_config.return_value = {
        "config": {
            "server": {"host": "0.0.0.0", "port": 7125},
            "file_manager": {"queue_gcode_uploads": True},
        },
    }
    client.server_restart.return_value = "ok"
    client.server_gcodestore.return_value = {
        "gcode_store": [
            {"message": "echo: G28 command", "time": 1700000000.0},
        ],
    }
    client.server_logs_rollover.return_value = "ok"
    client.server_announcements_list.return_value = {
        "entries": [
            {"title": "Update available", "dismissed": False, "description": "New version"},
        ],
    }
    client.server_announcements_dismiss.return_value = "ok"
    # System
    client.machine_systeminfo.return_value = {
        "system_info": {
            "cpu_info": {"model": "ARM Cortex-A72", "cpu_count": 4},
            "distribution": {"name": "Raspberry Pi OS", "version": "11"},
            "memory": {"total": 4000000},
            "network": {},
            "service_state": {
                "klipper": {"active_state": "active", "sub_state": "running"},
                "moonraker": {"active_state": "active", "sub_state": "running"},
            },
        },
    }
    client.machine_procstats.return_value = {
        "cpu_temp": 55.0,
        "system_uptime": 86400.0,
        "system_memory": {"total": 4000000, "used": 2000000},
        "system_cpu_usage": {"cpu": 15.0, "cpu0": 20.0},
        "websocket_connections": 3,
    }
    client.machine_shutdown.return_value = "ok"
    client.machine_reboot.return_value = "ok"
    client.machine_services_restart.return_value = "ok"
    client.machine_services_stop.return_value = "ok"
    client.machine_services_start.return_value = "ok"
    client.machine_peripherals_usb.return_value = [
        {"device_num": 1, "description": "USB Hub", "vendor_id": "1234", "product_id": "5678"},
    ]
    client.machine_peripherals_serial.return_value = [
        {"device_path": "/dev/ttyACM0", "driver_name": "cdc_acm"},
    ]
    client.machine_peripherals_video.return_value = []
    client.machine_peripherals_canbus.return_value = []
    # Update
    client.machine_update_status.return_value = {
        "version_info": {
            "klipper": {
                "version": "v0.12.0",
                "remote_version": "v0.12.1",
                "is_dirty": False,
                "is_valid": True,
            },
            "moonraker": {
                "version": "v0.8.0",
                "remote_version": "v0.8.0",
                "is_dirty": False,
                "is_valid": True,
            },
        },
    }
    client.machine_update_refresh.return_value = "ok"
    client.machine_update_upgrade.return_value = "ok"
    client.machine_update_rollback.return_value = "ok"
    client.machine_update_recover.return_value = "ok"
    # Power
    client.power_devices_list.return_value = {
        "devices": [
            {
                "device": "printer_power",
                "type": "gpio",
                "status": "on",
                "locked_while_printing": True,
            },
        ],
    }
    client.power_device_status.return_value = {
        "device": "printer_power",
        "status": "on",
    }
    client.power_device_set.return_value = {"printer_power": "on"}
    return client


def _invoke(args: list[str], mock_client: MagicMock | None = None) -> object:
    if mock_client is None:
        mock_client = _mock_client()
    runner = CliRunner()
    with patch("klipperctl.client.build_client", return_value=mock_client):
        return runner.invoke(cli, args, catch_exceptions=False)


class TestServerInfo:
    def test_human(self) -> None:
        result = _invoke(["server", "info"])
        assert result.exit_code == 0
        assert "v0.8.0" in result.output

    def test_json(self) -> None:
        result = _invoke(["--json", "server", "info"])
        data = json.loads(result.output)
        assert data["moonraker_version"] == "v0.8.0"


class TestServerConfig:
    def test_human(self) -> None:
        result = _invoke(["server", "config"])
        assert result.exit_code == 0
        assert "host" in result.output


class TestServerRestart:
    def test_restart(self) -> None:
        result = _invoke(["server", "restart"])
        assert result.exit_code == 0


class TestServerLogs:
    def test_human(self) -> None:
        result = _invoke(["server", "logs"])
        assert result.exit_code == 0
        assert "G28" in result.output

    def test_filter_includes(self) -> None:
        mock = _mock_client()
        mock.server_gcodestore.return_value = {
            "gcode_store": [
                {"message": "echo: G28 command", "time": 1700000000.0},
                {"message": "echo: M104 S200", "time": 1700000001.0},
            ],
        }
        result = _invoke(["server", "logs", "--filter", "G28"], mock)
        assert result.exit_code == 0
        assert "G28" in result.output
        assert "M104" not in result.output

    def test_exclude_hides(self) -> None:
        mock = _mock_client()
        mock.server_gcodestore.return_value = {
            "gcode_store": [
                {"message": "echo: G28 command", "time": 1700000000.0},
                {"message": "echo: error occurred", "time": 1700000001.0},
            ],
        }
        result = _invoke(["server", "logs", "--exclude", "error"], mock)
        assert result.exit_code == 0
        assert "G28" in result.output
        assert "error" not in result.output

    def test_exclude_temps(self) -> None:
        mock = _mock_client()
        mock.server_gcodestore.return_value = {
            "gcode_store": [
                {"message": "echo: G28 command", "time": 1700000000.0},
                {"message": "ok T:210.5 /210.0 B:60.1 /60.0", "time": 1700000001.0},
            ],
        }
        result = _invoke(["server", "logs", "--exclude-temps"], mock)
        assert result.exit_code == 0
        assert "G28" in result.output
        assert "210.5" not in result.output

    def test_json_with_filter(self) -> None:
        mock = _mock_client()
        mock.server_gcodestore.return_value = {
            "gcode_store": [
                {"message": "echo: G28 command", "time": 1700000000.0},
                {"message": "ok T:210.5 /210.0 B:60.1 /60.0", "time": 1700000001.0},
            ],
        }
        result = _invoke(["--json", "server", "logs", "--exclude-temps"], mock)
        data = json.loads(result.output)
        assert len(data) == 1
        assert "G28" in data[0]["message"]


class TestServerConsole:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["server", "console", "--help"])
        assert result.exit_code == 0
        assert "Stream console messages" in result.output
        assert "--filter" in result.output
        assert "--exclude" in result.output
        assert "--exclude-temps" in result.output


class TestServerAnnouncements:
    def test_human(self) -> None:
        result = _invoke(["server", "announcements"])
        assert result.exit_code == 0
        assert "Update available" in result.output


class TestSystemInfo:
    def test_human(self) -> None:
        result = _invoke(["system", "info"])
        assert result.exit_code == 0
        assert "ARM Cortex-A72" in result.output

    def test_json(self) -> None:
        result = _invoke(["--json", "system", "info"])
        data = json.loads(result.output)
        assert "cpu_info" in data


class TestSystemHealth:
    def test_human(self) -> None:
        result = _invoke(["system", "health"])
        assert result.exit_code == 0
        assert "55.0" in result.output


class TestSystemServices:
    def test_human(self) -> None:
        result = _invoke(["system", "services"])
        assert result.exit_code == 0
        assert "klipper" in result.output


class TestSystemServiceRestart:
    def test_restart(self) -> None:
        mock = _mock_client()
        result = _invoke(["system", "service", "restart", "klipper"], mock)
        assert result.exit_code == 0
        mock.machine_services_restart.assert_called_once_with("klipper")


class TestSystemShutdown:
    def test_with_yes(self) -> None:
        result = _invoke(["system", "shutdown", "--yes"])
        assert result.exit_code == 0


class TestSystemPeripherals:
    def test_usb(self) -> None:
        result = _invoke(["system", "peripherals", "--type", "usb"])
        assert result.exit_code == 0
        assert "USB Hub" in result.output


class TestUpdateStatus:
    def test_human(self) -> None:
        result = _invoke(["update", "status"])
        assert result.exit_code == 0
        assert "klipper" in result.output

    def test_json(self) -> None:
        result = _invoke(["--json", "update", "status"])
        data = json.loads(result.output)
        assert "klipper" in data


class TestUpdateUpgrade:
    def test_upgrade(self) -> None:
        result = _invoke(["update", "upgrade"])
        assert result.exit_code == 0


class TestUpdateRollback:
    def test_rollback_passes_name(self) -> None:
        client = _mock_client()
        result = _invoke(["update", "rollback", "klipper"], mock_client=client)
        assert result.exit_code == 0
        client.machine_update_rollback.assert_called_once_with("klipper")

    def test_rollback_json(self) -> None:
        result = _invoke(["--json", "update", "rollback", "moonraker"])
        assert result.exit_code == 0


class TestPowerList:
    def test_human(self) -> None:
        result = _invoke(["power", "list"])
        assert result.exit_code == 0
        assert "printer_power" in result.output

    def test_json(self) -> None:
        result = _invoke(["--json", "power", "list"])
        data = json.loads(result.output)
        assert len(data) == 1


class TestPowerOnOff:
    def test_on_with_yes(self) -> None:
        mock = _mock_client()
        result = _invoke(["power", "on", "printer_power", "--yes"], mock)
        assert result.exit_code == 0
        mock.power_device_set.assert_called_once_with("printer_power", "on")

    def test_off_with_yes(self) -> None:
        mock = _mock_client()
        result = _invoke(["power", "off", "printer_power", "--yes"], mock)
        assert result.exit_code == 0
        mock.power_device_set.assert_called_once_with("printer_power", "off")

    def test_on_requires_confirmation(self) -> None:
        mock = _mock_client()
        result = _invoke(["power", "on", "printer_power"], mock)
        assert result.exit_code != 0
        mock.power_device_set.assert_not_called()

    def test_off_requires_confirmation(self) -> None:
        mock = _mock_client()
        result = _invoke(["power", "off", "printer_power"], mock)
        assert result.exit_code != 0
        mock.power_device_set.assert_not_called()
