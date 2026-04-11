"""
Unofficial Honda Connect Europe API client.

Tested on Honda e. Should work with other Honda Connect Europe vehicles
(e:Ny1, ZR-V, CR-V, Civic, HR-V, Jazz 2020+) but these are untested.
"""

import os
import time
import logging
import threading
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
    vehicles: list = field(default_factory=list)  # list[Vehicle]

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
            data["vehicles"] = [
                v.to_dict() if isinstance(v, Vehicle) else v
                for v in self.vehicles
            ]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AuthTokens":
        """Deserialize from a dict."""
        fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if "vehicles" in fields:
            fields["vehicles"] = [
                Vehicle.from_dict(v) if isinstance(v, dict) else v
                for v in fields["vehicles"]
            ]
        return cls(**fields)


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


@dataclass
class VehicleCapabilities:
    """Feature capabilities reported by the Honda API for a vehicle."""
    remote_lock: bool = False
    remote_climate: bool = False
    remote_charge: bool = False
    remote_horn: bool = False
    digital_key: bool = False
    charge_schedule: bool = False
    climate_schedule: bool = False
    max_charge: bool = False
    car_finder: bool = False
    journey_history: bool = False
    send_poi: bool = False
    geo_fence: bool = False
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, cap_map: dict) -> "VehicleCapabilities":
        """Parse the vehicleCapability map from the API."""
        caps = cap_map.get("capabilities", {})

        def _active(key: str) -> bool:
            return caps.get(key, {}).get("featureStatus") == "active"

        return cls(
            remote_lock=_active("telematicsRemoteLockUnlock"),
            remote_climate=_active("telematicsRemoteClimate"),
            remote_charge=_active("telematicsRemoteCharge"),
            remote_horn=_active("telematicsRemoteHorn"),
            digital_key=_active("digitalKey"),
            charge_schedule=_active("telematicsRemoteChargeSchedule"),
            climate_schedule=_active("telematicsRemoteClimateSchedule"),
            max_charge=_active("telematicsMaxChargeSettings"),
            car_finder=_active("telematicsRemoteCarFinder"),
            journey_history=_active("telematicsJourneyHistory"),
            send_poi=_active("telematicsSendPoi"),
            geo_fence=_active("telematicsGeoFence"),
            raw=caps,
        )

    def to_dict(self) -> dict:
        return {
            "remote_lock": self.remote_lock,
            "remote_climate": self.remote_climate,
            "remote_charge": self.remote_charge,
            "remote_horn": self.remote_horn,
            "digital_key": self.digital_key,
            "charge_schedule": self.charge_schedule,
            "climate_schedule": self.climate_schedule,
            "max_charge": self.max_charge,
            "car_finder": self.car_finder,
            "journey_history": self.journey_history,
            "send_poi": self.send_poi,
            "geo_fence": self.geo_fence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VehicleCapabilities":
        if not data:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SubscriptionService:
    """A service included in a subscription package."""
    code: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        return {"code": self.code, "description": self.description}

    @classmethod
    def from_dict(cls, data: dict) -> "SubscriptionService":
        return cls(code=data.get("code", ""), description=data.get("description", ""))


@dataclass
class Subscription:
    """Subscription package info for a vehicle."""
    package_name: str = ""
    status: str = ""
    package_type: str = ""
    price: float = 0.0
    currency: str = ""
    payment_term: str = ""
    term: int = 0
    trial_term: int = 0
    renewal: bool = False
    start_date: str = ""
    end_date: str = ""
    next_payment_date: str = ""
    services: list[SubscriptionService] = field(default_factory=list)

    @classmethod
    def from_api(cls, packages: list) -> "Subscription | None":
        """Parse the first active packageInfo entry."""
        if not packages:
            return None
        p = packages[0]
        services = [
            SubscriptionService(code=s.get("code", ""), description=s.get("description", ""))
            for s in p.get("services", [])
        ]
        return cls(
            package_name=p.get("description", ""),
            status=p.get("billStatus", ""),
            package_type=p.get("packageType", ""),
            price=float(p.get("price", 0)),
            currency=p.get("currency1", ""),
            payment_term=p.get("paymentTerm", ""),
            term=int(p.get("term", 0)),
            trial_term=int(p.get("trialTerm", 0)),
            renewal=p.get("renewal", False),
            start_date=p.get("startDate", "").split("T")[0] if p.get("startDate") else "",
            end_date=p.get("endDate", "").split("T")[0] if p.get("endDate") else "",
            next_payment_date=p.get("nextPaymentDate", "").split("T")[0] if p.get("nextPaymentDate") else "",
            services=services,
        )

    def to_dict(self) -> dict:
        d: dict = {
            "package_name": self.package_name,
            "status": self.status,
            "package_type": self.package_type,
            "price": self.price,
            "currency": self.currency,
            "payment_term": self.payment_term,
            "term": self.term,
            "trial_term": self.trial_term,
            "renewal": self.renewal,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "next_payment_date": self.next_payment_date,
            "services": [s.to_dict() for s in self.services],
        }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Subscription":
        if not data:
            return cls()
        services = [SubscriptionService.from_dict(s) for s in data.get("services", [])]
        fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__ and k != "services"}
        return cls(**fields, services=services)


