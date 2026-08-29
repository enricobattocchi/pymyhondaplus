"""Behavioral tests for CLI flows."""

import importlib.metadata

import pytest

from pymyhondaplus import cli
from pymyhondaplus.api import HondaAPIError, HondaAuthError
from pymyhondaplus.http import DEFAULT_AUTH_TIMEOUT


class _FakeTokens:
    def __init__(self, vehicles, default_vin=""):
        self.vehicles = vehicles
        self.default_vin = default_vin

    @staticmethod
    def resolve_vin(value: str) -> str:
        return value


class _FakeAPI:
    def __init__(self, vehicles, default_vin=""):
        self.tokens = _FakeTokens(vehicles, default_vin=default_vin)
        self.remote_lock_called = False
        self.refresh_location_called = False
        self.refresh_dashboard_called = False

    def _dashboard_payload(self):
        return {
            "gpsData": {
                "coordinate": {"latitude": "41,53,24.904", "longitude": "12,29,32.543"},
                "dtTime": "2026-03-24T22:53:01+00:00",
                "velocity": {"value": "0.0", "unit": "km/h"},
            }
        }

    def get_dashboard(self, vin: str, fresh: bool = False):
        return self._dashboard_payload()

    def get_dashboard_cached(self, vin: str, language: str = "it"):
        return self._dashboard_payload()

    def refresh_location(self, vin: str):
        self.refresh_location_called = True
        return "loc-cmd-1"

    def refresh_dashboard(self, vin: str):
        self.refresh_dashboard_called = True
        return "dash-cmd-1"

    def remote_lock(self, vin: str):
        self.remote_lock_called = True
        return "cmd-1"

    def get_charge_schedule(self, vin: str, fresh: bool = False):
        return []

    def set_charge_schedule(self, vin: str, rules):
        return "cmd-2"

    def wait_for_command(self, cmd_id: str, timeout: int = 60):
        import json as _json

        class _Result:
            success = True
            complete = True
            status = "success"
            timed_out = False
            reason = None
            raw = {
                "output": {
                    "RequestStatus": "success",
                    "Content": _json.dumps({
                        "gpsData": {
                            "dtTime": "2026-04-26T18:18:01+00:00",
                            "coordinate": {
                                "datum": "wgs84", "format": "mas",
                                "latitude": 156791051,
                                "longitude": 37196051,
                            },
                            "courseHeading": 293.9,
                            "velocity": {"unit": "kph", "value": 0},
                        },
                        "ignition": "ignitionOff",
                    }),
                },
            }

        return _Result()


def _patch_common(monkeypatch, fake_api):
    monkeypatch.setattr(importlib.metadata, "version", lambda _: "0.0")
    monkeypatch.setattr(cli, "get_storage", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "HondaAPI", lambda storage=None, request_timeout=None: fake_api)


def test_multi_vehicle_without_vin_exits_with_message(monkeypatch, capsys):
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"},
        {"vin": "VIN456", "name": "Civic", "plate": "AB123CD", "fuel_type": "G"},
    ])
    _patch_common(monkeypatch, fake_api)
    monkeypatch.setattr(cli.sys, "argv", ["pymyhondaplus", "status"])

    rc = cli.main()

    err = capsys.readouterr().err
    assert rc == 1
    assert "Multiple vehicles on account. Please specify one with --vin:" in err
    assert "VIN123  Honda e" in err
    assert "VIN456  Civic (AB123CD)" in err


def test_destructive_command_aborts_when_confirmation_declined(monkeypatch, capsys):
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"},
    ], default_vin="VIN123")
    _patch_common(monkeypatch, fake_api)
    monkeypatch.setattr(cli.sys, "argv", ["pymyhondaplus", "lock"])
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "_confirm", lambda command: False)

    rc = cli.main()

    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip()  # shows translated abort message
    assert fake_api.remote_lock_called is False


def test_location_json_outputs_raw_gps_payload(monkeypatch, capsys):
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"},
    ], default_vin="VIN123")
    _patch_common(monkeypatch, fake_api)
    monkeypatch.setattr(cli.sys, "argv", ["pymyhondaplus", "--json", "location"])

    rc = cli.main()

    out = capsys.readouterr()
    assert rc == 0
    assert '"coordinate": {' in out.out
    assert '"latitude": "41,53,24.904"' in out.out
    assert '"dtTime": "2026-03-24T22:53:01+00:00"' in out.out


