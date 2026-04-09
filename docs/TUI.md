# klipperctl TUI Guide

The klipperctl TUI (Text User Interface) provides an interactive terminal dashboard for monitoring and controlling your 3D printer. It is built with [Textual](https://textual.textualize.io/) and provides real-time status updates, temperature monitoring, and access to all CLI commands through nested menus.

## Installation

The TUI requires the `tui` optional dependency:

```bash
pip install klipperctl[tui]
```

For development:

```bash
pip install -e ".[dev,tui]"
```

## Launching the TUI

```bash
# Use default printer (from config or localhost)
klipperctl tui

# Connect to a specific URL
klipperctl --url http://your-printer:7125 tui

# Use a named printer profile
klipperctl tui --printer myprinter
```

## Screens

The TUI has three main screens, accessible via keyboard shortcuts from anywhere:

### Dashboard (d)

The default screen showing real-time printer status:

```
┌─────────────────────────────────────────────┐
│ klipperctl — 3D Printer Control             │
│ Connected: http://printer:7125              │
├──────────────────────┬──────────────────────┤
│  Printer Status      │  Temperatures        │
│  State: Printing     │  Hotend: 210/210°C   │
│  File: benchy.gcode  │  Bed:     60/60°C    │
│  ████████████ 73%    │  Chamber:  45°C      │
│  Elapsed: 1h 23m     │  ▁▂▃▅▆▇█▇▆▅ (trend) │
│  ETA: 32m            │                      │
├──────────────────────┴──────────────────────┤
│  d Dashboard  c Console  m Commands  q Quit │
└─────────────────────────────────────────────┘
```

Features:
- **Printer status**: Current state with color coding (green=ready, cyan=printing, yellow=paused, red=error)
- **Print progress**: Progress bar, filename, elapsed time, and ETA
- **Temperature display**: All heaters and sensors with current/target readings
- **Temperature sparkline**: Visual trend of the primary heater over time
- **Auto-refresh**: Data polls every 2 seconds; press `r` for manual refresh

### Console (c)

Interactive GCode console for sending commands and viewing responses:

- Type GCode commands in the input field and press Enter to send
- Responses appear in the scrollable log above
- Message filtering support via the `MessageFilter` class
- Press `Escape` to return to the previous screen

### Commands (m)

Nested menu system providing access to all CLI functionality:

**Command Groups:**

| Group | Commands |
|-------|----------|
| **Printer Control** | status, info, temps, set-temp, gcode, gcode-help, objects, query, endstops, restart, firmware-restart, emergency-stop |
| **Print Jobs** | start, pause, resume, cancel, progress |
| **File Management** | list, info, upload, download, delete, move, copy, mkdir, rmdir, thumbnails, scan |
| **Print History** | list, show, totals, reset-totals |
| **Job Queue** | status, add, start, pause, jump, remove |
| **Server** | info, config, restart, logs, logs-rollover, announcements, dismiss |
| **System** | info, health, services, service restart/stop/start, peripherals, shutdown, reboot |
| **Software Updates** | status, upgrade, rollback, recover |
| **Power Devices** | list, status, on, off |
| **Authentication** | login, logout, whoami, info, api-key |
| **Configuration** | show, set, printers, add-printer, remove-printer, use |

**How it works:**
1. Select a command group from the top-level menu
2. Select a specific command from the group's submenu
3. **Smart selection lists**: Commands that accept filenames, device names, services, etc. fetch the available options from the printer API and present a selection list instead of requiring manual text entry
4. For commands requiring freeform input (GCode, temperatures, paths), a form dialog appears
5. Destructive commands (delete, cancel, emergency-stop, shutdown, etc.) show a confirmation dialog
6. Results are displayed in a modal dialog

**Selection lists are used for:**
- Print start, file info/download/delete/thumbnails/scan (fetches file list from printer)
- Queue add/jump/remove (fetches queued jobs)
- System service restart/stop/start (fetches system services)
- Update upgrade/rollback/recover (fetches updatable components)
- Power on/off (fetches power device list)
- Config remove-printer/use (reads local printer profiles)

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `d` | Switch to Dashboard |
| `c` | Switch to Console |
| `m` | Switch to Commands menu |
| `r` | Refresh data (on Dashboard) |
| `q` | Quit the TUI |
| `Escape` | Quit (on Dashboard) / Go back (elsewhere) |
| `Enter` | Select menu item / submit form |

## Connection

The TUI resolves the printer connection using the same priority as the CLI:

1. `--url` flag on the command line
2. `MOONRAKER_URL` environment variable
3. `--printer` flag (named profile from config)
4. Default printer from config file
5. `http://localhost:7125`

## Architecture

The TUI is implemented as an isolated package at `src/klipperctl/tui/`:

```
tui/
├── __init__.py
├── app.py              # Main KlipperApp (Textual App subclass)
├── screens/
│   ├── __init__.py
│   ├── dashboard.py    # Status + temperature dashboard
│   ├── console.py      # GCode console with input
│   └── commands.py     # Command menu system (all 11 groups)
└── widgets/
    ├── __init__.py
    ├── status.py       # PrinterStatusWidget (state, progress, ETA)
    └── temperatures.py # TemperatureWidget (readings + sparkline)
```

Key design decisions:
- **Optional dependency**: Textual is in the `[tui]` extra, keeping the base CLI lean
- **Reuses existing code**: Formatters from `output.py`, filtering from `filtering.py`, config from `config.py`
- **Async polling**: Background workers poll printer data every 2 seconds without blocking the UI
- **CLI execution**: Commands run through Click's `CliRunner` to reuse all existing command logic
- **No changes to existing code**: The TUI adds new files only; existing commands, tests, and modules are untouched (except registering the `tui` command in `cli.py`)