@dataclass
class UIConfiguration:
    """UI display hints from Honda for a vehicle."""
    hide_window_status: bool = False
    hide_rear_door_status: bool = False
    hide_internal_temperature: bool = False
    hide_climate_settings: bool = False
    show_plugin_warning_climate_schedule: bool = False

    @classmethod
    def from_api(cls, cfg: dict) -> "UIConfiguration":
        return cls(
            hide_window_status=cfg.get("hideWindowStatus", False),
            hide_rear_door_status=cfg.get("hideRearDoorStatus", False),
            hide_internal_temperature=cfg.get("shouldHideInternalTemperature", False),
            hide_climate_settings=cfg.get("shouldHideClimateSettingsButton", False),
            show_plugin_warning_climate_schedule=cfg.get("shouldDisplayPluginWarningForClimateSchedule", False),
        )

    def to_dict(self) -> dict:
        return {
            "hide_window_status": self.hide_window_status,
            "hide_rear_door_status": self.hide_rear_door_status,
            "hide_internal_temperature": self.hide_internal_temperature,
            "hide_climate_settings": self.hide_climate_settings,
            "show_plugin_warning_climate_schedule": self.show_plugin_warning_climate_schedule,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UIConfiguration":
        if not data:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class UserProfile:
    """User profile from the Honda account."""
    first_name: str = ""
    last_name: str = ""
    title: str = ""
    email: str = ""
    phone_number: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    postal_address: str = ""
    country: str = ""
    pref_language: str = ""
    pref_notification_setting: str = ""
    pref_notification_channels: list[str] = field(default_factory=list)
    subs_expiry: bool = False

    @classmethod
    def from_api(cls, data: dict) -> "UserProfile":
        return cls(
            first_name=data.get("firstName", ""),
            last_name=data.get("lastName", ""),
            title=data.get("title", ""),
            email=data.get("email", ""),
            phone_number=data.get("phoneNumber", ""),
            city=data.get("city", ""),
            state=data.get("state", ""),
            postal_code=data.get("postalCode", ""),
            postal_address=data.get("postalAddress", ""),
            country=data.get("country", ""),
            pref_language=data.get("prefLanguage", ""),
            pref_notification_setting=data.get("prefNotificationSetting", ""),
            pref_notification_channels=data.get("prefNotificationChannel", []),
            subs_expiry=data.get("subsExpiry", False),
        )


@dataclass
class Geofence:
    """Geofence configuration for a vehicle."""
    active: bool = False
    name: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    radius: float = 0.0
    schedule_type: str = ""
    processing: bool = False
    waiting_activate: bool = False
    waiting_deactivate: bool = False

    @classmethod
    def from_api(cls, data: dict) -> "Geofence | None":
        """Parse geofence config. Returns None if no geofence is set."""
        if data.get("activationEnable") == "disabled":
            return None
        setup = data.get("geoFenceSetup", {})
        coord = setup.get("gpsDetails", {}).get("coordinate", {})
        return cls(
            active=data.get("activationSetup") == "active",
            name=data.get("nickName", ""),
            latitude=coord.get("latitude", 0) / 3_600_000,
            longitude=coord.get("longitude", 0) / 3_600_000,
            radius=float(setup.get("radius", {}).get("value", 0)),
            schedule_type=data.get("schedule", {}).get("type", ""),
            processing=data.get("isCommandProcessing", False),
            waiting_activate=data.get("isWaitingForActivate", False),
            waiting_deactivate=data.get("isWaitingForDeactivate", False),
        )


@dataclass
class Vehicle:
    """A vehicle from the Honda account."""
    vin: str = ""
    name: str = ""
    plate: str = ""
    role: str = ""
    fuel_type: str = ""
    model_name: str = ""
    grade: str = ""
    model_year: str = ""
    category_code: str = ""
    registration_date: str = ""
    production_date: str = ""
    doors: int = 0
    transmission: str = ""
    weight: float = 0.0
    country_code: str = ""
    image_front: str = ""
    image_side: str = ""
    capabilities: VehicleCapabilities = field(default_factory=VehicleCapabilities)
    ui_config: UIConfiguration = field(default_factory=UIConfiguration)
    subscription: Subscription | None = None

    def __getitem__(self, key: str):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    @classmethod
    def from_api(cls, v: dict) -> "Vehicle":
        """Build a Vehicle from a vehiclesInfo entry."""
        ui_config = v.get("vehicleUIConfiguration", {})
        cap_map = v.get("vehicleCapability", {})
        prod = v.get("dateProduction", "")
        if prod and "T" in prod:
            prod = prod.split("T")[0]
        return cls(
            vin=v.get("vin", ""),
            name=v.get("vehicleNickName", ""),
            plate=v.get("vehicleRegNumber", ""),
            role=v.get("role", ""),
            fuel_type=v.get("fuelType", ""),
            model_name=ui_config.get("friendlyModelName", ""),
            grade=v.get("grade", ""),
            model_year=str(v.get("modelYear", "")),
            category_code=v.get("vehicleCategoryCode", ""),
            registration_date=v.get("registrationDate", ""),
            production_date=prod,
            doors=int(v.get("doors", 0)),
            transmission=v.get("transmission", ""),
            weight=float(v.get("weight", 0)),
            country_code=v.get("countryCode", ""),
            image_front=v.get("vehicleFront34ImageUrl", ""),
            image_side=v.get("vehicleSideImageUrl", ""),
            capabilities=VehicleCapabilities.from_api(cap_map),
            ui_config=UIConfiguration.from_api(ui_config),
            subscription=Subscription.from_api(v.get("packageInfo", [])),
        )

    def to_dict(self) -> dict:
        d: dict = {
            "vin": self.vin,
            "name": self.name,
            "plate": self.plate,
            "role": self.role,
            "fuel_type": self.fuel_type,
            "model_name": self.model_name,
            "grade": self.grade,
            "model_year": self.model_year,
            "category_code": self.category_code,
            "registration_date": self.registration_date,
            "production_date": self.production_date,
            "doors": self.doors,
            "transmission": self.transmission,
            "weight": self.weight,
            "country_code": self.country_code,
            "image_front": self.image_front,
            "image_side": self.image_side,
            "capabilities": self.capabilities.to_dict(),
            "ui_config": self.ui_config.to_dict(),
        }
        if self.subscription:
            d["subscription"] = self.subscription.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Vehicle":
        """Deserialize from storage. Handles both old 5-field and new formats."""
        caps = data.get("capabilities")
        ui = data.get("ui_config")
        sub = data.get("subscription")
        return cls(
            vin=data.get("vin", ""),
            name=data.get("name", ""),
            plate=data.get("plate", ""),
            role=data.get("role", ""),
            fuel_type=data.get("fuel_type", ""),
            model_name=data.get("model_name", ""),
            grade=data.get("grade", ""),
            model_year=data.get("model_year", ""),
            category_code=data.get("category_code", ""),
            registration_date=data.get("registration_date", ""),
            production_date=data.get("production_date", ""),
            doors=int(data.get("doors", 0)),
            transmission=data.get("transmission", ""),
            weight=float(data.get("weight", 0)),
            country_code=data.get("country_code", ""),
            image_front=data.get("image_front", ""),
            image_side=data.get("image_side", ""),
            capabilities=VehicleCapabilities.from_dict(caps) if caps else VehicleCapabilities(),
            ui_config=UIConfiguration.from_dict(ui) if ui else UIConfiguration(),
            subscription=Subscription.from_dict(sub) if sub else None,
        )


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
        self._lock = threading.Lock()
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
        with self._lock:
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
        """Refresh the access token via Honda's auth API.

        Thread-safe: acquires the lock and skips the refresh if another
        thread already refreshed since the caller last checked.
        """
        with self._lock:
            if not self.tokens.is_expired:
                return self.tokens
            return self._refresh_auth_locked()

    def _refresh_auth_locked(self) -> AuthTokens:
        """Refresh the access token. Caller must hold self._lock."""
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
        """Ensure we have a valid access token. Caller must hold self._lock."""
        if not self.tokens.access_token:
            raise HondaAuthError(401, "No tokens configured")
        if self.tokens.is_expired:
            self._refresh_auth_locked()

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make an authenticated API request. Thread-safe."""
        with self._lock:
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
                self._refresh_auth_locked()
                headers["authorization"] = f"Bearer {self.tokens.access_token}"
                resp = self.session.request(
                    method, f"{API_BASE}{path}", headers=headers, **kwargs,
                )
                if resp.status_code == 401:
                    raise HondaAuthError(
                        401, "Authentication failed after token refresh",
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
        if resp.status_code != 200:
            raise HondaAPIError(resp.status_code, resp.text)
        return resp.json()

    def get_user_profile(self, **kwargs) -> UserProfile:
        """Get the user profile (name, email, address, preferences)."""
        info = self.get_user_info(**kwargs)
        return UserProfile.from_api(info)

    def get_vehicles(self, **kwargs) -> list[Vehicle]:
        """Return list of vehicles with model info, images, and capabilities."""
        info = self.get_user_info(**kwargs)
        return [
            Vehicle.from_api(v)
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

    # -- Geofence --

    def get_geofence(self, vin: str) -> Geofence | None:
        """Get current geofence config. Returns None if no geofence is set."""
        resp = self._request("GET", f"/tsp/geo-fence-config?vin={vin}")
        if resp.status_code != 200:
            raise HondaAPIError(resp.status_code, resp.text)
        return Geofence.from_api(resp.json())

    def set_geofence(self, vin: str, latitude: float, longitude: float,
                     radius: float = 1.0, name: str = "Geofence") -> Geofence:
        """Create or update the geofence. Returns updated config.

        Args:
            vin: Vehicle VIN
            latitude: Center latitude in degrees
            longitude: Center longitude in degrees
            radius: Radius in km (default: 1.0)
            name: Geofence display name (default: "Geofence")
        """
        lat_mas = int(latitude * 3_600_000)
        lon_mas = int(longitude * 3_600_000)
        body = {
            "nickName": name,
            "activationSetup": "active",
            "geoFenceSetup": {
                "type": {"type": "circle", "mode": "inclusion"},
                "radius": {"value": radius, "unit": "km"},
                "gpsDetails": {
                    "coordinate": {
                        "latitude": lat_mas, "longitude": lon_mas,
                        "datum": "wgs84", "format": "mas",
                    }
                },
            },
            "schedule": {"type": "always"},
            "vin": vin,
        }
        resp = self._request("PUT", "/tsp/geo-fence-config", json=body)
        if resp.status_code != 200:
            raise HondaAPIError(resp.status_code, resp.text)
        return Geofence.from_api(resp.json())

    def wait_for_geofence(self, vin: str, timeout: int = 120,
                          poll_interval: float = 5.0) -> Geofence | None:
        """Poll geofence config until processing completes or timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            gf = self.get_geofence(vin)
            if gf is None or not gf.processing:
                return gf
            time.sleep(poll_interval)
        return gf

    def clear_geofence(self, vin: str) -> str:
        """Delete the geofence. Returns async command ID for polling."""
        resp = self._request("DELETE", f"/tsp/geo-fence-config?vin={vin}")
        if resp.status_code not in (200, 202):
            raise HondaAPIError(resp.status_code, resp.text)
        data = resp.json()
        uri = data.get("statusQueryGetUri", "")
        return uri.split("id=")[-1] if "id=" in uri else ""

    # -- Drivers --

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

@dataclass
class EVStatus:
    """Parsed EV status from a dashboard response."""
    battery_level: int = 0
    range_climate_on: int = 0
    range_climate_off: int = 0
    total_range: int = 0
    distance_unit: str = "km"
    speed_unit: str = "km/h"
    temp_unit: str = "c"
    charge_status: str = "unknown"
    plug_status: str = "unknown"
    home_away: str = "unknown"
    charge_limit_home: int = 0
    charge_limit_away: int = 0
    climate_active: bool = False
    cabin_temp: int = 0
    interior_temp: int = 0
    odometer: int = 0
    latitude: str = ""
    longitude: str = ""
    timestamp: str = ""
    doors_locked: bool = True
    all_doors_closed: bool = True
    all_windows_closed: bool = True
    lights_on: bool = False
    headlights: str = "unknown"
    parking_lights: str = "unknown"
    ignition: str = "unknown"
    charge_mode: str = "unknown"
    time_to_charge: int = 0
    hood_open: bool = False
    trunk_open: bool = False
    warning_lamps: list = field(default_factory=list)
    speed: float = 0.0
    climate_temp: str = "unknown"
    climate_duration: int = 0
    climate_defrost: bool = False

    def __getitem__(self, key: str):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)


