"""Tests for parse_ev_status."""

from pymyhondaplus.api import parse_ev_status


def test_basic_fields(dashboard_ev):
    ev = parse_ev_status(dashboard_ev)
    assert ev["battery_level"] == 82
    assert ev["range_climate_on"] == 176
    assert ev["range_climate_off"] == 181
    assert ev["charge_status"] == "stopped"
    assert ev["plug_status"] == "plugged in"
    assert ev["home_away"] == "away"
    assert ev["charge_limit_home"] == 80
    assert ev["charge_limit_away"] == 90
    assert ev["odometer"] == 43202
    assert ev["ignition"] == "OFF"
    assert ev["charge_mode"] == "unconfirmed"
    assert ev["time_to_charge"] == 0


def test_temperature(dashboard_ev):
    ev = parse_ev_status(dashboard_ev)
    assert ev["cabin_temp"] == 24
    assert ev["interior_temp"] == 15
    assert ev["temp_unit"] == "c"


def test_gps(dashboard_ev):
    ev = parse_ev_status(dashboard_ev)
    assert abs(ev["latitude"] - 41.890251) < 0.000001
    assert abs(ev["longitude"] - 12.492373) < 0.000001
    assert ev["speed"] == 0.0
    assert ev["speed_unit"] == "km/h"
    assert ev["distance_unit"] == "km"


def test_units_uk_aliases(dashboard_ev):
    """Honda returns 'mile' / 'mile/h' for UK accounts; canonicalize to miles."""
    dashboard_ev["evStatus"]["rangeUnit"] = "mile"
    dashboard_ev["odometer"]["unit"] = "mile"
    dashboard_ev["gpsData"]["velocity"]["unit"] = "mile/h"
    ev = parse_ev_status(dashboard_ev)
    assert ev["distance_unit"] == "miles"
    assert ev["speed_unit"] == "miles/h"


def test_units_distance_alias_falls_through_to_odometer(dashboard_ev):
    """If rangeUnit is absent we read odometer.unit, normalized."""
    dashboard_ev["evStatus"].pop("rangeUnit", None)
    dashboard_ev["odometer"]["unit"] = "Miles"
    ev = parse_ev_status(dashboard_ev)
    assert ev["distance_unit"] == "miles"


def test_units_unknown_distance_defaults_to_km(dashboard_ev):
    dashboard_ev["evStatus"]["rangeUnit"] = "furlong"
    dashboard_ev["odometer"]["unit"] = "furlong"
    ev = parse_ev_status(dashboard_ev)
    assert ev["distance_unit"] == "km"
    assert ev["speed_unit"] == "km/h"


def test_doors_locked(dashboard_ev):
    ev = parse_ev_status(dashboard_ev)
    assert ev["doors_locked"] is True
    assert ev["all_doors_closed"] is True
    assert ev["hood_open"] is False
    assert ev["trunk_open"] is False


def test_doors_unlocked(dashboard_ev):
    dashboard_ev["doorStatus"]["firstRowDriver"]["lockState"] = "unlock"
    ev = parse_ev_status(dashboard_ev)
    assert ev["doors_locked"] is False


def test_door_open(dashboard_ev):
    dashboard_ev["doorStatus"]["trunk"]["openState"] = "open"
    ev = parse_ev_status(dashboard_ev)
    assert ev["all_doors_closed"] is False
    assert ev["trunk_open"] is True


def test_windows(dashboard_ev):
    ev = parse_ev_status(dashboard_ev)
    assert ev["all_windows_closed"] is True

    dashboard_ev["windowStatus"]["frontWindowDR"]["closeState"] = "open"
    ev = parse_ev_status(dashboard_ev)
    assert ev["all_windows_closed"] is False


def test_lights(dashboard_ev):
    ev = parse_ev_status(dashboard_ev)
    assert ev["lights_on"] is False
    assert ev["headlights"] == "off"

    dashboard_ev["lightStatus"]["headlights"]["lightState"] = "on"
    ev = parse_ev_status(dashboard_ev)
    assert ev["lights_on"] is True
    assert ev["headlights"] == "on"


def test_climate_active(dashboard_ev):
    ev = parse_ev_status(dashboard_ev)
    assert ev["climate_active"] is False

    dashboard_ev["climateControl"]["status"]["isActive"] = True
    ev = parse_ev_status(dashboard_ev)
    assert ev["climate_active"] is True


def test_climate_settings(dashboard_ev):
    ev = parse_ev_status(dashboard_ev)
    assert ev["climate_temp"] == "normal"
    assert ev["climate_duration"] == 30
    assert ev["climate_defrost"] is True


