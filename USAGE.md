# CLI Usage Guide

Full reference for all `pymyhondaplus` commands and options.

## Authentication

### Login

```bash
# Login (triggers email verification on first use)
pymyhondaplus login --email user@example.com

# With password (otherwise prompted)
pymyhondaplus login --email user@example.com --password secret

# With locale
pymyhondaplus login --email user@example.com --locale de
```

On first login from a new device, Honda will send a verification email. **Do not click** the link — copy the URL and paste it when prompted.

### Logout

```bash
pymyhondaplus logout
```

Removes saved tokens and device key.

## Vehicle selection

If you have only one vehicle on your account, it's selected automatically. With multiple vehicles, specify one using `--vin` (or `-v`) with a VIN, nickname, or plate number:

```bash
pymyhondaplus -v "Honda e" status
pymyhondaplus -v GE395KM status
pymyhondaplus -v JHMZC7840LXXXXXX status

# Or via environment variable
export HONDA_VIN="Honda e"
pymyhondaplus status
```

### List vehicles

```bash
pymyhondaplus list
```

## Vehicle status

```bash
# Get cached status
pymyhondaplus status

# Request fresh data from car (wakes the TCU)
pymyhondaplus status --fresh

# Output as JSON
pymyhondaplus --json status
```

Shows: ignition, speed, battery, range, charge status/mode, plug status, time to full charge, location, coordinates, charge limits, climate, temperatures, odometer, doors, hood, trunk, lights, warnings, and timestamp.

### Watch mode

Poll at regular intervals and print only fields that changed, with a timestamp:

```bash
pymyhondaplus status --watch 5m       # every 5 minutes
pymyhondaplus status --watch 30s      # every 30 seconds
pymyhondaplus status --watch 2h       # every 2 hours
pymyhondaplus status --watch 300      # every 300 seconds
```

Output:

```
Watching every 5m (Ctrl+C to stop)

2026-03-23 14:00:00  Battery: 68%  Range: 108 km  Charge: charging  Plug: connected
2026-03-23 14:05:01  Battery: 70%  Range: 112 km
2026-03-23 14:10:02  Battery: 72%  Range: 115 km
2026-03-23 14:15:01  Battery: 74%  Range: 119 km  Charge: complete
```

With `--json`, outputs one JSON object per line (JSONL), suitable for piping to `jq` or logging to a file.

Press Ctrl+C to stop.

## Location

```bash
# Get last known location
pymyhondaplus location

# Request fresh location from car (wakes TCU)
pymyhondaplus location --fresh

# Output as JSON
pymyhondaplus --json location
```

## Remote commands

All remote commands prompt for confirmation before executing. Use `--yes` or `-y` to skip:

```bash
pymyhondaplus lock              # prompts: Execute 'lock'? [y/N]
pymyhondaplus lock -y           # executes immediately
```

When stdin is not a terminal (e.g. piped or in a script), the prompt is skipped automatically.

### Doors

```bash
pymyhondaplus lock
pymyhondaplus unlock
```

### Horn & lights

```bash
pymyhondaplus horn
```

### Climate control

```bash
pymyhondaplus climate-start
pymyhondaplus climate-stop

# View current climate settings
pymyhondaplus climate-settings

# Configure temperature, duration, and defrost
pymyhondaplus climate-settings-set --temp hotter --duration 30
pymyhondaplus climate-settings-set --temp cooler --duration 10 --no-defrost
pymyhondaplus climate-settings-set --temp normal --duration 20
```

Temperature options: `cooler`, `normal`, `hotter`. Duration: `10`, `20`, or `30` minutes. Defrost is on by default, use `--no-defrost` to disable.

### Climate schedule

Schedule automatic climate start times (up to 7 slots):

```bash
# View current schedule
pymyhondaplus climate-schedule

# Set a slot
pymyhondaplus climate-schedule-set --days mon,tue,fri --start 07:00
pymyhondaplus climate-schedule-set --days sat,sun --start 09:00 --slot 2

# Clear all slots
pymyhondaplus climate-schedule-clear
```

