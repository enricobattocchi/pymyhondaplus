"""Tests for capability checks on API methods."""

import time
from unittest.mock import MagicMock

import pytest

from pymyhondaplus.api import (
    AuthTokens,
    HondaAPI,
    HondaAPIError,
    HondaAuthError,
    UIConfiguration,
    Vehicle,
    VehicleCapabilities,
)


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


def _make_climate_api(ui_config=None, **cap_overrides):
    """Create a HondaAPI whose only vehicle supports remote climate."""
    api = _make_api_with_vehicle(remote_climate=True, **cap_overrides)
    if ui_config is not None:
        api.tokens.vehicles[0].ui_config = ui_config
    api._remote_command = MagicMock(return_value="cmd-1")
    api.get_vehicles = MagicMock(return_value=list(api.tokens.vehicles))
    return api


RANGE_16_TO_30 = UIConfiguration(climate_temp_min=16.0, climate_temp_max=30.0, climate_temp_step=0.5)


class TestRemoteClimateStart:
    def test_default_payload_is_unchanged(self):
        api = _make_climate_api()
        assert api.remote_climate_start("VIN123") == "cmd-1"
        api._remote_command.assert_called_once_with(
            "remote-climate", "VIN123",
            command="start",
            temperatureMode="specific",
            temperature=0,
            autoDefrosterSetting="autoOn",
        )

    def test_default_payload_is_unchanged_with_specific_temperature(self):
        api = _make_climate_api(RANGE_16_TO_30, specific_temperature=True)
        api.remote_climate_start("VIN123")
        assert api._remote_command.call_args.kwargs["temperature"] == 0

    def test_temperature_and_defrost_payload(self):
        api = _make_climate_api(RANGE_16_TO_30, specific_temperature=True)
        api.remote_climate_start("VIN123", temperature=21.5, defrost=False)
        api._remote_command.assert_called_once_with(
            "remote-climate", "VIN123",
            command="start",
            temperatureMode="specific",
            temperature=21.5,
            autoDefrosterSetting="autoOff",
        )

    def test_defrost_off_without_temperature(self):
        api = _make_climate_api()
        api.remote_climate_start("VIN123", defrost=False)
        kwargs = api._remote_command.call_args.kwargs
        assert kwargs["temperature"] == 0
        assert kwargs["autoDefrosterSetting"] == "autoOff"

    def test_temperature_requires_capability(self):
        api = _make_climate_api(RANGE_16_TO_30, specific_temperature=False)
        with pytest.raises(ValueError, match="specific_temperature"):
            api.remote_climate_start("VIN123", temperature=21.5)
        api._remote_command.assert_not_called()

    @pytest.mark.parametrize("temperature", [16, 16.0, 16.5, 21.5, 30, 30.0])
    def test_accepts_values_in_vehicle_range(self, temperature):
        api = _make_climate_api(RANGE_16_TO_30, specific_temperature=True)
        api.remote_climate_start("VIN123", temperature=temperature)
        assert api._remote_command.call_args.kwargs["temperature"] == temperature

    @pytest.mark.parametrize("temperature", [0, 15.5, 30.5, 21.3])
    def test_rejects_values_outside_vehicle_range(self, temperature):
        api = _make_climate_api(RANGE_16_TO_30, specific_temperature=True)
        with pytest.raises(ValueError, match="temperature must be"):
            api.remote_climate_start("VIN123", temperature=temperature)
        api._remote_command.assert_not_called()

    def test_limits_follow_the_vehicle(self):
        ui_config = UIConfiguration(climate_temp_min=10.0, climate_temp_max=12.0, climate_temp_step=1.0)
        api = _make_climate_api(ui_config, specific_temperature=True)
        api.remote_climate_start("VIN123", temperature=11)
        with pytest.raises(ValueError, match="between 10.0 and 12.0"):
            api.remote_climate_start("VIN123", temperature=21.5)
        with pytest.raises(ValueError, match="multiple of 1.0"):
            api.remote_climate_start("VIN123", temperature=10.5)

    @pytest.mark.parametrize(
        "config, temperature, message",
        [
            (UIConfiguration(climate_temp_min=16.0), 15.5, "at least 16.0"),
            (UIConfiguration(climate_temp_max=30.0), 30.5, "at most 30.0"),
        ],
    )
    def test_single_temperature_limit_error(self, config, temperature, message):
        api = _make_climate_api(config, specific_temperature=True)
        with pytest.raises(ValueError, match=message):
            api.remote_climate_start("VIN123", temperature=temperature)
        api._remote_command.assert_not_called()

    @pytest.mark.parametrize("temperature", [True, "21.5", float("nan"), float("inf")])
    def test_rejects_non_numeric_values(self, temperature):
        api = _make_climate_api(RANGE_16_TO_30, specific_temperature=True)
        with pytest.raises(ValueError, match="must be a number"):
            api.remote_climate_start("VIN123", temperature=temperature)
        api._remote_command.assert_not_called()

    def test_sends_temperature_when_vehicle_reports_no_range(self):
        api = _make_climate_api(specific_temperature=True)
        api.remote_climate_start("VIN123", temperature=21.3)
        assert api._remote_command.call_args.kwargs["temperature"] == 21.3

    def test_sends_temperature_for_unknown_vehicle(self):
        api = _make_api_without_vehicles()
        api._remote_command = MagicMock(return_value="cmd-1")
        api.remote_climate_start("VIN123", temperature=21.5)
        assert api._remote_command.call_args.kwargs["temperature"] == 21.5


