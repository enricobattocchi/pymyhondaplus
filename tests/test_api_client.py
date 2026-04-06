"""Tests for HondaAPI HTTP layer — auth headers, token refresh, error handling."""

from unittest.mock import MagicMock
import time

import pytest
import requests

from pymyhondaplus.api import HondaAPI, HondaAPIError, AuthTokens


def _make_api(**token_overrides):
    """Create a HondaAPI instance with fake tokens and no storage."""
    api = HondaAPI()
    defaults = dict(
        access_token="tok123",
        refresh_token="ref456",
        expires_at=time.time() + 3600,
        personal_id="pid789",
        user_id="uid",
    )
    defaults.update(token_overrides)
    api.tokens = AuthTokens(**defaults)
    return api


def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text or ""
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


class TestRequestAuth:
    """_request() sets correct auth headers and handles 401 retry."""

    def test_sets_bearer_and_personal_id(self):
        api = _make_api()
        resp = _mock_response(200, {"ok": True})
        api.session.request = MagicMock(return_value=resp)

        api._request("GET", "/test")

        _, kwargs = api.session.request.call_args
        assert kwargs["headers"]["authorization"] == "Bearer tok123"
        assert kwargs["headers"]["x-app-personal-id"] == "pid789"

    def test_sets_bearer_without_personal_id(self):
        api = _make_api(personal_id="")
        resp = _mock_response(200)
        api.session.request = MagicMock(return_value=resp)

        api._request("GET", "/test")

        _, kwargs = api.session.request.call_args
        assert kwargs["headers"]["authorization"] == "Bearer tok123"
        assert "x-app-personal-id" not in kwargs["headers"]

    def test_retries_on_401_with_token_refresh(self):
        api = _make_api()
        resp_401 = _mock_response(401)
        resp_ok = _mock_response(200, {"data": "fresh"})
        api.session.request = MagicMock(side_effect=[resp_401, resp_ok])

        # Mock _refresh_auth_locked to update the token
        def fake_refresh():
            api.tokens.access_token = "newtok"
            return api.tokens
        api._refresh_auth_locked = fake_refresh

        result = api._request("GET", "/test")

        assert result == resp_ok
        assert api.session.request.call_count == 2
        # Second call should use refreshed token
        _, kwargs2 = api.session.request.call_args_list[1]
        assert kwargs2["headers"]["authorization"] == "Bearer newtok"

    def test_raises_without_tokens(self):
        api = _make_api(access_token="")
        with pytest.raises(HondaAPIError, match="No tokens configured"):
            api._request("GET", "/test")


class TestPutMethods:
    """PUT methods send correct payloads and return command IDs."""

    def _setup_put(self, api):
        """Set up session mock for PUT methods."""
        resp = _mock_response(202, {
            "statusQueryGetUri": "https://example.com/status?id=cmd-abc-123"
        })
        api.session.put = MagicMock(return_value=resp)
        # Also mock session.request for methods that go through _request
        api.session.request = MagicMock(return_value=resp)
        return resp

    def test_set_charge_limit_payload(self):
        api = _make_api()
        self._setup_put(api)

        result = api.set_charge_limit("VIN123", home=85, away=95)

        assert result == "cmd-abc-123"
        # Verify the PUT was called (either directly or via _request)
        put_call = api.session.put if api.session.put.called else None
        req_call = api.session.request if api.session.request.called else None
        called = put_call or req_call
        assert called is not None

    def test_set_charge_limit_invalid(self):
        api = _make_api()
        with pytest.raises(ValueError, match="Charge limits must be one of"):
            api.set_charge_limit("VIN123", home=77, away=90)

    def test_set_charge_schedule_payload(self):
        api = _make_api()
        self._setup_put(api)

        rules = [{"days": "mon,tue", "location": "all",
                  "start_time": "07:00", "end_time": "08:00"}]
        result = api.set_charge_schedule("VIN123", rules)

        assert result == "cmd-abc-123"

    def test_set_climate_schedule_payload(self):
        api = _make_api()
        self._setup_put(api)

        rules = [{"days": "mon,fri", "start_time": "07:00"}]
        result = api.set_climate_schedule("VIN123", rules)

        assert result == "cmd-abc-123"

    def test_put_methods_use_request_for_401_retry(self):
        """PUT methods go through _request() and get automatic 401 retry."""
        api = _make_api()
        resp_401 = _mock_response(401)
        resp_ok = _mock_response(202, {
            "statusQueryGetUri": "https://example.com/status?id=retried-ok"
        })
        api.session.request = MagicMock(side_effect=[resp_401, resp_ok])

        def fake_refresh():
            api.tokens.access_token = "refreshed"
            return api.tokens
        api._refresh_auth_locked = fake_refresh

        result = api.set_charge_limit("VIN123", home=80, away=90)

        assert result == "retried-ok"
        assert api.session.request.call_count == 2