def test_location_fresh_uses_dashboard_refresh(monkeypatch, capsys):
    """`location --fresh` is a dashboard refresh now; car-location is `find-car`."""
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"},
    ], default_vin="VIN123")
    _patch_common(monkeypatch, fake_api)
    monkeypatch.setattr(cli.sys, "argv", ["pymyhondaplus", "--fresh", "location"])

    rc = cli.main()

    assert rc == 0
    assert fake_api.refresh_dashboard_called is True
    assert fake_api.refresh_location_called is False


def test_find_car_calls_car_location_endpoint(monkeypatch, capsys):
    """`find-car` is the dedicated Car Finder command; hits /tsp/car-location."""
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"},
    ], default_vin="VIN123")
    _patch_common(monkeypatch, fake_api)
    monkeypatch.setattr(cli.sys, "argv", ["pymyhondaplus", "find-car"])

    rc = cli.main()

    out = capsys.readouterr()
    assert rc == 0
    assert fake_api.refresh_location_called is True
    assert fake_api.refresh_dashboard_called is False
    assert "Latitude:" in out.out
    assert "Timestamp:" in out.out
    # Default: UTC suffix preserved
    assert "2026-04-26T18:18:01+00:00" in out.out


def test_find_car_local_tz_shifts_timestamp(monkeypatch, capsys):
    """`--local-tz find-car` renders the TCU fix time in local timezone."""
    import time as _time
    if not hasattr(_time, "tzset"):
        pytest.skip("time.tzset not available on this platform")
    monkeypatch.setenv("TZ", "Europe/Rome")
    _time.tzset()

    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"},
    ], default_vin="VIN123")
    _patch_common(monkeypatch, fake_api)
    monkeypatch.setattr(cli.sys, "argv", ["pymyhondaplus", "--local-tz", "find-car"])

    rc = cli.main()

    out = capsys.readouterr().out
    assert rc == 0
    # 2026-04-26 is past DST switch → Europe/Rome is UTC+2 (CEST).
    assert "2026-04-26T20:18:01+02:00" in out
    assert "+00:00" not in out  # raw UTC must not leak through


def test_status_json_outputs_raw_dashboard(monkeypatch, capsys):
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"},
    ], default_vin="VIN123")
    _patch_common(monkeypatch, fake_api)
    monkeypatch.setattr(
        cli.sys, "argv", ["pymyhondaplus", "--json", "status"]
    )

    rc = cli.main()

    out = capsys.readouterr()
    assert rc == 0
    assert '"gpsData": {' in out.out
    assert '"coordinate": {' in out.out
    assert '"latitude": "41,53,24.904"' in out.out


def test_climate_settings_json_outputs_parsed_fields(monkeypatch, capsys):
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"},
    ], default_vin="VIN123")
    _patch_common(monkeypatch, fake_api)
    monkeypatch.setattr(
        cli.sys, "argv", ["pymyhondaplus", "--json", "climate-settings"]
    )
    monkeypatch.setattr(cli, "parse_ev_status", lambda dashboard: {
        "climate_active": True,
        "climate_temp": "normal",
        "climate_duration": 30,
        "climate_defrost": True,
        "cabin_temp": 21,
        "interior_temp": 19,
        "temp_unit": "c",
    })

    rc = cli.main()

    out = capsys.readouterr()
    assert rc == 0
    assert '"active": true' in out.out
    assert '"temp": "normal"' in out.out
    assert '"duration": 30' in out.out
    assert '"temp_unit": "c"' in out.out


def test_remote_command_timeout_exits_with_error(monkeypatch, capsys):
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"},
    ], default_vin="VIN123")

    class _TimeoutResult:
        success = False
        complete = False
        status = "pending"
        timed_out = True
        reason = "car may be unreachable"

    _patch_common(monkeypatch, fake_api)
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setattr(
        cli.sys, "argv", ["pymyhondaplus", "lock", "--yes"]
    )
    fake_api.wait_for_command = lambda cmd_id, timeout=90: _TimeoutResult()

    rc = cli.main()

    out = capsys.readouterr()
    assert rc == 1
    assert "Lock: timed out" in out.err


