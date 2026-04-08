"""Behavioral tests for CLI flows."""

import importlib.metadata

import pytest

from pymyhondaplus import cli


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
                "coordinate": {"latitude": "41.890251", "longitude": "12.492373"},
                "dtTime": "2026-03-24T22:53:01+00:00",
                "velocity": {"value": "0.0", "unit": "km/h"},
            }
        }

    def remote_lock(self, vin: str):
        self.remote_lock_called = True
        return "cmd-1"


def _patch_common(monkeypatch, fake_api):
    monkeypatch.setattr(importlib.metadata, "version", lambda _: "0.0")
    monkeypatch.setattr(cli, "get_storage", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "HondaAPI", lambda storage=None: fake_api)


def test_multi_vehicle_without_vin_exits_with_message(monkeypatch, capsys):
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"},
        {"vin": "VIN456", "name": "Civic", "plate": "AB123CD", "fuel_type": "G"},
    ])
    _patch_common(monkeypatch, fake_api)
    monkeypatch.setattr(cli.sys, "argv", ["pymyhondaplus", "status"])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    err = capsys.readouterr().err
    assert exc.value.code == 1
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

    with pytest.raises(SystemExit) as exc:
        cli.main()

    out = capsys.readouterr().out
    assert exc.value.code == 0
    assert "Aborted." in out
    assert fake_api.remote_lock_called is False


def test_location_json_outputs_raw_gps_payload(monkeypatch, capsys):
    fake_api = _FakeAPI([
        {"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"},
    ], default_vin="VIN123")
    _patch_common(monkeypatch, fake_api)
    monkeypatch.setattr(cli.sys, "argv", ["pymyhondaplus", "--json", "location"])

    cli.main()

    out = capsys.readouterr()
    assert '"coordinate": {' in out.out
    assert '"latitude": "41.890251"' in out.out
    assert '"dtTime": "2026-03-24T22:53:01+00:00"' in out.out
