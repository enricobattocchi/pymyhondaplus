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



class TestWaitForGeofence:
    """Ensure wait_for_geofence polls until activate/deactivate status is terminal."""

    def _build_api(self, responses):
        """Return a HondaAPI whose get_geofence emits the given sequence of Geofence objects."""
        import time as _time

        from pymyhondaplus.api import HondaAPI

        api = HondaAPI.__new__(HondaAPI)  # skip __init__ (no auth needed)
        it = iter(responses)

        def _get_geofence(_vin):
            return next(it)

        api.get_geofence = _get_geofence  # type: ignore[method-assign]

        # Avoid real sleeping between polls.
        self._sleeps = []

        def _fake_sleep(seconds):
            self._sleeps.append(seconds)

        self._real_sleep = _time.sleep
        _time.sleep = _fake_sleep  # monkey-patch module-level
        self._time_module = _time
        return api

    def teardown_method(self):
        # Restore real sleep.
        if hasattr(self, "_real_sleep") and self._real_sleep is not None:
            self._time_module.sleep = self._real_sleep
            self._real_sleep = None

    def test_returns_immediately_on_terminal_success(self):
        gf_success = Geofence.from_api({**ACTIVE_GEOFENCE_API, "activateAsyncCommandStatus": "success"})
        api = self._build_api([gf_success])
        result = api.wait_for_geofence("VIN", timeout=60, poll_interval=1.0)
        assert result is gf_success
        assert self._sleeps == []  # no polling needed

    def test_returns_immediately_on_terminal_failure(self):
        gf_failure = Geofence.from_api({**ACTIVE_GEOFENCE_API, "activateAsyncCommandStatus": "failure"})
        api = self._build_api([gf_failure])
        result = api.wait_for_geofence("VIN", timeout=60, poll_interval=1.0)
        assert result is gf_failure

    def test_returns_immediately_on_terminal_timeout(self):
        gf_timeout = Geofence.from_api({**ACTIVE_GEOFENCE_API, "activateAsyncCommandStatus": "timeout"})
        api = self._build_api([gf_timeout])
        result = api.wait_for_geofence("VIN", timeout=60, poll_interval=1.0)
        assert result is gf_timeout

    def test_polls_past_is_command_processing_until_activate_status_terminal(self):
        """Regression: isCommandProcessing=False alone is not enough to exit."""
        raw_processing = {
            **ACTIVE_GEOFENCE_API,
            "isCommandProcessing": False,  # server state machine idle
            "activateAsyncCommandStatus": "",  # but async command still pending (empty != terminal for "processing")
        }
        # Empty string IS in the terminal set — simulate "still pending" via a non-empty non-terminal value.
        raw_processing["activateAsyncCommandStatus"] = "processing"
        gf_pending = Geofence.from_api(raw_processing)
        gf_success = Geofence.from_api({**ACTIVE_GEOFENCE_API, "activateAsyncCommandStatus": "success"})
        api = self._build_api([gf_pending, gf_pending, gf_success])
        result = api.wait_for_geofence("VIN", timeout=60, poll_interval=2.0)
        assert result is gf_success
        assert self._sleeps == [2.0, 2.0]  # slept twice between polls

    def test_times_out_without_terminal_status(self, monkeypatch):
        """If deadline hits while async status still pending, return last observed state."""
        import time as _time

        raw_pending = {**ACTIVE_GEOFENCE_API, "activateAsyncCommandStatus": "processing"}
        gf_pending = Geofence.from_api(raw_pending)

        # Simulate clock advancing past the deadline after a few polls.
        fake_now = [1000.0]
        monkeypatch.setattr(_time, "time", lambda: fake_now[0])
        monkeypatch.setattr(_time, "sleep", lambda s: fake_now.__setitem__(0, fake_now[0] + s))

        from pymyhondaplus.api import HondaAPI
        api = HondaAPI.__new__(HondaAPI)
        api.get_geofence = lambda _vin: gf_pending  # type: ignore[method-assign]

        try:
            result = api.wait_for_geofence("VIN", timeout=3, poll_interval=1.0)
        finally:
            # pytest monkeypatch auto-restores at teardown
            pass
        assert result is gf_pending
        assert result.activate_status == "processing"

    def test_returns_none_when_geofence_cleared(self):
        api = self._build_api([None])
        result = api.wait_for_geofence("VIN", timeout=60, poll_interval=1.0)
        assert result is None

    def test_empty_async_status_is_terminal(self):
        """An empty string means the command is not pending; do not keep polling."""
        gf_empty = Geofence.from_api({
            **ACTIVE_GEOFENCE_API,
            "activateAsyncCommandStatus": "",
            "deactivateAsyncCommandStatus": "",
        })
        api = self._build_api([gf_empty])
        result = api.wait_for_geofence("VIN", timeout=60, poll_interval=1.0)
        assert result is gf_empty
        assert self._sleeps == []
