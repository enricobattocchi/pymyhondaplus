"""Tests for Vehicle, VehicleCapabilities, and Subscription dataclasses."""

import time

from pymyhondaplus.api import AuthTokens, Subscription, Vehicle, VehicleCapabilities


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
    "vehicleFront34ImageUrl": "https://example.com/front.png",
    "vehicleSideImageUrl": "https://example.com/side.png",
    "vehicleUIConfiguration": {
        "friendlyModelName": "Honda e",
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
            "price": 4.99,
            "currency1": "EUR",
            "paymentTerm": "MONTHLY",
            "renewal": True,
            "startDate": "2026-04-05T00:00:00+00:00",
            "endDate": "2026-05-05T00:00:00+00:00",
            "nextPaymentDate": "2026-04-30T00:00:00+00:00",
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
        assert v.image_front == "https://example.com/front.png"
        assert v.image_side == "https://example.com/side.png"

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
        assert sub.price == 4.99
        assert sub.currency == "EUR"
        assert sub.payment_term == "MONTHLY"
        assert sub.renewal is True
        assert sub.start_date == "2026-04-05"
        assert sub.end_date == "2026-05-05"
        assert sub.next_payment_date == "2026-04-30"

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
