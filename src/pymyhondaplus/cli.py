"""CLI entry point for pymyhondaplus."""

import argparse
import csv
import getpass
import importlib.metadata
import json
import logging
import os
import sys
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import argcomplete
except ImportError:
    argcomplete = None

from .api import DEFAULT_TOKEN_FILE, HondaAPI, HondaAPIError, HondaAuthError, compute_trip_stats, parse_ev_status
from .auth import DEFAULT_DEVICE_KEY_FILE, DeviceKey, HondaAuth
from .storage import get_storage

WATCH_FIELDS = {
    "battery_level": ("Battery", "%"),
    "range": ("Range", " {dist}"),
    "charge_status": ("Charge", ""),
    "plug_status": ("Plug", ""),
    "time_to_charge": ("ETA", " min"),
    "climate_active": ("Climate", ""),
    "cabin_temp": ("Cabin", " {temp}"),
    "interior_temp": ("Interior", " {temp}"),
    "ignition": ("Ignition", ""),
    "speed": ("Speed", " {speed}"),
    "doors_locked": ("Doors", ""),
    "lights_on": ("Lights", ""),
    "home_away": ("Location", ""),
}


def _parse_interval(s: str) -> int:
    """Parse interval string like '5m', '30s', '2h', '120' to seconds."""
    s = s.strip().lower()
    if s.endswith("h"):
        return int(s[:-1]) * 3600
    if s.endswith("m"):
        return int(s[:-1]) * 60
    if s.endswith("s"):
        return int(s[:-1])
    return int(s)


def _format_watch_fields(ev: dict, fields: dict, prev: dict | None = None) -> str:
    """Format changed fields for watch output. If prev is None, format all fields."""
    units = {
        "dist": ev.get("distance_unit", "km"),
        "speed": ev.get("speed_unit", "km/h"),
        "temp": ev.get("temp_unit", "c"),
    }
    parts = []
    for key, (label, suffix) in fields.items():
        val = ev.get(key)
        if val is None:
            continue
        if prev is not None and prev.get(key) == val:
            continue
        if key == "climate_active":
            val = "ON" if val else "OFF"
        parts.append(f"{label}: {val}{suffix.format_map(units)}")
    return "  ".join(parts)


def _to_camel_case(name: str) -> str:
    """Convert snake_case to CamelCase. Already CamelCase names pass through."""
    if "_" not in name:
        return name
    return "".join(p.title() for p in name.split("_"))


def _month_starts_for_period(start_date: date, end_date: date) -> list[str]:
    """Return month-start timestamps covering the inclusive date range."""
    month_starts = []
    current = start_date.replace(day=1)
    last = end_date.replace(day=1)
    while current <= last:
        month_starts.append(current.strftime("%Y-%m-%dT00:00:00.000Z"))
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return month_starts


CONFIRM_COMMANDS = frozenset({
    "lock", "unlock", "horn",
    "climate-start", "climate-stop", "climate-settings-set",
    "climate-schedule-set", "climate-schedule-clear",
    "charge-start", "charge-stop", "charge-limit",
    "charge-schedule-set", "charge-schedule-clear",
})


def _confirm(command: str) -> bool:
    """Prompt for confirmation. Returns True if user confirms."""
    try:
        answer = input(f"Execute '{command}'? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("y", "yes")


class _Spinner:
    """Simple spinner shown on stderr during blocking operations."""

    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, label: str):
        self._label = label
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self):
        if sys.stderr.isatty():
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        if self._thread:
            self._thread.join()
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()

    def _spin(self):
        i = 0
        while not self._stop.wait(0.1):
            frame = self.FRAMES[i % len(self.FRAMES)]
            sys.stderr.write(f"\r{frame} {self._label}...")
            sys.stderr.flush()
            i += 1


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Unofficial Honda Connect Europe (My Honda+) API client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  %(prog)s login -e user@example.com -p secret    Login with email/password
  %(prog)s list                                    List vehicles on your account
  %(prog)s status                                  Get status (auto-selects if only one vehicle)
  %(prog)s status --fresh                          Get fresh status from car
  %(prog)s status --watch 5m                       Watch status (prints changes)
  %(prog)s lock                                    Lock doors
  %(prog)s horn                                    Flash lights & horn
  %(prog)s trips --all                             Get all trips

