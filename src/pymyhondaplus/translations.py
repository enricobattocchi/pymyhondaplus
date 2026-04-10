"""Internationalization support for CLI output.

Translations are extracted from the My Honda+ app translation strings.
The system locale (LANG / LC_ALL) is used to select the language,
with English as the fallback.
"""

import locale
import os

# Extracted from myhondaplus_translations_final.json.
# Keys: chargeSpeedNormalText, chargeSpeedFastText, chargingLabel,
# notChargingLabel, chargeUnpluggedLabel, lockedLabel, unlockedLabel,
# lightsText, windowsText, doorsText, minsText/unitsText.
TRANSLATIONS = {
    "cs": {
        "charge_speed_normal": "Normální",
        "charge_speed_fast": "Rychlé",
        "charging": "Nabíjí se",
        "not_charging": "Nenabíjí se",
        "unplugged": "Odpojeno",
        "locked": "Zamknuto",
        "unlocked": "Odemknuto",
        "lights_on": "Světlomety vozidla jsou zapnuté",
        "windows_open": "Otevřená okna",
        "doors_open": "Otevřené dveře",
        "mins": "min",
    },
    "da": {
        "charge_speed_normal": "Normal",
        "charge_speed_fast": "Hurtig",
        "charging": "Oplader",
        "not_charging": "Oplader ikke",
        "unplugged": "Ikke tilsluttet",
        "locked": "Låst",
        "unlocked": "Låst op",
        "lights_on": "Bilens lygter er tændt",
        "windows_open": "Vinduer åbne",
        "doors_open": "Døre åbne",
        "mins": "minutter",
    },
    "de": {
        "charge_speed_normal": "Normal",
        "charge_speed_fast": "Schnell",
        "charging": "Wird geladen",
        "not_charging": "Wird nicht geladen",
        "unplugged": "Getrennt",
        "locked": "Verriegelt",
        "unlocked": "Entriegelt",
        "lights_on": "Fahrzeugbeleuchtung ist eingeschaltet",
        "windows_open": "Fenster geöffnet",
        "doors_open": "Türen geöffnet",
        "mins": "Min.",
    },
    "en": {
        "charge_speed_normal": "Normal",
        "charge_speed_fast": "Fast",
        "charging": "Charging",
        "not_charging": "Not charging",
        "unplugged": "Unplugged",
        "locked": "Locked",
        "unlocked": "Unlocked",
        "lights_on": "Your vehicle's lights are on",
        "windows_open": "Windows open",
        "doors_open": "Doors open",
        "mins": "mins",
    },
    "es": {
        "charge_speed_normal": "Normal",
        "charge_speed_fast": "Rápido",
        "charging": "Carga",
        "not_charging": "No se está cargando",
        "unplugged": "Desenchufado",
        "locked": "Cerrado",
        "unlocked": "Abierto",
        "lights_on": "Las luces del vehículo están encendidas",
        "windows_open": "Ventanas abiertas",
        "doors_open": "Puertas abiertas",
        "mins": "minutos",
    },
    "fr": {
        "charge_speed_normal": "Normale",
        "charge_speed_fast": "Rapide",
        "charging": "En charge",
        "not_charging": "Pas de charge",
        "unplugged": "Débranché",
        "locked": "Verrouillée",
        "unlocked": "Déverrouillée",
        "lights_on": "Les feux de votre véhicule sont allumés",
        "windows_open": "Fenêtres ouvertes",
        "doors_open": "Portes ouvertes",
        "mins": "min",
    },
    "hu": {
        "charge_speed_normal": "Normál",
        "charge_speed_fast": "Gyors",
        "charging": "Töltés",
        "not_charging": "Nem töltődik",
        "unplugged": "Leválasztva",
        "locked": "Zárva",
        "unlocked": "Nyitva",
        "lights_on": "A gépjármű lámpái világítanak",
        "windows_open": "Ablakok nyitva",
        "doors_open": "Ajtók nyitva",
        "mins": "perc",
    },
    "it": {
        "charge_speed_normal": "Normale",
        "charge_speed_fast": "Veloce",
        "charging": "In carica",
        "not_charging": "Non in carica",
        "unplugged": "Scollegato",
        "locked": "Bloccato",
        "unlocked": "Sbloccato",
        "lights_on": "Le luci del veicolo sono accese",
        "windows_open": "Finestrini aperti",
        "doors_open": "Portiere aperte",
        "mins": "min",
    },
    "nl": {
        "charge_speed_normal": "Normaal",
        "charge_speed_fast": "Snel",
        "charging": "Wordt opgeladen",
        "not_charging": "Laadt niet op",
        "unplugged": "Niet aangesloten",
        "locked": "Vergrendeld",
        "unlocked": "Ontgrendeld",
        "lights_on": "De lichten van uw voertuig branden",
        "windows_open": "Ramen open",
        "doors_open": "Portieren open",
        "mins": "min.",
    },
    "no": {
        "charge_speed_normal": "normal",
        "charge_speed_fast": "Rask",
        "charging": "Lader",
        "not_charging": "Lader ikke",
        "unplugged": "Frakoblet",
        "locked": "Låst",
        "unlocked": "ulåst",
        "lights_on": "Kjøretøyets lys er på",
        "windows_open": "Vinduer åpne",
        "doors_open": "Dører åpne",
        "mins": "min",
    },
    "pl": {
        "charge_speed_normal": "Temperatura optymalna",
        "charge_speed_fast": "Szybkie ładowanie",
        "charging": "Ładowanie",
        "not_charging": "Nie ładuje",
        "unplugged": "Niepodłączone",
        "locked": "Zamknięte",
        "unlocked": "Odblokowanie",
        "lights_on": "Światła pojazdu są włączone",
        "windows_open": "Otwarte szyby",
        "doors_open": "Otwarte drzwi",
        "mins": "min",
    },
    "sk": {
        "charge_speed_normal": "Normálne",
        "charge_speed_fast": "Rýchle",
        "charging": "Nabíjanie",
        "not_charging": "Nenabíja sa",
        "unplugged": "Odpojené",
        "locked": "Zamknuté",
        "unlocked": "Odomknuté",
        "lights_on": "Zapnuté svetlá vozidla",
        "windows_open": "Otvorené okná",
        "doors_open": "Otvorené dvere",
        "mins": "minúty",
    },
    "sv": {
        "charge_speed_normal": "Normalt",
        "charge_speed_fast": "Snabbt",
        "charging": "Laddar",
        "not_charging": "Laddar inte",
        "unplugged": "Frånkopplad",
        "locked": "Låst",
        "unlocked": "Upplåst",
        "lights_on": "Fordonets belysning är tänd",
        "windows_open": "Fönster öppna",
        "doors_open": "Dörrar öppna",
        "mins": "minuter",
    },
}

