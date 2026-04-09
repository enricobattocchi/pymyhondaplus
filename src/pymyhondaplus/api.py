"""
Unofficial Honda Connect Europe API client.

Tested on Honda e. Should work with other Honda Connect Europe vehicles
(e:Ny1, ZR-V, CR-V, Civic, HR-V, Jazz 2020+) but these are untested.
"""

import os
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

if TYPE_CHECKING:
    from .storage import SecretStorage

logger = logging.getLogger(__name__)

API_BASE = "https://mobile-api.connected.honda-eu.com"

DEFAULT_HEADERS = {
    "user-agent": "okhttp/4.12.0",
    "accept-encoding": "gzip",
    "x-app-device-os": "android",
    "x-app-device-osversion": "26",
    "x-app-device-model": "HomeAssistant",
}

DEFAULT_TOKEN_FILE = Path(os.environ.get(
    "HONDA_TOKEN_FILE",
    Path.home() / ".honda_tokens.json",
))


def _safe_float(value, default: float = 0.0) -> float:
    """Convert a numeric-looking value to float, returning default on bad input."""
    try:
        if isinstance(value, str):
            value = value.strip()
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value, default: int = 0) -> int:
    """Convert a numeric-looking value to int, tolerating float-like strings."""
    return int(_safe_float(value, float(default)))


def _format_hhmm(raw: str) -> str:
    """Format an HHMM-ish string as HH:MM, falling back to 00:00."""
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if len(digits) < 4:
        digits = digits.zfill(4)
    return f"{digits[:2]}:{digits[2:4]}"


