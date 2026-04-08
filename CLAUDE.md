# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`klipperctl` is a Python CLI for controlling 3D printers running Klipper via the Moonraker API. It wraps the `moonraker-client` library (at `../moonraker-api-client/`) into user-friendly commands with Rich output and JSON pipeline support.

## Build & Run Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pip install -e "../moonraker-api-client"  # sibling library dependency

# Run
klipperctl --help
klipperctl --url http://your-printer:7125 status

# Unit tests (no server needed)
pytest tests/unit/

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

- `src/klipperctl/cli.py` — Root click.Group, global options (--url, --json, --timeout), top-level alias expansion
- `src/klipperctl/client.py` — MoonrakerClient construction from flags/env/config (priority: flags > env > config > defaults)
- `src/klipperctl/output.py` — Output formatting: JSON mode, Rich tables, unit conversions (duration, bytes, temp)
- `src/klipperctl/config.py` — Config file management (~/.config/klipperctl/config.toml)
- `src/klipperctl/commands/` — One module per command group (printer, print_cmd, files, etc.)

### Key Patterns

- **Global --json flag**: When set, all commands output JSON to stdout. Errors go to stderr as JSON. Without it, Rich tables and colored output are used.
- **Exit codes**: 0=success, 1=API error, 2=connection/auth/timeout error, 3=user error, 130=interrupted
- **Client lifecycle**: `get_client(ctx)` lazily creates and caches a MoonrakerClient on the click context, with automatic cleanup.
- **Error handling**: `_handle_error()` in cli.py maps moonraker-client exceptions to exit codes and user-friendly messages.
- **Alias expansion**: AliasGroup.parse_args() rewrites top-level shortcuts (status → printer status) before dispatch.
- **Commands use helpers**: Prefer `moonraker_client.helpers` functions over raw API calls where available.

### Dependencies

- `click>=8.1` — CLI framework
- `rich>=13.0` — Tables, progress bars, colored output
- `moonraker-client>=0.1.0` — Moonraker API client library
- Dev: `pytest`, `ruff`, `mypy`

### Test Structure

- `tests/unit/` — Click CliRunner tests with mocked MoonrakerClient
- `tests/functional/` — Tests against a live Moonraker server (skipped without `MOONRAKER_URL` + `--functional`)
- Follows same conventions as moonraker-client (pytest markers, env var config)