vehicle selection (only needed with multiple vehicles):
  %(prog)s -v "Honda e" status                     Select by nickname
  %(prog)s -v GE395KM status                       Select by plate
  %(prog)s -v JHMZC... status                      Select by VIN
  HONDA_VIN="Honda e" %(prog)s status              Via environment variable
""",
    )
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {importlib.metadata.version('pymyhondaplus')}")
    parser.add_argument("--vin", "-v", default=os.environ.get("HONDA_VIN"),
                        help="Vehicle VIN, nickname, or plate (default: auto if only one vehicle; or set HONDA_VIN)")
    parser.add_argument("--fresh", action="store_true",
                        help="Request fresh data from car")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--user-info", action="store_true",
                        help="Show user info and vehicle list")
    parser.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_FILE,
                        help=f"Token file path (default: {DEFAULT_TOKEN_FILE})")
    parser.add_argument("--key-file", type=Path, default=DEFAULT_DEVICE_KEY_FILE,
                        help=f"Device key file path (default: {DEFAULT_DEVICE_KEY_FILE})")
    parser.add_argument("--storage", default=os.environ.get("HONDA_STORAGE", "auto"),
                        choices=["auto", "keyring", "encrypted", "plain"],
                        help="Storage backend for secrets (default: auto; or set HONDA_STORAGE)")
    # Defaults for when no subcommand is given
    parser.set_defaults(debug=False, timeout=60, yes=False)

    # Shared flags inherited by all subcommands (can appear before or after subcommand)
    _common = argparse.ArgumentParser(add_help=False)
    _common.add_argument("--debug", action="store_true",
                         help="Show full tracebacks on error")
    _common.add_argument("--timeout", type=int, default=60,
                         help="Timeout in seconds for remote commands (default: 60)")

    subparsers = parser.add_subparsers(dest="command")

    # login subcommand
    login_parser = subparsers.add_parser("login", parents=[_common], help="Login with email/password")
    login_parser.add_argument("--email", "-e", required=True, help="Honda account email")
    login_parser.add_argument("--password", "-p", default=None, help="Honda account password (prompted if not given)")
    login_parser.add_argument("--locale", "-l", default="it", help="Locale (default: it)")

    subparsers.add_parser("logout", parents=[_common], help="Remove saved tokens and device key")
    subparsers.add_parser("list", parents=[_common], help="List vehicles on your account")

    # vehicle commands
    status_parser = subparsers.add_parser("status", parents=[_common], help="Get vehicle status")
    status_parser.add_argument("--watch", metavar="INTERVAL",
                                help="Poll at interval (e.g. 5m, 30s, 120). Prints only changes.")
    subparsers.add_parser("location", parents=[_common], help="Get car GPS location")

    _yes = argparse.ArgumentParser(add_help=False)
    _yes.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    for cmd_name, cmd_help in [
        ("lock", "Lock doors"),
        ("unlock", "Unlock doors"),
        ("horn", "Flash lights & horn"),
        ("climate-start", "Start climate control"),
        ("climate-stop", "Stop climate control"),
        ("charge-start", "Start charging"),
        ("charge-stop", "Stop charging"),
    ]:
        subparsers.add_parser(cmd_name, parents=[_common, _yes], help=cmd_help)

    subparsers.add_parser("climate-settings", parents=[_common], help="Show current climate settings")

    climate_set = subparsers.add_parser("climate-settings-set", parents=[_common, _yes],
                                         help="Configure climate settings")
    climate_set.add_argument("--temp", default="normal",
                              choices=["cooler", "normal", "hotter"])
    climate_set.add_argument("--duration", type=int, default=30,
                              choices=[10, 20, 30])
    climate_set.add_argument("--defrost", default=True,
                              action=argparse.BooleanOptionalAction,
                              help="Auto defrost (default: on, use --no-defrost to disable)")

    charge_limit = subparsers.add_parser("charge-limit", parents=[_common, _yes], help="Set charge limits")
    charge_limit.add_argument("--home", type=int, default=80,
                               choices=[80, 85, 90, 95, 100],
                               help="Charge limit at home %% (default: 80)")
    charge_limit.add_argument("--away", type=int, default=90,
                               choices=[80, 85, 90, 95, 100],
                               help="Charge limit away %% (default: 90)")

    subparsers.add_parser("charge-schedule", parents=[_common], help="Show charge prohibition schedule")

    charge_schedule_set = subparsers.add_parser("charge-schedule-set", parents=[_common, _yes],
                                                 help="Set charge prohibition schedule")
    charge_schedule_set.add_argument("--days", required=True,
                                      help="Days: mon,tue,wed,thu,fri,sat,sun (comma-separated)")
    charge_schedule_set.add_argument("--start", required=True,
                                      help="Prohibition start time (HH:MM)")
    charge_schedule_set.add_argument("--end", required=True,
                                      help="Prohibition end time (HH:MM)")
    charge_schedule_set.add_argument("--location", default="all",
                                      choices=["all", "home"],
                                      help="Location (default: all)")
    charge_schedule_set.add_argument("--rule", type=int, default=1,
                                      choices=[1, 2],
                                      help="Which rule slot to set (1 or 2, default: 1)")

    subparsers.add_parser("charge-schedule-clear", parents=[_common, _yes], help="Clear charge prohibition schedule")

    subparsers.add_parser("climate-schedule", parents=[_common], help="Show climate schedule")

    climate_schedule_set = subparsers.add_parser("climate-schedule-set", parents=[_common, _yes],
                                                  help="Set a climate schedule slot")
    climate_schedule_set.add_argument("--days", required=True,
                                       help="Days: mon,tue,wed,thu,fri,sat,sun (comma-separated)")
    climate_schedule_set.add_argument("--start", required=True,
                                       help="Start time (HH:MM)")
    climate_schedule_set.add_argument("--slot", type=int, default=1,
                                       choices=[1, 2, 3, 4, 5, 6, 7],
                                       help="Which slot to set (1-7, default: 1)")

    subparsers.add_parser("climate-schedule-clear", parents=[_common, _yes], help="Clear climate schedule")

    trips = subparsers.add_parser("trips", parents=[_common], help="Get recent trip history")
    trips.add_argument("--month", default="",
                        help="Month start (ISO 8601, e.g. 2026-03-01T00:00:00.000Z). Defaults to current month.")
    trips.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    trips.add_argument("--all", dest="all_pages", action="store_true",
                        help="Fetch all pages")
    trips.add_argument("--locations", action="store_true",
                        help="Include start/end GPS coordinates (slower, 2 API calls per trip)")
    trips.add_argument("--csv", action="store_true",
                        help="Output as CSV")

    trip_detail = subparsers.add_parser("trip-detail", parents=[_common], help="Show details for a specific trip")
    trip_detail.add_argument("start_time", help="Trip start time (ISO 8601, from trips output)")
    trip_detail.add_argument("end_time", help="Trip end time (ISO 8601, from trips output)")

    trip_stats = subparsers.add_parser("trip-stats", parents=[_common], help="Aggregated trip statistics")
    trip_stats.add_argument("--period", default="month",
                             choices=["day", "week", "month"],
                             help="Aggregation period (default: month)")
    trip_stats.add_argument("--date", dest="ref_date", default=None,
                             help="Reference date YYYY-MM-DD (default: today)")
    trip_stats.add_argument("--csv", action="store_true",
                             help="Output as CSV")

    if argcomplete:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()

    storage = get_storage(args.token_file, args.key_file, args.storage)

    if args.command == "login":
        device_key = DeviceKey(storage=storage)
        auth = HondaAuth(device_key=device_key)
        password = args.password or getpass.getpass("Password: ")
        try:
            result = auth.full_login(args.email, password, locale=args.locale)
        except HondaAuthError as e:
            print(f"\nLogin failed: {e}", file=sys.stderr)
            sys.exit(2)

        print("\nLogin successful!")
        print(f"Expires in: {result.get('expires_in', 'N/A')}s")

        user_id = HondaAuth.extract_user_id(result["access_token"])
        api = HondaAPI(storage=storage)
        api.set_tokens(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            expires_in=result.get("expires_in", 3599),
            user_id=user_id,
        )

        # Fetch and store vehicles
        vehicles = api.get_vehicles()
        if vehicles:
            api.tokens.vehicles = vehicles
            api._save_tokens()
            for v in vehicles:
                label = v["name"] or v["vin"]
                plate = f" ({v['plate']})" if v["plate"] else ""
                print(f"Vehicle: {label}{plate}")

        print(f"Tokens saved to {args.token_file}")
        return

    if args.command == "logout":
        has_files = args.token_file.exists() or args.key_file.exists()
        if has_files:
            storage.clear()
            print("Logged out (credentials removed)")
        else:
            print("Nothing to remove (not logged in)")
        return

    api = HondaAPI(storage=storage)

    if args.user_info:
        info = api.get_user_info()
        print(json.dumps(info, indent=2))
        return

    if args.command == "list":
        vehicles = api.get_vehicles()
        if vehicles:
            # Update stored vehicles
            api.tokens.vehicles = vehicles
            api._save_tokens()
            print(f"Found {len(vehicles)} vehicle(s):")
            for v in vehicles:
                label = v["name"] or v["vin"]
                plate = f" ({v['plate']})" if v["plate"] else ""
                print(f"  {v['vin']}  {label}{plate}")
        else:
            print("No vehicles found on this account.")
        return

    if not args.command:
        args.command = "status"

    if not args.vin:
        default = api.tokens.default_vin
        if default:
            vin = default
        elif api.tokens.vehicles:
            print("Multiple vehicles on account. Please specify one with --vin:", file=sys.stderr)
            for v in api.tokens.vehicles:
                label = v["name"] or v["vin"]
                plate = f" ({v['plate']})" if v["plate"] else ""
                print(f"  {v['vin']}  {label}{plate}", file=sys.stderr)
            sys.exit(1)
        else:
            print("No VIN specified. Use --vin, set HONDA_VIN, or re-login to auto-detect.", file=sys.stderr)
            sys.exit(1)
    else:
        vin = api.tokens.resolve_vin(args.vin) or args.vin

    # Find vehicle info for display
    vehicle_info = next((v for v in api.tokens.vehicles if v["vin"] == vin), None)
    consumption_unit = "kWh/100km" if (vehicle_info or {}).get("fuel_type") == "E" else "L/100km"
    if not args.json and not getattr(args, "csv", False):
        if vehicle_info:
            label = vehicle_info["name"] or vin
            plate = f" ({vehicle_info['plate']})" if vehicle_info.get("plate") else ""
            print(f"[{label}{plate}]", file=sys.stderr)
        else:
            print(f"[{vin}]", file=sys.stderr)
        print(file=sys.stderr)

    def wait_command(cmd_id: str, label: str):
        with _Spinner(label):
            result = api.wait_for_command(cmd_id, timeout=args.timeout)
        if result.success:
            print(f"{label}: done!")
        elif not result.complete and result.status == "no_command_id":
            print(f"{label}: failed (no command ID returned)", file=sys.stderr)
            sys.exit(1)
        elif result.timed_out:
            reason = result.reason or "car may be unreachable"
            print(f"{label}: timed out ({reason})", file=sys.stderr)
            sys.exit(1)
        else:
            reason = result.reason or result.status
            print(f"{label}: failed ({reason})", file=sys.stderr)
            sys.exit(1)

    # Confirmation prompt for destructive commands
    if args.command in CONFIRM_COMMANDS and not getattr(args, "yes", False) and sys.stdin.isatty():
        if not _confirm(args.command):
            print("Aborted.")
            sys.exit(0)

    if args.command == "status":
        if args.watch:
            interval = _parse_interval(args.watch)
            print(f"Watching every {args.watch} (Ctrl+C to stop)\n")
            prev_ev = None
            try:
                while True:
                    dashboard = api.get_dashboard(vin, fresh=args.fresh)
                    ev = parse_ev_status(dashboard)
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if args.json:
                        print(json.dumps(ev), flush=True)
                    else:
                        line = _format_watch_fields(ev, WATCH_FIELDS, prev_ev)
                        if line:
                            print(f"{ts}  {line}", flush=True)
                    prev_ev = ev.copy()
                    time.sleep(interval)
            except KeyboardInterrupt:
                print()
        else:
            dashboard = api.get_dashboard(vin, fresh=args.fresh)
            if args.json:
                print(json.dumps(dashboard, indent=2))
            else:
                ev = parse_ev_status(dashboard)
                du = ev['distance_unit']
                su = ev['speed_unit']
                tu = ev['temp_unit']
                print(f"Ignition:      {ev['ignition']}")
                print(f"Speed:         {ev['speed']} {su}")
                print(f"Battery:       {ev['battery_level']}%")
                print(f"Range:         {ev['range']} {du}")
                print(f"Charge status: {ev['charge_status']}")
                print(f"Charge mode:   {ev['charge_mode']}")
                print(f"Plug status:   {ev['plug_status']}")
                if ev['time_to_charge']:
                    print(f"Time to full:  {ev['time_to_charge']} min")
                print(f"Location:      {ev['home_away']}")
                print(f"Coordinates:   {ev['latitude']}, {ev['longitude']}")
                print(f"Charge limit:  {ev['charge_limit_home']}% (home) / {ev['charge_limit_away']}% (away)")
                print(f"Climate:       {'ON' if ev['climate_active'] else 'OFF'}")
                print(f"Cabin temp:    {ev['cabin_temp']} {tu}")
                print(f"Interior temp: {ev['interior_temp']} {tu}")
                print(f"Odometer:      {ev['odometer']} {du}")
                print(f"Doors locked:  {ev['doors_locked']}")
                print(f"Hood:          {'open' if ev['hood_open'] else 'closed'}")
                print(f"Trunk:         {'open' if ev['trunk_open'] else 'closed'}")
                print(f"Lights on:     {ev['lights_on']}")
                if ev['warning_lamps']:
                    print(f"Warnings:      {', '.join(ev['warning_lamps'])}")
                print(f"Timestamp:     {ev['timestamp']}")

    elif args.command == "location":
        dashboard = api.get_dashboard(vin, fresh=args.fresh)
        gps = dashboard.get("gpsData", {})
        if args.json:
            print(json.dumps(gps, indent=2))
        else:
            coord = gps.get("coordinate", {})
            print(f"Latitude:  {coord.get('latitude', 'N/A')}")
            print(f"Longitude: {coord.get('longitude', 'N/A')}")
            speed_unit = gps.get('velocity', {}).get('unit', 'km/h')
            print(f"Speed:     {gps.get('velocity', {}).get('value', 'N/A')} {speed_unit}")
            print(f"Timestamp: {gps.get('dtTime', 'N/A')}")

    elif args.command == "lock":
        wait_command(api.remote_lock(vin), "Lock")

    elif args.command == "unlock":
        wait_command(api.remote_unlock(vin), "Unlock")

    elif args.command == "horn":
        wait_command(api.remote_horn_lights(vin), "Horn & lights")

    elif args.command == "charge-start":
        wait_command(api.remote_charge_start(vin), "Charge start")

    elif args.command == "charge-stop":
        wait_command(api.remote_charge_stop(vin), "Charge stop")

    elif args.command == "climate-start":
        wait_command(api.remote_climate_start(vin), "Climate start")

    elif args.command == "climate-stop":
        wait_command(api.remote_climate_stop(vin), "Climate stop")

    elif args.command == "climate-settings":
        dashboard = api.get_dashboard(vin, fresh=args.fresh)
        ev = parse_ev_status(dashboard)
        if args.json:
            print(json.dumps({
                "active": ev["climate_active"],
                "temp": ev["climate_temp"],
                "duration": ev["climate_duration"],
                "defrost": ev["climate_defrost"],
                "cabin_temp": ev["cabin_temp"],
                "interior_temp": ev["interior_temp"],
                "temp_unit": ev["temp_unit"],
            }, indent=2))
        else:
            tu = ev['temp_unit']
            print(f"Active:      {'ON' if ev['climate_active'] else 'OFF'}")
            print(f"Temperature: {ev['climate_temp']}")
            print(f"Duration:    {ev['climate_duration']} min")
            print(f"Defrost:     {'on' if ev['climate_defrost'] else 'off'}")
            print(f"Cabin:       {ev['cabin_temp']} {tu}")
            print(f"Interior:    {ev['interior_temp']} {tu}")

    elif args.command == "climate-settings-set":
        wait_command(
            api.set_climate_settings(vin, temp=args.temp, duration=args.duration,
                                  defrost=args.defrost),
            f"Climate settings ({args.temp}, {args.duration}min, defrost={'on' if args.defrost else 'off'})",
        )

    elif args.command == "charge-limit":
        wait_command(
            api.set_charge_limit(vin, home=args.home, away=args.away),
            f"Charge limit ({args.home}% home, {args.away}% away)",
        )

    elif args.command == "charge-schedule":
        schedule = api.get_charge_schedule(vin, fresh=args.fresh)
        if args.json:
            print(json.dumps(schedule, indent=2))
        else:
            has_rules = False
            for i, rule in enumerate(schedule, 1):
                if rule["enabled"]:
                    has_rules = True
                    days = ",".join(rule["days"])
                    print(f"Rule {i}: {days}  {rule['start_time']}-{rule['end_time']}  ({rule['location']})")
            if not has_rules:
                print("No charge prohibition schedule set.")

    elif args.command == "charge-schedule-set":
        try:
            # Read current schedule to preserve the other rule
            current = api.get_charge_schedule(vin)
            rules = []
            for i in range(2):
                if i < len(current):
                    rules.append(current[i])
                else:
                    rules.append({"enabled": False})

            idx = args.rule - 1
            rules[idx] = {
                "enabled": True,
                "days": args.days,
                "location": args.location,
                "start_time": args.start,
                "end_time": args.end,
            }
            wait_command(
                api.set_charge_schedule(vin, rules),
                f"Charge schedule rule {args.rule}",
            )
        except HondaAPIError:
            role = (vehicle_info or {}).get("role", "")
            if role and role != "primary":
                print(f"Charge schedule is not available for {role} users.")
            else:
                raise

    elif args.command == "charge-schedule-clear":
        try:
            wait_command(
                api.set_charge_schedule(vin, []),
                "Clear charge schedule",
            )
        except HondaAPIError:
            role = (vehicle_info or {}).get("role", "")
            if role and role != "primary":
                print(f"Charge schedule is not available for {role} users.")
            else:
                raise

    elif args.command == "climate-schedule":
        schedule = api.get_climate_schedule(vin, fresh=args.fresh)
        if args.json:
            print(json.dumps(schedule, indent=2))
        else:
            has_rules = False
            for i, rule in enumerate(schedule, 1):
                if rule["enabled"]:
                    has_rules = True
                    days = ",".join(rule["days"])
                    print(f"Slot {i}: {days}  {rule['start_time']}")
            if not has_rules:
                print("No climate schedule set.")

    elif args.command == "climate-schedule-set":
        try:
            current = api.get_climate_schedule(vin)
            rules = []
            for i in range(7):
                if i < len(current):
                    rules.append(current[i])
                else:
                    rules.append({"enabled": False})

            idx = args.slot - 1
            rules[idx] = {
                "enabled": True,
                "days": args.days,
                "start_time": args.start,
            }
            wait_command(
                api.set_climate_schedule(vin, rules),
                f"Climate schedule slot {args.slot}",
            )
        except HondaAPIError:
            role = (vehicle_info or {}).get("role", "")
            if role and role != "primary":
                print(f"Climate schedule is not available for {role} users.")
            else:
                raise

    elif args.command == "climate-schedule-clear":
        try:
            wait_command(
                api.set_climate_schedule(vin, []),
                "Clear climate schedule",
            )
        except HondaAPIError:
            role = (vehicle_info or {}).get("role", "")
            if role and role != "primary":
                print(f"Climate schedule is not available for {role} users.")
            else:
                raise

    elif args.command == "trips":
        try:
            if args.all_pages or args.csv:
                rows = api.get_all_trips(vin, month_start=args.month)
            else:
                data = api.get_trips(vin, month_start=args.month, page=args.page)
                if args.json and not args.locations and not args.csv:
                    print(json.dumps(data, indent=2))
                    return
                payload = data.get("payload", {})
                fields = payload.get("def", [])
                rows = [dict(zip(fields, trip)) for trip in payload.get("data", [])]
                if not args.json and not args.csv:
                    print(f"Page {data.get('page', '?')}/{data.get('maxPage', '?')}")
        except HondaAPIError as e:
            role = (vehicle_info or {}).get("role", "")
            if role and role != "primary":
                print(f"Trip history is not available for {role} users.", file=sys.stderr)
            else:
                print(f"Failed to fetch trips: {e}", file=sys.stderr)
            sys.exit(1)

        if not rows:
            print("No trips found.")
        else:
            # Enrich with locations if requested
            for row in rows:
                start = row.get("StartTime", "?")
                end = row.get("EndTime", "?")
                if args.locations and start != "?" and end != "?":
                    try:
                        row.update(api.get_trip_locations(vin, start, end))
                    except HondaAPIError:
                        pass

            if args.json:
                print(json.dumps(rows, indent=2))
            elif args.csv:
                if rows:
                    camel_rows = [{_to_camel_case(k): v for k, v in row.items()} for row in rows]
                    writer = csv.DictWriter(sys.stdout, fieldnames=camel_rows[0].keys())
                    writer.writeheader()
                    writer.writerows(camel_rows)
            else:
                for row in rows:
                    line = (f"  {row.get('OneTripDate', '?')}  {row.get('StartTime', '?')} -> {row.get('EndTime', '?')}  "
                            f"{row.get('Mileage', '?')}  {row.get('DriveTime', '?')} min  "
                            f"avg {row.get('AveSpeed', '?')}  max {row.get('MaxSpeed', '?')}  "
                            f"{row.get('AveFuelEconomy', '?')} {consumption_unit}")
                    if "start_lat" in row:
                        line += (f"\n    from {row['start_lat']},{row['start_lon']}"
                                 f"  to {row['end_lat']},{row['end_lon']}")
                    print(line)

    elif args.command == "trip-detail":
        try:
            locs = api.get_trip_locations(vin, args.start_time, args.end_time)
        except HondaAPIError as e:
            print(f"Failed to fetch trip detail: {e}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(locs, indent=2))
        else:
            print("Start:")
            print(f"  Time:      {locs.get('start_time', 'N/A')}")
            print(f"  Location:  {locs.get('start_lat', 'N/A')}, {locs.get('start_lon', 'N/A')}")
            print("End:")
            print(f"  Time:      {locs.get('end_time', 'N/A')}")
            print(f"  Location:  {locs.get('end_lat', 'N/A')}, {locs.get('end_lon', 'N/A')}")

    elif args.command == "trip-stats":
        ref = date.fromisoformat(args.ref_date) if args.ref_date else date.today()

        # Determine filter range
        if args.period == "day":
            start_date, end_date = ref, ref
        elif args.period == "week":
            start_date = ref - timedelta(days=ref.weekday())  # Monday
            end_date = start_date + timedelta(days=6)          # Sunday
        else:
            start_date = ref.replace(day=1)
            if ref.month == 12:
                end_date = ref.replace(year=ref.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = ref.replace(month=ref.month + 1, day=1) - timedelta(days=1)

        try:
            all_rows = []
            seen_trip_ids = set()
            for month_start in _month_starts_for_period(start_date, end_date):
                for row in api.get_all_trips(vin, month_start=month_start):
                    trip_key = (
                        row.get("OneTripNo"),
                        row.get("OneTripDate"),
                        row.get("StartTime"),
                        row.get("EndTime"),
                    )
                    if trip_key in seen_trip_ids:
                        continue
                    seen_trip_ids.add(trip_key)
                    all_rows.append(row)
        except HondaAPIError as e:
            role = (vehicle_info or {}).get("role", "")
            if role and role != "primary":
                print(f"Trip history is not available for {role} users.", file=sys.stderr)
            else:
                print(f"Failed to fetch trips: {e}", file=sys.stderr)
            sys.exit(1)

        # Filter to period
        rows = []
        for row in all_rows:
            try:
                trip_date = date.fromisoformat(row.get("OneTripDate", "")[:10])
            except (ValueError, TypeError):
                continue
            if start_date <= trip_date <= end_date:
                rows.append(row)

        if not rows:
            print("No trips found.")
        else:
            fuel_type = (vehicle_info or {}).get("fuel_type", "")
            stats = compute_trip_stats(rows, args.period, fuel_type=fuel_type)
            if args.json:
                print(json.dumps(stats, indent=2))
            elif args.csv:
                camel_stats = {_to_camel_case(k): v for k, v in stats.items()}
                writer = csv.DictWriter(sys.stdout, fieldnames=camel_stats.keys())
                writer.writeheader()
                writer.writerow(camel_stats)
            else:
                hours = int(stats["total_minutes"]) // 60
                mins = int(stats["total_minutes"]) % 60
                du = stats["distance_unit"]
                su = stats["speed_unit"]
                print(f"Period:          {stats['start_date']} — {stats['end_date']} ({stats['period']})")
                print(f"Trips:           {stats['trips']}")
                print(f"Total distance:  {stats['total_distance']} {du}")
                print(f"Total time:      {hours}h {mins}min")
                print(f"Avg distance:    {stats['avg_distance_per_trip']} {du}/trip")
                print(f"Avg duration:    {stats['avg_min_per_trip']} min/trip")
                print(f"Avg speed:       {stats['avg_speed']} {su}")
                print(f"Max speed:       {stats['max_speed']} {su}")
                print(f"Avg consumption: {stats['avg_consumption']} {stats['consumption_unit']}")


def _main():
    """Wrapper with catch-all error handling."""
    try:
        main()
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    except HondaAuthError as e:
        if "--debug" in sys.argv:
            raise
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except HondaAPIError as e:
        if "--debug" in sys.argv:
            raise
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if "--debug" in sys.argv:
            raise
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _main()
