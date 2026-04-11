"""Regression tests for CLI trip-stats month-boundary behavior."""

import importlib.metadata

from pymyhondaplus import cli


class _FakeTokens:
    default_vin = "VIN123"
    vehicles = [{"vin": "VIN123", "name": "Honda e", "plate": "", "fuel_type": "E"}]

    @staticmethod
    def resolve_vin(value: str) -> str:
        return value


class _FakeAPI:
    def __init__(self):
        self.tokens = _FakeTokens()
        self.requested_months = []

    def get_all_trips(self, vin: str, month_start: str = ""):
        self.requested_months.append(month_start)
        if month_start.startswith("2026-03-01"):
            return [{
                "OneTripDate": "2026-03-30",
                "OneTripNo": "march-trip",
                "Mileage": "10",
                "AveSpeed": "20",
                "MaxSpeed": "30",
                "DriveTime": "15",
                "AveFuelEconomy": "10",
            }]
        if month_start.startswith("2026-04-01"):
            return [{
                "OneTripDate": "2026-04-01",
                "OneTripNo": "april-trip",
                "Mileage": "20",
                "AveSpeed": "40",
                "MaxSpeed": "60",
                "DriveTime": "30",
                "AveFuelEconomy": "12",
            }]
        return []


def test_trip_stats_week_fetches_all_months_in_range(monkeypatch, capsys):
    fake_api = _FakeAPI()

    monkeypatch.setattr(importlib.metadata, "version", lambda _: "0.0")
    monkeypatch.setattr(cli, "get_storage", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "HondaAPI", lambda storage=None, request_timeout=None: fake_api)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["pymyhondaplus", "--json", "trip-stats", "--period", "week", "--date", "2026-04-01"],
    )

    assert cli.main() == 0

    out = capsys.readouterr()
    assert fake_api.requested_months == [
        "2026-03-01T00:00:00.000Z",
        "2026-04-01T00:00:00.000Z",
    ]
    assert '"trips": 2' in out.out
    assert '"start_date": "2026-03-30"' in out.out
    assert '"end_date": "2026-04-01"' in out.out