def test_remote_command_no_command_id_returns_error(monkeypatch, capsys):
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"},
    ], default_vin="VIN123")

    class _NoCommandResult:
        success = False
        complete = False
        status = "no_command_id"
        timed_out = False
        reason = None

    _patch_common(monkeypatch, fake_api)
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setattr(cli.sys, "argv", ["pymyhondaplus", "lock", "--yes"])
    fake_api.wait_for_command = lambda cmd_id, timeout=90: _NoCommandResult()

    rc = cli.main()

    out = capsys.readouterr()
    assert rc == 1
    assert "Lock: failed" in out.err


def test_role_restricted_schedule_returns_success(monkeypatch, capsys):
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E", "role": "secondary"},
    ], default_vin="VIN123")
    _patch_common(monkeypatch, fake_api)
    monkeypatch.setattr(cli.sys, "argv", ["pymyhondaplus", "charge-schedule-clear", "--yes"])
    fake_api.set_charge_schedule = lambda vin, rules: (_ for _ in ()).throw(HondaAPIError(403, "Forbidden"))

    rc = cli.main()

    out = capsys.readouterr()
    assert rc == 0
    assert "Charge schedule is not available for secondary users." in out.out


def test_login_auth_failure_returns_2(monkeypatch, capsys):
    _patch_common(monkeypatch, _FakeAPI([]))
    monkeypatch.setattr(cli.sys, "argv", ["pymyhondaplus", "login", "--email", "user@example.com", "--password", "secret"])

    class _FakeAuth:
        def __init__(self, device_key=None, request_timeout=None):
            pass

        def full_login(self, email: str, password: str, locale: str = "it"):
            raise HondaAuthError(401, "bad credentials")

    monkeypatch.setattr(cli, "DeviceKey", lambda storage=None: object())
    monkeypatch.setattr(cli, "HondaAuth", _FakeAuth)

    rc = cli.main()

    err = capsys.readouterr().err
    assert rc == 2
    assert "Login failed: HTTP 401: bad credentials" in err


def test_http_timeout_is_forwarded_to_clients(monkeypatch, capsys):
    recorded = {}

    class _FakeAuth:
        def __init__(self, device_key=None, request_timeout=DEFAULT_AUTH_TIMEOUT):
            recorded["auth_timeout"] = request_timeout

        def full_login(self, email: str, password: str, locale: str = "it"):
            return {
                "access_token": "header.eyJzdWIiOiAidXNlci0xIn0.signature",
                "refresh_token": "refresh",
                "expires_in": 3600,
            }

        @staticmethod
        def extract_user_id(token: str) -> str:
            return "user-1"

    class _FakeAPI:
        def __init__(self, storage=None, request_timeout=None):
            recorded.setdefault("api_timeouts", []).append(request_timeout)
            self.tokens = type("Tokens", (), {"vehicles": []})()

        def set_tokens(self, **kwargs):
            return None

        def get_vehicles(self):
            return []

    monkeypatch.setattr(importlib.metadata, "version", lambda _: "0.0")
    monkeypatch.setattr(cli, "get_storage", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "DeviceKey", lambda storage=None: object())
    monkeypatch.setattr(cli, "HondaAuth", _FakeAuth)
    monkeypatch.setattr(cli, "HondaAPI", _FakeAPI)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "pymyhondaplus",
            "login",
            "--email",
            "user@example.com",
            "--password",
            "secret",
            "--http-timeout",
            "4.5",
        ],
    )

    rc = cli.main()

    assert rc == 0
    assert recorded["auth_timeout"] == DEFAULT_AUTH_TIMEOUT
    assert recorded["api_timeouts"] == [4.5]


def test__main_exits_130_on_keyboard_interrupt(monkeypatch):
    monkeypatch.setattr(cli, "main", lambda: (_ for _ in ()).throw(KeyboardInterrupt()))

    with pytest.raises(SystemExit) as exc:
        cli._main()

    assert exc.value.code == 130


@pytest.mark.parametrize("value", [None, "", "2026-03-21", "not-a-timestamp"])
def test_format_ts_passes_through_non_iso_or_empty(value):
    assert cli._format_ts(value, True) == value


def test_format_ts_returns_input_when_local_disabled():
    assert cli._format_ts("2026-03-21T14:12:41+00:00", False) == "2026-03-21T14:12:41+00:00"


