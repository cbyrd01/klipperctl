"""Tests for output formatting utilities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from klipperctl.output import (
    _json_default,
    format_bytes,
    format_duration,
    format_percent,
    format_temp,
    format_timestamp,
)


class TestFormatDuration:
    def test_zero(self) -> None:
        assert format_duration(0) == "0s"

    def test_negative(self) -> None:
        assert format_duration(-5) == "0s"

    def test_seconds_only(self) -> None:
        assert format_duration(45) == "45s"

    def test_minutes_and_seconds(self) -> None:
        assert format_duration(65) == "1m 5s"

    def test_hours_minutes_seconds(self) -> None:
        assert format_duration(3661) == "1h 1m 1s"

    def test_days(self) -> None:
        assert format_duration(86461) == "1d 0h 1m"

    def test_fractional(self) -> None:
        assert format_duration(90.7) == "1m 30s"


class TestFormatBytes:
    def test_bytes(self) -> None:
        assert format_bytes(512) == "512 B"

    def test_kilobytes(self) -> None:
        assert format_bytes(1024) == "1.0 KB"

    def test_megabytes(self) -> None:
        assert format_bytes(1048576) == "1.0 MB"

    def test_gigabytes(self) -> None:
        assert format_bytes(1073741824) == "1.0 GB"

    def test_fractional(self) -> None:
        assert format_bytes(1536) == "1.5 KB"

    def test_zero(self) -> None:
        assert format_bytes(0) == "0 B"


class TestFormatTemp:
    def test_normal(self) -> None:
        assert format_temp(200.0) == "200.0\u00b0C"

    def test_fraction(self) -> None:
        assert format_temp(19.85) == "19.9\u00b0C"

    def test_zero(self) -> None:
        assert format_temp(0) == "0.0\u00b0C"


class TestFormatPercent:
    def test_full(self) -> None:
        assert format_percent(1.0) == "100.0%"

    def test_half(self) -> None:
        assert format_percent(0.5) == "50.0%"

    def test_zero(self) -> None:
        assert format_percent(0.0) == "0.0%"

    def test_fractional(self) -> None:
        assert format_percent(0.473) == "47.3%"


class TestFormatTimestamp:
    def test_returns_string(self) -> None:
        result = format_timestamp(1700000000.0)
        assert isinstance(result, str)
        assert "2023" in result


class TestJsonDefault:
    def test_datetime_serializes_to_iso(self) -> None:
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = _json_default(dt)
        assert result == "2024-01-15T12:00:00+00:00"

    def test_path_serializes_to_string(self) -> None:
        p = Path("/tmp/test.gcode")
        result = _json_default(p)
        assert result == "/tmp/test.gcode"

    def test_set_serializes_to_list(self) -> None:
        result = _json_default({1, 2, 3})
        assert sorted(result) == [1, 2, 3]

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(TypeError, match="not JSON serializable"):
            _json_default(object())

    def test_full_json_dumps(self) -> None:
        data = {"time": datetime(2024, 1, 1, tzinfo=timezone.utc), "path": Path("/x")}
        result = json.dumps(data, default=_json_default)
        parsed = json.loads(result)
        assert parsed["time"] == "2024-01-01T00:00:00+00:00"
        assert parsed["path"] == "/x"
