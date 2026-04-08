# klipperctl CLI Reference

Complete command reference for klipperctl v0.1.0.

## Command Tree

```
klipperctl [global options] <command> [options] [arguments]

  printer                          Printer state and direct control
    status                           Comprehensive printer dashboard
    info                             Raw Klipper host information
    temps                            Extruder and bed temperatures
    set-temp                         Set heater target temperatures
    gcode                            Send raw GCode command(s)
    gcode-help                       List registered GCode commands
    objects                          List Klipper printer objects
    query                            Query specific printer objects
    endstops                         Query endstop states
    restart                          Soft restart Klipper
    firmware-restart                 Full firmware restart (resets MCUs)
    emergency-stop                   Emergency stop the printer

  print                            Active print job control
    start                            Start printing a file
    pause                            Pause the current print
    resume                           Resume the paused print
    cancel                           Cancel the current print
    progress                         Show current print progress

  files                            File management
    list                             List gcode files
    info                             Show file metadata
    upload                           Upload a local gcode file
    download                         Download a file from the printer
    delete                           Delete a file
    move                             Move or rename a file
    copy                             Copy a file
    mkdir                            Create a directory
    rmdir                            Delete a directory
    thumbnails                       List thumbnails for a gcode file
    scan                             Trigger metadata rescan

  history                          Print history
    list                             List past print jobs
    show                             Show details of a single job
    totals                           Show aggregate print totals
    reset-totals                     Reset print totals to zero

  queue                            Job queue management
    status                           Show queue state and pending jobs
    add                              Enqueue one or more files
    start                            Start processing the queue
    pause                            Pause the queue
    jump                             Move a job to front of queue
    remove                           Remove job(s) from queue

  server                           Moonraker server management
    info                             Server info (version, components)
    config                           Show Moonraker configuration
    restart                          Restart the Moonraker server
    logs                             Show cached GCode responses
    logs-rollover                    Rollover log files
    announcements                    List announcements
    dismiss                          Dismiss an announcement

  system                           Host machine management
    info                             System info (OS, CPU, memory)
    health                           System health summary
    shutdown                         Shutdown the host OS
    reboot                           Reboot the host OS
    services                         List system services
    service restart                  Restart a system service
    service stop                     Stop a system service
    service start                    Start a system service
    peripherals                      List USB, serial, video, CAN devices

  update                           Software update management
    status                           Update status for all components
    upgrade                          Upgrade software
    rollback                         Rollback to previous version
    recover                          Recover a corrupt repo

  power                            Power device control
    list                             List configured power devices
    status                           Show power device status
    on                               Turn on a power device
    off                              Turn off a power device

  auth                             Authentication management
    login                            Login to Moonraker
    logout                           Logout from Moonraker
    info                             Show auth module info
    whoami                           Show current user
    api-key                          Show the current API key

  config                           Local CLI configuration
    show                             Show current configuration
    set                              Set a configuration value
    printers                         List configured printers
    add-printer                      Add a printer profile
    remove-printer                   Remove a printer profile
    use                              Switch active printer
```

## Top-Level Aliases

These shortcuts expand to their full form before dispatch:

| Alias | Expands To |
|-------|------------|
| `klipperctl status` | `klipperctl printer status` |
| `klipperctl temps` | `klipperctl printer temps --all` |
| `klipperctl progress` | `klipperctl print progress` |
| `klipperctl gcode CMD` | `klipperctl printer gcode CMD` |

## Global Options

These options apply to all commands and must appear before the command name.

| Option | Env Var | Description |
|--------|---------|-------------|
| `--url TEXT` | `MOONRAKER_URL` | Moonraker server URL |
| `--api-key TEXT` | `MOONRAKER_API_KEY` | API key for authentication |
| `--json` | | Machine-readable JSON output to stdout |
| `--no-color` | | Disable colored output |
| `--timeout FLOAT` | | Request timeout in seconds (default: 30.0) |
| `--version` | | Show version and exit |
| `--help` | | Show help and exit |

