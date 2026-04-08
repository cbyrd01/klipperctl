"""Tests for Phase 2 commands: files (remaining), history, queue."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from klipperctl.cli import cli


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.close.return_value = None
    # Files
    client.files_download.return_value = b"G28\nG1 X10\n"
    client.files_delete.return_value = {"item": {"path": "test.gcode"}}
    client.files_move.return_value = {"item": {"path": "dest.gcode"}}
    client.files_copy.return_value = {"item": {"path": "copy.gcode"}}
    client.files_create_directory.return_value = {"item": {"path": "gcodes/subdir"}}
    client.files_delete_directory.return_value = {"item": {"path": "gcodes/subdir"}}
    client.files_thumbnails.return_value = [
        {"width": 300, "height": 300, "size": 5000, "thumbnail_type": "PNG"},
    ]
    client.files_metascan.return_value = {"filename": "test.gcode"}
    # History
    client.server_history_list.return_value = {
        "jobs": [
            {
                "filename": "benchy.gcode",
                "status": "completed",
                "print_duration": 7200,
                "filament_used": 5000,
                "start_time": 1700000000.0,
            },
        ],
    }
    client.server_history_job.return_value = {
        "job": {
            "filename": "benchy.gcode",
            "status": "completed",
            "print_duration": 7200,
            "total_duration": 7500,
            "filament_used": 5000,
            "start_time": 1700000000.0,
            "end_time": 1700007200.0,
            "metadata": {"slicer": "PrusaSlicer", "estimated_time": 7000},
        },
    }
    client.server_history_totals.return_value = {
        "job_totals": {
            "total_jobs": 42,
            "total_time": 360000,
            "total_filament_used": 500000,
            "longest_job": 14400,
            "longest_print": 14000,
        },
    }
    client.server_history_resettotals.return_value = "ok"
    # Queue
    client.server_jobqueue_status.return_value = {
        "queue_state": "ready",
        "queued_jobs": [
            {"job_id": "abc123", "filename": "part1.gcode", "time_added": 1700000000.0},
        ],
    }
    client.server_jobqueue_job.return_value = {"queued_jobs": []}
    client.server_jobqueue_start.return_value = "ok"
    client.server_jobqueue_pause.return_value = "ok"
    client.server_jobqueue_jump.return_value = "ok"
    client.server_jobqueue_delete.return_value = "ok"
    return client


def _invoke(args: list[str], mock_client: MagicMock | None = None) -> object:
    if mock_client is None:
        mock_client = _mock_client()
    runner = CliRunner()
    with patch("klipperctl.client.build_client", return_value=mock_client):
        return runner.invoke(cli, args, catch_exceptions=False)


class TestFilesDownload:
    def test_to_file(self, tmp_path: object) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as f:
            outpath = f.name
        result = _invoke(["files", "download", "test.gcode", "--output", outpath])
        assert result.exit_code == 0

    def test_json_mode(self) -> None:
        result = _invoke(["--json", "files", "download", "test.gcode"])
        data = json.loads(result.output)
        assert data["filename"] == "test.gcode"

    def test_rejects_path_traversal_in_filename(self) -> None:
        result = _invoke(["files", "download", "../../../etc/passwd"])
        assert result.exit_code != 0

    def test_rejects_output_path_traversal(self) -> None:
        result = _invoke(["files", "download", "test.gcode", "--output", "../../../evil.gcode"])
        assert result.exit_code != 0


class TestFilesDelete:
    def test_with_yes(self) -> None:
        result = _invoke(["files", "delete", "test.gcode", "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.output


class TestFilesMove:
    def test_move(self) -> None:
        result = _invoke(["files", "move", "a.gcode", "b.gcode"])
        assert result.exit_code == 0
        assert "Moved" in result.output


class TestFilesCopy:
    def test_copy(self) -> None:
        result = _invoke(["files", "copy", "a.gcode", "b.gcode"])
        assert result.exit_code == 0
        assert "Copied" in result.output


class TestFilesMkdir:
    def test_mkdir(self) -> None:
        result = _invoke(["files", "mkdir", "gcodes/subdir"])
        assert result.exit_code == 0
        assert "Created" in result.output


class TestFilesRmdir:
    def test_with_yes(self) -> None:
        result = _invoke(["files", "rmdir", "gcodes/subdir", "--yes"])
        assert result.exit_code == 0


class TestFilesThumbnails:
    def test_human(self) -> None:
        result = _invoke(["files", "thumbnails", "test.gcode"])
        assert result.exit_code == 0
        assert "300" in result.output

    def test_json(self) -> None:
        result = _invoke(["--json", "files", "thumbnails", "test.gcode"])
        data = json.loads(result.output)
        assert data[0]["width"] == 300


class TestFilesScan:
    def test_scan(self) -> None:
        result = _invoke(["files", "scan", "test.gcode"])
        assert result.exit_code == 0


class TestHistoryList:
    def test_human(self) -> None:
        result = _invoke(["history", "list"])
        assert result.exit_code == 0
        assert "benchy.gcode" in result.output

    def test_json(self) -> None:
        result = _invoke(["--json", "history", "list"])
        data = json.loads(result.output)
        assert len(data) == 1


class TestHistoryShow:
    def test_human(self) -> None:
        result = _invoke(["history", "show", "abc123"])
        assert result.exit_code == 0
        assert "benchy.gcode" in result.output
        assert "PrusaSlicer" in result.output


class TestHistoryTotals:
    def test_human(self) -> None:
        result = _invoke(["history", "totals"])
        assert result.exit_code == 0
        assert "42" in result.output

    def test_json(self) -> None:
        result = _invoke(["--json", "history", "totals"])
        data = json.loads(result.output)
        assert data["total_jobs"] == 42


class TestHistoryResetTotals:
    def test_with_yes(self) -> None:
        result = _invoke(["history", "reset-totals", "--yes"])
        assert result.exit_code == 0


class TestQueueStatus:
    def test_human(self) -> None:
        result = _invoke(["queue", "status"])
        assert result.exit_code == 0
        assert "ready" in result.output
        assert "part1.gcode" in result.output

    def test_json(self) -> None:
        result = _invoke(["--json", "queue", "status"])
        data = json.loads(result.output)
        assert data["queue_state"] == "ready"


class TestQueueAdd:
    def test_add(self) -> None:
        mock = _mock_client()
        result = _invoke(["queue", "add", "a.gcode", "b.gcode"], mock)
        assert result.exit_code == 0
        mock.server_jobqueue_job.assert_called_once()


class TestQueueStartPause:
    def test_start(self) -> None:
        result = _invoke(["queue", "start"])
        assert result.exit_code == 0

    def test_pause(self) -> None:
        result = _invoke(["queue", "pause"])
        assert result.exit_code == 0


class TestQueueJump:
    def test_jump(self) -> None:
        result = _invoke(["queue", "jump", "abc123"])
        assert result.exit_code == 0


class TestQueueRemove:
    def test_remove(self) -> None:
        mock = _mock_client()
        result = _invoke(["queue", "remove", "abc123"], mock)
        assert result.exit_code == 0
        mock.server_jobqueue_delete.assert_called_once()