### Charging

```bash
pymyhondaplus charge-start
pymyhondaplus charge-stop

# Set charge limits
pymyhondaplus charge-limit --home 80 --away 90
```

### Charge prohibition schedule

Define time windows when the car should **not** charge (up to 2 rules):

```bash
# View current schedule
pymyhondaplus charge-schedule

# Set a rule (don't charge 07:00-08:00 every day, everywhere)
pymyhondaplus charge-schedule-set --days mon,tue,wed,thu,fri,sat,sun --start 07:00 --end 08:00 --location all

# Set rule 2 (don't charge 22:00-06:00 on weekdays, at home)
pymyhondaplus charge-schedule-set --days mon,tue,wed,thu,fri --start 22:00 --end 06:00 --location home --rule 2

# Clear all rules
pymyhondaplus charge-schedule-clear
```

## Trip history

```bash
# List trips (current month, page 1)
pymyhondaplus trips

# All pages
pymyhondaplus trips --all

# Specific month
pymyhondaplus trips --month "2026-01-01T00:00:00.000Z"

# Specific page
pymyhondaplus trips --page 3

# Include start/end GPS coordinates (2 API calls per trip)
pymyhondaplus trips --locations

# JSON output with locations
pymyhondaplus --json trips --locations
```

### Trip detail

Show start and end GPS coordinates for a specific trip. Use the timestamps from `trips` output:

```bash
pymyhondaplus trip-detail "2026-03-19T16:23:13+00:00" "2026-03-19T17:05:56+00:00"

# JSON output
pymyhondaplus --json trip-detail "2026-03-19T16:23:13+00:00" "2026-03-19T17:05:56+00:00"
```

### Trip statistics

Aggregated statistics over a period:

```bash
# Current month (default)
pymyhondaplus trip-stats

# Current week
pymyhondaplus trip-stats --period week

# Today
pymyhondaplus trip-stats --period day

# Specific date
pymyhondaplus trip-stats --date 2026-01-15

# Week containing a specific date
pymyhondaplus trip-stats --period week --date 2026-01-15

# JSON output
pymyhondaplus --json trip-stats
```

Output:

```
Period:          2026-03-01 — 2026-03-22 (month)
Trips:           42
Total distance:  1,234.5 km
Total time:      48h 30min
Avg distance:    29.4 km/trip
Avg duration:    69 min/trip
Avg speed:       38.2 km/h
Max speed:       127 km/h
Avg consumption: 5.3 kWh/100km
```

## Global options

These must be placed **before** the subcommand:

| Option | Description |
|--------|-------------|
| `--vin`, `-v` | Vehicle VIN, nickname, or plate |
| `--json` | Output raw JSON |
| `--fresh` | Request fresh data from car (wakes TCU) |
| `--token-file PATH` | Custom token file path (or set `HONDA_TOKEN_FILE`) |
| `--key-file PATH` | Custom device key file path (or set `HONDA_KEY_FILE`) |
| `--storage {auto,keyring,encrypted,plain}` | Storage backend for secrets (or set `HONDA_STORAGE`) |
| `--user-info` | Show full user info and vehicle details as JSON |

## Subcommand options

These can be placed before or after the subcommand:

| Option | Description | Available on |
|--------|-------------|--------------|
| `--debug` | Show full tracebacks on error | all subcommands |
| `--timeout SECONDS` | Timeout for remote commands (default: 60) | all subcommands |
| `--yes`, `-y` | Skip confirmation prompt | destructive commands only |

## Shell completion

Tab completion for subcommands and options. First, install `argcomplete`:

```bash
pip install pymyhondaplus[completion]
# or on Debian/Ubuntu:
apt install python3-argcomplete
# or with pipx:
pipx inject pymyhondaplus argcomplete
```

Then add this to your `~/.bashrc` (or `~/.zshrc`):

```bash
eval "$(register-python-argcomplete pymyhondaplus)"
```

