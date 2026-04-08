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
- `src/klipperctl/client.py` — MoonrakerClient construction from flags/env/config (priority: flags > env > config > defaults)
- `src/klipperctl/output.py` — Output formatting: JSON mode, Rich tables/console, unit conversions (duration, bytes, temp, percent, timestamp)
- `src/klipperctl/config.py` — Config file management (~/.config/klipperctl/config.toml) with TOML read/write
- `src/klipperctl/commands/` — One module per command group (11 total):
  - `printer.py` — Printer state, temps, GCode, restart, emergency stop
  - `print_cmd.py` — Print start/pause/resume/cancel/progress
  - `files.py` — File list/upload/download/delete/move/copy/mkdir/rmdir/thumbnails/scan
  - `history.py` — Print history list/show/totals
  - `queue.py` — Job queue status/add/start/pause/jump/remove
  - `server.py` — Server info/config/restart/logs/announcements
  - `system.py` — System info/health/services/peripherals/shutdown/reboot
  - `update.py` — Update status/upgrade/rollback/recover
  - `power.py` — Power device list/status/on/off
  - `auth.py` — Login/logout/whoami/api-key
  - `config_cmd.py` — Multi-printer profile management

### Key Patterns

- **Global --json flag**: When set, all commands output JSON to stdout. Errors go to stderr as JSON. Without it, Rich tables and colored output are used.
- **Exit codes**: 0=success, 1=API error, 2=connection/auth/timeout error, 3=user error, 130=interrupted
- **Client lifecycle**: `get_client(ctx)` in client.py lazily creates and caches a MoonrakerClient on the Click context, with automatic cleanup via `ctx.call_on_close`.
- **Error handling**: `_handle_error()` in cli.py maps moonraker-client exceptions to exit codes and user-friendly messages. All commands catch exceptions and delegate to this function.
- **Alias expansion**: `AliasGroup.resolve_command()` rewrites top-level shortcuts (e.g., `status` -> `printer status`) before Click resolves the command.
- **Lazy loading**: Command groups are loaded on demand via `COMMAND_GROUPS` dict in cli.py using `importlib.import_module()` for fast startup.
- **Commands use helpers**: Prefer `moonraker_client.helpers` functions (get_printer_status, get_temperatures, start_print, etc.) over raw API calls where available.
- **Output pattern**: Each command calls `output(data, human_fn)` — in JSON mode it serializes `data`, otherwise it calls `human_fn` for Rich-formatted output.
- **Destructive commands**: Require `--yes` flag or interactive confirmation (emergency-stop, cancel, delete, shutdown, reboot, reset-totals).

### Dependencies

- `click>=8.1` — CLI framework (zero transitive deps)
- `rich>=13.0` — Tables, colored output
- `moonraker-client>=0.1.0` — Moonraker API client library (httpx + websockets)
- Dev: `pytest`, `ruff`, `mypy`

### Test Structure

- `tests/unit/` — Click CliRunner tests with mocked MoonrakerClient (122 tests)
  - `test_output.py` — Unit conversion formatting
  - `test_config.py` — Config file read/write/roundtrip
  - `test_cli.py` — Help output, alias expansion
  - `test_commands.py` — Phase 1 commands (printer, print, files)
  - `test_commands_phase2.py` — Files extended, history, queue
  - `test_commands_phase3.py` — Server, system, update, power
  - `test_commands_phase4.py` — Auth, config
- `tests/functional/` — Tests against a live Moonraker server (32 tests)
  - Skipped without `MOONRAKER_URL` env var + `--functional` flag
  - `test_printer.py` — Core commands against live printer
  - `test_all_commands.py` — History, queue, server, system, files
- Test pattern: mock `build_client` to inject a MagicMock for unit tests; use CliRunner for both unit and functional tests
