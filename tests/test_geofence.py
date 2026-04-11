"""Tests for Geofence dataclass and coordinate conversion."""

from pymyhondaplus.api import Geofence


# Colosseum, Rome: 41.890251°N, 12.492373°E → MAS: 150804903, 44972542
ACTIVE_GEOFENCE_API = {
    "nickName": "Geofence",
    "activationEnable": "enabled",
    "activationSetup": "active",
    "geoFenceSetup": {
        "type": {"type": "circle", "mode": "inclusion"},
        "radius": {"value": 5.0, "unit": "km"},
        "gpsDetails": {
            "coordinate": {
                "latitude": 150804903,
                "longitude": 44972542,
                "datum": "wgs84",
                "format": "decimal_degrees",
            }
        },
    },
    "schedule": {"type": "always", "expirationTime": "2023-03-11T22:51:08+00:00"},
    "isCommandProcessing": False,
    "isWaitingForActivate": False,
    "isWaitingForDeactivate": False,
    "activateAsyncCommandStatus": "success",
    "deactivateAsyncCommandStatus": "",
}

DISABLED_GEOFENCE_API = {
    "activationEnable": "disabled",
    "isCommandProcessing": False,
    "isWaitingForActivate": False,
    "isWaitingForDeactivate": False,
    "activateAsyncCommandStatus": "",
    "deactivateAsyncCommandStatus": "success",
}

PROCESSING_GEOFENCE_API = {
    **ACTIVE_GEOFENCE_API,
    "isCommandProcessing": True,
    "isWaitingForActivate": True,
    "activateAsyncCommandStatus": "",
}


class TestGeofenceFromApi:

    def test_active_geofence(self):
        gf = Geofence.from_api(ACTIVE_GEOFENCE_API)
        assert gf is not None
        assert gf.active is True
        assert gf.name == "Geofence"
        assert gf.radius == 5.0
        assert gf.schedule_type == "always"
        assert gf.processing is False

    def test_disabled_returns_none(self):
        gf = Geofence.from_api(DISABLED_GEOFENCE_API)
        assert gf is None

    def test_processing_state(self):
        gf = Geofence.from_api(PROCESSING_GEOFENCE_API)
        assert gf is not None
        assert gf.processing is True
        assert gf.waiting_activate is True
        assert gf.waiting_deactivate is False


class TestCoordinateConversion:

    def test_mas_to_degrees(self):
        gf = Geofence.from_api(ACTIVE_GEOFENCE_API)
        # 150804903 MAS ≈ 41.890251° (Colosseum, Rome)
        assert abs(gf.latitude - 41.890251) < 0.001
        # 44972542 MAS ≈ 12.492373°
        assert abs(gf.longitude - 12.492373) < 0.001

    def test_degrees_to_mas_roundtrip(self):
        lat, lon = 41.890251, 12.492373
        lat_mas = int(lat * 3_600_000)
        lon_mas = int(lon * 3_600_000)
        assert abs(lat_mas / 3_600_000 - lat) < 0.000001
        assert abs(lon_mas / 3_600_000 - lon) < 0.000001

    def test_zero_coordinates(self):
        data = {**ACTIVE_GEOFENCE_API}
        data["geoFenceSetup"] = {
            "type": {"type": "circle", "mode": "inclusion"},
            "radius": {"value": 1.0, "unit": "km"},
            "gpsDetails": {"coordinate": {"latitude": 0, "longitude": 0}},
        }
        gf = Geofence.from_api(data)
        assert gf.latitude == 0.0
        assert gf.longitude == 0.0
