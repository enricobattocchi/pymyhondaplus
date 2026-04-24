"""Tests for Vehicle, VehicleCapabilities, Subscription, UIConfiguration, and UserProfile."""

import time

import pytest
from pymyhondaplus.api import (
    AuthTokens, Subscription, UserProfile, Vehicle, VehicleCapabilities,
)


# -- Sample API data matching captured response --

FULL_VEHICLE_API = {
    "vin": "JHMZC7840LX204934",
    "vehicleNickName": "Honda e",
    "vehicleRegNumber": "GE395KM",
    "role": "primary",
    "fuelType": "E",
    "grade": "E ADVANCE",
    "modelYear": 2020,
    "vehicleCategoryCode": "2EX",
    "registrationDate": "2021-03-23",
    "dateProduction": "2020-11-03T00:00:00.000Z",
    "doors": 5,
    "transmission": "A",
    "weight": 1595.0,
    "countryCode": "IT",
    "vehicleFront34ImageUrl": "https://example.com/front.png",
    "vehicleSideImageUrl": "https://example.com/side.png",
    "vehicleUIConfiguration": {
        "friendlyModelName": "Honda e",
        "hideWindowStatus": False,
        "hideRearDoorStatus": False,
        "shouldHideInternalTemperature": False,
        "shouldHideClimateSettingsButton": False,
        "shouldDisplayPluginWarningForClimateSchedule": False,
    },
    "vehicleCapability": {
        "capabilities": {
            "telematicsRemoteLockUnlock": {"featureStatus": "active"},
            "telematicsRemoteClimate": {"featureStatus": "active"},
            "telematicsRemoteCharge": {"featureStatus": "active"},
            "telematicsRemoteHorn": {"featureStatus": "active"},
            "digitalKey": {"featureStatus": "active"},
            "telematicsRemoteChargeSchedule": {"featureStatus": "active"},
            "telematicsRemoteClimateSchedule": {"featureStatus": "active"},
            "telematicsMaxChargeSettings": {"featureStatus": "active"},
            "telematicsRemoteCarFinder": {"featureStatus": "active"},
            "telematicsJourneyHistory": {"featureStatus": "active"},
            "telematicsSendPoi": {"featureStatus": "active"},
            "telematicsGeoFence": {"featureStatus": "active"},
            "telematicsCareAssistance": {"featureStatus": "notSupported"},
            "smartCharge": {"featureStatus": "notSupported"},
        }
    },
    "packageInfo": [
        {
            "description": "My Honda+",
            "billStatus": "ACTIVE",
            "packageType": "STANDARD",
            "price": 4.99,
            "currency1": "EUR",
            "paymentTerm": "MONTHLY",
            "term": 1,
            "trialTerm": 0,
            "renewal": True,
            "startDate": "2026-04-05T00:00:00+00:00",
            "endDate": "2026-05-05T00:00:00+00:00",
            "nextPaymentDate": "2026-04-30T00:00:00+00:00",
            "services": [
                {"code": "remote-lock", "description": "Remote lock"},
                {"code": "ev-remote-charge", "description": "Remote charge"},
            ],
        }
    ],
}

MINIMAL_VEHICLE_API = {"vin": "VIN_MINIMAL"}


