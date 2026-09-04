"""Tests for the user-agreement flow and Honda's 10052 error code."""

import time
from unittest.mock import MagicMock

import pytest
import requests

from pymyhondaplus.api import (
    AuthTokens,
    HondaAgreementError,
    HondaAPI,
    HondaAPIError,
    UserAgreement,
)


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
    return resp


class TestErrorCodeMapping:
    """Honda's error codes map to dedicated exceptions."""

    def test_10052_raises_agreement_error(self):
        api = _make_api()
        api.session.request = MagicMock(return_value=_mock_response(
            502, {"errorCode": 10052, "errorMessage": "BR006 Rule Failed"},
        ))
        with pytest.raises(HondaAgreementError) as exc:
            api._request("GET", "/tsp/dashboard-latest?vin=X")
        assert exc.value.status_code == 502
        assert "terms and conditions" in str(exc.value)

    def test_other_codes_are_left_alone(self):
        api = _make_api()
        api.session.request = MagicMock(return_value=_mock_response(
            502, {"errorCode": 10001, "errorMessage": "Vehicle not found"},
        ))
        resp = api._request("GET", "/tsp/dashboard-latest?vin=X")
        assert resp.status_code == 502

    def test_agreement_endpoints_are_exempt(self):
        """Mapping 10052 on these would make the agreement impossible to accept."""
        api = _make_api()
        api.session.request = MagicMock(return_value=_mock_response(
            502, {"errorCode": 10052},
        ))
        resp = api._request("GET", "/tsp/get-user-agreement?language=it")
        assert resp.status_code == 502

    def test_non_json_body_does_not_break(self):
        api = _make_api()
        resp = _mock_response(502, text="<html>gateway</html>")
        resp.json.side_effect = ValueError
        api.session.request = MagicMock(return_value=resp)
        assert api._request("GET", "/tsp/dashboard-latest").status_code == 502


class TestUserAgreementModel:
    """Honda's field names differ from the ones the model exposes."""

    def test_from_api_maps_honda_field_names(self):
        agreement = UserAgreement.from_api(
            {"agreement": False, "termId": "100013", "fileContent": "text"},
        )
        assert agreement == UserAgreement(
            term_id="100013", accepted=False, text="text",
        )

    def test_from_api_tolerates_missing_fields(self):
        assert UserAgreement.from_api({}) == UserAgreement()


class TestAgreementCalls:
    """get_user_agreement() and accept_user_agreement()."""

    def test_get_reads_the_pending_agreement(self):
        api = _make_api()
        api.session.request = MagicMock(return_value=_mock_response(
            200, {"agreement": False, "termId": "100013", "fileContent": "t"},
        ))
        agreement = api.get_user_agreement(language="it")
        assert agreement.term_id == "100013"
        assert agreement.accepted is False
        url = api.session.request.call_args[0][1]
        assert "agreementType=1" in url
        assert "personalId=pid789" in url

    def test_accept_posts_the_payload_the_app_sends(self):
        api = _make_api()
        api.session.request = MagicMock(return_value=_mock_response(
            200, {"agreement": True, "termId": "100013", "fileContent": "t"},
        ))
        result = api.accept_user_agreement("100013", language="it")
        assert result.accepted is True
        post = next(c for c in api.session.request.call_args_list
                    if c[0][0] == "POST")
        assert post[1]["json"] == {
            "termId": "100013",
            "action": "accept",
            "personalId": "pid789",
            "agreementType": "1",
            "language": "it",
        }

    def test_accept_looks_up_the_term_id_when_omitted(self):
        api = _make_api()
        api.session.request = MagicMock(return_value=_mock_response(
            200, {"agreement": False, "termId": "100013", "fileContent": "t"},
        ))
        api.accept_user_agreement()
        post = next(c for c in api.session.request.call_args_list
                    if c[0][0] == "POST")
        assert post[1]["json"]["termId"] == "100013"

    def test_accept_without_any_agreement_raises(self):
        api = _make_api()
        api.session.request = MagicMock(return_value=_mock_response(
            200, {"agreement": False, "termId": "", "fileContent": ""},
        ))
        with pytest.raises(HondaAPIError):
            api.accept_user_agreement()

    def test_personal_id_falls_back_to_login_info(self):
        """Stored tokens can carry an empty personal ID."""
        api = _make_api(personal_id="")
        api.session.request = MagicMock(return_value=_mock_response(
            200, {"personalId": "frominfo", "agreement": True,
                  "termId": "100013", "fileContent": "t"},
        ))
        api.get_user_agreement()
        url = api.session.request.call_args[0][1]
        assert "personalId=frominfo" in url
