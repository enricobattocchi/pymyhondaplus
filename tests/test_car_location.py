"""Tests for CarLocation parsing from car-location command results."""

import json

from pymyhondaplus.api import CarLocation, CommandResult


def _make_result(content: dict | str | None, request_status: str = "success") -> CommandResult:
    """Build a CommandResult mirroring async-command-status JSON for tests."""
    output = {"RequestStatus": request_status}
    if content is not None:
        output["Content"] = (
            content if isinstance(content, str) else json.dumps(content)
        )
    return CommandResult(
        complete=True,
        status=request_status,
        raw={"output": output, "isWaitingForResult": False},
    )


def test_parses_real_response_shape():
    """Real shape captured from /tsp/car-location → async-command-status."""
    result = _make_result({
        "gpsData": {
            "dtTime": "2026-04-26T18:18:01+00:00",
            "coordinate": {
                "datum": "wgs84", "format": "mas",
                "latitude": 156791051, "longitude": 37196051,
            },
            "courseHeading": 293.9,
            "accuracy": {"pdop": 2, "hdop": 2},
            "velocity": {"unit": "kph", "value": 0},
        },
        "ignition": "ignitionOff",
    })

    loc = CarLocation.from_command_result(result)

    assert loc is not None
    # MAS / 3,600,000 → decimal degrees
    assert abs(loc.latitude - 43.553) < 0.001
    assert abs(loc.longitude - 10.332) < 0.001
    assert loc.timestamp == "2026-04-26T18:18:01+00:00"
    assert loc.speed == 0
    assert loc.speed_unit == "km/h"  # kph normalized
    assert loc.course_heading == 293.9
    assert loc.ignition == "off"


def test_returns_none_on_missing_content():
    result = _make_result(None)
    assert CarLocation.from_command_result(result) is None


def test_returns_none_on_invalid_json():
    result = _make_result("{not valid json")
    assert CarLocation.from_command_result(result) is None


def test_handles_missing_gps_data():
    """Server may return success with empty Content; don't crash."""
    result = _make_result({"ignition": "ignitionOff"})
    loc = CarLocation.from_command_result(result)
    assert loc is not None
    assert loc.latitude == 0.0
    assert loc.longitude == 0.0
    assert loc.ignition == "off"


def test_handles_pre_parsed_content():
    """Some callers may pre-parse Content into a dict."""
    result = CommandResult(
        complete=True,
        status="success",
        raw={"output": {"Content": {
            "gpsData": {
                "dtTime": "2026-04-26T12:00:00+00:00",
                "coordinate": {"latitude": 0, "longitude": 0},
                "velocity": {"value": 5.0, "unit": "kph"},
            },
            "ignition": "ignitionOn",
        }}},
    )
    loc = CarLocation.from_command_result(result)
    assert loc is not None
    assert loc.speed == 5.0
    assert loc.ignition == "on"
