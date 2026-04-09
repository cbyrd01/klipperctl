"""Tests for message filtering."""

from __future__ import annotations

from klipperctl.filtering import MessageFilter, build_filter


class TestMessageFilter:
    def test_no_filters_passes_everything(self) -> None:
        f = MessageFilter()
        assert f.matches("anything")
        assert f.matches("")
        assert f.matches("ok T:210.5 /210.0 B:60.1 /60.0")

    def test_include_matches(self) -> None:
        f = build_filter("G28", None, False)
        assert f.matches("echo: G28 command")
        assert not f.matches("echo: M104 command")

    def test_include_case_insensitive(self) -> None:
        f = build_filter("firmware", None, False)
        assert f.matches("FIRMWARE_RESTART")
        assert f.matches("firmware_restart")

    def test_include_regex(self) -> None:
        f = build_filter(r"state:\s+\w+", None, False)
        assert f.matches("Klipper state: Disconnect")
        assert not f.matches("some other message")

    def test_exclude_hides_matching(self) -> None:
        f = build_filter(None, "error", False)
        assert not f.matches("An error occurred")
        assert f.matches("All good")

    def test_exclude_case_insensitive(self) -> None:
        f = build_filter(None, "error", False)
        assert not f.matches("ERROR: something")

    def test_exclude_temps_hides_temp_reports(self) -> None:
        f = build_filter(None, None, True)
        assert not f.matches("ok T:210.5 /210.0 B:60.1 /60.0")
        assert not f.matches("T:210.5 /210.0")
        assert not f.matches("T0:210.5 /210.0 T1:195.0 /195.0 B:60.1 /60.0")
        assert not f.matches(" T:25.0 /0.0 B:25.0 /0.0")
        assert not f.matches("B:60.1 /60.0")

    def test_exclude_temps_passes_normal_messages(self) -> None:
        f = build_filter(None, None, True)
        assert f.matches("echo: G28 command")
        assert f.matches("Klipper state: Disconnect")
        assert f.matches("FIRMWARE_RESTART")
        assert f.matches("")

    def test_combined_include_and_exclude(self) -> None:
        f = build_filter("state", "Disconnect", False)
        assert f.matches("Klipper state: Shutdown")
        assert not f.matches("Klipper state: Disconnect")
        assert not f.matches("echo: G28 command")

    def test_combined_all_filters(self) -> None:
        f = build_filter("klipper", "shutdown", True)
        assert f.matches("Klipper state: Ready")
        assert not f.matches("Klipper state: Shutdown")
        assert not f.matches("ok T:210.5 /210.0")
        assert not f.matches("some random message")

    def test_empty_message(self) -> None:
        f = build_filter("something", None, False)
        assert not f.matches("")

    def test_build_filter_none_patterns(self) -> None:
        f = build_filter(None, None, False)
        assert f.include is None
        assert f.exclude is None
        assert f.exclude_temps is False
