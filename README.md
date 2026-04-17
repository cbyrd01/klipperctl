# klipperctl

Command line interface for 3D printers using [Moonraker](https://moonraker.readthedocs.io/) and [Klipper](https://www.klipper3d.org/).

## Features

- 11 command groups covering the full Moonraker API
- Rich terminal output with tables and color
- Machine-readable JSON mode (`--json`) for shell pipelines
- Multi-printer profile management
- Live monitoring with `--watch` for temperatures and print progress
- Automatic unit conversions (duration, file sizes, temperatures)
- Stdin support for GCode piping
- Interactive TUI dashboard with real-time monitoring (optional)

## Installation

Install from PyPI:

```bash
pip install klipperctl
```

With TUI support (interactive terminal dashboard):

```bash
pip install "klipperctl[tui]"
```

For development (sibling-checkout layout):

```bash
git clone https://github.com/cbyrd01/moonraker-client.git
git clone https://github.com/cbyrd01/klipperctl.git
cd klipperctl
python3 -m venv .venv && source .venv/bin/activate
pip install -e "../moonraker-client"          # editable sibling for local changes
pip install -e ".[dev,tui]"                   # editable install of klipperctl
```

The editable `moonraker-client` install shadows the PyPI dependency declared in
`pyproject.toml`, so local changes to either repo are picked up immediately.

Build local wheels for smoke testing (no PyPI upload):

```bash
python -m build                                 # in each repo
pip install dist/moonraker_client-*.whl dist/klipperctl-*.whl
klipperctl --help
```

## Quick Start

```bash
# Configure your printer (saved to ~/.config/klipperctl/config.toml)
klipperctl config add-printer myprinter http://your-printer:7125 --default

# Or set via environment variable
export MOONRAKER_URL=http://your-printer:7125

# Or pass directly
klipperctl --url http://your-printer:7125 status
```

### Multiple printers

`klipperctl` can manage several printers via named profiles. The config
file lives at `~/.config/klipperctl/config.toml` on Linux,
`~/Library/Application Support/klipperctl/config.toml` on macOS, and
`%APPDATA%\klipperctl\config.toml` on Windows. It's created 0o600 (user
only), since profiles may carry API keys.

```toml
# ~/.config/klipperctl/config.toml
default_printer = "voron"

[printers.voron]
url = "http://voron.local:7125"
api_key = "optional-moonraker-api-key"

[printers.ender3]
url = "http://192.168.1.42:7125"

[printers.virtual]
url = "http://localhost:7125"
```

Select a profile per-invocation with `--printer`:

```bash
klipperctl --printer ender3 status
klipperctl --printer voron print start benchy.gcode
```

`--url` always wins over `--printer`, and `MOONRAKER_URL` wins over
the default profile.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Cannot connect to Moonraker at ...` (exit 2) | Wrong `--url`, printer powered off, or Moonraker not running | Verify with `curl http://your-printer:7125/server/info`. Check `sudo systemctl status moonraker` on the printer. |
| `Authentication required` (exit 2) | API key required but missing | Set `--api-key`, `MOONRAKER_API_KEY`, or add `api_key = "..."` to your profile. |
| `Request timed out` (exit 2) | Slow network, busy printer, or a long-running gcode blocking the dispatch | Increase `--timeout`. For `print cancel`, the printer may still be chewing on the cancel sequence; wait and retry. |
| Commands succeed but `klippy_state` is `shutdown` | Klipper hit a runtime error (config, MCU timer, etc.) | `klipperctl printer firmware-restart`. Investigate `klippy.log` via `klipperctl server logs`. |
| `File not found on printer` (exit 3) | `print start` with a filename that isn't in the gcodes root | `klipperctl files list` to confirm the exact path; upload with `klipperctl files upload`. |
| TUI dashboard frozen / no updates | Transient network error during polling; the TUI now surfaces these as error toasts and backs off exponentially | Wait a few seconds; the poll timer recovers automatically. If the error persists, use `klipperctl printer status` directly to diagnose. |
| Logs command exits immediately | No `--watch` flag | Add `--watch` to tail. Use `--exclude-temps` and `--filter` to focus on interesting output. |

## Commands

### Printer Control

