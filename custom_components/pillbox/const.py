"""Konstanten für Pillbox."""
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "pillbox"
PLATFORMS = [Platform.NUMBER, Platform.SWITCH, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]

STORAGE_KEY = f"{DOMAIN}.state"
STORAGE_VERSION = 1

SUBENTRY_MEDICATION = "medication"  # ein Medikament mit einer Packung je Wirkstärke
SUBENTRY_PERSON = "person"  # wer etwas einnimmt, mit eigenem NFC-Tag

# Medikament
CONF_TAG_ID = "tag_id"
CONF_STOCK = "stock"
CONF_STRENGTH = "strength"  # z. B. "10 mg", nur Anzeige
CONF_TABLETS_PER_INTAKE = "tablets_per_intake"
CONF_INTAKES = "intakes"  # Liste von Einnahme-Schlüsseln "<zeit-id>|<person-id>" (Person leer = ohne Person)
CONF_LOW_THRESHOLD = "low_threshold"
SECTION_ADVANCED = "advanced"
CONF_PACKS = "packs"  # Liste der Packungen (je Wirkstärke) eines Medikaments
CONF_PACK_ID = "id"  # stabile id einer Packung (Store, unique_id, Gerät)
CONF_STRENGTHS = "strengths"  # nur im Formular: Liste der Wirkstärken
# Person
CONF_HA_PERSON = "ha_person"  # optional: person.* aus HA
# Pillbox-Optionen: Einnahme-Zeiten des Tages, id ("1".."6") -> Name; Reihenfolge = id
CONF_SLOTS = "slots"
MAX_SLOTS = 6

# Alte Felder (v0.1-dev), nur noch zum Übernehmen bestehender Einträge
CONF_INTAKES_PER_DAY = "intakes_per_day"
LEGACY_FIELDS = (CONF_INTAKES_PER_DAY, "reminder_weekday", "reminder_weekend", "notify_action")

DEFAULT_LOW_THRESHOLD = 20
# Standard-Einnahme-Zeiten je nach HA-Sprache
SLOT_DEFAULTS = {
    "de": ["Morgens", "Mittags", "Abends", "Nachts"],
    "en": ["Morning", "Noon", "Evening", "Night"],
}
DAY_RESET_HOUR = 4  # Tageswechsel für "heute genommen" (Einnahme nach Mitternacht zählt noch zum Vortag)

EVENT_TAG_SCANNED = "tag_scanned"
SERVICE_TAKE = "take"
SERVICE_REFILL = "refill"
EVENT_LOW_STOCK = f"{DOMAIN}_low_stock"


def signal(entry_id: str, subentry_id: str) -> str:
    """Dispatcher-Signal, auf das die Entitäten eines Medikaments bzw. einer Person hören."""
    return f"{DOMAIN}_{entry_id}_{subentry_id}_update"


def slot_defaults(language: str | None) -> list[str]:
    return SLOT_DEFAULTS.get((language or "en").split("-")[0], SLOT_DEFAULTS["en"])


def default_slots(language: str | None) -> dict[str, str]:
    return {str(i + 1): name for i, name in enumerate(slot_defaults(language))}


def ordered_slots(slots: dict[str, str]) -> list[tuple[str, str]]:
    """(id, Name) in Tagesreihenfolge."""
    return sorted(slots.items(), key=lambda kv: int(kv[0]))


def make_key(slot_id: str, person_id: str | None) -> str:
    return f"{slot_id}|{person_id or ''}"


def parse_key(key: str) -> tuple[str, str | None]:
    slot_id, _, person_id = key.partition("|")
    return slot_id, person_id or None


def legacy_intake_names(data: dict, language: str | None) -> list[str]:
    """Einnahme-Namen aus alten Einträgen (freie Namen je Medikament oder nur eine Anzahl)."""
    if names := data.get(CONF_INTAKES):
        return [str(n) for n in names]
    count = max(1, int(data.get(CONF_INTAKES_PER_DAY, 1)))
    defaults = slot_defaults(language)
    if count == 1:
        return [defaults[0]]
    if count == 2:
        return [defaults[0], defaults[2]]
    return defaults[:count] if count <= len(defaults) else [str(i + 1) for i in range(count)]