# Map raw API chargeMode values to translation keys.
# Possible values (from enums): unknown, 100v charging, 200v charging,
# fast charging, unconfirmed.
CHARGE_MODE_MAP = {
    "100v charging": "charge_speed_normal",
    "200v charging": "charge_speed_normal",
    "fast charging": "charge_speed_fast",
}

# Map raw API chargeStatus values to translation keys.
# Possible values (from enums): unknown, stopped, running, unavailable.
CHARGE_STATUS_MAP = {
    "running": "charging",
    "stopped": "not_charging",
}

# Map raw API plugStatus values to translation keys.
# Possible values (from enums): unknown, unplugged, plugged in.
PLUG_STATUS_MAP = {
    "unplugged": "unplugged",
}


def _detect_lang():
    """Detect language code from environment (LANG / LC_ALL)."""
    for var in ("LC_ALL", "LANG"):
        val = os.environ.get(var, "")
        if val in ("C", "POSIX"):
            return "en"
        if val:
            # e.g. "de_DE.UTF-8" → "de", "fr_FR" → "fr", "it" → "it"
            return val.split("_")[0].split(".")[0].lower()
    # Last resort: Python's locale module
    try:
        lang = locale.getlocale()[0]
    except ValueError:
        lang = None
    if lang:
        return lang.split("_")[0].lower()
    return "en"


def get_translator(lang=None):
    """Return a translate function for the given language.

    If *lang* is None, detects from the system locale.
    Falls back to English for missing keys or unknown languages.
    """
    if lang is None:
        lang = _detect_lang()
    strings = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    fallback = TRANSLATIONS["en"]

    def t(key, raw=None):
        """Translate *key*. If not found, return *raw* (or *key* itself)."""
        val = strings.get(key)
        if val is not None:
            return val
        val = fallback.get(key)
        if val is not None:
            return val
        return raw if raw is not None else key

    return t
