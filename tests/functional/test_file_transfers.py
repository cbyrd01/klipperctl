"""Functional tests for file upload/download + progress callback.

These exercise the full round trip against a live Moonraker server:
upload a local file through the library, CLI, and TUI modalities;
download the same file back and verify the bytes match; and assert
that a progress callback fires at least twice with monotonic
``bytes_transferred`` values and a final tick at full completion.

The pre-existing ``files_download`` implementation was silently
broken (it tried to JSON-parse binary responses and crashed with
``JSONDecodeError``); Phase 4b fixed it as a side-effect of adding
the streaming download path. These tests pin that fix down and
guard against regressions.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = [pytest.mark.functional, pytest.mark.asyncio]


def _unique_filename() -> str:
    return f"klipperctl_upload_test_{uuid.uuid4().hex[:8]}.gcode"


PAYLOAD = b"; klipperctl upload/download functional test\n" + (b"M117 tick\n" * 200)


async def test_upload_fires_progress_callback(
    fresh_client,
    moonraker_url: str,
) -> None:  # type: ignore[no-untyped-def]
    """Upload a file through the library with a progress callback.

    Verifies:
    - Callback fires at least twice (start + completion).
    - ``bytes_sent`` values are monotonic.
    - The final tick reports the full file size.
    - The upload actually completes and the file appears on the printer.

    Teardown deletes the uploaded file so the printer's gcode root
    doesn't accumulate sentinel files across runs.
    """
    import io

    filename = _unique_filename()
    buf = io.BytesIO(PAYLOAD)
    buf.name = filename  # type: ignore[attr-defined]

    ticks: list[tuple[int, int | None]] = []

    try:
        result = fresh_client.files_upload(
            buf, progress=lambda done, total: ticks.append((done, total))
        )
        assert result.get("item", {}).get("path", "").endswith(filename)
        assert len(ticks) >= 2, f"progress callback fired fewer than twice: {ticks}"
        done_values = [d for d, _ in ticks]
        assert done_values == sorted(done_values), f"progress not monotonic: {done_values}"
        assert any(d == len(PAYLOAD) for d, _ in ticks), (
            f"no tick reported full completion ({len(PAYLOAD)} bytes): {ticks}"
        )
    finally:
        import contextlib

        with contextlib.suppress(Exception):
            fresh_client.files_delete("gcodes", filename)


async def test_download_returns_raw_bytes_and_fires_progress(
    fresh_client,
) -> None:  # type: ignore[no-untyped-def]
    """Download a file and verify bytes + progress callback.

    Regression pin: before Phase 4b this path was broken outright
    (JSONDecodeError on the gcode response body). Also validates
    that the library uses the streaming path and fires progress
    ticks with monotonic bytes-received values.
    """
    import contextlib

    filename = _unique_filename()
    # Upload via the same client so the test is self-contained.
    import io

    buf = io.BytesIO(PAYLOAD)
    buf.name = filename  # type: ignore[attr-defined]
    fresh_client.files_upload(buf)

    try:
        ticks: list[tuple[int, int | None]] = []
        result = fresh_client.files_download(
            "gcodes", filename, progress=lambda d, t: ticks.append((d, t))
        )
        assert isinstance(result, bytes)
        assert result == PAYLOAD
        assert ticks, "progress callback never fired"
        assert ticks[0][0] == 0
        assert ticks[-1][0] == len(PAYLOAD)
        # Final tick should report the full total from Content-Length.
        assert ticks[-1][1] == len(PAYLOAD)
    finally:
        with contextlib.suppress(Exception):
            fresh_client.files_delete("gcodes", filename)


async def test_cli_upload_and_download_roundtrip(
    moonraker_url: str,
    printer_ready: bool,
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    """CLI-level round trip: upload → download → compare bytes.

    Exercises both ``klipperctl files upload`` and
    ``klipperctl files download`` against a live Moonraker with the
    `--no-progress` flag (since Click's CliRunner is non-interactive
    and Rich's live progress bar would be noise in the captured output).
    """
    import contextlib
    from pathlib import Path

    from click.testing import CliRunner
    from moonraker_client import MoonrakerClient

    from klipperctl.cli import cli

    _ = printer_ready

    filename = _unique_filename()
    local_src = Path(str(tmp_path)) / filename
    local_src.write_bytes(PAYLOAD)

    local_dst = Path(str(tmp_path)) / f"roundtrip-{filename}"

    runner = CliRunner()
    try:
        upload_result = runner.invoke(
            cli,
            [
                "--url",
                moonraker_url,
                "files",
                "upload",
                str(local_src),
                "--no-progress",
            ],
        )
        assert upload_result.exit_code == 0, upload_result.output
        assert "Uploaded" in upload_result.output

        download_result = runner.invoke(
            cli,
            [
                "--url",
                moonraker_url,
                "files",
                "download",
                filename,
                "--output",
                str(local_dst),
                "--no-progress",
            ],
        )
        assert download_result.exit_code == 0, download_result.output
        assert local_dst.exists()
        assert local_dst.read_bytes() == PAYLOAD
    finally:
        with contextlib.suppress(Exception), MoonrakerClient(
            base_url=moonraker_url, timeout=15.0
        ) as client:
            client.files_delete("gcodes", filename)