def test_format_ts_converts_utc_to_local_when_enabled(monkeypatch):
    import time as _time
    if not hasattr(_time, "tzset"):
        pytest.skip("time.tzset not available on this platform")
    monkeypatch.setenv("TZ", "Europe/Rome")
    _time.tzset()
    # 14:12:41 UTC on 2026-03-21 is 15:12:41 CET (winter, UTC+1).
    assert cli._format_ts("2026-03-21T14:12:41+00:00", True) == "2026-03-21T15:12:41+01:00"


def test_format_ts_output_roundtrips_through_to_utc_iso(monkeypatch):
    """Local-tz output must parse cleanly back into UTC via _to_utc_iso."""
    import time as _time
    if not hasattr(_time, "tzset"):
        pytest.skip("time.tzset not available on this platform")
    monkeypatch.setenv("TZ", "Europe/Rome")
    _time.tzset()
    src = "2026-03-21T14:12:41+00:00"
    local = cli._format_ts(src, True)
    assert cli._to_utc_iso(local) == src


@pytest.mark.parametrize("inp, expected", [
    ("2026-03-21T14:12:41+00:00", "2026-03-21T14:12:41+00:00"),
    ("2026-03-21T15:12:41+01:00", "2026-03-21T14:12:41+00:00"),
    ("2026-03-21T11:12:41-03:00", "2026-03-21T14:12:41+00:00"),
])
def test_to_utc_iso_normalizes_any_offset_to_utc(inp, expected):
    assert cli._to_utc_iso(inp) == expected


@pytest.mark.parametrize("garbage", ["", "garbage", None])
def test_to_utc_iso_returns_input_on_unparseable(garbage):
    assert cli._to_utc_iso(garbage) == garbage


def test_trip_detail_normalizes_local_tz_input_to_utc(monkeypatch, capsys):
    """trips --local-tz prints offsets like +01:00; pasting those back into trip-detail
    must still hit Honda's endpoint with UTC strings."""
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"},
    ], default_vin="VIN123")
    captured = {}

    def fake_get_trip_locations(vin, start_time, end_time):
        captured["vin"] = vin
        captured["start"] = start_time
        captured["end"] = end_time
        return {
            "start_time": "2026-03-21T14:12:41+00:00",
            "end_time": "2026-03-21T14:49:55+00:00",
            "start_lat": 41.0, "start_lon": 12.0,
            "end_lat": 42.0, "end_lon": 13.0,
        }

    fake_api.get_trip_locations = fake_get_trip_locations
    _patch_common(monkeypatch, fake_api)
    monkeypatch.setattr(cli.sys, "argv", [
        "pymyhondaplus", "trip-detail",
        "2026-03-21T15:12:41+01:00", "2026-03-21T15:49:55+01:00",
    ])

    rc = cli.main()

    assert rc == 0
    assert captured["start"] == "2026-03-21T14:12:41+00:00"
    assert captured["end"] == "2026-03-21T14:49:55+00:00"
    # Output (text mode) should still show UTC by default
    out = capsys.readouterr().out
    assert "2026-03-21T14:12:41+00:00" in out


def test_status_renders_fuel_rows_for_hybrids(monkeypatch, capsys):
    """Hybrid dashboards render the fuel level and fuel range rows."""
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Prelude", "plate": "", "fuel_type": "P"},
    ], default_vin="VIN123")
    payload = fake_api._dashboard_payload()
    payload["fuelLevel"] = {
        "currentLevel": {"gaugeBars": 10, "value": "100", "unit": "percentage"},
        "driveRange": {"value": "598", "unit": "km"},
    }
    monkeypatch.setattr(fake_api, "_dashboard_payload", lambda: payload)
    _patch_common(monkeypatch, fake_api)
    monkeypatch.setattr(cli.sys, "argv", ["pymyhondaplus", "status"])

    rc = cli.main()

    out = capsys.readouterr().out
    assert rc == 0
    assert "Fuel level" in out
    assert "100%" in out
    assert "Fuel range" in out
    assert "598 km" in out


def test_status_hides_fuel_rows_without_fuel_data(monkeypatch, capsys):
    """BEV dashboards (no fuelLevel block) do not render fuel rows."""
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"},
    ], default_vin="VIN123")
    _patch_common(monkeypatch, fake_api)
    monkeypatch.setattr(cli.sys, "argv", ["pymyhondaplus", "status"])

    rc = cli.main()

    out = capsys.readouterr().out
    assert rc == 0
    assert "Fuel level" not in out
    assert "Fuel range" not in out