**URL resolution priority:** `--url` flag > `MOONRAKER_URL` env var > config file default printer > `http://localhost:7125`

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Moonraker API error (invalid request, file not found, etc.) |
| 2 | Connection, authentication, or timeout error |
| 3 | User input error (bad arguments, missing file) |
| 130 | Interrupted (Ctrl+C during `--watch` or confirmation) |

---

## printer

Printer state and direct control.

### printer status

Show a comprehensive printer dashboard including state, temperatures, and print progress.

```
klipperctl printer status
```

### printer info

Show raw Klipper host information (state, hostname, version, paths).

```
klipperctl printer info
```

### printer temps

Show extruder and bed temperatures.

```
klipperctl printer temps [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--all` | Include all heaters and temperature sensors |
| `--watch` | Continuously poll temperatures |
| `--interval FLOAT` | Poll interval in seconds (default: 2.0) |

### printer set-temp

Set heater target temperatures.

```
klipperctl printer set-temp [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--hotend FLOAT` | Hotend target temperature in °C |
| `--bed FLOAT` | Bed target temperature in °C |
| `--tool INT` | Tool index (default: 0) |
| `--wait` | Block until temperatures are reached |
| `--tolerance FLOAT` | Degrees tolerance for `--wait` (default: 2.0) |
| `--timeout FLOAT` | Max wait time in seconds (default: 300.0) |

At least one of `--hotend` or `--bed` is required.

### printer gcode

Send raw GCode command(s).

```
klipperctl printer gcode [SCRIPT]
```

Pass GCode as an argument, or use `-` to read from stdin:

```bash
klipperctl gcode "G28"
klipperctl gcode "G28\nG1 X50 Y50"
echo "G28" | klipperctl gcode -
cat macro.gcode | klipperctl gcode -
```

### printer gcode-help

List registered GCode commands with descriptions.

```
klipperctl printer gcode-help [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--filter TEXT` | Filter by command name substring |

### printer objects

List all available Klipper printer objects (extruder, heater_bed, toolhead, etc.).

```
klipperctl printer objects
```

### printer query

Query specific printer object attributes.

```
klipperctl printer query OBJECT_NAMES... [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--attrs TEXT` | Comma-separated attribute names |

```bash
klipperctl printer query toolhead --attrs position,homed_axes
klipperctl printer query extruder heater_bed
```

### printer endstops

Query endstop states (open/triggered).

```
klipperctl printer endstops
```

### printer restart

Soft restart Klipper.

```
klipperctl printer restart
```

### printer firmware-restart

Full firmware restart that resets MCUs.

```
klipperctl printer firmware-restart [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--wait / --no-wait` | Wait for ready state (default: wait) |
| `--timeout FLOAT` | Max wait time in seconds (default: 30.0) |

### printer emergency-stop

Emergency stop the printer. All heaters will be immediately disabled.

```
klipperctl printer emergency-stop [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--yes` | Skip confirmation prompt |

---

## print

Active print job control.

### print start

Start printing a file.

```
klipperctl print start FILENAME
```

The file must exist on the printer. Use `klipperctl files list` to see available files.

### print pause

Pause the current print.

```
klipperctl print pause
```

### print resume

Resume a paused print.

```
klipperctl print resume
```

### print cancel

Cancel the current print.

```
klipperctl print cancel [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--yes` | Skip confirmation prompt |

Shows the filename and progress percentage in the confirmation prompt.

### print progress

Show current print progress (filename, state, percentage, elapsed time).

```
klipperctl print progress [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--watch` | Continuously update progress display |
| `--interval FLOAT` | Poll interval in seconds (default: 2.0) |

---

## files

File management.

### files list

List gcode files.

```
klipperctl files list [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--root TEXT` | Root directory (default: gcodes) |
| `--sort [modified\|size\|path]` | Sort field (default: modified) |
| `--long` | Show extended metadata (size, modified date) |

### files info

Show file metadata including slicer, estimated time, filament usage, layer height, and temperatures.

