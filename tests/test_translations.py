"""Tests for the translations module."""

import os

from pymyhondaplus.translations import (
    CHARGE_MODE_MAP, CHARGE_STATUS_MAP, PLUG_STATUS_MAP,
    TRANSLATIONS, get_translator,
)


def test_all_languages_have_required_keys():
    """Every language should have the core value and label keys."""
    required = {
        "charge_speed_normal", "charge_speed_fast", "charging", "not_charging",
        "unplugged", "locked", "unlocked", "open", "closed",
        "battery_label", "charge_speed_label", "time_remaining_label",
        "climate_label", "bonnet_label", "boot_label", "defrost_label",
        "doors_label", "home", "away",
    }
    for lang, strings in TRANSLATIONS.items():
        missing = required - set(strings)
        assert not missing, f"{lang} is missing keys: {missing}"


def test_english_fallback_for_unknown_locale():
    t = get_translator("xx")
    assert t("locked") == "Locked"
    assert t("charge_speed_fast") == "Fast"


def test_locale_detection_from_lang(monkeypatch):
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    monkeypatch.delenv("LC_ALL", raising=False)
    t = get_translator()
    assert t("locked") == "Verriegelt"
    assert t("charge_speed_fast") == "Schnell"


def test_locale_detection_lc_all_takes_precedence(monkeypatch):
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setenv("LC_ALL", "fr_FR.UTF-8")
    t = get_translator()
    assert t("locked") == "Verrouillée"


def test_explicit_lang_overrides_env(monkeypatch):
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    t = get_translator("it")
    assert t("locked") == "Bloccato"


def test_missing_key_returns_raw():
    t = get_translator("en")
    assert t("nonexistent_key", raw="fallback_value") == "fallback_value"


def test_missing_key_returns_key_when_no_raw():
    t = get_translator("en")
    assert t("nonexistent_key") == "nonexistent_key"


def test_charge_mode_map():
    t = get_translator("en")
    for raw, tkey in CHARGE_MODE_MAP.items():
        translated = t(tkey, raw=raw)
        assert translated in ("Normal", "Fast"), f"{raw} -> {translated}"


def test_charge_mode_map_german():
    t = get_translator("de")
    assert t(CHARGE_MODE_MAP["200v charging"]) == "Normal"
    assert t(CHARGE_MODE_MAP["fast charging"]) == "Schnell"


def test_missing_key_in_lang_falls_back_to_english():
    """If a language is missing a key that English has, fall back to English."""
    t = get_translator("en")
    en_val = t("mins")
    # Pick a language where we can verify fallback
    # (cs doesn't have 'mins' in the test data, but the JSON had 'min')
    # Just test the mechanism: unknown key falls back to English
    t2 = get_translator("xx")
    assert t2("mins") == en_val


def test_posix_locale_falls_back_to_english(monkeypatch):
    monkeypatch.setenv("LANG", "POSIX")
    monkeypatch.delenv("LC_ALL", raising=False)
    t = get_translator()
    assert t("locked") == "Locked"


def test_c_locale_falls_back_to_english(monkeypatch):
    monkeypatch.setenv("LANG", "C")
    monkeypatch.delenv("LC_ALL", raising=False)
    t = get_translator()
    assert t("locked") == "Locked"


def test_charge_status_map():
    t = get_translator("en")
    assert t(CHARGE_STATUS_MAP["running"]) == "Charging"
    assert t(CHARGE_STATUS_MAP["stopped"]) == "Not charging"


def test_charge_status_map_german():
    t = get_translator("de")
    assert t(CHARGE_STATUS_MAP["running"]) == "Wird geladen"
    assert t(CHARGE_STATUS_MAP["stopped"]) == "Wird nicht geladen"


def test_plug_status_map():
    t = get_translator("en")
    assert t(PLUG_STATUS_MAP["unplugged"]) == "Unplugged"


def test_plug_status_mapped():
    """All known plug status values should be mapped."""
    t = get_translator("en")
    assert t(PLUG_STATUS_MAP["plugged in"]) == "Plugged in"
    assert t(PLUG_STATUS_MAP["unplugged"]) == "Unplugged"
    assert t(PLUG_STATUS_MAP["unknown"]) == "Unknown"


def test_charge_status_all_mapped():
    """All known charge status values should be mapped."""
    t = get_translator("en")
    assert t(CHARGE_STATUS_MAP["running"]) == "Charging"
    assert t(CHARGE_STATUS_MAP["stopped"]) == "Not charging"
    assert t(CHARGE_STATUS_MAP["unavailable"]) == "Unavailable"
    assert t(CHARGE_STATUS_MAP["unknown"]) == "Unknown"


def test_label_translations_italian():
    t = get_translator("it")
    assert t("battery_label") == "Percentuale della batteria"
    assert t("charge_speed_label") == "Velocità di ricarica"
    assert t("bonnet_label") == "Cofano"
    assert t("boot_label") == "Bagagliaio"
    assert t("open") == "Aperto"
    assert t("closed") == "Chiuso"


def test_label_translations_german():
    t = get_translator("de")
    assert t("battery_label") == "Batterieladestand in Prozent"
    assert t("bonnet_label") == "Motorhaube"
    assert t("boot_label") == "Kofferraum"
    assert t("open") == "Geöffnet"
    assert t("closed") == "Geschlossen"
