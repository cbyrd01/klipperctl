"""Tests for output formatting utilities."""

from __future__ import annotations

from klipperctl.output import (
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
