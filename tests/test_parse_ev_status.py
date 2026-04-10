"""Tests for parse_ev_status."""

from pymyhondaplus.api import parse_ev_status


def test_basic_fields(dashboard_ev):
    ev = parse_ev_status(dashboard_ev)
    assert ev["battery_level"] == 82
    assert ev["range"] == 176
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
    assert ev["latitude"] == "43.553456"
    assert ev["longitude"] == "10.332365"
    assert ev["speed"] == 0.0
    assert ev["speed_unit"] == "km/h"
    assert ev["distance_unit"] == "km"


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
    assert ev["range"] == 0
    assert ev["charge_status"] == "unknown"
    assert ev["doors_locked"] is True  # all() on empty is True
    assert ev["lights_on"] is False
    assert ev["warning_lamps"] == []


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
    assert ev["range"] == 0
    assert ev["charge_limit_home"] == 0
    assert ev["climate_duration"] == 0
    assert ev["speed"] == 0.0
    assert ev["cabin_temp"] == 0
    assert ev["odometer"] == 0
