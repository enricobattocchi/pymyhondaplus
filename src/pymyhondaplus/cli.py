"""CLI entry point for pymyhondaplus."""

import argparse
import getpass
import json
import logging
import os
import time
from pathlib import Path

from .api import DEFAULT_TOKEN_FILE, HondaAPI, extract_tokens_from_captures, parse_ev_status
from .auth import DEFAULT_DEVICE_KEY_FILE, DeviceKey, HondaAuth
from .storage import get_storage


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
    parser.add_argument("--extract-tokens", action="store_true",
                        help="Extract tokens from mitmproxy captured flows")
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

    subparsers = parser.add_subparsers(dest="command")

    # login subcommand
    login_parser = subparsers.add_parser("login", help="Login with email/password")
    login_parser.add_argument("--email", "-e", required=True, help="Honda account email")
    login_parser.add_argument("--password", "-p", default=None, help="Honda account password (prompted if not given)")
    login_parser.add_argument("--locale", "-l", default="it", help="Locale (default: it)")

    subparsers.add_parser("logout", help="Remove saved tokens and device key")
    subparsers.add_parser("list", help="List vehicles on your account")

    # vehicle commands
    subparsers.add_parser("status", help="Get vehicle status")
    subparsers.add_parser("location", help="Get car GPS location")
    subparsers.add_parser("lock", help="Lock doors")
    subparsers.add_parser("unlock", help="Unlock doors")
    subparsers.add_parser("horn", help="Flash lights & horn")
    subparsers.add_parser("climate-start", help="Start climate control")
    subparsers.add_parser("climate-stop", help="Stop climate control")
    subparsers.add_parser("charge-start", help="Start charging")
    subparsers.add_parser("charge-stop", help="Stop charging")

    climate_settings = subparsers.add_parser("climate-settings",
                                              help="Configure climate settings")
    climate_settings.add_argument("--temp", default="normal",
                                   choices=["cooler", "normal", "hotter"])
    climate_settings.add_argument("--duration", type=int, default=30,
                                   choices=[10, 20, 30])

    charge_limit = subparsers.add_parser("charge-limit", help="Set charge limits")
    charge_limit.add_argument("--home", type=int, default=80,
                               help="Charge limit at home %% (default: 80)")
    charge_limit.add_argument("--away", type=int, default=90,
                               help="Charge limit away %% (default: 90)")

    trips = subparsers.add_parser("trips", help="Get recent trip history")
    trips.add_argument("--month", default="",
                        help="Month start (ISO 8601, e.g. 2026-03-01T00:00:00.000Z). Defaults to current month.")
    trips.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    trips.add_argument("--all", dest="all_pages", action="store_true",
                        help="Fetch all pages")

    args = parser.parse_args()

    storage = get_storage(args.token_file, args.key_file, args.storage)

    if args.extract_tokens:
        print("Extracting tokens from captured flows...")
        tokens = extract_tokens_from_captures()
        api = HondaAPI(storage=storage)
        api.set_tokens(**tokens)
        print(f"Tokens saved to {args.token_file}")
        print(f"User ID: {tokens['user_id']}")
        print(f"Personal ID: {tokens['personal_id']}")
        if tokens['refresh_token']:
            print(f"Refresh token: {tokens['refresh_token'][:20]}...")
        else:
            print("No refresh token found (need complete-login capture)")
        return

    if args.command == "login":
        device_key = DeviceKey(storage=storage)
        auth = HondaAuth(device_key=device_key)
        password = args.password or getpass.getpass("Password: ")
        try:
            result = auth.full_login(args.email, password, locale=args.locale)
        except RuntimeError as e:
            print(f"\nLogin failed: {e}")
            return

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
            print("Multiple vehicles on account. Please specify one with --vin:")
            for v in api.tokens.vehicles:
                label = v["name"] or v["vin"]
                plate = f" ({v['plate']})" if v["plate"] else ""
                print(f"  {v['vin']}  {label}{plate}")
            return
        else:
            print("No VIN specified. Use --vin, set HONDA_VIN, or re-login to auto-detect.")
            return
    else:
        vin = api.tokens.resolve_vin(args.vin) or args.vin

    # Find vehicle info for display
    vehicle_info = next((v for v in api.tokens.vehicles if v["vin"] == vin), None)
    if vehicle_info:
        label = vehicle_info["name"] or vin
        plate = f" ({vehicle_info['plate']})" if vehicle_info.get("plate") else ""
        print(f"[{label}{plate}]")
    else:
        print(f"[{vin}]")
    print()

    def wait_command(cmd_id: str, label: str):
        if not cmd_id:
            print(f"Failed: no command ID returned")
            return
        for i in range(30):
            result = api.poll_command(cmd_id)
            if result["status_code"] == 200:
                print(f"{label}: done!")
                return
            time.sleep(2)
        print(f"{label}: timed out waiting for confirmation")

    if args.command == "status":
        dashboard = api.get_dashboard(vin, fresh=args.fresh)
        if args.json:
            print(json.dumps(dashboard, indent=2))
        else:
            ev = parse_ev_status(dashboard)
            print(f"Ignition:      {ev['ignition']}")
            print(f"Speed:         {ev['speed_kmh']} km/h")
            print(f"Battery:       {ev['battery_level']}%")
            print(f"Range:         {ev['range_km']} km")
            print(f"Charge status: {ev['charge_status']}")
            print(f"Charge mode:   {ev['charge_mode']}")
            print(f"Plug status:   {ev['plug_status']}")
            if ev['time_to_charge']:
                print(f"Time to full:  {ev['time_to_charge']} min")
            print(f"Location:      {ev['home_away']}")
            print(f"Coordinates:   {ev['latitude']}, {ev['longitude']}")
            print(f"Charge limit:  {ev['charge_limit_home']}% (home) / {ev['charge_limit_away']}% (away)")
            print(f"Climate:       {'ON' if ev['climate_active'] else 'OFF'}")
            print(f"Cabin temp:    {ev['cabin_temp_c']}°C")
            print(f"Interior temp: {ev['interior_temp_c']}°C")
            print(f"Odometer:      {ev['odometer_km']} km")
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
            print(f"Speed:     {gps.get('velocity', {}).get('value', 'N/A')} km/h")
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
        wait_command(
            api.remote_climate_on(vin, temp=args.temp, duration=args.duration),
            f"Climate settings ({args.temp}, {args.duration}min)",
        )

    elif args.command == "charge-limit":
        wait_command(
            api.set_charge_limit(vin, home=args.home, away=args.away),
            f"Charge limit ({args.home}% home, {args.away}% away)",
        )

    elif args.command == "trips":
        if args.all_pages:
            all_trips = []
            page = 1
            while True:
                data = api.get_trips(vin, month_start=args.month, page=page)
                payload = data.get("payload", {})
                all_trips.extend(payload.get("data", []))
                if page >= data.get("maxPage", 1):
                    break
                page += 1
            # Use fields from last response
            fields = payload.get("def", [])
            units = payload.get("unit", [])
        else:
            data = api.get_trips(vin, month_start=args.month, page=args.page)
            if args.json:
                print(json.dumps(data, indent=2))
                return
            payload = data.get("payload", {})
            fields = payload.get("def", [])
            units = payload.get("unit", [])
            all_trips = payload.get("data", [])
            print(f"Page {data.get('page', '?')}/{data.get('maxPage', '?')}")

        if not all_trips:
            print("No trips found.")
        else:
            for trip in all_trips:
                row = dict(zip(fields, trip))
                date = row.get("OneTripDate", "?")
                start = row.get("StartTime", "?")
                end = row.get("EndTime", "?")
                km = row.get("Mileage", "?")
                duration = row.get("DriveTime", "?")
                avg_speed = row.get("AveSpeed", "?")
                max_speed = row.get("MaxSpeed", "?")
                consumption = row.get("AveFuelEconomy", "?")
                print(f"  {date}  {start} -> {end}  "
                      f"{km} km  {duration} min  "
                      f"avg {avg_speed} km/h  max {max_speed} km/h  "
                      f"{consumption} L/100km")


if __name__ == "__main__":
    main()
