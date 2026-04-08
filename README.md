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

## Installation

```bash
pip install klipperctl
```

For development:

```bash
git clone https://github.com/cbyrd01/mooncli.git
cd mooncli
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pip install -e "../moonraker-api-client"  # sibling library dependency
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
