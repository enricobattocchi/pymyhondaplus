"""Tests for the CLI `capabilities` command."""

import importlib.metadata

from pymyhondaplus import cli
from pymyhondaplus.api import VehicleCapabilities


def _make_vehicle(cap_raw, name="Honda e", vin="VIN123"):
    class _V:
        pass

    v = _V()
    v.__dict__ = {"vin": vin, "name": name, "plate": "", "fuel_type": "E"}
    v.vin = vin
    v.name = name
    v.capabilities = VehicleCapabilities(raw=cap_raw)

    def _getitem(key, _v=v):
        return getattr(_v, key)

    v.__class__ = type("V", (_V,), {"__getitem__": lambda self, k: getattr(self, k)})
    return v


class _FakeTokens:
    def __init__(self, vehicles, default_vin=""):
        self.vehicles = vehicles
        self.default_vin = default_vin

    @staticmethod
    def resolve_vin(value):
        return value


class _FakeAPI:
    def __init__(self, vehicles, default_vin=""):
        self.tokens = _FakeTokens(vehicles, default_vin=default_vin)


def _run(monkeypatch, fake_api, vin):
    monkeypatch.setattr(importlib.metadata, "version", lambda _: "0.0")
    monkeypatch.setattr(cli, "get_storage", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "HondaAPI", lambda storage=None, request_timeout=None: fake_api)
    monkeypatch.setattr(cli.sys, "argv", ["pymyhondaplus", "--vin", vin, "capabilities"])
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    return cli.main()


def test_all_known_active_capabilities_shown_with_translated_labels(monkeypatch, capsys):
    cap_raw = {
        key: {"featureStatus": "active"}
        for key in cli.CAPABILITY_API_KEY_TO_TRANSLATION_KEY
    }
    fake = _FakeAPI([_make_vehicle(cap_raw)], default_vin="VIN123")
    rc = _run(monkeypatch, fake, "VIN123")
    out = capsys.readouterr().out
    assert rc == 0
    assert "Capabilities for Honda e:" in out
    assert "Lock/Unlock" in out
    assert "Charging" in out
    assert "Climate control" in out
    assert "Geo-fence" in out
    assert "Digital Key" in out


def test_only_active_capabilities_are_listed(monkeypatch, capsys):
    cap_raw = {
        "telematicsRemoteLockUnlock": {"featureStatus": "active"},
        "telematicsRemoteHorn": {"featureStatus": "notSupported"},
        "telematicsRemoteClimate": {"featureStatus": "active"},
        "telematicsGeoFence": {"featureStatus": "notSupported"},
    }
    fake = _FakeAPI([_make_vehicle(cap_raw)], default_vin="VIN123")
    rc = _run(monkeypatch, fake, "VIN123")
    out = capsys.readouterr().out
    assert rc == 0
    assert "Lock/Unlock" in out
    assert "Climate control" in out
    assert "Horn" not in out
    assert "Geo-fence" not in out


def test_unknown_future_api_key_renders_raw(monkeypatch, capsys):
    cap_raw = {
        "telematicsRemoteLockUnlock": {"featureStatus": "active"},
        "telematicsFuturePhonyFeature": {"featureStatus": "active"},
        "useSpecificTemperatureControl": {"featureStatus": "active"},
    }
    fake = _FakeAPI([_make_vehicle(cap_raw)], default_vin="VIN123")
    rc = _run(monkeypatch, fake, "VIN123")
    out = capsys.readouterr().out
    assert rc == 0
    assert "Lock/Unlock" in out
    assert "telematicsFuturePhonyFeature" in out
    assert "useSpecificTemperatureControl" in out


def test_no_active_capabilities_prints_message(monkeypatch, capsys):
    cap_raw = {
        "telematicsRemoteLockUnlock": {"featureStatus": "notSupported"},
        "telematicsRemoteHorn": {"featureStatus": "notSupported"},
    }
    fake = _FakeAPI([_make_vehicle(cap_raw)], default_vin="VIN123")
    rc = _run(monkeypatch, fake, "VIN123")
    out = capsys.readouterr().out
    assert rc == 0
    assert "No active capabilities reported." in out


def test_vehicle_without_capabilities_attribute(monkeypatch, capsys):
    class _Bare:
        def __init__(self):
            self.vin = "VIN123"
            self.name = "Honda e"
            self.plate = ""
            self.fuel_type = "E"

        def __getitem__(self, key):
            return getattr(self, key)

    fake = _FakeAPI([_Bare()], default_vin="VIN123")
    rc = _run(monkeypatch, fake, "VIN123")
    out = capsys.readouterr().out
    assert rc == 1
    assert "No capability data stored." in out


def test_entries_are_alphabetized_by_api_key(monkeypatch, capsys):
    cap_raw = {
        "zzzTrailingFuture": {"featureStatus": "active"},
        "telematicsRemoteLockUnlock": {"featureStatus": "active"},
        "aaaFirstFuture": {"featureStatus": "active"},
    }
    fake = _FakeAPI([_make_vehicle(cap_raw)], default_vin="VIN123")
    rc = _run(monkeypatch, fake, "VIN123")
    out = capsys.readouterr().out
    assert rc == 0
    # First active bullet should be "aaaFirstFuture" (alphabetical)
    lines = [ln.strip() for ln in out.splitlines() if ln.startswith("  ")]
    assert lines[0] == "aaaFirstFuture"
    assert lines[-1] == "zzzTrailingFuture"


def test_non_dict_entries_are_ignored(monkeypatch, capsys):
    cap_raw = {
        "telematicsRemoteLockUnlock": {"featureStatus": "active"},
        "bogusTopLevelString": "not a dict",
        "anotherWeirdOne": None,
    }
    fake = _FakeAPI([_make_vehicle(cap_raw)], default_vin="VIN123")
    rc = _run(monkeypatch, fake, "VIN123")
    out = capsys.readouterr().out
    assert rc == 0
    assert "Lock/Unlock" in out
    assert "bogusTopLevelString" not in out
    assert "anotherWeirdOne" not in out