@dataclass
class AuthTokens:
    access_token: str = ""
    refresh_token: str = ""
    expires_at: float = 0
    personal_id: str = ""
    user_id: str = ""
    vehicles: list[dict] = field(default_factory=list)

    @property
    def default_vin(self) -> str:
        """Return the VIN if exactly one vehicle is stored, else empty string."""
        return self.vehicles[0]["vin"] if len(self.vehicles) == 1 else ""

    def resolve_vin(self, identifier: str) -> str:
        """Resolve a VIN, nickname, or plate to a VIN. Returns empty string if no match."""
        id_lower = identifier.lower()
        for v in self.vehicles:
            if v["vin"].lower() == id_lower:
                return v["vin"]
            if v.get("name", "").lower() == id_lower:
                return v["vin"]
            if v.get("plate", "").lower() == id_lower:
                return v["vin"]
        return ""

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 60  # 1 min buffer

    def to_dict(self) -> dict:
        """Serialize to a dict for storage."""
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "personal_id": self.personal_id,
            "user_id": self.user_id,
        }
        if self.vehicles:
            data["vehicles"] = self.vehicles
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AuthTokens":
        """Deserialize from a dict."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CommandResult:
    """Parsed result of an async command poll."""
    complete: bool
    status: str  # "pending", "success", or server-provided status
    timed_out: bool = False
    reason: str | None = None
    command_id: str = ""
    feature: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_poll(cls, status_code: int, data: dict) -> "CommandResult":
        if status_code != 200:
            return cls(complete=False, status="pending", raw=data)
        output = data.get("output") or {}
        return cls(
            complete=True,
            status=output.get("RequestStatus", "unknown"),
            timed_out=output.get("functionTimedOut", False),
            reason=output.get("StatusReason"),
            command_id=output.get("RequestId", ""),
            feature=output.get("NotificationFeature", ""),
            raw=data,
        )

    @classmethod
    def pending_timeout(cls) -> "CommandResult":
        return cls(complete=False, status="pending", timed_out=True)

    @property
    def success(self) -> bool:
        return self.complete and self.status == "success" and not self.timed_out


class HondaAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class HondaAuthError(HondaAPIError):
    """Raised for authentication failures (login, device registration, etc.)."""
    pass


class HondaAPI:
    """Unofficial Honda Connect Europe API client.

    Args:
        storage: SecretStorage backend for token persistence. None disables persistence.
        token_file: Deprecated — use storage instead. Kept for backward compatibility.
    """

    def __init__(self, storage: Optional["SecretStorage"] = None,
                 token_file: Optional[Path] = None):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=None,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self._storage = storage

        # Backward compatibility: token_file without storage
        if storage is None and token_file is not None:
            from .storage import PlainFileStorage
            from .auth import DEFAULT_DEVICE_KEY_FILE
            self._storage = PlainFileStorage(token_file, DEFAULT_DEVICE_KEY_FILE)

        if self._storage is not None:
            data = self._storage.load_tokens()
            self.tokens = AuthTokens.from_dict(data) if data else AuthTokens()
        else:
            self.tokens = AuthTokens()

    def _save_tokens(self):
        """Persist tokens via storage backend if available."""
        if self._storage is not None:
            self._storage.save_tokens(self.tokens.to_dict())

    def set_tokens(self, access_token: str, refresh_token: str,
                   expires_in: int = 3599, personal_id: str = "",
                   user_id: str = "", vehicles: list[dict] | None = None):
        """Set authentication tokens."""
        self.tokens = AuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=time.time() + expires_in,
            personal_id=personal_id,
            user_id=user_id,
            vehicles=vehicles or [],
        )
        self._save_tokens()

    def refresh_auth(self) -> AuthTokens:
        """Refresh the access token via Honda's auth API."""
        if not self.tokens.refresh_token:
            raise HondaAuthError(401, "No refresh token")

        logger.info("Refreshing access token")
        resp = self.session.post(
            f"{API_BASE}/auth/isv-prod/refresh",
            json={"refreshToken": self.tokens.refresh_token},
        )

        if resp.status_code != 200:
            raise HondaAuthError(resp.status_code, resp.text)

        data = resp.json()
        self.tokens.access_token = data["access_token"]
        self.tokens.refresh_token = data.get("refresh_token", self.tokens.refresh_token)
        self.tokens.expires_at = time.time() + data.get("expires_in", 3599)
        self._save_tokens()
        logger.info("Token refreshed, expires in %ds", data.get("expires_in", 3599))
        return self.tokens

    def _ensure_auth(self):
        """Ensure we have a valid access token."""
        if not self.tokens.access_token:
            raise HondaAuthError(401, "No tokens configured")
        if self.tokens.is_expired:
            self.refresh_auth()

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make an authenticated API request."""
        self._ensure_auth()

        headers = {
            "authorization": f"Bearer {self.tokens.access_token}",
        }
        if self.tokens.personal_id:
            headers["x-app-personal-id"] = self.tokens.personal_id

        resp = self.session.request(
            method, f"{API_BASE}{path}", headers=headers, **kwargs,
        )

        if resp.status_code == 401:
            self.refresh_auth()
            headers["authorization"] = f"Bearer {self.tokens.access_token}"
            resp = self.session.request(
                method, f"{API_BASE}{path}", headers=headers, **kwargs,
            )
            if resp.status_code == 401:
                raise HondaAuthError(401, "Authentication failed after token refresh")

        return resp

    # -- Vehicle data --

    def get_user_info(self, user_id: str = "", language: str = "it",
                      country: str = "IT") -> dict:
        """Get user profile and vehicle info."""
        uid = user_id or self.tokens.user_id
        resp = self._request(
            "GET",
            f"/user/get-login-info?userid={uid}"
            f"&agreementType=1&country={country}&language={language}",
        )
        if resp.status_code != 200:
            raise HondaAPIError(resp.status_code, resp.text)
        return resp.json()

    def get_vehicles(self, **kwargs) -> list[dict]:
        """Return list of vehicles with VIN, name, and plate."""
        info = self.get_user_info(**kwargs)
        return [
            {
                "vin": v["vin"],
                "name": v.get("vehicleNickName", ""),
                "plate": v.get("vehicleRegNumber", ""),
                "role": v.get("role", ""),
                "fuel_type": v.get("fuelType", ""),
            }
            for v in info.get("vehiclesInfo", [])
            if "vin" in v
        ]

    def get_vins(self, **kwargs) -> list[str]:
        """Return list of VINs associated with the account."""
        return [v["vin"] for v in self.get_vehicles(**kwargs)]

    def get_dashboard_cached(self, vin: str, language: str = "it") -> dict:
        """Get the most recently cached dashboard data (fast, no car wake-up)."""
        resp = self._request(
            "GET", f"/tsp/dashboard-latest?vin={vin}&languageCode={language}",
        )
        if resp.status_code != 200:
            raise HondaAPIError(resp.status_code, resp.text)
        return resp.json()

    def request_dashboard_refresh(self, vin: str) -> str:
        """
        Request fresh data from the car (wakes up the TCU).
        Returns the async command ID to poll with poll_command().
        """
        resp = self._request("POST", f"/tsp/dashboard?vin={vin}")
        if resp.status_code not in (200, 202):
            raise HondaAPIError(resp.status_code, resp.text)

        data = resp.json()
        status_url = data.get("statusQueryGetUri", "")
        return status_url.split("id=")[-1] if "id=" in status_url else ""

    def poll_command(self, command_id: str) -> CommandResult:
        """Poll an async command status. Returns a parsed CommandResult."""
        resp = self._request(
            "GET", f"/euw/tsp/async-command-status?id={command_id}",
        )
        return CommandResult.from_poll(resp.status_code, resp.json())

    def wait_for_command(self, command_id: str,
                         timeout: int = 60,
                         poll_interval: float = 1.5) -> CommandResult:
        """Poll until a command completes or times out.

        Returns a CommandResult with details about the outcome.
        """
        if not command_id:
            return CommandResult(complete=False, status="no_command_id")

        start = time.time()
        while time.time() - start < timeout:
            result = self.poll_command(command_id)
            if result.complete:
                if not result.success:
                    logger.debug("Command %s finished: status=%s timedOut=%s reason=%s",
                                 command_id, result.status, result.timed_out, result.reason)
                return result
            time.sleep(poll_interval)

        logger.warning("Gave up polling command %s after %ds", command_id, timeout)
        return CommandResult.pending_timeout()

    def get_dashboard(self, vin: str, language: str = "it", fresh: bool = False,
                      timeout: int = 90, poll_interval: float = 1.5) -> dict:
        """
        Get full dashboard data.

        Args:
            vin: Vehicle Identification Number
            language: Language code for messages
            fresh: If True, request fresh data from car (slower, wakes TCU)
            timeout: Max seconds to wait for fresh data
            poll_interval: Seconds between polls
        """
        if not fresh:
            return self.get_dashboard_cached(vin, language)

        result = self.refresh_dashboard(vin, timeout, poll_interval)
        if not result.success:
            logger.debug("Dashboard refresh did not succeed (status=%s), using cached data",
                         result.status)

        return self.get_dashboard_cached(vin, language)

    def refresh_dashboard(self, vin: str, timeout: int = 90,
                          poll_interval: float = 1.5) -> CommandResult:
        """Request fresh data from car and wait for completion.

        Returns the CommandResult (check .success to see if the car responded).
        """
        command_id = self.request_dashboard_refresh(vin)
        if not command_id:
            logger.warning("No command ID returned")
            return CommandResult(complete=False, status="no_command_id")
        return self.wait_for_command(command_id, timeout, poll_interval)

    # -- Location --

    def request_car_location(self, vin: str) -> str:
        """Request fresh car location (async, wakes TCU). Returns command ID."""
        return self._remote_command("car-location", vin)

    # -- Remote commands --

    def _remote_command(self, endpoint: str, vin: str, **json_body) -> str:
        """Send a remote command, return the async command ID."""
        kwargs = {"json": json_body} if json_body else {}
        resp = self._request("POST", f"/tsp/{endpoint}?vin={vin}", **kwargs)
        if resp.status_code not in (200, 202):
            raise HondaAPIError(resp.status_code, resp.text)
        data = resp.json()
        status_url = data.get("statusQueryGetUri", "")
        return status_url.split("id=")[-1] if "id=" in status_url else ""

    def _async_put_command(self, path: str, json_body: dict) -> str:
        """Send an async PUT command, return the command ID."""
        resp = self._request("PUT", path, json=json_body)
        if resp.status_code not in (200, 202):
            raise HondaAPIError(resp.status_code, resp.text)
        data = resp.json()
        status_url = data.get("statusQueryGetUri", "")
        return status_url.split("id=")[-1] if "id=" in status_url else ""

    def remote_lock(self, vin: str) -> str:
        """Lock all doors."""
        return self._remote_command("remote-lock", vin, command="allLock")

    def remote_unlock(self, vin: str) -> str:
        """Unlock doors."""
        return self._remote_command("remote-lock", vin, command="doorUnlock")

    def set_climate_settings(self, vin: str, temp: str = "normal",
                             duration: int = 30, defrost: bool = True) -> str:
        """Configure climate control settings (temperature, duration, defrost)."""
        temp_map = {"cooler": "05", "normal": "04", "hotter": "03"}
        if temp not in temp_map:
            raise ValueError(f"temp must be one of {list(temp_map.keys())}")
        if duration not in (10, 20, 30):
            raise ValueError("duration must be 10, 20, or 30")

        return self._remote_command(
            "remote-climate-settings", vin,
            acDefSetting="autoOn" if defrost else "autoOff",
            acTempVal=temp_map[temp],
            acDurationSetting=str(duration),
            temperature=0,
            temperatureMode="simple",
        )

    def remote_climate_start(self, vin: str) -> str:
        """Start climate control (uses previously configured settings)."""
        return self._remote_command(
            "remote-climate", vin,
            command="start",
            temperatureMode="specific",
            temperature=0,
            autoDefrosterSetting="autoOn",
        )

    def remote_climate_stop(self, vin: str) -> str:
        """Stop climate control."""
        return self._remote_command("remote-climate", vin, command="stop")

    def remote_horn_lights(self, vin: str) -> str:
        """Activate horn and lights."""
        return self._remote_command("remote-horn-light", vin, command="horn")

    def remote_charge_start(self, vin: str) -> str:
        """Start charging."""
        return self._remote_command("remote-charge", vin, command="start")

    def remote_charge_stop(self, vin: str) -> str:
        """Stop charging."""
        return self._remote_command("remote-charge", vin, command="stop")

    def set_charge_limit(self, vin: str, home: int = 80, away: int = 90) -> str:
        """Set charge limits for home and away locations.

        Valid values: 80, 85, 90, 95, 100.
        """
        valid = (80, 85, 90, 95, 100)
        if home not in valid or away not in valid:
            raise ValueError(f"Charge limits must be one of {valid}")
        return self._async_put_command(
            "/tsp/maximum-charge-config",
            {"vin": vin, "locationHome": {"maxCharge": home}, "locationAway": {"maxCharge": away}},
        )

    def get_charge_schedule(self, vin: str, fresh: bool = False) -> list[dict]:
        """Get charge prohibition schedule from dashboard.

        Args:
            vin: Vehicle VIN
            fresh: If True, request fresh data from car (wakes TCU).

        Returns:
            List of up to 2 schedule rules, each with keys:
            - enabled: bool
            - days: list of day abbreviations (e.g. ["mon", "tue"])
            - location: "all" or "home"
            - start_time: "HH:MM"
            - end_time: "HH:MM"
        """
        dashboard = self.get_dashboard(vin, fresh=fresh)
        return parse_charge_schedule(dashboard)

    def set_charge_schedule(self, vin: str, rules: list[dict]) -> str:
        """Set charge prohibition schedule (up to 2 rules).

        Args:
            vin: Vehicle VIN
            rules: List of up to 2 dicts, each with:
                - days: comma-separated day string or list (e.g. "mon,tue,wed" or ["mon","tue","wed"])
                - location: "all" or "home"
                - start_time: "HH:MM" or "HHMM"
                - end_time: "HH:MM" or "HHMM"
                Pass an empty list or rules with enabled=False to clear.

        Returns:
            Async command ID for polling.
        """
        settings = []
        for i in range(2):
            if i < len(rules) and rules[i].get("enabled", True):
                r = rules[i]
                days = r.get("days", "")
                if isinstance(days, list):
                    days = ",".join(days)
                start = r.get("start_time", "0000").replace(":", "")
                end = r.get("end_time", "0000").replace(":", "")
                settings.append({
                    "chargeProhibitionDayOfWeek": days,
                    "chargeProhibitionTimerCommand": "time",
                    "chargeProhibitionLocation": r.get("location", "home"),
                    "chargeProhibitionTimerOption": {
                        "chargeProhibitionStartTime": start,
                        "chargeProhibitionEndTime": end,
                    },
                })
            else:
                settings.append({
                    "chargeProhibitionDayOfWeek": "",
                    "chargeProhibitionTimerCommand": "off",
                    "chargeProhibitionLocation": "home",
                    "chargeProhibitionTimerOption": {
                        "chargeProhibitionStartTime": "0000",
                        "chargeProhibitionEndTime": "0000",
                    },
                })

        return self._async_put_command(
            "/tsp/charge-prohibition-schedule",
            {"vin": vin, "chargeProhibitionTimerSettings": settings},
        )

    def get_climate_schedule(self, vin: str, fresh: bool = False) -> list[dict]:
        """Get climate schedule from dashboard.

        Args:
            vin: Vehicle VIN
            fresh: If True, request fresh data from car (wakes TCU).

        Returns:
            List of up to 7 schedule slots, each with keys:
            - enabled: bool
            - days: list of day abbreviations
            - start_time: "HH:MM"
        """
        dashboard = self.get_dashboard(vin, fresh=fresh)
        return parse_climate_schedule(dashboard)

    def set_climate_schedule(self, vin: str, rules: list[dict]) -> str:
        """Set climate schedule (up to 7 slots).

        Args:
            vin: Vehicle VIN
            rules: List of up to 7 dicts, each with:
                - days: comma-separated day string or list
                - start_time: "HH:MM" or "HHMM"
                Pass an empty list or rules with enabled=False to clear.

        Returns:
            Async command ID for polling.
        """
        settings = []
        for i in range(7):
            if i < len(rules) and rules[i].get("enabled", True):
                r = rules[i]
                days = r.get("days", "")
                if isinstance(days, list):
                    days = ",".join(days)
                start = r.get("start_time", "0000").replace(":", "")
                settings.append({
                    "acDayOfWeek": days,
                    "acTimerCommand": "timer",
                    "acTimerOption": {"acStartTime1": start},
                })
            else:
                settings.append({
                    "acDayOfWeek": "",
                    "acTimerCommand": "off",
                    "acTimerOption": {"acStartTime1": "0000"},
                })

        return self._async_put_command(
            "/tsp/remote-climate-schedule",
            {"vin": vin, "acTimerSettings": settings},
        )

    def get_drivers(self, vin: str) -> dict:
        """Get drivers associated with the vehicle."""
        resp = self._request("GET", f"/tsp/drivers-by-vehicle?vin={vin}")
        if resp.status_code != 200:
            raise HondaAPIError(resp.status_code, resp.text)
        return resp.json()

    def get_trips(self, vin: str, month_start: str = "", page: int = 1) -> dict:
        """Get trip list for a month.

        Args:
            vin: Vehicle VIN
            month_start: First day of month in ISO 8601 (e.g. "2026-03-01T00:00:00.000Z").
                         Defaults to current month.
            page: Page number (1-based)
        """
        if not month_start:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime(
                "%Y-%m-%dT%H:%M:%S.000Z")
        import urllib.parse
        encoded_month = urllib.parse.quote(month_start, safe="")
        resp = self._request(
            "GET",
            f"/tsp/journey-history?vin={vin}&monthStart={encoded_month}&page={page}",
        )
        if resp.status_code != 200:
            raise HondaAPIError(resp.status_code, resp.text)
        return resp.json()

    def get_trip_detail(self, vin: str, from_date: str, to_date: str,
                        trip_type: str = "end") -> dict:
        """Get GPS detail for a specific trip.

        Args:
            vin: Vehicle VIN
            from_date: Trip start time in ISO 8601
            to_date: Trip end time in ISO 8601
            trip_type: "start" or "end" (which end of the trip to get points for)
        """
        import urllib.parse
        enc_from = urllib.parse.quote(from_date, safe="")
        enc_to = urllib.parse.quote(to_date, safe="")
        resp = self._request(
            "GET",
            f"/tsp/journey-history-detail?vin={vin}"
            f"&fromDate={enc_from}&toDate={enc_to}&type={trip_type}",
        )
        if resp.status_code != 200:
            raise HondaAPIError(resp.status_code, resp.text)
        return resp.json()
    def get_all_trips(self, vin: str, month_start: str = "",
                       ref_date: str = "") -> list[dict]:
        """Fetch all pages of trips for a month and return parsed trip dicts.

        Args:
            vin: Vehicle VIN
            month_start: First day of month in ISO 8601. Defaults to current month.
            ref_date: If given (YYYY-MM-DD), only return trips matching this date.
                      The month is derived automatically, so month_start is ignored.

        Returns:
            List of dicts with field names as keys (e.g. OneTripDate, Mileage, etc.)
        """
        if ref_date:
            # Derive month_start from ref_date
            month_start = ref_date[:7] + "-01T00:00:00.000Z"

        all_trips = []
        fields = []
        page = 1
        while True:
            data = self.get_trips(vin, month_start=month_start, page=page)
            payload = data.get("payload", {})
            fields = payload.get("def", [])
            all_trips.extend(payload.get("data", []))
            if page >= data.get("maxPage", 1):
                break
            page += 1
        rows = [dict(zip(fields, trip)) for trip in all_trips]

        if ref_date:
            rows = [r for r in rows if r.get("OneTripDate", "").startswith(ref_date[:10])]
        return rows

    def get_trip_locations(self, vin: str, start_time: str,
                           end_time: str) -> dict:
        """Get start and end GPS coordinates for a trip.

        Args:
            vin: Vehicle VIN
            start_time: Trip start time in ISO 8601
            end_time: Trip end time in ISO 8601

        Returns:
            Dict with start_lat, start_lon, start_dir, end_lat, end_lon, end_dir.
        """
        result = {}
        for prefix, trip_type in [("start", "start"), ("end", "end")]:
            detail = self.get_trip_detail(vin, start_time, end_time, trip_type)
            data = detail.get("payload", {}).get("data", [[]])[0]
            fields = detail.get("payload", {}).get("def", [])
            row = dict(zip(fields, data))
            result[f"{prefix}_lat"] = row.get("lat")
            result[f"{prefix}_lon"] = row.get("lon")
            result[f"{prefix}_dir"] = row.get("dir")
            result[f"{prefix}_time"] = row.get("date")
        return result


# -- Convenience helpers --

def parse_ev_status(dashboard: dict) -> dict:
    """Extract the most useful EV data from a dashboard response."""
    ev = dashboard.get("evStatus", {})
    gps = dashboard.get("gpsData", {})
    coord = gps.get("coordinate", {})
    distance_unit = ev.get("rangeUnit", dashboard.get("odometer", {}).get("unit", "km"))
    speed_unit = gps.get("velocity", {}).get("unit", f"{distance_unit}/h")
    temp_unit = dashboard.get("temperature", {}).get("cabin", {}).get("unit", "c")

    return {
        "battery_level": _safe_int(ev.get("soc", 0)),
        "range": _safe_int(ev.get("evRange", 0)),
        "total_range": _safe_int(ev.get("totalRange", 0)),
        "distance_unit": distance_unit,
        "speed_unit": speed_unit,
        "temp_unit": temp_unit,
        "charge_status": ev.get("chargeStatus", "unknown"),
        "plug_status": ev.get("plugStatus", "unknown"),
        "home_away": ev.get("homeAway", "unknown").lower(),
        "charge_limit_home": _safe_int(ev.get("chargeLimitHome", 0)),
        "charge_limit_away": _safe_int(ev.get("chargeLimitAway", 0)),
        "climate_active": dashboard.get("climateControl", {}).get("status", {}).get("isActive", False),
        "cabin_temp": _safe_int(dashboard.get("temperature", {}).get("cabin", {}).get("value", 0)),
        "interior_temp": _safe_int(ev.get("intTemp", 0)),
        "odometer": _safe_int(dashboard.get("odometer", {}).get("value", 0)),
        "latitude": coord.get("latitude", ""),
        "longitude": coord.get("longitude", ""),
        "timestamp": dashboard.get("timestamp", ""),
        "doors_locked": all(
            door.get("lockState") == "lock"
            for key, door in dashboard.get("doorStatus", {}).items()
            if "lockState" in door
        ),
        "all_doors_closed": all(
            door.get("openState") == "closed"
            for door in dashboard.get("doorStatus", {}).values()
            if isinstance(door, dict)
        ),
        "all_windows_closed": all(
            w.get("closeState") == "closed"
            for w in dashboard.get("windowStatus", {}).values()
            if isinstance(w, dict)
        ),
        "lights_on": any(
            light.get("lightState") == "on"
            for light in dashboard.get("lightStatus", {}).values()
            if isinstance(light, dict)
        ),
        "headlights": dashboard.get("lightStatus", {}).get("headlights", {}).get("lightState", "unknown"),
        "parking_lights": dashboard.get("lightStatus", {}).get("parkingLights", {}).get("lightState", "unknown"),
        "ignition": ev.get("igStatus", "unknown"),
        "charge_mode": ev.get("chargeMode", "unknown"),
        "time_to_charge": _safe_int(ev.get("timeToTargetSoc", 0)),
        "hood_open": dashboard.get("doorStatus", {}).get("hood", {}).get("openState", "unknown") != "closed",
        "trunk_open": dashboard.get("doorStatus", {}).get("trunk", {}).get("openState", "unknown") != "closed",
        "warning_lamps": [
            msg.get("lampName", "")
            for msg in dashboard.get("warningLamps", {}).get("messages", [])
            if msg.get("condition") == "ON"
        ],
        "speed": _safe_float(gps.get("velocity", {}).get("value", 0)),
        "climate_temp": {"05": "cooler", "04": "normal", "03": "hotter",
                         "cool": "cooler", "warm": "hotter"}.get(
            ev.get("acTempVal", "normal"), ev.get("acTempVal", "unknown")),
        "climate_duration": _safe_int(ev.get("acDurationSetting", 0)),
        "climate_defrost": ev.get("acDefAutoSetting", "").lower().startswith("def auto on"),
    }


def parse_charge_schedule(dashboard: dict) -> list[dict]:
    """Parse charge prohibition schedule from a dashboard response."""
    ev = dashboard.get("evStatus", {})
    raw = ev.get("chargeProhibitionTimerSettings", [])
    rules = []
    for entry in raw:
        cmd = entry.get("chargeProhibitionTimerCommand", "off").lower()
        enabled = cmd not in ("off", "")
        days_str = entry.get("chargeProhibitionDayOfWeek", "")
        days = [d.strip() for d in days_str.split(",") if d.strip()] if days_str else []
        opts = entry.get("chargeProhibitionTimerOption", {})
        rules.append({
            "enabled": enabled,
            "days": days,
            "location": entry.get("chargeProhibitionLocation", "home").lower(),
            "start_time": _format_hhmm(opts.get("chargeProhibitionStartTime", "0000")),
            "end_time": _format_hhmm(opts.get("chargeProhibitionEndTime", "0000")),
        })
    return rules


def parse_climate_schedule(dashboard: dict) -> list[dict]:
    """Parse climate schedule from a dashboard response."""
    ev = dashboard.get("evStatus", {})
    raw = ev.get("acTimerSettings", [])
    rules = []
    for entry in raw:
        cmd = entry.get("acTimerCommand", "off").lower()
        enabled = cmd not in ("off", "")
        days_str = entry.get("acDayOfWeek", "")
        days = [d.strip() for d in days_str.split(",") if d.strip() and d.strip() != "unknown"] if days_str else []
        opts = entry.get("acTimerOption", {})
        rules.append({
            "enabled": enabled,
            "days": days,
            "start_time": _format_hhmm(opts.get("acStartTime1", "0000")),
        })
    return rules


def compute_trip_stats(rows: list[dict], period: str = "month",
                       fuel_type: str = "", distance_unit: str = "km") -> dict:
    """Compute aggregated statistics from a list of trip dicts.

    Args:
        rows: List of trip dicts (as returned by get_all_trips).
        period: Label for the period (e.g. "day", "week", "month").
        fuel_type: Vehicle fuel type (e.g. "E" for electric). Used to set consumption_unit.
        distance_unit: Distance unit from the vehicle (e.g. "km" or "miles").

    Returns:
        Dict with aggregated stats.
    """
    count = len(rows)
    total_km = sum(_safe_float(r.get("Mileage")) for r in rows)
    total_min = sum(_safe_float(r.get("DriveTime")) for r in rows)
    avg_speed = sum(_safe_float(r.get("AveSpeed")) for r in rows) / count if count else 0
    max_speed = max((_safe_float(r.get("MaxSpeed")) for r in rows), default=0)

    if total_km > 0:
        avg_consumption = sum(
            _safe_float(r.get("AveFuelEconomy")) * _safe_float(r.get("Mileage"))
            for r in rows
        ) / total_km
    else:
        avg_consumption = 0.0

    actual_dates = sorted(set(r.get("OneTripDate", "")[:10] for r in rows))
    speed_unit = f"{distance_unit}/h"
    return {
        "period": period,
        "start_date": actual_dates[0] if actual_dates else "",
        "end_date": actual_dates[-1] if actual_dates else "",
        "trips": count,
        "total_distance": round(total_km, 1),
        "total_minutes": round(total_min, 1),
        "avg_distance_per_trip": round(total_km / count, 1) if count else 0,
        "avg_min_per_trip": round(total_min / count, 1) if count else 0,
        "avg_speed": round(avg_speed, 1),
        "max_speed": round(max_speed, 1),
        "avg_consumption": round(avg_consumption, 1),
        "distance_unit": distance_unit,
        "speed_unit": speed_unit,
        "consumption_unit": "kWh/100km" if fuel_type == "E" else "L/100km",
    }
