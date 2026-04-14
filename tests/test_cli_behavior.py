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

    def get_dashboard(self, vin: str, fresh: bool = False):
        return {
            "gpsData": {
                "coordinate": {"latitude": "41,53,24.904", "longitude": "12,29,32.543"},
                "dtTime": "2026-03-24T22:53:01+00:00",
                "velocity": {"value": "0.0", "unit": "km/h"},
            }
        }

    def remote_lock(self, vin: str):
        self.remote_lock_called = True
        return "cmd-1"

    def get_charge_schedule(self, vin: str, fresh: bool = False):
        return []

    def set_charge_schedule(self, vin: str, rules):
        return "cmd-2"

    def wait_for_command(self, cmd_id: str, timeout: int = 60):
        class _Result:
            success = True
            complete = True
            status = "success"
            timed_out = False
            reason = None

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
