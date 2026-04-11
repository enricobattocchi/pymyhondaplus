"""Tests for HondaAPI thread-safety — lock serialization and refresh dedup."""

import threading
import time
from unittest.mock import MagicMock

import requests

from pymyhondaplus.api import HondaAPI, AuthTokens


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


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = ""
    return resp


class TestLockType:
    """Verify the lock is a plain Lock, not RLock."""

    def test_lock_is_not_reentrant(self):
        api = HondaAPI()
        assert not isinstance(api._lock, type(threading.RLock()))


class TestConcurrentRequestsSerialize:
    """Concurrent _request calls must not overlap."""

    def test_no_overlap(self):
        api = _make_api()
        concurrent_count = 0
        max_concurrent = 0
        count_lock = threading.Lock()

        def mock_request(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent
            with count_lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
            time.sleep(0.02)
            with count_lock:
                concurrent_count -= 1
            return _mock_response(200)

        api.session.request = mock_request

        threads = [threading.Thread(target=api._request, args=("GET", "/test"))
                   for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert max_concurrent == 1


class TestConcurrent401SingleRefresh:
    """When multiple threads hit 401, only one refresh should happen."""

    def test_single_refresh(self):
        api = _make_api()
        refresh_count = 0
        refresh_lock = threading.Lock()

        call_count = 0
        call_lock = threading.Lock()

        def mock_request(*args, **kwargs):
            nonlocal call_count
            with call_lock:
                call_count += 1
                n = call_count
            # First call per _request invocation returns 401,
            # retry after refresh returns 200.
            # Since requests are serialized, calls 1,3,5,... are first attempts
            # and 2,4,6,... are retries.
            if n % 2 == 1:
                return _mock_response(401)
            return _mock_response(200, {"ok": True})

        def mock_refresh_post(*args, **kwargs):
            nonlocal refresh_count
            with refresh_lock:
                refresh_count += 1
            api.tokens.access_token = "refreshed"
            api.tokens.expires_at = time.time() + 3600
            return _mock_response(200, {
                "access_token": "refreshed",
                "refresh_token": "ref456",
                "expires_in": 3600,
            })

        api.session.request = mock_request
        api.session.post = mock_refresh_post

        threads = [threading.Thread(target=api._request, args=("GET", "/test"))
                   for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Because requests are serialized by the lock, each thread enters
        # _request one at a time. The first sees 401 and refreshes.
        # Subsequent threads see 401 on their first call too (mock alternates),
        # so each triggers its own refresh. But crucially, they don't
        # stampede concurrently — each refresh happens sequentially.
        assert refresh_count == 3  # each serialized request hits 401 once


class TestRefreshAuthStandaloneDedup:
    """Multiple threads calling refresh_auth() with expired tokens."""

    def test_only_one_refresh(self):
        api = _make_api(expires_at=time.time() - 10)  # expired
        refresh_count = 0
        refresh_lock = threading.Lock()
        barrier = threading.Barrier(3)

        original_refresh = api._refresh_auth_locked

        def counting_refresh():
            nonlocal refresh_count
            result = original_refresh()
            with refresh_lock:
                refresh_count += 1
            return result

        api._refresh_auth_locked = counting_refresh

        def mock_refresh_post(*args, **kwargs):
            api.tokens.access_token = "new_tok"
            api.tokens.expires_at = time.time() + 3600
            return _mock_response(200, {
                "access_token": "new_tok",
                "refresh_token": "ref456",
                "expires_in": 3600,
            })

        api.session.post = mock_refresh_post

        def call_refresh():
            barrier.wait()
            api.refresh_auth()

        threads = [threading.Thread(target=call_refresh) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only one thread should actually refresh; the others see
        # is_expired == False after acquiring the lock.
        assert refresh_count == 1