class TestVehicleFromApi:

    def test_full_entry(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        assert v.vin == "JHMZC7840LX204934"
        assert v.name == "Honda e"
        assert v.plate == "GE395KM"
        assert v.role == "primary"
        assert v.fuel_type == "E"
        assert v.model_name == "Honda e"
        assert v.grade == "E ADVANCE"
        assert v.model_year == "2020"
        assert v.category_code == "2EX"
        assert v.registration_date == "2021-03-23"
        assert v.production_date == "2020-11-03"
        assert v.doors == 5
        assert v.transmission == "A"
        assert v.weight == 1595.0
        assert v.country_code == "IT"
        assert v.image_front == "https://example.com/front.png"
        assert v.image_side == "https://example.com/side.png"

    def test_ui_config(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        assert v.ui_config.hide_window_status is False
        assert v.ui_config.hide_rear_door_status is False
        assert v.ui_config.hide_internal_temperature is False
        assert v.ui_config.hide_climate_settings is False
        assert v.ui_config.show_plugin_warning_climate_schedule is False

    def test_minimal_entry(self):
        v = Vehicle.from_api(MINIMAL_VEHICLE_API)
        assert v.vin == "VIN_MINIMAL"
        assert v.name == ""
        assert v.model_name == ""
        assert v.capabilities.remote_lock is False


class TestVehicleCapabilitiesFromApi:

    def test_active_capabilities(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        caps = v.capabilities
        assert caps.remote_lock is True
        assert caps.remote_climate is True
        assert caps.remote_charge is True
        assert caps.remote_horn is True
        assert caps.digital_key is True
        assert caps.charge_schedule is True
        assert caps.climate_schedule is True
        assert caps.max_charge is True
        assert caps.car_finder is True
        assert caps.journey_history is True
        assert caps.send_poi is True
        assert caps.geo_fence is True

    def test_not_supported_excluded(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        # smartCharge is notSupported in the test data, not exposed as a named field
        # but raw dict preserves it
        assert "smartCharge" in v.capabilities.raw

    def test_empty_capability_map(self):
        caps = VehicleCapabilities.from_api({})
        assert caps.remote_lock is False
        assert caps.digital_key is False
        assert caps.raw == {}

    def test_active_api_keys_from_raw(self):
        caps = VehicleCapabilities(raw={
            "telematicsRemoteLockUnlock": {"featureStatus": "active"},
            "telematicsRemoteHorn": {"featureStatus": "notSupported"},
            "useSpecificTemperatureControl": {"featureStatus": "active"},
            "someFutureFlag": {"featureStatus": "active"},
        })
        assert caps.active_api_keys() == [
            "someFutureFlag",
            "telematicsRemoteLockUnlock",
            "useSpecificTemperatureControl",
        ]

    def test_from_dict_synthesizes_raw_from_old_booleans(self):
        """Tokens saved by pymyhondaplus <= 5.8.0 had per-field booleans but no raw."""
        old_format = {
            "remote_lock": True,
            "remote_climate": True,
            "digital_key": True,
            "specific_temperature": True,
            "remote_horn": False,
        }
        caps = VehicleCapabilities.from_dict(old_format)
        assert caps.active_api_keys() == [
            "digitalKey",
            "telematicsRemoteClimate",
            "telematicsRemoteLockUnlock",
            "useSpecificTemperatureControl",
        ]
        assert caps.remote_lock is True
        assert caps.remote_horn is False

    def test_kwargs_constructor_builds_raw(self):
        """VehicleCapabilities(remote_lock=True, ...) is a valid construction form."""
        caps = VehicleCapabilities(remote_lock=True, digital_key=True, remote_horn=False)
        assert caps.active_api_keys() == ["digitalKey", "telematicsRemoteLockUnlock"]
        assert caps.not_supported_api_keys() == ["telematicsRemoteHorn"]
        assert caps.remote_lock is True
        assert caps.remote_horn is False
        assert caps.digital_key is True

    def test_not_supported_api_keys(self):
        caps = VehicleCapabilities(raw={
            "telematicsRemoteLockUnlock": {"featureStatus": "active"},
            "displayPhevRange": {"featureStatus": "notSupported"},
            "hpa": {"featureStatus": "notSupported"},
        })
        assert caps.active_api_keys() == ["telematicsRemoteLockUnlock"]
        assert caps.not_supported_api_keys() == ["displayPhevRange", "hpa"]

    def test_unknown_attribute_raises(self):
        caps = VehicleCapabilities()
        with pytest.raises(AttributeError):
            _ = caps.not_a_real_capability

    def test_unknown_kwarg_raises(self):
        with pytest.raises(TypeError):
            VehicleCapabilities(totally_fake_cap=True)

    def test_active_api_keys_no_data(self):
        assert VehicleCapabilities().active_api_keys() == []

    def test_to_dict_roundtrip_preserves_raw(self):
        """raw must be in to_dict() so serialized tokens keep unknown-future keys."""
        caps = VehicleCapabilities.from_api({
            "capabilities": {
                "telematicsRemoteLockUnlock": {"featureStatus": "active"},
                "someUnknownFuture": {"featureStatus": "active"},
            }
        })
        restored = VehicleCapabilities.from_dict(caps.to_dict())
        assert restored.raw == caps.raw
        assert "someUnknownFuture" in restored.active_api_keys()


class TestVehicleDictAccess:

    def test_getitem(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        assert v["vin"] == "JHMZC7840LX204934"
        assert v["fuel_type"] == "E"

    def test_get_with_default(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        assert v.get("vin") == "JHMZC7840LX204934"
        assert v.get("nonexistent", "fallback") == "fallback"

    def test_contains(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        assert "vin" in v
        assert "nonexistent" not in v

    def test_missing_key_raises(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        try:
            _ = v["nonexistent"]
            assert False, "Should have raised KeyError"
        except KeyError:
            pass


class TestVehicleSerialization:

    def test_roundtrip(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        d = v.to_dict()
        v2 = Vehicle.from_dict(d)
        assert v2.vin == v.vin
        assert v2.model_name == v.model_name
        assert v2.grade == v.grade
        assert v2.image_front == v.image_front
        assert v2.capabilities.remote_lock == v.capabilities.remote_lock

    def test_from_old_format(self):
        """Old stored tokens have 5-field vehicle dicts."""
        old = {"vin": "VIN1", "name": "My Car", "plate": "AB123", "role": "primary", "fuel_type": "E"}
        v = Vehicle.from_dict(old)
        assert v.vin == "VIN1"
        assert v.name == "My Car"
        assert v.model_name == ""
        assert v.capabilities.remote_lock is False

    def test_capabilities_included_even_without_raw(self):
        v = Vehicle(vin="VIN1")
        d = v.to_dict()
        assert "capabilities" in d
        assert d["capabilities"]["remote_lock"] is False


class TestAuthTokensVehicleMigration:

    def test_from_dict_old_vehicles(self):
        """AuthTokens.from_dict handles old 5-field vehicle dicts."""
        data = {
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_at": time.time() + 3600,
            "vehicles": [
                {"vin": "VIN1", "name": "Car1", "plate": "", "role": "primary", "fuel_type": "E"},
            ],
        }
        tokens = AuthTokens.from_dict(data)
        assert isinstance(tokens.vehicles[0], Vehicle)
        assert tokens.vehicles[0].vin == "VIN1"
        assert tokens.vehicles[0].model_name == ""

    def test_roundtrip_with_vehicles(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        tokens = AuthTokens(
            access_token="tok",
            refresh_token="ref",
            expires_at=time.time() + 3600,
            vehicles=[v],
        )
        d = tokens.to_dict()
        tokens2 = AuthTokens.from_dict(d)
        assert isinstance(tokens2.vehicles[0], Vehicle)
        assert tokens2.vehicles[0].vin == "JHMZC7840LX204934"
        assert tokens2.vehicles[0].model_name == "Honda e"

    def test_resolve_vin_with_vehicle_objects(self):
        v = Vehicle(vin="VIN1", name="My Car", plate="AB123")
        tokens = AuthTokens(vehicles=[v])
        assert tokens.resolve_vin("VIN1") == "VIN1"
        assert tokens.resolve_vin("my car") == "VIN1"
        assert tokens.resolve_vin("ab123") == "VIN1"
        assert tokens.resolve_vin("unknown") == ""

    def test_default_vin_with_vehicle_objects(self):
        v = Vehicle(vin="VIN1")
        tokens = AuthTokens(vehicles=[v])
        assert tokens.default_vin == "VIN1"


class TestSubscription:

    def test_from_api(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        sub = v.subscription
        assert sub is not None
        assert sub.package_name == "My Honda+"
        assert sub.status == "ACTIVE"
        assert sub.package_type == "STANDARD"
        assert sub.price == 4.99
        assert sub.currency == "EUR"
        assert sub.payment_term == "MONTHLY"
        assert sub.term == 1
        assert sub.trial_term == 0
        assert sub.renewal is True
        assert sub.start_date == "2026-04-05"
        assert sub.end_date == "2026-05-05"
        assert sub.next_payment_date == "2026-04-30"
        assert len(sub.services) == 2
        assert sub.services[0].code == "remote-lock"
        assert sub.services[1].description == "Remote charge"

    def test_from_api_empty(self):
        sub = Subscription.from_api([])
        assert sub is None

    def test_no_package_info(self):
        v = Vehicle.from_api(MINIMAL_VEHICLE_API)
        assert v.subscription is None

    def test_roundtrip(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        d = v.to_dict()
        v2 = Vehicle.from_dict(d)
        assert v2.subscription is not None
        assert v2.subscription.package_name == "My Honda+"
        assert v2.subscription.price == 4.99
        assert v2.subscription.end_date == "2026-05-05"

    def test_subscription_omitted_when_none(self):
        v = Vehicle(vin="VIN1")
        d = v.to_dict()
        assert "subscription" not in d

    def test_services_roundtrip(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        d = v.to_dict()
        v2 = Vehicle.from_dict(d)
        assert len(v2.subscription.services) == 2
        assert v2.subscription.services[0].code == "remote-lock"


class TestUIConfiguration:

    def test_from_api(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        assert v.ui_config.hide_window_status is False
        assert v.ui_config.hide_climate_settings is False

    def test_roundtrip(self):
        v = Vehicle.from_api(FULL_VEHICLE_API)
        d = v.to_dict()
        v2 = Vehicle.from_dict(d)
        assert v2.ui_config.hide_window_status is False

    def test_defaults(self):
        v = Vehicle.from_api(MINIMAL_VEHICLE_API)
        assert v.ui_config.hide_window_status is False
        assert v.ui_config.hide_internal_temperature is False


class TestUserProfile:

    def test_from_api(self):
        data = {
            "firstName": "Enrico",
            "lastName": "Battocchi",
            "title": "Signor",
            "email": "user@example.com",
            "phoneNumber": "+39123456789",
            "city": "Livorno",
            "state": "Livorno",
            "postalCode": "57124",
            "postalAddress": "Via Test 1",
            "country": "IT",
            "prefLanguage": "it",
            "prefNotificationSetting": "On",
            "prefNotificationChannel": ["SmartphonePush"],
            "subsExpiry": True,
        }
        p = UserProfile.from_api(data)
        assert p.first_name == "Enrico"
        assert p.last_name == "Battocchi"
        assert p.email == "user@example.com"
        assert p.city == "Livorno"
        assert p.country == "IT"
        assert p.pref_language == "it"
        assert p.pref_notification_channels == ["SmartphonePush"]
        assert p.subs_expiry is True

    def test_from_empty(self):
        p = UserProfile.from_api({})
        assert p.first_name == ""
        assert p.subs_expiry is False
