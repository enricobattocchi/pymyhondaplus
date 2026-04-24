"""Unofficial Honda Connect Europe (My Honda+) API client library."""

from .api import AuthTokens, CommandResult, EVStatus, Geofence, HondaAPI, HondaAPIError, HondaAuthError, SubscriptionService, Subscription, UIConfiguration, UserProfile, Vehicle, VehicleCapabilities, compute_trip_stats, parse_charge_schedule, parse_climate_schedule, parse_ev_status
from .auth import DeviceKey, HondaAuth, encrypt_request
from .storage import SecretStorage, get_storage
from .translations import TRANSLATIONS, get_translator

__all__ = [
    "AuthTokens",
    "CommandResult",
    "EVStatus",
    "Geofence",
    "Subscription",
    "SubscriptionService",
    "TRANSLATIONS",
    "UIConfiguration",
    "UserProfile",
    "Vehicle",
    "VehicleCapabilities",
    "HondaAPI",
    "HondaAPIError",
    "HondaAuthError",
    "compute_trip_stats",
    "get_translator",
    "parse_charge_schedule",
    "parse_climate_schedule",
    "parse_ev_status",
    "DeviceKey",
    "HondaAuth",
    "encrypt_request",
    "SecretStorage",
    "get_storage",
]