def test_climate_temp_mapping(dashboard_ev):
    dashboard_ev["evStatus"]["acTempVal"] = "03"
    assert parse_ev_status(dashboard_ev)["climate_temp"] == "hotter"

    dashboard_ev["evStatus"]["acTempVal"] = "05"
    assert parse_ev_status(dashboard_ev)["climate_temp"] == "cooler"

    # Dashboard sometimes returns text labels instead of codes
    dashboard_ev["evStatus"]["acTempVal"] = "warm"
    assert parse_ev_status(dashboard_ev)["climate_temp"] == "hotter"

    dashboard_ev["evStatus"]["acTempVal"] = "cool"
    assert parse_ev_status(dashboard_ev)["climate_temp"] == "cooler"

    dashboard_ev["evStatus"]["acTempVal"] = "normal"
    assert parse_ev_status(dashboard_ev)["climate_temp"] == "normal"


def test_charge_status_running_normalized_to_charging(dashboard_ev):
    dashboard_ev["evStatus"]["chargeStatus"] = "running"
    assert parse_ev_status(dashboard_ev)["charge_status"] == "charging"


def test_charge_status_stopped_passes_through(dashboard_ev):
    dashboard_ev["evStatus"]["chargeStatus"] = "stopped"
    assert parse_ev_status(dashboard_ev)["charge_status"] == "stopped"


def test_charge_status_unavailable_normalized_to_unknown(dashboard_ev):
    dashboard_ev["evStatus"]["chargeStatus"] = "unavailable"
    assert parse_ev_status(dashboard_ev)["charge_status"] == "unknown"


def test_charge_status_unknown_passes_through(dashboard_ev):
    dashboard_ev["evStatus"]["chargeStatus"] = "unknown"
    assert parse_ev_status(dashboard_ev)["charge_status"] == "unknown"


def test_charge_status_case_insensitive(dashboard_ev):
    dashboard_ev["evStatus"]["chargeStatus"] = "RUNNING"
    assert parse_ev_status(dashboard_ev)["charge_status"] == "charging"

    dashboard_ev["evStatus"]["chargeStatus"] = "Stopped"
    assert parse_ev_status(dashboard_ev)["charge_status"] == "stopped"


def test_charge_status_missing_is_unknown(dashboard_ev):
    dashboard_ev["evStatus"].pop("chargeStatus", None)
    assert parse_ev_status(dashboard_ev)["charge_status"] == "unknown"


def test_charge_status_unexpected_value_is_unknown(dashboard_ev, caplog):
    import logging
    dashboard_ev["evStatus"]["chargeStatus"] = "weird-new-state"
    with caplog.at_level(logging.DEBUG, logger="pymyhondaplus.api"):
        assert parse_ev_status(dashboard_ev)["charge_status"] == "unknown"
    assert any("weird-new-state" in rec.message for rec in caplog.records)


def test_charge_status_non_string_is_unknown(dashboard_ev):
    dashboard_ev["evStatus"]["chargeStatus"] = 42
    assert parse_ev_status(dashboard_ev)["charge_status"] == "unknown"

    dashboard_ev["evStatus"]["chargeStatus"] = None
    assert parse_ev_status(dashboard_ev)["charge_status"] == "unknown"


def test_climate_defrost_off(dashboard_ev):
    dashboard_ev["evStatus"]["acDefAutoSetting"] = "def auto off"
    ev = parse_ev_status(dashboard_ev)
    assert ev["climate_defrost"] is False


def test_warning_lamps(dashboard_ev):
    ev = parse_ev_status(dashboard_ev)
    assert ev["warning_lamps"] == []

    dashboard_ev["warningLamps"]["messages"] = [
        {"lampName": "check engine", "condition": "ON"},
        {"lampName": "tire pressure", "condition": "OFF"},
    ]
    ev = parse_ev_status(dashboard_ev)
    assert ev["warning_lamps"] == ["check engine"]


def test_empty_dashboard():
    ev = parse_ev_status({})
    assert ev["battery_level"] == 0
    assert ev["range_climate_on"] == 0
    assert ev["charge_status"] == "unknown"
    assert ev["doors_locked"] is True  # all() on empty is True
    assert ev["lights_on"] is False
    assert ev["warning_lamps"] == []


def test_home_away_normalization(dashboard_ev):
    dashboard_ev["evStatus"]["homeAway"] = "Home"
    assert parse_ev_status(dashboard_ev)["home_away"] == "home"

    dashboard_ev["evStatus"]["homeAway"] = "Away"
    assert parse_ev_status(dashboard_ev)["home_away"] == "away"

    dashboard_ev["evStatus"]["homeAway"] = "home is unregistered"
    assert parse_ev_status(dashboard_ev)["home_away"] == "unknown"

    dashboard_ev["evStatus"]["homeAway"] = "something unexpected"
    assert parse_ev_status(dashboard_ev)["home_away"] == "unknown"


