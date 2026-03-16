"""CLI entry point for pymyhondaplus."""

import argparse
import json
import logging
import os
import time
from pathlib import Path

from .api import DEFAULT_TOKEN_FILE, HondaAPI, extract_tokens_from_captures, parse_ev_status
from .auth import DEFAULT_DEVICE_KEY_FILE, DeviceKey, HondaAuth


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Honda Connect Europe (My Honda+) API client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  %(prog)s login -e user@example.com -p secret    Login with email/password
  %(prog)s --extract-tokens                        Extract tokens from mitmproxy capture
  %(prog)s -v JHMZC... status                      Get vehicle status (cached)
  %(prog)s -v JHMZC... status --fresh              Get fresh status from car
  %(prog)s -v JHMZC... location                    Get car GPS location
  %(prog)s -v JHMZC... lock                        Lock doors
  %(prog)s -v JHMZC... horn                        Flash lights & horn
  %(prog)s -v JHMZC... climate-start               Start climate control
  %(prog)s -v JHMZC... climate-stop                Stop climate control
  %(prog)s -v JHMZC... climate-settings --temp hotter --duration 30
  %(prog)s -v JHMZC... charge-limit --home 80 --away 90
""",
    )
    parser.add_argument("--extract-tokens", action="store_true",
                        help="Extract tokens from mitmproxy captured flows")
    parser.add_argument("--vin", "-v", default=os.environ.get("HONDA_VIN"),
                        help="Vehicle VIN (or set HONDA_VIN env var)")
    parser.add_argument("--fresh", action="store_true",
                        help="Request fresh data from car")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--user-info", action="store_true",
                        help="Show user info and vehicle list")
    parser.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_FILE,
                        help=f"Token file path (default: {DEFAULT_TOKEN_FILE})")
    parser.add_argument("--key-file", type=Path, default=DEFAULT_DEVICE_KEY_FILE,
                        help=f"Device key file path (default: {DEFAULT_DEVICE_KEY_FILE})")

    subparsers = parser.add_subparsers(dest="command")

    # login subcommand
    login_parser = subparsers.add_parser("login", help="Login with email/password")
    login_parser.add_argument("--email", "-e", required=True, help="Honda account email")
    login_parser.add_argument("--password", "-p", required=True, help="Honda account password")
    login_parser.add_argument("--locale", "-l", default="it", help="Locale (default: it)")

    # vehicle commands
    subparsers.add_parser("status", help="Get vehicle status")
    subparsers.add_parser("location", help="Get car GPS location")
    subparsers.add_parser("lock", help="Lock doors")
    subparsers.add_parser("unlock", help="Unlock doors")
    subparsers.add_parser("horn", help="Flash lights & horn")
    subparsers.add_parser("climate-start", help="Start climate control")
    subparsers.add_parser("climate-stop", help="Stop climate control")

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

    args = parser.parse_args()

    if args.extract_tokens:
        print("Extracting tokens from captured flows...")
        tokens = extract_tokens_from_captures()
        api = HondaAPI(token_file=args.token_file)
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
        device_key = DeviceKey(key_file=args.key_file)
        auth = HondaAuth(device_key=device_key)
        result = auth.full_login(args.email, args.password, locale=args.locale)

        print("\nLogin successful!")
        print(f"Access token: {result['access_token'][:50]}...")
        print(f"Refresh token: {result['refresh_token'][:50]}...")
        print(f"Expires in: {result.get('expires_in', 'N/A')}s")

        user_id = HondaAuth.extract_user_id(result["access_token"])
        api = HondaAPI(token_file=args.token_file)
        api.set_tokens(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            expires_in=result.get("expires_in", 3599),
            user_id=user_id,
        )
        print(f"\nTokens saved to {args.token_file}")
        return

    api = HondaAPI(token_file=args.token_file)

    if args.user_info:
        info = api.get_user_info()
        print(json.dumps(info, indent=2))
        return

    if not args.command:
        args.command = "status"

    if not args.vin:
        parser.print_help()
        return

    vin = args.vin

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
            print(f"Battery:       {ev['battery_level']}%")
            print(f"Range:         {ev['range_km']} km")
            print(f"Charge status: {ev['charge_status']}")
            print(f"Plug status:   {ev['plug_status']}")
            print(f"Location:      {ev['home_away']}")
            print(f"Coordinates:   {ev['latitude']}, {ev['longitude']}")
            print(f"Charge limit:  {ev['charge_limit_home']}% (home) / {ev['charge_limit_away']}% (away)")
            print(f"Climate:       {'ON' if ev['climate_active'] else 'OFF'}")
            print(f"Cabin temp:    {ev['cabin_temp_c']}°C")
            print(f"Odometer:      {ev['odometer_km']} km")
            print(f"Doors locked:  {ev['doors_locked']}")
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


if __name__ == "__main__":
    main()