```bash
klipperctl status                         # printer dashboard (alias)
klipperctl printer info                   # raw Klipper host info
klipperctl temps                          # all temperatures (alias)
klipperctl printer temps --watch          # live temperature monitor
klipperctl printer set-temp --hotend 210 --bed 60 --wait
klipperctl gcode "G28"                    # send GCode (alias)
klipperctl printer gcode-help             # list available GCode commands
klipperctl printer objects                # list Klipper printer objects
klipperctl printer query toolhead --attrs position
klipperctl printer restart                # soft restart Klipper
klipperctl printer firmware-restart       # full firmware restart
klipperctl printer emergency-stop --yes   # emergency stop
```

### Print Job Management

```bash
klipperctl print start benchy.gcode       # start a print
klipperctl progress                       # print progress (alias)
klipperctl print progress --watch         # live progress monitor
klipperctl print pause
klipperctl print resume
klipperctl print cancel --yes
```

### File Management

```bash
klipperctl files list                     # list gcode files
klipperctl files list --long --sort size  # detailed listing sorted by size
klipperctl files info benchy.gcode        # file metadata (slicer, time, filament)
klipperctl files upload model.gcode --print  # upload and start printing
klipperctl files download benchy.gcode --output ./benchy.gcode
klipperctl files delete old-print.gcode --yes
klipperctl files move a.gcode subdir/a.gcode
klipperctl files copy a.gcode backup/a.gcode
klipperctl files mkdir gcodes/project
klipperctl files rmdir gcodes/old --force --yes
klipperctl files thumbnails benchy.gcode
klipperctl files scan benchy.gcode        # trigger metadata rescan
```

### Print History

```bash
klipperctl history list                   # recent print jobs
klipperctl history list --limit 50 --order asc
klipperctl history show JOB_ID            # details of a single job
klipperctl history totals                 # aggregate stats
klipperctl history reset-totals --yes
```

### Job Queue

```bash
klipperctl queue status                   # queue state and pending jobs
klipperctl queue add part1.gcode part2.gcode part3.gcode
klipperctl queue add batch.gcode --reset  # clear queue first
klipperctl queue start
klipperctl queue pause
klipperctl queue jump JOB_ID              # move job to front
klipperctl queue remove JOB_ID
```

### Server Management

```bash
klipperctl server info                    # Moonraker version, components
klipperctl server config                  # Moonraker configuration
klipperctl server restart                 # restart Moonraker
klipperctl server logs --count 50         # cached GCode responses
klipperctl server logs-rollover
klipperctl server announcements
klipperctl server dismiss ENTRY_ID
```

### System Administration

```bash
klipperctl system info                    # OS, CPU, memory, network
klipperctl system health                  # CPU temp, uptime, memory usage
klipperctl system health --watch          # live system monitor
klipperctl system services                # service status table
klipperctl system service restart klipper
klipperctl system service stop moonraker
klipperctl system peripherals             # USB, serial, video, CAN devices
klipperctl system peripherals --type usb
klipperctl system shutdown --yes
klipperctl system reboot --yes
```

### Software Updates

```bash
klipperctl update status                  # update status for all components
klipperctl update status --refresh        # force refresh (CPU-intensive)
klipperctl update upgrade                 # upgrade all
klipperctl update upgrade --name klipper  # upgrade specific component
klipperctl update rollback klipper
klipperctl update recover klipper --hard
```

### Power Devices

```bash
klipperctl power list                     # configured power devices
klipperctl power status --all             # status of all devices
klipperctl power on printer_power
klipperctl power off led_strip
```

### Authentication

```bash
klipperctl auth login                     # interactive login
klipperctl auth login --username admin --password secret
klipperctl auth logout
klipperctl auth whoami
klipperctl auth info
klipperctl auth api-key
```

### CLI Configuration

```bash
klipperctl config show                    # current config
klipperctl config printers                # list configured printers
klipperctl config add-printer voron http://voron.local:7125 --default
klipperctl config add-printer ender http://ender.local:7125 --api-key KEY
klipperctl config use ender               # switch active printer
klipperctl config remove-printer old
klipperctl config set key value
```

## Interactive TUI