def test_climate_temp_numeric_passes_through(dashboard_ev):
    dashboard_ev["evStatus"]["acTempVal"] = "17"
    assert parse_ev_status(dashboard_ev)["climate_temp"] == "17"

    dashboard_ev["evStatus"]["acTempVal"] = "25.5"
    assert parse_ev_status(dashboard_ev)["climate_temp"] == "25.5"


def test_climate_temp_garbage_normalized_to_unknown(dashboard_ev):
    dashboard_ev["evStatus"]["acTempVal"] = "not a temp"
    assert parse_ev_status(dashboard_ev)["climate_temp"] == "unknown"


def test_malformed_numeric_fields_do_not_crash(dashboard_ev):
    dashboard_ev["evStatus"]["soc"] = "n/a"
    dashboard_ev["evStatus"]["evRange"] = None
    dashboard_ev["evStatus"]["chargeLimitHome"] = "eighty"
    dashboard_ev["evStatus"]["acDurationSetting"] = "30m"
    dashboard_ev["gpsData"]["velocity"]["value"] = "fast"
    dashboard_ev["temperature"]["cabin"]["value"] = ""
    dashboard_ev["odometer"]["value"] = "unknown"

    ev = parse_ev_status(dashboard_ev)

    assert ev["battery_level"] == 0
    assert ev["range_climate_on"] == 0
    assert ev["charge_limit_home"] == 0
    assert ev["climate_duration"] == 0
    assert ev["speed"] == 0.0
    assert ev["cabin_temp"] == 0
    assert ev["odometer"] == 0


def test_fuel_fields_default_to_zero_without_fuel_level(dashboard_ev):
    """BEV dashboards have no fuelLevel block; fuel fields default to 0."""
    ev = parse_ev_status(dashboard_ev)
    assert ev["fuel_level"] == 0
    assert ev["fuel_range"] == 0


def test_fuel_fields_hybrid(dashboard_ev):
    """Hybrids report fuel under fuelLevel (seen on the 2026 Prelude e:HEV)."""
    dashboard_ev["fuelLevel"] = {
        "currentLevel": {"gaugeBars": 10, "value": "100", "unit": "percentage"},
        "driveRange": {"value": "598", "unit": "km"},
    }
    ev = parse_ev_status(dashboard_ev)
    assert ev["fuel_level"] == 100
    assert ev["fuel_range"] == 598


def test_total_range_falls_back_to_fuel_range(dashboard_ev):
    """On hybrids evStatus.totalRange is "unknown"; fall back to driveRange."""
    dashboard_ev["fuelLevel"] = {
        "currentLevel": {"gaugeBars": 10, "value": "100", "unit": "percentage"},
        "driveRange": {"value": "598", "unit": "km"},
    }
    dashboard_ev["evStatus"]["totalRange"] = "unknown"
    ev = parse_ev_status(dashboard_ev)
    assert ev["total_range"] == 598


def test_total_range_prefers_ev_status_when_present(dashboard_ev):
    """A real evStatus.totalRange (BEV/PHEV) wins over the fuel fallback."""
    dashboard_ev["fuelLevel"] = {
        "currentLevel": {"gaugeBars": 3, "value": "30", "unit": "percentage"},
        "driveRange": {"value": "150", "unit": "km"},
    }
    ev = parse_ev_status(dashboard_ev)
    assert ev["total_range"] == 176


def test_fuel_level_malformed_block(dashboard_ev):
    """A fuelLevel block with missing keys parses to zeros, not errors."""
    dashboard_ev["fuelLevel"] = {"currentLevel": {}, "driveRange": {"value": "unknown"}}
    ev = parse_ev_status(dashboard_ev)
    assert ev["fuel_level"] == 0
    assert ev["fuel_range"] == 0


def test_distance_unit_falls_back_to_fuel_drive_range_unit(dashboard_ev):
    """UK hybrids: evStatus.rangeUnit is "unknown" but driveRange carries miles."""
    dashboard_ev["evStatus"]["rangeUnit"] = "unknown"
    dashboard_ev["odometer"]["unit"] = "unknown"
    dashboard_ev["fuelLevel"] = {
        "currentLevel": {"gaugeBars": 8, "value": "80", "unit": "percentage"},
        "driveRange": {"value": "370", "unit": "mile"},
    }
    ev = parse_ev_status(dashboard_ev)
    assert ev["distance_unit"] == "miles"


def test_total_range_zero_is_not_replaced_by_fuel_range(dashboard_ev):
    """A genuine totalRange of 0 must survive; only the "unknown" sentinel falls back."""
    dashboard_ev["fuelLevel"] = {
        "currentLevel": {"gaugeBars": 10, "value": "100", "unit": "percentage"},
        "driveRange": {"value": "598", "unit": "km"},
    }
    dashboard_ev["evStatus"]["totalRange"] = "0"
    ev = parse_ev_status(dashboard_ev)
    assert ev["total_range"] == 0