Restart your shell, and `pymyhondaplus <TAB>` will complete subcommands, flags, and choices.

## CSV output

The `trips` and `trip-stats` commands support `--csv` for piping to spreadsheets or other tools:

```bash
pymyhondaplus trips --all --csv > trips.csv
pymyhondaplus trip-stats --csv
pymyhondaplus trips --all --csv --locations   # includes GPS columns
```

## Security

Tokens and device keys are encrypted at rest using Fernet (AES-128-CBC). The encryption key is:

- **With `pymyhondaplus[keyring]`**: stored in the OS keyring (macOS Keychain, Windows Credential Vault, Linux Secret Service/KDE Wallet)
- **Without keyring**: derived from a machine-specific fingerprint (username + hostname + random salt via PBKDF2)

Use `--storage plain` to disable encryption. Existing plain-text token files are automatically migrated to encrypted format on first use.

## Library usage

```python
from pymyhondaplus import HondaAPI, HondaAPIError, HondaAuth, DeviceKey, compute_trip_stats
# Authenticate
auth = HondaAuth()
tokens = auth.full_login("user@example.com", "password")

# Use the API
api = HondaAPI()
api.set_tokens(**tokens)

# Vehicle status (units from car: distance_unit, speed_unit, temp_unit)
status = api.get_dashboard("JHMZC7840LXXXXXX")

# Trips (all pages, parsed as dicts)
trips = api.get_all_trips("JHMZC7840LXXXXXX")

# Trips for a specific date
today_trips = api.get_all_trips("JHMZC7840LXXXXXX", ref_date="2026-03-23")

# Trip start/end GPS coordinates
locs = api.get_trip_locations("JHMZC7840LXXXXXX",
    "2026-03-19T16:23:13+00:00", "2026-03-19T17:05:56+00:00")

# Aggregated trip statistics
stats = compute_trip_stats(trips, period="month", fuel_type="E", distance_unit="km")
# stats["total_distance"], stats["distance_unit"], stats["speed_unit"]
# stats["avg_consumption"], stats["consumption_unit"]

# Charge prohibition schedule
schedule = api.get_charge_schedule("JHMZC7840LXXXXXX")
api.set_charge_schedule("JHMZC7840LXXXXXX", [
    {"days": "mon,tue,wed", "location": "all", "start_time": "07:00", "end_time": "08:00"},
])

# Climate schedule
climate = api.get_climate_schedule("JHMZC7840LXXXXXX")
api.set_climate_schedule("JHMZC7840LXXXXXX", [
    {"days": "mon,tue,fri", "start_time": "07:00"},
])

# Remote commands return CommandResult
from pymyhondaplus import CommandResult

cmd_id = api.remote_lock("JHMZC7840LXXXXXX")
result = api.wait_for_command(cmd_id)

if result.success:
    print("Command succeeded")
elif result.timed_out:
    # Car in deep sleep or out of cellular range
    print(f"Car unreachable: {result.reason or 'timed out'}")
else:
    print(f"Command failed: {result.reason or result.status}")

# CommandResult fields:
#   result.complete    — True if the server returned a final answer
#   result.success     — True if completed successfully
#   result.timed_out   — True if the car couldn't be reached
#   result.status      — "pending", "success", "in-progress", etc.
#   result.reason      — server-provided explanation (often None)
#   result.command_id  — the async command ID
#   result.raw         — full server response dict

# You can also poll manually:
result = api.poll_command(cmd_id)  # returns CommandResult

# Error handling — all API methods raise HondaAPIError
try:
    status = api.get_dashboard("JHMZC7840LXXXXXX")
except HondaAPIError as e:
    print(f"API error: {e.status_code} — {e}")
```

Transient errors (5xx, connection timeouts) are automatically retried up to 3 times with backoff.

### Breaking changes in 5.0.0

`poll_command()` now returns a `CommandResult` object instead of a raw `dict`. If you were using the old return format (`{"status_code": ..., "data": ...}`), update your code to use `CommandResult` fields instead.