```
klipperctl files info FILENAME
```

### files upload

Upload a local gcode file to the printer.

```
klipperctl files upload FILE [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--path TEXT` | Remote subdirectory to upload into |
| `--print` | Start printing immediately after upload |

### files download

Download a file from the printer.

```
klipperctl files download FILENAME [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--output PATH` | Local output file path (default: stdout) |
| `--root TEXT` | Root directory (default: gcodes) |

### files delete

Delete a file from the printer.

```
klipperctl files delete FILENAME [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--root TEXT` | Root directory (default: gcodes) |
| `--yes` | Skip confirmation prompt |

### files move

Move or rename a file.

```
klipperctl files move SOURCE DEST
```

Paths must include the root prefix (e.g., `gcodes/old.gcode gcodes/new.gcode`).

### files copy

Copy a file.

```
klipperctl files copy SOURCE DEST
```

### files mkdir

Create a directory.

```
klipperctl files mkdir PATH
```

Path must include the root prefix (e.g., `gcodes/subdir`).

### files rmdir

Delete a directory.

```
klipperctl files rmdir PATH [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--force` | Force delete non-empty directory |
| `--yes` | Skip confirmation prompt |

### files thumbnails

List thumbnails embedded in a gcode file.

```
klipperctl files thumbnails FILENAME
```

### files scan

Trigger a metadata rescan for a file.

```
klipperctl files scan FILENAME
```

---

## history

Print history.

### history list

List past print jobs.

```
klipperctl history list [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--limit INT` | Max entries to return (default: 20) |
| `--since FLOAT` | Unix timestamp: only jobs after this time |
| `--before FLOAT` | Unix timestamp: only jobs before this time |
| `--order [asc\|desc]` | Sort order (default: desc) |

### history show

Show details of a single print job.

```
klipperctl history show JOB_ID
```

### history totals

Show aggregate print totals (total jobs, time, filament, longest job).

```
klipperctl history totals
```

### history reset-totals

Reset all print totals to zero.

```
klipperctl history reset-totals [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--yes` | Skip confirmation prompt |

---

## queue

Job queue management.

### queue status

Show queue state and list pending jobs.

```
klipperctl queue status
```

### queue add

Enqueue one or more files for printing.

```
klipperctl queue add FILES... [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--reset` | Clear queue before adding |

```bash
klipperctl queue add part1.gcode part2.gcode part3.gcode
klipperctl queue add batch.gcode --reset
```

### queue start

Start processing the job queue.

```
klipperctl queue start
```

### queue pause

Pause the job queue (prevents next job from loading).

```
klipperctl queue pause
```

### queue jump

Move a job to the front of the queue.

```
klipperctl queue jump JOB_ID
```

### queue remove

Remove job(s) from the queue.

```
klipperctl queue remove JOB_IDS...
```

---

## server

Moonraker server management.

### server info

Show Moonraker server info (version, API version, Klippy state, components).

```
klipperctl server info
```

### server config

Show the full Moonraker configuration.

```
klipperctl server config
```

### server restart

Restart the Moonraker server.

```
klipperctl server restart
```

### server logs

Show cached GCode responses.

```
klipperctl server logs [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--count INT` | Number of entries to return |

### server logs-rollover

Rollover log files (moonraker.log, klippy.log).

```
klipperctl server logs-rollover [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--app TEXT` | Application name (default: all) |

### server announcements

List current announcements.

```
klipperctl server announcements [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--include-dismissed` | Include dismissed entries |

### server dismiss

Dismiss an announcement.

```
klipperctl server dismiss ENTRY_ID
```

---

## system

Host machine management.

### system info

Show system information (OS, CPU model, cores, memory, network interfaces).

```
klipperctl system info
```

### system health

Show system health summary (CPU temperature, uptime, memory usage, CPU usage).

```
klipperctl system health [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--watch` | Continuously poll |
| `--interval FLOAT` | Poll interval in seconds (default: 5.0) |