class TestStoredVehicleWithoutClimateRange:
    def _fresh_vehicle(self):
        return Vehicle(vin="VIN123", name="Test",
                       capabilities=VehicleCapabilities(remote_climate=True, specific_temperature=True),
                       ui_config=RANGE_16_TO_30)

    def _make_api(self):
        api = _make_climate_api(specific_temperature=True)
        api._storage = MagicMock()
        return api

    def test_rereads_saves_and_validates(self):
        api = self._make_api()
        api.get_vehicles.return_value = [self._fresh_vehicle()]
        with pytest.raises(ValueError, match="between 16.0 and 30.0"):
            api.remote_climate_start("VIN123", temperature=40)
        api._remote_command.assert_not_called()
        assert api.tokens.vehicles[0].ui_config.climate_temp_min == 16.0
        api._storage.save_tokens.assert_called_once()

    def test_refresh_marks_all_returned_vehicles_as_refreshed(self):
        api = self._make_api()
        api.get_vehicles.return_value = [
            Vehicle(vin="VIN123", name="Test",
                    capabilities=VehicleCapabilities(remote_climate=True, specific_temperature=True)),
            Vehicle(vin="VIN456", name="Other"),
        ]
        api.remote_climate_start("VIN123", temperature=21.5)
        assert api._climate_config_refreshed == {"VIN123", "VIN456"}

    def test_rereads_once_when_vehicle_reports_no_range(self):
        api = self._make_api()
        api.get_vehicles.return_value = [
            Vehicle(vin="VIN123", name="Test",
                    capabilities=VehicleCapabilities(remote_climate=True, specific_temperature=True)),
        ]
        api.remote_climate_start("VIN123", temperature=21.5)
        api.remote_climate_start("VIN123", temperature=21.5)
        api.get_vehicles.assert_called_once()
        assert api._remote_command.call_count == 2

    def test_keeps_range_when_already_stored(self):
        api = _make_climate_api(RANGE_16_TO_30, specific_temperature=True)
        api.remote_climate_start("VIN123", temperature=21.5)
        api.get_vehicles.assert_not_called()

    def test_failed_reread_stops_before_starting(self):
        api = self._make_api()
        api.get_vehicles.side_effect = HondaAPIError(500, "boom")
        with pytest.raises(HondaAPIError, match="boom"):
            api.remote_climate_start("VIN123", temperature=21.5)
        api._remote_command.assert_not_called()
        api._storage.save_tokens.assert_not_called()

    def test_retries_reread_after_failure(self):
        api = self._make_api()
        api.get_vehicles.side_effect = [HondaAPIError(500, "boom"), [self._fresh_vehicle()]]
        with pytest.raises(HondaAPIError, match="boom"):
            api.remote_climate_start("VIN123", temperature=21.5)
        with pytest.raises(ValueError, match="between 16.0 and 30.0"):
            api.remote_climate_start("VIN123", temperature=40)
        assert api.get_vehicles.call_count == 2
        api._remote_command.assert_not_called()

    def test_auth_error_propagates(self):
        api = self._make_api()
        api.get_vehicles.side_effect = HondaAuthError(401, "expired")
        with pytest.raises(HondaAuthError):
            api.remote_climate_start("VIN123", temperature=21.5)
        api._remote_command.assert_not_called()

    def test_reread_without_this_vehicle_stops_before_starting(self):
        api = self._make_api()
        original = list(api.tokens.vehicles)
        api.get_vehicles.return_value = [Vehicle(vin="OTHER", name="Other")]
        with pytest.raises(ValueError, match="Could not refresh climate configuration"):
            api.remote_climate_start("VIN123", temperature=21.5)
        assert api.tokens.vehicles == original
        api._remote_command.assert_not_called()

    @pytest.mark.parametrize(
        "temperature, message",
        [
            (0, "above zero"),
            (-1.0, "above zero"),
            (True, "must be a number"),
            ("21.5", "must be a number"),
            (float("nan"), "must be a number"),
            (float("inf"), "must be a number"),
        ],
    )
    def test_invalid_value_stops_before_reread(self, temperature, message):
        api = self._make_api()
        api.get_vehicles.side_effect = HondaAuthError(401, "expired")
        with pytest.raises(ValueError, match=message):
            api.remote_climate_start("VIN123", temperature=temperature)
        api.get_vehicles.assert_not_called()
        api._remote_command.assert_not_called()

    def test_no_reread_without_temperature(self):
        api = self._make_api()
        api.remote_climate_start("VIN123")
        api.get_vehicles.assert_not_called()


class TestValidateClimateTemperature:
    @pytest.mark.parametrize("temperature", [16.0, 21.5, 30, 30.0])
    def test_accepts_values_inside_the_range(self, temperature):
        RANGE_16_TO_30.validate_climate_temperature(temperature)

    @pytest.mark.parametrize(
        "temperature, message",
        [
            (15.5, "between 16.0 and 30.0"),
            (30.5, "between 16.0 and 30.0"),
            (21.25, "multiple of 0.5"),
            (0, "above zero"),
            (-1.0, "above zero"),
            (True, "must be a number"),
            ("21.5", "must be a number"),
            (float("nan"), "must be a number"),
            (float("inf"), "must be a number"),
        ],
    )
    def test_rejects_invalid_values(self, temperature, message):
        with pytest.raises(ValueError, match=message):
            RANGE_16_TO_30.validate_climate_temperature(temperature)

    def test_without_limits_checks_only_the_value(self):
        UIConfiguration().validate_climate_temperature(21.3)
        with pytest.raises(ValueError, match="above zero"):
            UIConfiguration().validate_climate_temperature(0)

    def test_start_rejects_zero_without_stored_vehicles(self):
        api = _make_climate_api()
        api.tokens.vehicles = []
        with pytest.raises(ValueError, match="above zero"):
            api.remote_climate_start("VIN123", temperature=0)
        api._remote_command.assert_not_called()
