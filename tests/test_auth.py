"""Tests for HondaAuth — login flow and utility functions."""

import base64
import json
from unittest.mock import MagicMock

import pytest

from pymyhondaplus.api import HondaAPIError, HondaAuthError
from pymyhondaplus.auth import DeviceKey, HondaAuth, encrypt_request


class TestEncryptRequest:

    def test_returns_required_fields(self):
        result = encrypt_request({"email": "test@test.com"})
        assert "encryptedOneTimeKey" in result
        assert "encryptedOneTimeSalt" in result
        assert "encryptedPayload" in result
        assert "keyId" in result

    def test_payload_is_base64(self):
        result = encrypt_request({"foo": "bar"})
        decoded = base64.b64decode(result["encryptedPayload"])
        assert len(decoded) > 0

    def test_different_inputs_different_output(self):
        r1 = encrypt_request({"a": "1"})
        r2 = encrypt_request({"b": "2"})
        assert r1["encryptedPayload"] != r2["encryptedPayload"]


class TestExtractUserId:

    def test_extracts_sub_from_jwt(self):
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "USER123"}).encode()
        ).decode().rstrip("=")
        token = f"header.{payload}.signature"
        assert HondaAuth.extract_user_id(token) == "USER123"

    def test_returns_empty_on_invalid_token(self):
        assert HondaAuth.extract_user_id("not-a-jwt") == ""

    def test_returns_empty_on_missing_sub(self):
        payload = base64.urlsafe_b64encode(
            json.dumps({"other": "field"}).encode()
        ).decode().rstrip("=")
        token = f"header.{payload}.signature"
        assert HondaAuth.extract_user_id(token) == ""


class TestParseVerifyLinkKey:

    def test_extracts_key_and_type(self):
        link = "https://example.com/verify?key=abc123&type=mfa"
        key, link_type = HondaAuth.parse_verify_link_key(link)
        assert key == "abc123"
        assert link_type == "mfa"

    def test_defaults_type_to_mfa(self):
        link = "https://example.com/verify?key=abc123"
        key, link_type = HondaAuth.parse_verify_link_key(link)
        assert key == "abc123"
        assert link_type == "mfa"

    def test_url_decodes_key(self):
        link = "https://example.com/verify?key=a%20b%2Fc&type=mfa"
        key, _ = HondaAuth.parse_verify_link_key(link)
        assert key == "a b/c"

    def test_returns_empty_on_no_key(self):
        link = "https://example.com/verify?other=value"
        key, _ = HondaAuth.parse_verify_link_key(link)
        assert key == ""


def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text or json.dumps(json_data or {})
    return resp


class TestHondaAuthLogin:

    def _make_auth(self):
        dk = DeviceKey()
        auth = HondaAuth(device_key=dk)
        return auth

    def test_initiate_login_returns_json(self):
        auth = self._make_auth()
        resp = _mock_response(200, {
            "transactionId": "txn123",
            "signatureChallenge": "challenge456",
        })
        auth.session.post = MagicMock(return_value=resp)

        result = auth.initiate_login("user@test.com", "pass123")

        assert result["transactionId"] == "txn123"
        assert result["signatureChallenge"] == "challenge456"
        auth.session.post.assert_called_once()

    def test_initiate_login_raises_on_error(self):
        auth = self._make_auth()
        auth.session.post = MagicMock(
            return_value=_mock_response(401, text="Unauthorized")
        )

        with pytest.raises(HondaAuthError, match="initiate-login failed"):
            auth.initiate_login("user@test.com", "pass123")

    def test_complete_login_signs_challenge(self):
        auth = self._make_auth()
        resp = _mock_response(200, {
            "access_token": "tok",
            "refresh_token": "ref",
        })
        auth.session.post = MagicMock(return_value=resp)

        result = auth.complete_login(
            "user@test.com", "pass123", "txn123", "challenge456"
        )

        assert result["access_token"] == "tok"

    def test_complete_login_raises_on_error(self):
        auth = self._make_auth()
        auth.session.post = MagicMock(
            return_value=_mock_response(500, text="Server Error")
        )

        with pytest.raises(HondaAuthError, match="complete-login failed"):
            auth.complete_login("user@test.com", "pass123", "txn", "ch")

    def test_login_chains_initiate_and_complete(self):
        auth = self._make_auth()
        initiate_resp = _mock_response(200, {
            "transactionId": "txn",
            "signatureChallenge": "ch",
        })
        complete_resp = _mock_response(200, {
            "access_token": "final_tok",
        })
        auth.session.post = MagicMock(side_effect=[initiate_resp, complete_resp])

        result = auth.login("user@test.com", "pass123")

        assert result["access_token"] == "final_tok"
        assert auth.session.post.call_count == 2

    def test_register_device_raises_on_error(self):
        auth = self._make_auth()
        auth.session.post = MagicMock(
            return_value=_mock_response(403, text="Forbidden")
        )

        with pytest.raises(HondaAuthError, match="register failed"):
            auth.register_device("user@test.com", "pass123")


class TestHondaAuthErrorInheritance:

    def test_auth_error_is_api_error(self):
        err = HondaAuthError(401, "bad credentials")
        assert isinstance(err, HondaAPIError)

    def test_catchable_as_api_error(self):
        with pytest.raises(HondaAPIError):
            raise HondaAuthError(401, "bad credentials")

    def test_has_status_code(self):
        err = HondaAuthError(403, "forbidden")
        assert err.status_code == 403
