"""Tests for capability checks on API methods."""

import time

import pytest

from pymyhondaplus.api import AuthTokens, HondaAPI, Vehicle, VehicleCapabilities


def _make_api_with_vehicle(**cap_overrides):
    """Create a HondaAPI with a vehicle that has specific capabilities."""
    api = HondaAPI()
    api.tokens = AuthTokens(
        access_token="tok",
        refresh_token="ref",
        expires_at=time.time() + 3600,
    )
    caps = VehicleCapabilities(**cap_overrides)
    vehicle = Vehicle(vin="VIN123", name="Test", capabilities=caps)
    api.tokens.vehicles = [vehicle]
    return api


def _make_api_without_vehicles():
    """Create a HondaAPI with no vehicle data loaded."""
    api = HondaAPI()
    api.tokens = AuthTokens(
        access_token="tok",
        refresh_token="ref",
        expires_at=time.time() + 3600,
    )
    return api


class TestCapabilityCheckBlocks:
    """Methods should raise ValueError when capability is disabled."""

    def test_remote_lock_blocked(self):
        api = _make_api_with_vehicle(remote_lock=False)
        with pytest.raises(ValueError, match="remote_lock"):
            api.remote_lock("VIN123")

    def test_remote_unlock_blocked(self):
        api = _make_api_with_vehicle(remote_lock=False)
        with pytest.raises(ValueError, match="remote_lock"):
            api.remote_unlock("VIN123")

    def test_remote_horn_blocked(self):
        api = _make_api_with_vehicle(remote_horn=False)
        with pytest.raises(ValueError, match="remote_horn"):
            api.remote_horn_lights("VIN123")

    def test_remote_climate_start_blocked(self):
        api = _make_api_with_vehicle(remote_climate=False)
        with pytest.raises(ValueError, match="remote_climate"):
            api.remote_climate_start("VIN123")

    def test_remote_climate_stop_blocked(self):
        api = _make_api_with_vehicle(remote_climate=False)
        with pytest.raises(ValueError, match="remote_climate"):
            api.remote_climate_stop("VIN123")

    def test_climate_settings_blocked(self):
        api = _make_api_with_vehicle(remote_climate=False)
        with pytest.raises(ValueError, match="remote_climate"):
            api.set_climate_settings("VIN123")

    def test_remote_charge_start_blocked(self):
        api = _make_api_with_vehicle(remote_charge=False)
        with pytest.raises(ValueError, match="remote_charge"):
            api.remote_charge_start("VIN123")

    def test_remote_charge_stop_blocked(self):
        api = _make_api_with_vehicle(remote_charge=False)
        with pytest.raises(ValueError, match="remote_charge"):
            api.remote_charge_stop("VIN123")

    def test_charge_limit_blocked(self):
        api = _make_api_with_vehicle(max_charge=False)
        with pytest.raises(ValueError, match="max_charge"):
            api.set_charge_limit("VIN123")

    def test_charge_schedule_blocked(self):
        api = _make_api_with_vehicle(charge_schedule=False)
        with pytest.raises(ValueError, match="charge_schedule"):
            api.set_charge_schedule("VIN123", [])

    def test_climate_schedule_blocked(self):
        api = _make_api_with_vehicle(climate_schedule=False)
        with pytest.raises(ValueError, match="climate_schedule"):
            api.set_climate_schedule("VIN123", [])

    def test_geofence_get_blocked(self):
        api = _make_api_with_vehicle(geo_fence=False)
        with pytest.raises(ValueError, match="geo_fence"):
            api.get_geofence("VIN123")

    def test_geofence_set_blocked(self):
        api = _make_api_with_vehicle(geo_fence=False)
        with pytest.raises(ValueError, match="geo_fence"):
            api.set_geofence("VIN123", 41.89, 12.49)

    def test_geofence_clear_blocked(self):
        api = _make_api_with_vehicle(geo_fence=False)
        with pytest.raises(ValueError, match="geo_fence"):
            api.clear_geofence("VIN123")


class TestCapabilityCheckPasses:
    """Methods should not raise when capability is enabled (will fail on HTTP instead)."""

    def test_lock_passes_with_capability(self):
        api = _make_api_with_vehicle(remote_lock=True)
        api.session.post = lambda *a, **k: None  # will fail later, that's fine
        with pytest.raises(Exception, match="(?!remote_lock)"):
            api.remote_lock("VIN123")

    def test_geofence_passes_with_capability(self):
        api = _make_api_with_vehicle(geo_fence=True)
        with pytest.raises(Exception, match="(?!geo_fence)"):
            api.get_geofence("VIN123")


class TestCapabilityCheckWithoutVehicles:
    """Methods should pass through when no vehicle data is loaded."""

    def test_lock_without_vehicles(self):
        api = _make_api_without_vehicles()
        # No vehicles loaded — check should pass, fail on HTTP
        with pytest.raises(Exception, match="(?!remote_lock)"):
            api.remote_lock("VIN123")

    def test_unknown_vin(self):
        api = _make_api_with_vehicle(remote_lock=False)
        # VIN doesn't match — check should pass
        with pytest.raises(Exception, match="(?!remote_lock)"):
            api.remote_lock("UNKNOWN_VIN")
