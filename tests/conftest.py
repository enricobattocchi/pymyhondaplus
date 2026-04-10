"""Shared test fixtures."""

import pytest


@pytest.fixture
def dashboard_ev():
    """A realistic Honda e dashboard response."""
    return {
        "climateControl": {
            "status": {
                "isActive": False,
                "canBeEnabled": True,
                "remainingTimeInMinutes": 0,
                "initialDurationInMinutes": 30,
            },
        },
        "timestamp": "2026-03-24T22:53:01+00:00",
        "gpsData": {
            "coordinate": {
                "latitude": "43.553456",
                "longitude": "10.332365",
            },
            "dtTime": "2026-03-24T22:53:01+00:00",
            "velocity": {"value": "0.0", "unit": "km/h"},
        },
        "odometer": {"value": "43202", "unit": "km"},
        "temperature": {"cabin": {"value": "24", "unit": "c"}},
        "doorStatus": {
            "firstRowDriver": {"openState": "closed", "lockState": "lock"},
            "firstRowPassenger": {"openState": "closed", "lockState": "lock"},
            "secondRowDriver": {"openState": "closed", "lockState": "lock"},
            "secondRowPassenger": {"openState": "closed", "lockState": "lock"},
            "hood": {"openState": "closed"},
            "trunk": {"openState": "closed"},
        },
        "windowStatus": {
            "frontWindowDR": {"closeState": "closed"},
            "frontWindowAS": {"closeState": "closed"},
            "rearWindowRR": {"closeState": "closed"},
            "rearWindowRL": {"closeState": "closed"},
        },
        "lightStatus": {
            "headlights": {"lightState": "off"},
            "parkingLights": {"lightState": "off"},
        },
        "warningLamps": {"languageCode": "it", "messages": []},
        "evStatus": {
            "soc": "82",
            "evRange": "176",
            "evClimateOffRange": "5",
            "totalRange": "176",
            "chargeStatus": "stopped",
            "plugStatus": "plugged in",
            "chargeMode": "unconfirmed",
            "timeToTargetSoc": "0",
            "intTemp": "15",
            "igStatus": "OFF",
            "homeAway": "AWAY",
            "chargeLimitHome": "80",
            "chargeLimitAway": "90",
            "acTempVal": "04",
            "acDurationSetting": "30",
            "acDefAutoSetting": "def auto on",
            "chargeProhibitionTimerSettings": [
                {
                    "chargeProhibitionDayOfWeek": "mon,tue,wed,thu,fri,sat,sun",
                    "chargeProhibitionTimerCommand": "ON",
                    "chargeProhibitionLocation": "ALL",
                    "chargeProhibitionTimerOption": {
                        "chargeProhibitionStartTime": "0700",
                        "chargeProhibitionEndTime": "0800",
                    },
                },
                {
                    "chargeProhibitionDayOfWeek": "wed",
                    "chargeProhibitionTimerCommand": "ON",
                    "chargeProhibitionLocation": "HOME",
                    "chargeProhibitionTimerOption": {
                        "chargeProhibitionStartTime": "1000",
                        "chargeProhibitionEndTime": "2010",
                    },
                },
            ],
            "acTimerSettings": [
                {
                    "acDayOfWeek": "mon,tue,fri",
                    "acTimerCommand": "timer",
                    "acTimerOption": {"acStartTime1": "0700"},
                },
                {
                    "acDayOfWeek": "unknown",
                    "acTimerCommand": "OFF",
                    "acTimerOption": {"acStartTime1": "0000"},
                },
                {
                    "acDayOfWeek": "",
                    "acTimerCommand": "off",
                    "acTimerOption": {"acStartTime1": "0000"},
                },
            ],
        },
    }


@pytest.fixture
def trip_rows():
    """A list of parsed trip dicts."""
    return [
        {
            "OneTripDate": "2026-03-21",
            "OneTripNo": "1774102361",
            "Mileage": "5",
            "AveSpeed": "7.7",
            "MaxSpeed": "57.2",
            "DriveTime": "37",
            "AveFuelEconomy": "18.7",
            "StartTime": "2026-03-21T14:12:41+00:00",
            "EndTime": "2026-03-21T14:49:55+00:00",
        },
        {
            "OneTripDate": "2026-03-21",
            "OneTripNo": "1774092477",
            "Mileage": "6",
            "AveSpeed": "27.5",
            "MaxSpeed": "83.2",
            "DriveTime": "13",
            "AveFuelEconomy": "14.4",
            "StartTime": "2026-03-21T11:27:57+00:00",
            "EndTime": "2026-03-21T11:41:55+00:00",
        },
        {
            "OneTripDate": "2026-03-19",
            "OneTripNo": "1773937393",
            "Mileage": "33",
            "AveSpeed": "46.3",
            "MaxSpeed": "103.0",
            "DriveTime": "42",
            "AveFuelEconomy": "13.2",
            "StartTime": "2026-03-19T16:23:13+00:00",
            "EndTime": "2026-03-19T17:05:56+00:00",
        },
    ]
