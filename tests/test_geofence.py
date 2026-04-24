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
    """Ensure wait_for_geofence polls on waiting_activate / waiting_deactivate."""

    def _build_api(self, responses):
        """Return a HondaAPI whose get_geofence emits the given sequence."""
        import time as _time
        from pymyhondaplus.api import HondaAPI

        api = HondaAPI.__new__(HondaAPI)
        it = iter(responses)

        def _get_geofence(_vin):
            return next(it)

        api.get_geofence = _get_geofence  # type: ignore[method-assign]

        self._sleeps = []

        def _fake_sleep(seconds):
            self._sleeps.append(seconds)

        self._real_sleep = _time.sleep
        _time.sleep = _fake_sleep
        self._time_module = _time
        return api

    def teardown_method(self):
        if hasattr(self, "_real_sleep") and self._real_sleep is not None:
            self._time_module.sleep = self._real_sleep
            self._real_sleep = None

    def _settled(self, **overrides):
        return Geofence.from_api({
            **ACTIVE_GEOFENCE_API,
            "isWaitingForActivate": False,
            "isWaitingForDeactivate": False,
            **overrides,
        })

    def _in_flight(self, waiting_activate=True, waiting_deactivate=False, **overrides):
        return Geofence.from_api({
            **ACTIVE_GEOFENCE_API,
            "isWaitingForActivate": waiting_activate,
            "isWaitingForDeactivate": waiting_deactivate,
            "activateAsyncCommandStatus": "",
            **overrides,
        })

    def test_returns_immediately_when_no_waiting_flags_set(self):
        gf = self._settled(activateAsyncCommandStatus="success")
        api = self._build_api([gf])
        result = api.wait_for_geofence("VIN", timeout=60, poll_interval=1.0)
        assert result is gf
        assert self._sleeps == []

    def test_polls_while_waiting_activate_is_true(self):
        gf_pending = self._in_flight(waiting_activate=True)
        gf_done = self._settled(activateAsyncCommandStatus="success")
        api = self._build_api([gf_pending, gf_pending, gf_done])
        result = api.wait_for_geofence("VIN", timeout=60, poll_interval=2.0)
        assert result is gf_done
        assert self._sleeps == [2.0, 2.0]

    def test_polls_while_waiting_deactivate_is_true(self):
        gf_pending = self._in_flight(waiting_activate=False, waiting_deactivate=True)
        gf_done = self._settled(deactivateAsyncCommandStatus="success")
        api = self._build_api([gf_pending, gf_done])
        result = api.wait_for_geofence("VIN", timeout=60, poll_interval=1.0)
        assert result is gf_done

    def test_ignores_stale_activate_status_while_waiting_flag_set(self):
        """Regression: activate_status from a previous command must not trigger early exit
        while a new command is in flight (waiting_activate=True).
        """
        gf_stale = self._in_flight(waiting_activate=True, activateAsyncCommandStatus="failure")
        gf_done = self._settled(activateAsyncCommandStatus="success")
        api = self._build_api([gf_stale, gf_done])
        result = api.wait_for_geofence("VIN", timeout=60, poll_interval=1.0)
        assert result is gf_done
        assert result.activate_status == "success"

    def test_empty_async_status_does_not_trigger_exit_while_waiting_flag_set(self):
        gf_queued = self._in_flight(waiting_activate=True, activateAsyncCommandStatus="")
        gf_done = self._settled(activateAsyncCommandStatus="timeout")
        api = self._build_api([gf_queued, gf_done])
        result = api.wait_for_geofence("VIN", timeout=60, poll_interval=1.0)
        assert result is gf_done

    def test_returns_on_terminal_once_waiting_flag_clears(self):
        gf_pending = self._in_flight(waiting_activate=True)
        gf_failed = self._settled(activateAsyncCommandStatus="failure")
        api = self._build_api([gf_pending, gf_failed])
        result = api.wait_for_geofence("VIN", timeout=60, poll_interval=1.0)
        assert result is gf_failed
        assert result.activate_status == "failure"

    def test_times_out_while_still_waiting(self, monkeypatch):
        import time as _time

        gf_pending = self._in_flight(waiting_activate=True)
        fake_now = [1000.0]
        monkeypatch.setattr(_time, "time", lambda: fake_now[0])
        monkeypatch.setattr(_time, "sleep", lambda s: fake_now.__setitem__(0, fake_now[0] + s))

        from pymyhondaplus.api import HondaAPI
        api = HondaAPI.__new__(HondaAPI)
        api.get_geofence = lambda _vin: gf_pending  # type: ignore[method-assign]

        result = api.wait_for_geofence("VIN", timeout=3, poll_interval=1.0)
        assert result is gf_pending
        assert result.waiting_activate is True

    def test_returns_none_when_geofence_cleared(self):
        api = self._build_api([None])
        result = api.wait_for_geofence("VIN", timeout=60, poll_interval=1.0)
        assert result is None