class TestErrorTypes:
    """All API methods raise HondaAPIError on HTTP errors."""

    def test_get_user_info_raises_honda_error_on_failure(self):
        api = _make_api()
        resp = _mock_response(500, text="Internal Server Error")
        api.session.request = MagicMock(return_value=resp)

        with pytest.raises(HondaAPIError):
            api.get_user_info()

    def test_get_trips_raises_honda_error_on_failure(self):
        api = _make_api()
        resp = _mock_response(403, text="Forbidden")
        api.session.request = MagicMock(return_value=resp)

        with pytest.raises(HondaAPIError):
            api.get_trips("VIN123", month_start="2026-03-01T00:00:00.000Z")

    def test_remote_command_raises_honda_error(self):
        api = _make_api()
        resp = _mock_response(500, text="Server Error")
        api.session.request = MagicMock(return_value=resp)

        with pytest.raises(HondaAPIError):
            api.remote_lock("VIN123")

    def test_set_charge_limit_raises_honda_error_on_failure(self):
        api = _make_api()
        resp = _mock_response(400, text="Bad Request")
        api.session.put = MagicMock(return_value=resp)
        api.session.request = MagicMock(return_value=resp)

        with pytest.raises(HondaAPIError):
            api.set_charge_limit("VIN123", home=80, away=90)


class TestTimeoutAdapter:
    """_TimeoutAdapter applies default timeout to all requests."""

    def test_applies_default_timeout(self):
        from pymyhondaplus.api import _TimeoutAdapter, DEFAULT_TIMEOUT
        adapter = _TimeoutAdapter()
        kwargs = {"timeout": None}
        # Patch super().send to capture kwargs
        from unittest.mock import patch
        with patch("requests.adapters.HTTPAdapter.send") as mock_send:
            adapter.send("request", **kwargs)
            _, call_kwargs = mock_send.call_args
            assert call_kwargs["timeout"] == DEFAULT_TIMEOUT

    def test_respects_explicit_timeout(self):
        from pymyhondaplus.api import _TimeoutAdapter
        adapter = _TimeoutAdapter()
        kwargs = {"timeout": 10}
        from unittest.mock import patch
        with patch("requests.adapters.HTTPAdapter.send") as mock_send:
            adapter.send("request", **kwargs)
            _, call_kwargs = mock_send.call_args
            assert call_kwargs["timeout"] == 10

    def test_hanging_server_times_out(self):
        """Real connection to a black-hole socket times out instead of hanging."""
        import socket
        import threading
        from pymyhondaplus.api import _TimeoutAdapter

        # Start a server that accepts but never responds
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        stop = threading.Event()

        def accept_and_hold():
            conn, _ = srv.accept()
            # Hold the connection open, never respond
            stop.wait()
            conn.close()

        t = threading.Thread(target=accept_and_hold, daemon=True)
        t.start()

        try:
            session = requests.Session()
            adapter = _TimeoutAdapter(timeout=1)
            session.mount("http://", adapter)

            with pytest.raises(requests.exceptions.ReadTimeout):
                session.get(f"http://127.0.0.1:{port}/")
        finally:
            stop.set()
            srv.close()