klipperctl includes an optional interactive terminal dashboard built with [Textual](https://textual.textualize.io/):

```bash
klipperctl tui                          # launch dashboard
klipperctl --url http://printer:7125 tui
klipperctl tui --printer myprinter      # use a named profile
```

The TUI provides:
- **Dashboard**: Real-time printer status, progress bar, per-heater
  temperature charts, and an embedded gcode console. Each chart
  (hotend, bed) draws the recent current-temperature history as a
  block-character line, overlaid with a horizontal magenta reference
  line at the target setpoint, so you can see at a glance how close
  the printer is to the requested temperature. The embedded console
  at the bottom lets you fire off quick commands (`G28`, `M115`,
  `M117 hello`) without leaving the dashboard: press `g` to focus
  the input, type a command, press Enter. The console pre-fills on
  launch with the last ~25 entries from Moonraker's gcode store so
  you see recent printer activity immediately, and then **streams
  new activity live**: commands sent from any other client (Mainsail,
  a slicer, a running macro, another TUI session) or by your own
  print show up in the dashboard log within about a second, without
  you having to refresh or switch screens. Your own locally-submitted
  commands are deduped against the stream so you don't see double
  echoes. Up/Down recalls the last 50 commands you've submitted in
  this session. Press Escape to release focus from the input and
  return to the dashboard's single-key bindings (escape does NOT
  quit while the input is focused). Replies render green (success)
  or red (error) in a scrolling log above the input.
- **Console**: Full-screen GCode console with the same backfill +
  live-streaming + dedupe behavior as the dashboard-embedded console,
  expanded to fill the entire screen for when you want a larger
  scrollback to tail printer activity or run a long session of
  commands. Supports an optional `MessageFilter` (set
  programmatically) to suppress noisy entries like temperature
  reports. Press Escape to return to the dashboard in a single
  keypress.
- **Command Menu**: Nested menus exposing all 11 command groups with smart selection lists (files, devices, services, components), input forms, and confirmation dialogs

Keyboard shortcuts: `d` Dashboard, `c` Full Console, `m` Commands, `g` focus embedded gcode input, `r` Refresh, `q`/`Escape` Quit (dashboard, no input focus), `Escape` Back (other screens). Inside the dashboard gcode input: Up/Down cycles command history, Escape releases focus back to the dashboard (does not quit the app).

See [docs/TUI.md](docs/TUI.md) for the full TUI guide.

## Pipeline & JSON Mode

All commands support `--json` for machine-readable output, making klipperctl composable with standard Unix tools:

```bash
# Get file list as JSON
klipperctl --json files list | jq '.[0].path'

# Check print state
klipperctl --json print progress | jq -r '.state'

# Monitor temperatures in JSON stream
klipperctl --json printer temps --watch >> /var/log/temps.jsonl

# Conditionally act on printer state
if klipperctl --json print progress | jq -e '.state == "printing"' > /dev/null; then
  echo "Printer is busy"
fi

# Pipe GCode from stdin
echo "G28" | klipperctl gcode -
cat macro.gcode | klipperctl gcode -

# Batch queue from a file list
cat batch.txt | xargs klipperctl queue add
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Moonraker API error |
| 2 | Connection / auth / timeout error |
| 3 | User input error |
| 130 | Interrupted (Ctrl+C) |

## Global Options

```
--url TEXT        Moonraker server URL (env: MOONRAKER_URL)
--api-key TEXT    API key (env: MOONRAKER_API_KEY)
--json            Machine-readable JSON output
--no-color        Disable colored output
--timeout FLOAT   Request timeout in seconds (default: 30)
--version         Show version
--help            Show help
```

## Configuration

klipperctl stores printer profiles in `~/.config/klipperctl/config.toml`:

```toml
default_printer = "myprinter"

[printers.myprinter]
url = "http://192.168.1.100:7125"
api_key = "optional-api-key"
```

URL resolution priority: `--url` flag > `MOONRAKER_URL` env var > config file > `http://localhost:7125`

## Development

```bash
# Run tests
pytest tests/unit/                        # unit tests (no server needed)
MOONRAKER_URL=http://printer:7125 pytest tests/functional/ --functional

# Lint and format
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy src/klipperctl/
```

## License

GPL-3.0