### system shutdown

Shutdown the host operating system.

```
klipperctl system shutdown [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--yes` | Skip confirmation prompt |

### system reboot

Reboot the host operating system.

```
klipperctl system reboot [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--yes` | Skip confirmation prompt |

### system services

List system services with their states.

```
klipperctl system services
```

### system service restart

Restart a system service.

```
klipperctl system service restart SERVICE
```

### system service stop

Stop a system service.

```
klipperctl system service stop SERVICE
```

### system service start

Start a system service.

```
klipperctl system service start SERVICE
```

### system peripherals

List detected USB, serial, video, and CAN bus devices.

```
klipperctl system peripherals [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--type [usb\|serial\|video\|canbus]` | Filter by device type |

---

## update

Software update management.

### update status

Show update status for all components.

```
klipperctl update status [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--refresh` | Force refresh check (CPU-intensive) |

### update upgrade

Upgrade software to the latest version.

```
klipperctl update upgrade [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--name TEXT` | Specific component (default: all) |

### update rollback

Rollback a component to its previous version.

```
klipperctl update rollback NAME
```

### update recover

Recover a corrupt git repo.

```
klipperctl update recover NAME [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--hard` | Hard recovery mode |

---

## power

Power device control.

### power list

List all configured power devices with type, state, and lock status.

```
klipperctl power list
```

### power status

Show the status of a specific power device or all devices.

```
klipperctl power status [DEVICE] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--all` | Show all devices |

One of `DEVICE` or `--all` is required.

### power on

Turn on a power device. Requires confirmation (use `--yes` to skip).

```
klipperctl power on DEVICE [--yes]
```

### power off

Turn off a power device. Requires confirmation (use `--yes` to skip).

```
klipperctl power off DEVICE [--yes]
```

---

## auth

Authentication management.

### auth login

Login to the Moonraker server.

```
klipperctl auth login [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--username TEXT` | Username (prompted if not provided) |
| `--password TEXT` | Password (prompted with hidden input if not provided) |

### auth logout

Logout from the Moonraker server.

```
klipperctl auth logout
```

### auth info

Show authorization module info (default source, API key status).

```
klipperctl auth info
```

### auth whoami

Show the currently authenticated user.

```
klipperctl auth whoami
```

### auth api-key

Show the current API key.

```
klipperctl auth api-key
```

---

## config

Local CLI configuration. Manages printer profiles stored in `~/.config/klipperctl/config.toml`.

### config show

Show the current configuration including all printer profiles.

```
klipperctl config show
```

### config set

Set a top-level configuration value.

```
klipperctl config set KEY VALUE
```

### config printers

List configured printers with their URLs and which is active.

```
klipperctl config printers
```

### config add-printer

Add a new printer profile.

```
klipperctl config add-printer NAME URL [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--api-key TEXT` | API key for this printer |
| `--default` | Set as the default printer |

The first printer added is automatically set as default.

### config remove-printer

Remove a printer profile.

```
klipperctl config remove-printer NAME
```

If the removed printer was the default, the next available printer becomes the default.

### config use

Switch the active printer.

```
klipperctl config use NAME
```

---

## JSON Mode

When `--json` is passed, every command outputs a JSON object or array to stdout. This makes klipperctl composable with tools like `jq`, `grep`, and shell scripts.

- Successful output goes to **stdout** as JSON
- Errors go to **stderr** as `{"error": "message", "code": N}`
- Human-readable formatting (tables, colors) is suppressed
- `--watch` mode outputs one JSON object per poll cycle

```bash
# Parse with jq
klipperctl --json printer status | jq '.temperatures.extruder.current'

# Stream to log file
klipperctl --json printer temps --watch >> temps.jsonl

# Use in conditionals
if klipperctl --json print progress | jq -e '.state == "printing"' > /dev/null 2>&1; then
  echo "Printer is busy"
fi

# Chain commands
klipperctl --json files list | jq -r '.[0].path' | xargs klipperctl print start
```
