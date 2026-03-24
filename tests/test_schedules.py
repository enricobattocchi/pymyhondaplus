"""Tests for charge and climate schedule parsing."""

from pymyhondaplus.api import parse_charge_schedule, parse_climate_schedule


class TestChargeSchedule:
    def test_parse_active_rules(self, dashboard_ev):
        rules = parse_charge_schedule(dashboard_ev)
        assert len(rules) == 2

        assert rules[0]["enabled"] is True
        assert rules[0]["days"] == ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        assert rules[0]["location"] == "all"
        assert rules[0]["start_time"] == "07:00"
        assert rules[0]["end_time"] == "08:00"

        assert rules[1]["enabled"] is True
        assert rules[1]["days"] == ["wed"]
        assert rules[1]["location"] == "home"
        assert rules[1]["start_time"] == "10:00"
        assert rules[1]["end_time"] == "20:10"

    def test_parse_disabled_rules(self):
        dashboard = {
            "evStatus": {
                "chargeProhibitionTimerSettings": [
                    {
                        "chargeProhibitionDayOfWeek": "",
                        "chargeProhibitionTimerCommand": "off",
                        "chargeProhibitionLocation": "home",
                        "chargeProhibitionTimerOption": {
                            "chargeProhibitionStartTime": "0000",
                            "chargeProhibitionEndTime": "0000",
                        },
                    },
                ],
            },
        }
        rules = parse_charge_schedule(dashboard)
        assert len(rules) == 1
        assert rules[0]["enabled"] is False
        assert rules[0]["days"] == []
        assert rules[0]["start_time"] == "00:00"

    def test_parse_empty_dashboard(self):
        rules = parse_charge_schedule({})
        assert rules == []

    def test_case_insensitive_command(self):
        dashboard = {
            "evStatus": {
                "chargeProhibitionTimerSettings": [
                    {
                        "chargeProhibitionDayOfWeek": "mon",
                        "chargeProhibitionTimerCommand": "ON",
                        "chargeProhibitionLocation": "ALL",
                        "chargeProhibitionTimerOption": {
                            "chargeProhibitionStartTime": "0800",
                            "chargeProhibitionEndTime": "0900",
                        },
                    },
                ],
            },
        }
        rules = parse_charge_schedule(dashboard)
        assert rules[0]["enabled"] is True
        assert rules[0]["location"] == "all"


class TestClimateSchedule:
    def test_parse_active_slots(self, dashboard_ev):
        rules = parse_climate_schedule(dashboard_ev)
        assert len(rules) == 3

        assert rules[0]["enabled"] is True
        assert rules[0]["days"] == ["mon", "tue", "fri"]
        assert rules[0]["start_time"] == "07:00"

        assert rules[1]["enabled"] is False
        assert rules[1]["days"] == []  # "unknown" is filtered out

        assert rules[2]["enabled"] is False

    def test_parse_empty_dashboard(self):
        rules = parse_climate_schedule({})
        assert rules == []

    def test_unknown_days_filtered(self):
        dashboard = {
            "evStatus": {
                "acTimerSettings": [
                    {
                        "acDayOfWeek": "unknown",
                        "acTimerCommand": "OFF",
                        "acTimerOption": {"acStartTime1": "0000"},
                    },
                ],
            },
        }
        rules = parse_climate_schedule(dashboard)
        assert rules[0]["days"] == []
        assert rules[0]["enabled"] is False

    def test_timer_command(self):
        dashboard = {
            "evStatus": {
                "acTimerSettings": [
                    {
                        "acDayOfWeek": "sat,sun",
                        "acTimerCommand": "timer",
                        "acTimerOption": {"acStartTime1": "0900"},
                    },
                ],
            },
        }
        rules = parse_climate_schedule(dashboard)
        assert rules[0]["enabled"] is True
        assert rules[0]["days"] == ["sat", "sun"]
        assert rules[0]["start_time"] == "09:00"
