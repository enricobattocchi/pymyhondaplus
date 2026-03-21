"""
Unofficial Honda Connect Europe API client.

Tested on Honda e. Should work with other Honda Connect Europe vehicles
(e:Ny1, ZR-V, CR-V, Civic, HR-V, Jazz 2020+) but these are untested.
"""

import json
import os
import time
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

import requests

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


@dataclass
class AuthTokens:
    access_token: str = ""
    refresh_token: str = ""
    expires_at: float = 0
    personal_id: str = ""
    user_id: str = ""
    vehicles: list[dict] = None

    def __post_init__(self):
        if self.vehicles is None:
            self.vehicles = []

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


class HondaAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


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
                   user_id: str = "", vehicles: list[dict] = None):
        """Set tokens (from login or mitmproxy capture)."""
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
            raise HondaAPIError(401, "No refresh token")

        logger.info("Refreshing access token")
        resp = self.session.post(
            f"{API_BASE}/auth/isv-prod/refresh",
            json={"refreshToken": self.tokens.refresh_token},
        )

        if resp.status_code != 200:
            raise HondaAPIError(resp.status_code, resp.text)

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
            raise HondaAPIError(401, "No tokens configured")
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
        resp.raise_for_status()
        return resp.json()

    def get_vehicles(self, **kwargs) -> list[dict]:
        """Return list of vehicles with VIN, name, and plate."""
        info = self.get_user_info(**kwargs)
        return [
            {
                "vin": v["vin"],
                "name": v.get("vehicleNickName", ""),
                "plate": v.get("vehicleRegNumber", ""),
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
        resp.raise_for_status()
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

    def poll_command(self, command_id: str) -> dict:
        """Poll an async command status."""
        resp = self._request(
            "GET", f"/euw/tsp/async-command-status?id={command_id}",
        )
        return {"status_code": resp.status_code, "data": resp.json()}

    def get_dashboard(self, vin: str, language: str = "it", fresh: bool = False,
                      timeout: int = 60, poll_interval: int = 2) -> dict:
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

        command_id = self.request_dashboard_refresh(vin)
        if not command_id:
            logger.warning("No command ID, falling back to cached data")
            return self.get_dashboard_cached(vin, language)

        start = time.time()
        while time.time() - start < timeout:
            result = self.poll_command(command_id)
            if result["status_code"] == 200:
                break
            time.sleep(poll_interval)

        return self.get_dashboard_cached(vin, language)

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

    def remote_lock(self, vin: str) -> str:
        """Lock all doors."""
        return self._remote_command("remote-lock", vin, command="allLock")

    def remote_unlock(self, vin: str) -> str:
        """Unlock doors."""
        return self._remote_command("remote-lock", vin, command="doorUnlock")

    def remote_climate_on(self, vin: str, temp: str = "normal",
                          duration: int = 30) -> str:
        """Turn on climate control."""
        temp_map = {"cooler": "05", "normal": "04", "hotter": "03"}
        if temp not in temp_map:
            raise ValueError(f"temp must be one of {list(temp_map.keys())}")
        if duration not in (10, 20, 30):
            raise ValueError("duration must be 10, 20, or 30")

        return self._remote_command(
            "remote-climate-settings", vin,
            acDefSetting="autoOn",
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
        """Set charge limits for home and away locations."""
        self._ensure_auth()
        headers = {
            "authorization": f"Bearer {self.tokens.access_token}",
        }
        if self.tokens.personal_id:
            headers["x-app-personal-id"] = self.tokens.personal_id

        resp = self.session.put(
            f"{API_BASE}/tsp/maximum-charge-config",
            headers=headers,
            json={
                "vin": vin,
                "locationHome": {"maxCharge": home},
                "locationAway": {"maxCharge": away},
            },
        )
        if resp.status_code not in (200, 202):
            raise HondaAPIError(resp.status_code, resp.text)
        data = resp.json()
        status_url = data.get("statusQueryGetUri", "")
        return status_url.split("id=")[-1] if "id=" in status_url else ""

    def get_drivers(self, vin: str) -> dict:
        """Get drivers associated with the vehicle."""
        resp = self._request("GET", f"/tsp/drivers-by-vehicle?vin={vin}")
        resp.raise_for_status()
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
        resp.raise_for_status()
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
        resp = self._request(
            "GET",
            f"/tsp/journey-history-detail?vin={vin}"
            f"&fromDate={from_date}&toDate={to_date}&type={trip_type}",
        )
        resp.raise_for_status()
        return resp.json()


# -- Convenience helpers --

def parse_ev_status(dashboard: dict) -> dict:
    """Extract the most useful EV data from a dashboard response."""
    ev = dashboard.get("evStatus", {})
    gps = dashboard.get("gpsData", {})
    coord = gps.get("coordinate", {})

    return {
        "battery_level": int(ev.get("soc", 0)),
        "range_km": int(ev.get("evRange", 0)),
        "total_range_km": int(ev.get("totalRange", 0)),
        "charge_status": ev.get("chargeStatus", "unknown"),
        "plug_status": ev.get("plugStatus", "unknown"),
        "home_away": ev.get("homeAway", "unknown").lower(),
        "charge_limit_home": int(ev.get("chargeLimitHome", 0)),
        "charge_limit_away": int(ev.get("chargeLimitAway", 0)),
        "climate_active": dashboard.get("climateControl", {}).get("status", {}).get("isActive", False),
        "cabin_temp_c": int(dashboard.get("temperature", {}).get("cabin", {}).get("value", 0)),
        "interior_temp_c": int(ev.get("intTemp", 0)),
        "odometer_km": int(dashboard.get("odometer", {}).get("value", 0)),
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
        "time_to_charge": int(ev.get("timeToTargetSoc", 0)),
        "hood_open": dashboard.get("doorStatus", {}).get("hood", {}).get("openState", "unknown") != "closed",
        "trunk_open": dashboard.get("doorStatus", {}).get("trunk", {}).get("openState", "unknown") != "closed",
        "warning_lamps": [
            msg.get("lampName", "")
            for msg in dashboard.get("warningLamps", {}).get("messages", [])
            if msg.get("condition") == "ON"
        ],
        "speed_kmh": float(gps.get("velocity", {}).get("value", 0)),
    }


def extract_tokens_from_captures(capture_dir: Path = None) -> dict:
    """Extract tokens from mitmproxy captured flows."""
    if capture_dir is None:
        capture_dir = Path.cwd() / "captured_flows"

    import base64

    # Find complete-login response (has access_token + refresh_token)
    for f in sorted(capture_dir.glob("*.json"), reverse=True):
        data = json.loads(f.read_text())
        resp = data.get("response", {}).get("content", {})
        if isinstance(resp, dict) and "access_token" in resp and "refresh_token" in resp:
            req_headers = data.get("request", {}).get("headers", {})
            personal_id = req_headers.get("x-app-personal-id", "")

            token_parts = resp["access_token"].split(".")
            if len(token_parts) >= 2:
                payload = token_parts[1] + "=" * (4 - len(token_parts[1]) % 4)
                jwt_data = json.loads(base64.urlsafe_b64decode(payload))
                user_id = jwt_data.get("sub", "")
            else:
                user_id = ""

            return {
                "access_token": resp["access_token"],
                "refresh_token": resp["refresh_token"],
                "expires_in": resp.get("expires_in", 3599),
                "personal_id": personal_id,
                "user_id": user_id,
            }

    # Fall back: find any request with auth header + personal_id
    for f in sorted(capture_dir.glob("*.json"), reverse=True):
        data = json.loads(f.read_text())
        headers = data.get("request", {}).get("headers", {})
        auth = headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            token_parts = token.split(".")
            if len(token_parts) >= 2:
                payload = token_parts[1] + "=" * (4 - len(token_parts[1]) % 4)
                jwt_data = json.loads(base64.urlsafe_b64decode(payload))
                user_id = jwt_data.get("sub", "")
            else:
                user_id = ""

            return {
                "access_token": token,
                "refresh_token": "",
                "expires_in": 3599,
                "personal_id": headers.get("x-app-personal-id", ""),
                "user_id": user_id,
            }

    raise RuntimeError("No tokens found in captured flows")
