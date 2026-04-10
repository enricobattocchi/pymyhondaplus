"""Internationalization support for CLI output.

Translations are extracted from the My Honda+ app translation strings.
The system locale (LANG / LC_ALL) is used to select the language,
with English as the fallback.
"""

import locale
import os

# Extracted from myhondaplus_translations_final.json.
#
# Value keys from: chargeSpeedNormalText, chargeSpeedFastText, chargingLabel,
#   notChargingLabel, chargeUnpluggedLabel, lockedLabel, unlockedLabel,
#   openText@221, closedText@221, lightsText@101, doorsText@101,
#   windowsText@101, minsText/unitsText.
#
# Label keys from: batteryPercentageLabel@120, chargeSpeedLabel@120,
#   timeRemainingLabel@120, climateLabel@103, bonnetLabel@221,
#   bootLabel@221, autoDefrostLabel@117.
TRANSLATIONS = {
    "cs": {
        "charge_speed_normal": "Normální",
        "charge_speed_fast": "Rychlé",
        "charging": "Nabíjí se",
        "not_charging": "Nenabíjí se",
        "unplugged": "Odpojeno",
        "locked": "Zamknuto",
        "unlocked": "Odemknuto",
        "open": "Otevřeno",
        "closed": "Zavřeno",
        "lights_on": "Zapnutá světla",
        "windows_open": "Otevřená okna",
        "doors_open": "Otevřené dveře",
        "mins": "min",
        "battery_label": "Úroveň nabití akumulátoru (%)",
        "charge_speed_label": "Rychlost nabíjení",
        "time_remaining_label": "Zbývající doba",
        "climate_label": "Automatická klimatizace",
        "bonnet_label": "Kapota",
        "boot_label": "Zavazadlový prostor",
        "defrost_label": "Automatické odmrazování",
    },
    "da": {
        "charge_speed_normal": "Normal",
        "charge_speed_fast": "Hurtig",
        "charging": "Oplader",
        "not_charging": "Oplader ikke",
        "unplugged": "Ikke tilsluttet",
        "locked": "Låst",
        "unlocked": "Låst op",
        "open": "Åben",
        "closed": "Lukket",
        "lights_on": "Lygter tændt",
        "windows_open": "Vinduer åbne",
        "doors_open": "Døre åbne",
        "mins": "minutter",
        "battery_label": "Status for batteriet",
        "charge_speed_label": "Opladningshastighed",
        "time_remaining_label": "Resterende tid",
        "climate_label": "Klimaanlæg",
        "bonnet_label": "Frontklap",
        "boot_label": "Bagagerum",
        "defrost_label": "Automatisk afrimning",
    },
    "de": {
        "charge_speed_normal": "Normal",
        "charge_speed_fast": "Schnell",
        "charging": "Wird geladen",
        "not_charging": "Wird nicht geladen",
        "unplugged": "Getrennt",
        "locked": "Verriegelt",
        "unlocked": "Entriegelt",
        "open": "Geöffnet",
        "closed": "Geschlossen",
        "lights_on": "Beleuchtung ein",
        "windows_open": "Fenster geöffnet",
        "doors_open": "Türen geöffnet",
        "mins": "Min.",
        "battery_label": "Batterieladestand in Prozent",
        "charge_speed_label": "Ladegeschwindigkeit",
        "time_remaining_label": "Verbleibende Zeit",
        "climate_label": "Klimast.",
        "bonnet_label": "Motorhaube",
        "boot_label": "Kofferraum",
        "defrost_label": "Auto-Defrost",
    },
    "en": {
        "charge_speed_normal": "Normal",
        "charge_speed_fast": "Fast",
        "charging": "Charging",
        "not_charging": "Not charging",
        "unplugged": "Unplugged",
        "locked": "Locked",
        "unlocked": "Unlocked",
        "open": "Open",
        "closed": "Closed",
        "lights_on": "Lights on",
        "windows_open": "Windows open",
        "doors_open": "Doors open",
        "mins": "mins",
        "battery_label": "Battery percentage",
        "charge_speed_label": "Charge speed",
        "time_remaining_label": "Time remaining",
        "climate_label": "Climate control",
        "bonnet_label": "Bonnet",
        "boot_label": "Boot",
        "defrost_label": "Auto-Defrost",
    },
    "es": {
        "charge_speed_normal": "Normal",
        "charge_speed_fast": "Rápido",
        "charging": "Carga",
        "not_charging": "No se está cargando",
        "unplugged": "Desenchufado",
        "locked": "Cerrado",
        "unlocked": "Abierto",
        "open": "Abierto",
        "closed": "Cerrado",
        "lights_on": "Luces encendidas",
        "windows_open": "Ventanas abiertas",
        "doors_open": "Puertas abiertas",
        "mins": "minutos",
        "battery_label": "Porcentaje de la batería",
        "charge_speed_label": "Velocidad de carga",
        "time_remaining_label": "Tiempo restante",
        "climate_label": "Control de climatización",
        "bonnet_label": "Capó",
        "boot_label": "Funda",
        "defrost_label": "Descongelación automática",
    },
    "fr": {
        "charge_speed_normal": "Normale",
        "charge_speed_fast": "Rapide",
        "charging": "En charge",
        "not_charging": "Pas de charge",
        "unplugged": "Débranché",
        "locked": "Verrouillée",
        "unlocked": "Déverrouillée",
        "open": "Ouverte(s)",
        "closed": "Fermée(s)",
        "lights_on": "Feux allumés",
        "windows_open": "Fenêtres ouvertes",
        "doors_open": "Portes ouvertes",
        "mins": "min",
        "battery_label": "Pourcentage de batterie",
        "charge_speed_label": "Vitesse de charge",
        "time_remaining_label": "Temps restant",
        "climate_label": "Contrôle de la climatisation",
        "bonnet_label": "Capot",
        "boot_label": "Coffre",
        "defrost_label": "Dégivrage automatique",
    },
    "hu": {
        "charge_speed_normal": "Normál",
        "charge_speed_fast": "Gyors",
        "charging": "Töltés",
        "not_charging": "Nem töltődik",
        "unplugged": "Leválasztva",
        "locked": "Zárva",
        "unlocked": "Nyitva",
        "open": "Nyitva",
        "closed": "Zárva",
        "lights_on": "Lámpák bekapcsolva",
        "windows_open": "Ablakok nyitva",
        "doors_open": "Ajtók nyitva",
        "mins": "perc",
        "battery_label": "Akkumulátor-töltöttség százalékos aránya",
        "charge_speed_label": "Töltési sebesség",
        "time_remaining_label": "Hátralévő idő",
        "climate_label": "Klímaszab.",
        "bonnet_label": "Motorháztető",
        "boot_label": "Csomagtartó",
        "defrost_label": "Automatikus jégtelenítés",
    },
    "it": {
        "charge_speed_normal": "Normale",
        "charge_speed_fast": "Veloce",
        "charging": "In carica",
        "not_charging": "Non in carica",
        "unplugged": "Scollegato",
        "locked": "Bloccato",
        "unlocked": "Sbloccato",
        "open": "Apri",
        "closed": "Chiuso",
        "lights_on": "Luci accese",
        "windows_open": "Finestrini aperti",
        "doors_open": "Portiere aperte",
        "mins": "min",
        "battery_label": "Percentuale della batteria",
        "charge_speed_label": "Velocità di ricarica",
        "time_remaining_label": "Tempo rimanente",
        "climate_label": "Controllo del clima",
        "bonnet_label": "Cofano",
        "boot_label": "Bagagliaio",
        "defrost_label": "Sbrinamento automatico",
    },
    "nl": {
        "charge_speed_normal": "Normaal",
        "charge_speed_fast": "Snel",
        "charging": "Wordt opgeladen",
        "not_charging": "Laadt niet op",
        "unplugged": "Niet aangesloten",
        "locked": "Vergrendeld",
        "unlocked": "Ontgrendeld",
        "open": "Geopend",
        "closed": "Gesloten",
        "lights_on": "Verlichting aan",
        "windows_open": "Ramen open",
        "doors_open": "Portieren open",
        "mins": "min.",
        "battery_label": "Accupercentage",
        "charge_speed_label": "Laadsnelheid",
        "time_remaining_label": "Resterende tijd",
        "climate_label": "Klimaatregel.",
        "bonnet_label": "Motorkap",
        "boot_label": "Bagageruimte",
        "defrost_label": "Automatisch ontdooien",
    },
    "no": {
        "charge_speed_normal": "normal",
        "charge_speed_fast": "Rask",
        "charging": "Lader",
        "not_charging": "Lader ikke",
        "unplugged": "Frakoblet",
        "locked": "Låst",
        "unlocked": "ulåst",
        "open": "Åpne",
        "closed": "Lukket",
        "lights_on": "Lys på",
        "windows_open": "Vinduer åpne",
        "doors_open": "Dører åpne",
        "mins": "min",
        "battery_label": "Batteriprosent",
        "charge_speed_label": "Ladehastighet",
        "time_remaining_label": "Gjenværende tid",
        "climate_label": "Klimakontroll",
        "bonnet_label": "Panser",
        "boot_label": "Bagasjerom",
        "defrost_label": "Automatisk defroster",
    },
    "pl": {
        "charge_speed_normal": "Temperatura optymalna",
        "charge_speed_fast": "Szybkie ładowanie",
        "charging": "Ładowanie",
        "not_charging": "Nie ładuje",
        "unplugged": "Niepodłączone",
        "locked": "Zamknięte",
        "unlocked": "Odblokowanie",
        "open": "Otwarta",
        "closed": "Zamknięta",
        "lights_on": "Włączone światła",
        "windows_open": "Otwarte szyby",
        "doors_open": "Otwarte drzwi",
        "mins": "min",
        "battery_label": "Procentowe naładowanie akumulatorów",
        "charge_speed_label": "Szybkość ładowania",
        "time_remaining_label": "Pozostały czas",
        "climate_label": "Sterowanie AC",
        "bonnet_label": "Pokrywa silnika",
        "boot_label": "Osłona bagażnika",
        "defrost_label": "Automatyczne ogrzewanie szyby",
    },
    "sk": {
        "charge_speed_normal": "Normálne",
        "charge_speed_fast": "Rýchle",
        "charging": "Nabíjanie",
        "not_charging": "Nenabíja sa",
        "unplugged": "Odpojené",
        "locked": "Zamknuté",
        "unlocked": "Odomknuté",
        "open": "Otvorené",
        "closed": "Zatvorené",
        "lights_on": "Zapnuté svetlá",
        "windows_open": "Otvorené okná",
        "doors_open": "Otvorené dvere",
        "mins": "minúty",
        "battery_label": "Percento nabitia batérie",
        "charge_speed_label": "Rýchlosť nabíjania",
        "time_remaining_label": "Zostávajúci čas",
        "climate_label": "Ovládanie klimatizácie",
        "bonnet_label": "Kapota",
        "boot_label": "Batožinový priestor",
        "defrost_label": "Automatické odmrazovanie",
    },
    "sv": {
        "charge_speed_normal": "Normalt",
        "charge_speed_fast": "Snabbt",
        "charging": "Laddar",
        "not_charging": "Laddar inte",
        "unplugged": "Frånkopplad",
        "locked": "Låst",
        "unlocked": "Upplåst",
        "open": "Öppet/öppna",
        "closed": "Stängd/stängda",
        "lights_on": "Lampor på",
        "windows_open": "Fönster öppna",
        "doors_open": "Dörrar öppna",
        "mins": "minuter",
        "battery_label": "Batteriprocent",
        "charge_speed_label": "Laddningshastighet",
        "time_remaining_label": "Återstående tid",
        "climate_label": "Klimatanlägg.",
        "bonnet_label": "Motorhuv",
        "boot_label": "Baklucka",
        "defrost_label": "Automatisk avfrostning",
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