def parse_ev_status(dashboard: dict) -> EVStatus:
    """Extract the most useful EV data from a dashboard response."""
    ev = dashboard.get("evStatus", {})
    gps = dashboard.get("gpsData", {})
    coord = gps.get("coordinate", {})
    distance_unit = ev.get("rangeUnit", dashboard.get("odometer", {}).get("unit", "km"))
    speed_unit = gps.get("velocity", {}).get("unit", f"{distance_unit}/h")
    temp_unit = dashboard.get("temperature", {}).get("cabin", {}).get("unit", "c")

    return EVStatus(
        battery_level=_safe_int(ev.get("soc", 0)),
        range_climate_on=_safe_int(ev.get("evRange", 0)),
        range_climate_off=_safe_int(ev.get("evRange", 0)) + _safe_int(ev.get("evClimateOffRange", 0)),
        total_range=_safe_int(ev.get("totalRange", 0)),
        distance_unit=distance_unit,
        speed_unit=speed_unit,
        temp_unit=temp_unit,
        charge_status=ev.get("chargeStatus", "unknown"),
        plug_status=ev.get("plugStatus", "unknown"),
        home_away=ev.get("homeAway", "unknown").lower(),
        charge_limit_home=_safe_int(ev.get("chargeLimitHome", 0)),
        charge_limit_away=_safe_int(ev.get("chargeLimitAway", 0)),
        climate_active=dashboard.get("climateControl", {}).get("status", {}).get("isActive", False),
        cabin_temp=_safe_int(dashboard.get("temperature", {}).get("cabin", {}).get("value", 0)),
        interior_temp=_safe_int(ev.get("intTemp", 0)),
        odometer=_safe_int(dashboard.get("odometer", {}).get("value", 0)),
        latitude=coord.get("latitude", ""),
        longitude=coord.get("longitude", ""),
        timestamp=dashboard.get("timestamp", ""),
        doors_locked=all(
            door.get("lockState") == "lock"
            for key, door in dashboard.get("doorStatus", {}).items()
            if "lockState" in door
        ),
        all_doors_closed=all(
            door.get("openState") == "closed"
            for door in dashboard.get("doorStatus", {}).values()
            if isinstance(door, dict)
        ),
        all_windows_closed=all(
            w.get("closeState") == "closed"
            for w in dashboard.get("windowStatus", {}).values()
            if isinstance(w, dict)
        ),
        lights_on=any(
            light.get("lightState") == "on"
            for light in dashboard.get("lightStatus", {}).values()
            if isinstance(light, dict)
        ),
        headlights=dashboard.get("lightStatus", {}).get("headlights", {}).get("lightState", "unknown"),
        parking_lights=dashboard.get("lightStatus", {}).get("parkingLights", {}).get("lightState", "unknown"),
        ignition=ev.get("igStatus", "unknown"),
        charge_mode=ev.get("chargeMode", "unknown"),
        time_to_charge=_safe_int(ev.get("timeToTargetSoc", 0)),
        hood_open=dashboard.get("doorStatus", {}).get("hood", {}).get("openState", "unknown") != "closed",
        trunk_open=dashboard.get("doorStatus", {}).get("trunk", {}).get("openState", "unknown") != "closed",
        warning_lamps=[
            msg.get("lampName", "")
            for msg in dashboard.get("warningLamps", {}).get("messages", [])
            if msg.get("condition") == "ON"
        ],
        speed=_safe_float(gps.get("velocity", {}).get("value", 0)),
        climate_temp={"05": "cooler", "04": "normal", "03": "hotter",
                      "cool": "cooler", "warm": "hotter"}.get(
            ev.get("acTempVal", "normal"), ev.get("acTempVal", "unknown")),
        climate_duration=_safe_int(ev.get("acDurationSetting", 0)),
        climate_defrost=ev.get("acDefAutoSetting", "").lower().startswith("def auto on"),
    )


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
