# klipperctl

Command line interface for 3D printers using Moonraker and Klipper.

## Installation

```bash
pip install klipperctl
```

## Quick Start

```bash
# Set your printer URL (or use --url each time)
export MOONRAKER_URL=http://your-printer:7125

# Check printer status
klipperctl status

# Monitor temperatures
klipperctl temps --watch

# Upload and print a file
klipperctl files upload model.gcode --print

# View print progress
klipperctl progress --watch

# Send GCode
klipperctl gcode "G28"
```

## Pipeline Support

All commands support `--json` for machine-readable output:

```bash
# Get file list as JSON
klipperctl files list --json

# Check if printing
klipperctl print progress --json | jq '.state'

# Pipe GCode from stdin
echo "G28" | klipperctl gcode -
```

## License

GPL-3.0
