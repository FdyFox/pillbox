"""Constants for Pillbox."""
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "pillbox"
PLATFORMS = [Platform.NUMBER, Platform.SWITCH, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]

STORAGE_KEY = f"{DOMAIN}.state"
STORAGE_VERSION = 1

SUBENTRY_MEDICATION = "medication"  # a medication with one pack per strength
SUBENTRY_PERSON = "person"  # all people (one device each, own NFC tag)

# Medication
CONF_TAG_ID = "tag_id"
CONF_STOCK = "stock"
CONF_STRENGTH = "strength"  # e.g. "10 mg", display only
CONF_TABLETS_PER_INTAKE = "tablets_per_intake"
CONF_INTAKES = "intakes"  # list of intake keys "<slot-id>|<person-id>" (empty person = no person)
CONF_LOW_THRESHOLD = "low_threshold"
SECTION_ADVANCED = "advanced"
CONF_PACKS = "packs"  # list of packs (one per strength) of a medication
CONF_PACK_ID = "id"  # stable id of a pack or person (store, unique_id, device)
CONF_STRENGTHS = "strengths"  # form only: list of strengths
# People: one "People" subentry with a list; each person is a device
CONF_PERSONS = "persons"
CONF_HA_PERSON = "ha_person"  # optional: person.* entity from HA
PERSONS_TITLE = {"de": "Personen", "en": "People"}
# Pillbox options: times of day, id ("1".."6") -> name; order = id
CONF_SLOTS = "slots"
MAX_SLOTS = 6

# Old fields (v0.1-dev), only used to migrate existing entries
CONF_INTAKES_PER_DAY = "intakes_per_day"
LEGACY_FIELDS = (CONF_INTAKES_PER_DAY, "reminder_weekday", "reminder_weekend", "notify_action")

DEFAULT_LOW_THRESHOLD = 20
# Default times of day depending on the HA language
SLOT_DEFAULTS = {
    "de": ["Morgens", "Mittags", "Abends", "Nachts"],
    "en": ["Morning", "Noon", "Evening", "Night"],
}
DAY_RESET_HOUR = 4  # day change for "taken today" (an intake after midnight still counts for the previous day)

EVENT_TAG_SCANNED = "tag_scanned"
SERVICE_TAKE = "take"
SERVICE_REFILL = "refill"
EVENT_LOW_STOCK = f"{DOMAIN}_low_stock"


def signal(entry_id: str, subentry_id: str) -> str:
    """Dispatcher signal the entities of a pack or person listen to."""
    return f"{DOMAIN}_{entry_id}_{subentry_id}_update"


def slot_defaults(language: str | None) -> list[str]:
    return SLOT_DEFAULTS.get((language or "en").split("-")[0], SLOT_DEFAULTS["en"])


def default_slots(language: str | None) -> dict[str, str]:
    return {str(i + 1): name for i, name in enumerate(slot_defaults(language))}


def ordered_slots(slots: dict[str, str]) -> list[tuple[str, str]]:
    """(id, name) in order of the day."""
    return sorted(slots.items(), key=lambda kv: int(kv[0]))


def make_key(slot_id: str, person_id: str | None) -> str:
    return f"{slot_id}|{person_id or ''}"


def parse_key(key: str) -> tuple[str, str | None]:
    slot_id, _, person_id = key.partition("|")
    return slot_id, person_id or None


def legacy_intake_names(data: dict, language: str | None) -> list[str]:
    """Intake names from old entries (free names per medication or just a count)."""
    if names := data.get(CONF_INTAKES):
        return [str(n) for n in names]
    count = max(1, int(data.get(CONF_INTAKES_PER_DAY, 1)))
    defaults = slot_defaults(language)
    if count == 1:
        return [defaults[0]]
    if count == 2:
        return [defaults[0], defaults[2]]
    return defaults[:count] if count <= len(defaults) else [str(i + 1) for i in range(count)]


def persons_title(language: str | None) -> str:
    return PERSONS_TITLE.get((language or "en").split("-")[0], PERSONS_TITLE["en"])
