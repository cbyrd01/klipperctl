# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`klipperctl` is a Python CLI for controlling 3D printers running Klipper via the Moonraker API. It wraps the `moonraker-client` library (at `../moonraker-client/`) into user-friendly commands with Rich output and JSON pipeline support.

## Build & Run Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pip install -e "../moonraker-client"  # sibling library dependency

# Run
klipperctl --help
klipperctl --url http://your-printer:7125 status

# Unit tests (no server needed)
pytest tests/unit/

# Single test file
pytest tests/unit/test_commands.py -v

# Single test
pytest tests/unit/test_commands.py::TestPrinterStatus::test_json_output -v

# Functional tests (requires a live Moonraker server)
MOONRAKER_URL=http://192.168.1.212:7125 pytest tests/functional/ --functional

# Lint and format
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy src/klipperctl/
```

## Architecture

### Package Layout

- `src/klipperctl/cli.py` — Root click.Group with global options (--url, --json, --timeout), alias expansion, lazy command loading, and error handling
- `src/klipperctl/client.py` — MoonrakerClient construction from flags/env/config (priority: flags > env > config > defaults). Also provides `build_async_client()` for WebSocket commands.
- `src/klipperctl/filtering.py` — Reusable message filtering: regex include/exclude patterns and temperature report hiding for console/log commands
- `src/klipperctl/output.py` — Output formatting: JSON mode, Rich tables/console, unit conversions (duration, bytes, temp, percent, timestamp)
- `src/klipperctl/config.py` — Config file management with TOML read/write. Platform-aware paths: Linux `~/.config/klipperctl/`, macOS `~/Library/Application Support/klipperctl/`, Windows `%APPDATA%/klipperctl/`
- `src/klipperctl/commands/` — One module per command group (11 total):
  - `printer.py` — Printer state, temps, GCode, restart, emergency stop
  - `print_cmd.py` — Print start/pause/resume/cancel/progress
  - `files.py` — File list/upload/download/delete/move/copy/mkdir/rmdir/thumbnails/scan
  - `history.py` — Print history list/show/totals
  - `queue.py` — Job queue status/add/start/pause/jump/remove
  - `server.py` — Server info/config/restart/logs (with --watch/--filter/--exclude/--exclude-temps)/console (WebSocket streaming)/announcements
  - `system.py` — System info/health/services/peripherals/shutdown/reboot
  - `update.py` — Update status/upgrade/rollback/recover
  - `power.py` — Power device list/status/on/off
  - `auth.py` — Login/logout/whoami/api-key
  - `config_cmd.py` — Multi-printer profile management
  - `tui_cmd.py` — TUI launch command (`klipperctl tui`)
- `src/klipperctl/tui/` — Interactive TUI (optional, requires `textual`):
  - `app.py` — Main `KlipperApp` (Textual App), polling workers, CLI command execution
  - `screens/dashboard.py` — Real-time status + temperature dashboard
  - `screens/console.py` — GCode console with WebSocket streaming
  - `screens/commands.py` — Nested command menus for all 11 command groups, confirmation/input/result modals
  - `widgets/status.py` — `PrinterStatusWidget` (state, progress bar, elapsed, ETA)
  - `widgets/temperatures.py` — `TemperatureWidget` (heater readings + sparkline history)

### Key Patterns

- **Global --json flag**: When set, all commands output JSON to stdout. Errors go to stderr as JSON. Without it, Rich tables and colored output are used.
- **Exit codes**: 0=success, 1=API error, 2=connection/auth/timeout error, 3=user error, 130=interrupted
- **Client lifecycle**: `get_client(ctx)` in client.py lazily creates and caches a MoonrakerClient on the Click context, with automatic cleanup via `ctx.call_on_close`.
- **Error handling**: `_handle_error()` in cli.py maps moonraker-client exceptions to exit codes and user-friendly messages. All commands catch specific exceptions `(MoonrakerError, click.Abort, OSError)` and delegate to this function.
- **Alias expansion**: `AliasGroup.resolve_command()` rewrites top-level shortcuts (e.g., `status` -> `printer status`) before Click resolves the command.
- **Lazy loading**: Command groups are loaded on demand via `COMMAND_GROUPS` dict in cli.py using `importlib.import_module()` for fast startup.
- **Commands use helpers**: Prefer `moonraker_client.helpers` functions (get_printer_status, get_temperatures, start_print, etc.) over raw API calls where available.
- **Output pattern**: Each command calls `output(data, human_fn)` — in JSON mode it serializes `data`, otherwise it calls `human_fn` for Rich-formatted output.
- **Response unwrapping**: Use `unwrap_result(result, key)` from output.py to extract nested API responses instead of inline isinstance/get patterns.
- **Watch loops**: Use `watch_loop(fn, interval)` from output.py for `--watch` polling commands (temps, health, progress). For tail-follow patterns (e.g. `server logs --watch`), use custom append loops instead of `watch_loop` (which clears the screen).
- **Async/WebSocket commands**: Use `build_async_client(ctx)` from client.py for commands needing WebSocket (e.g. `server console`). Bridge async into Click commands with `asyncio.run()`. Manage client lifecycle with `async with`.
- **Message filtering**: Use `build_filter()` / `MessageFilter` from filtering.py for `--filter`, `--exclude`, `--exclude-temps` options on log/console commands.
- **Destructive commands**: Require `--yes` flag or interactive confirmation (emergency-stop, cancel, delete, shutdown, reboot, reset-totals, power on/off).
- **Config security**: Config files are written with 0o600 permissions (directory 0o700) since they may contain API keys.
- **Path validation**: File download operations validate remote filenames and output paths against path traversal.
- **TUI architecture**: The TUI is an optional Textual app (`pip install klipperctl[tui]`). It polls printer data via sync `MoonrakerClient` in background workers (`run_worker` with `asyncio.to_thread`). Command execution uses Click's `CliRunner` internally to reuse all existing command logic. Screens use Textual's reactive attributes for auto-refresh.
- **TUI command menus**: All 11 CLI command groups are mirrored as `_BaseCommandScreen` subclasses in `screens/commands.py`. Each screen maps list item selections to CLI args. Destructive commands use `ConfirmModal`, commands with args use `InputFormScreen`.

### Dependencies

- `click>=8.1` — CLI framework (zero transitive deps)
- `rich>=13.0` — Tables, colored output
- `moonraker-client>=0.1.0` — Moonraker API client library (httpx + websockets)
- Optional TUI: `textual>=1.0` — Terminal UI framework (install with `pip install klipperctl[tui]`)
- Dev: `pytest`, `pytest-asyncio`, `ruff`, `mypy`

### Test Structure

- `tests/unit/` — Click CliRunner tests with mocked MoonrakerClient and Textual app tests
  - `test_filtering.py` — Message filtering (regex, temp reports)
  - `test_output.py` — Unit conversion formatting
  - `test_config.py` — Config file read/write/roundtrip
  - `test_cli.py` — Help output, alias expansion
  - `test_commands.py` — Phase 1 commands (printer, print, files)
  - `test_commands_phase2.py` — Files extended, history, queue
  - `test_commands_phase3.py` — Server, system, update, power
  - `test_commands_phase4.py` — Auth, config
  - `test_tui_widgets.py` — TUI widget unit tests (friendly names, reactive values, history)
  - `test_tui_app.py` — TUI app lifecycle, navigation, dashboard updates
  - `test_tui_screens.py` — TUI screen rendering, modals, forms
  - `test_tui_command_screens.py` — All 11 command group screens, navigation, set-temp args
  - `test_tui_cmd.py` — `klipperctl tui` CLI entry point, connection resolution
- `tests/functional/` — Tests against a live Moonraker server
  - Skipped without `MOONRAKER_URL` env var + `--functional` flag
  - `test_printer.py` — Core commands against live printer
  - `test_all_commands.py` — History, queue, server, system, files
  - `test_tui.py` — TUI dashboard, navigation, command execution against live server
- Test pattern: mock `build_client` to inject a MagicMock for unit tests; use CliRunner for both unit and functional tests. TUI tests use Textual's `app.run_test()` with `pilot` for headless interaction.
