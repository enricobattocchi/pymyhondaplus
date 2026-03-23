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

# Configure temperature and duration
pymyhondaplus climate-settings --temp hotter --duration 30
pymyhondaplus climate-settings --temp cooler --duration 10
pymyhondaplus climate-settings --temp normal --duration 20
```

Temperature options: `cooler`, `normal`, `hotter`. Duration: `10`, `20`, or `30` minutes.

### Charging

```bash
pymyhondaplus charge-start
pymyhondaplus charge-stop

# Set charge limits
pymyhondaplus charge-limit --home 80 --away 90
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

| Option | Description |
|--------|-------------|
| `--vin`, `-v` | Vehicle VIN, nickname, or plate |
| `--json` | Output raw JSON (place before subcommand) |
| `--fresh` | Request fresh data from car (wakes TCU) |
| `--token-file PATH` | Custom token file path |
| `--key-file PATH` | Custom device key file path |
| `--storage {auto,keyring,encrypted,plain}` | Storage backend for secrets |
| `--user-info` | Show full user info and vehicle details as JSON |

## Security

Tokens and device keys are encrypted at rest using Fernet (AES-128-CBC). The encryption key is:

- **With `pymyhondaplus[keyring]`**: stored in the OS keyring (macOS Keychain, Windows Credential Vault, Linux Secret Service/KDE Wallet)
- **Without keyring**: derived from a machine-specific fingerprint (username + hostname + random salt via PBKDF2)

Use `--storage plain` to disable encryption. Existing plain-text token files are automatically migrated to encrypted format on first use.

## Library usage

```python
from pymyhondaplus.api import HondaAPI, compute_trip_stats
from pymyhondaplus.auth import HondaAuth, DeviceKey

# Authenticate
auth = HondaAuth()
tokens = auth.full_login("user@example.com", "password")

# Use the API
api = HondaAPI()
api.set_tokens(**tokens)

# Vehicle status
status = api.get_dashboard("JHMZC7840LXXXXXX")

# Trips (all pages, parsed as dicts)
trips = api.get_all_trips("JHMZC7840LXXXXXX")

# Trip start/end GPS coordinates
locs = api.get_trip_locations("JHMZC7840LXXXXXX",
    "2026-03-19T16:23:13+00:00", "2026-03-19T17:05:56+00:00")

# Aggregated trip statistics
stats = compute_trip_stats(trips, period="month")
```
