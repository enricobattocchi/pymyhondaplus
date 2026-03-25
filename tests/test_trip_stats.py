"""Tests for compute_trip_stats."""

from pymyhondaplus.api import compute_trip_stats


def test_basic_stats(trip_rows):
    stats = compute_trip_stats(trip_rows, period="month")
    assert stats["period"] == "month"
    assert stats["trips"] == 3
    assert stats["total_distance"] == 44.0  # 5 + 6 + 33
    assert stats["total_minutes"] == 92.0  # 37 + 13 + 42
    assert stats["start_date"] == "2026-03-19"
    assert stats["end_date"] == "2026-03-21"
    assert stats["distance_unit"] == "km"
    assert stats["speed_unit"] == "km/h"


def test_averages(trip_rows):
    stats = compute_trip_stats(trip_rows)
    assert stats["avg_distance_per_trip"] == 14.7  # 44 / 3
    assert stats["avg_min_per_trip"] == 30.7  # 92 / 3
    # avg speed = (7.7 + 27.5 + 46.3) / 3 = 27.2
    assert stats["avg_speed"] == 27.2
    assert stats["max_speed"] == 103.0


def test_weighted_consumption(trip_rows):
    stats = compute_trip_stats(trip_rows)
    # weighted avg: (18.7*5 + 14.4*6 + 13.2*33) / 44 = (93.5 + 86.4 + 435.6) / 44 = 13.99
    assert stats["avg_consumption"] == 14.0


def test_consumption_unit_ev(trip_rows):
    stats = compute_trip_stats(trip_rows, fuel_type="E")
    assert stats["consumption_unit"] == "kWh/100km"


def test_consumption_unit_ice(trip_rows):
    stats = compute_trip_stats(trip_rows, fuel_type="G")
    assert stats["consumption_unit"] == "L/100km"


def test_consumption_unit_default(trip_rows):
    stats = compute_trip_stats(trip_rows)
    assert stats["consumption_unit"] == "L/100km"


def test_distance_unit(trip_rows):
    stats = compute_trip_stats(trip_rows, distance_unit="miles")
    assert stats["distance_unit"] == "miles"
    assert stats["speed_unit"] == "miles/h"


def test_empty_rows():
    stats = compute_trip_stats([])
    assert stats["trips"] == 0
    assert stats["total_distance"] == 0
    assert stats["avg_distance_per_trip"] == 0
    assert stats["avg_speed"] == 0
    assert stats["max_speed"] == 0
    assert stats["avg_consumption"] == 0
    assert stats["start_date"] == ""
    assert stats["end_date"] == ""


def test_single_trip():
    rows = [{
        "OneTripDate": "2026-03-21",
        "Mileage": "10",
        "AveSpeed": "30.0",
        "MaxSpeed": "60.0",
        "DriveTime": "20",
        "AveFuelEconomy": "15.0",
    }]
    stats = compute_trip_stats(rows)
    assert stats["trips"] == 1
    assert stats["total_distance"] == 10.0
    assert stats["avg_distance_per_trip"] == 10.0
    assert stats["avg_consumption"] == 15.0


def test_zero_distance():
    rows = [{
        "OneTripDate": "2026-03-21",
        "Mileage": "0",
        "AveSpeed": "0",
        "MaxSpeed": "0",
        "DriveTime": "5",
        "AveFuelEconomy": "0",
    }]
    stats = compute_trip_stats(rows)
    assert stats["total_distance"] == 0
    assert stats["avg_consumption"] == 0  # no division by zero


def test_missing_fields():
    rows = [{"OneTripDate": "2026-03-21"}]
    stats = compute_trip_stats(rows)
    assert stats["trips"] == 1
    assert stats["total_distance"] == 0
    assert stats["max_speed"] == 0


def test_period_label():
    rows = [{"OneTripDate": "2026-03-21", "Mileage": "1", "AveSpeed": "1",
             "MaxSpeed": "1", "DriveTime": "1", "AveFuelEconomy": "1"}]
    assert compute_trip_stats(rows, period="day")["period"] == "day"
    assert compute_trip_stats(rows, period="week")["period"] == "week"
