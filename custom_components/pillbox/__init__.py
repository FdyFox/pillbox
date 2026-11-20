"""Pillbox – Medikamenten-Tracking mit Tag-Scan, Vorrat und Reichweite.

Modell: Ein Medikament ist eine Packung (Vorrat). Seine Einnahmen sind Kombinationen aus
Einnahme-Zeit (für die ganze Pillbox gleich, z. B. Morgens/Mittags) und optional einer Person.
Mehrere Personen können sich eine Packung teilen.

Kernlogik: logic.py (getestet). Hier: Verdrahtung mit HA.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HA_PERSON,
    CONF_INTAKES,
    CONF_LOW_THRESHOLD,
    CONF_SLOTS,
    CONF_STOCK,
    CONF_STRENGTH,
    CONF_TABLETS_PER_INTAKE,
    CONF_TAG_ID,
    DAY_RESET_HOUR,
    DEFAULT_LOW_THRESHOLD,
    EVENT_LOW_STOCK,
    EVENT_TAG_SCANNED,
    LEGACY_FIELDS,
    MAX_SLOTS,
    PLATFORMS,
    STORAGE_KEY,
    STORAGE_VERSION,
    SUBENTRY_MEDICATION,
    SUBENTRY_PERSON,
    default_slots,
    legacy_intake_names,
    make_key,
    parse_key,
    signal,
)
from .logic import Medication

_LOGGER = logging.getLogger(__name__)

# Feste Entitäten (Schlüssel = Suffix der unique_id); dazu ein Schalter je Einnahme.
MED_ENTITY_KEYS = ("stock", "days_left", "runs_out_on", "taken_count", "low_stock", "complete_today", "take")
PERSON_ENTITY_KEYS = ("take_now", "open_intakes")

type PillboxConfigEntry = ConfigEntry["PillboxManager"]


def logical_today(now: datetime | None = None) -> date:
    """Aktueller Pillbox-Tag: wechselt um DAY_RESET_HOUR statt um Mitternacht."""
    now = now or dt_util.now()
    return (now - timedelta(hours=DAY_RESET_HOUR)).date()


@dataclass
class Person:
    name: str
    tag_id: str | None = None
    ha_person: str | None = None


@dataclass
class MedInfo:
    """Anzeige-Infos eines Medikaments (Packung)."""

    name: str
    strength: str | None = None
    tag_id: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def device_name(self) -> str:
        return f"{self.name} {self.strength}" if self.strength else self.name


class PillboxManager:
    """Hält Medikamente und Personen im Speicher, persistiert Vorrat/Status, verarbeitet Scans."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store: Store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}")
        self.slots: dict[str, str] = dict(entry.options.get(CONF_SLOTS) or default_slots(hass.config.language))
        self.persons: dict[str, Person] = {}  # key = subentry_id
        self.meds: dict[str, Medication] = {}  # key = subentry_id
        self.info: dict[str, MedInfo] = {}  # key = subentry_id
        self.tags: dict[str, tuple[str, str]] = {}  # tag_id -> ("medication"|"person", subentry_id)
        self._config_stock: dict[str, int] = {}  # zuletzt übernommener Startvorrat aus der Konfiguration
        self.day: date = logical_today()

    # --- Laden / Speichern -------------------------------------------------

    def _slot_order(self, key: str) -> tuple[int, str]:
        slot_id, person_id = parse_key(key)
        person = self.persons.get(person_id) if person_id else None
        return (int(slot_id) if slot_id.isdigit() else 99, person.name.casefold() if person else "")

    async def async_load(self) -> None:
        saved = await self.store.async_load() or {}
        saved_meds: dict[str, dict] = saved.get("meds", {})
        saved_day = saved.get("day")

        for sub_id, sub in self.entry.subentries.items():
            if sub.subentry_type == SUBENTRY_PERSON:
                self.persons[sub_id] = Person(
                    name=sub.title, tag_id=sub.data.get(CONF_TAG_ID), ha_person=sub.data.get(CONF_HA_PERSON)
                )
                if tag := sub.data.get(CONF_TAG_ID):
                    self.tags[tag] = (SUBENTRY_PERSON, sub_id)

        for sub_id, sub in self.entry.subentries.items():
            if sub.subentry_type != SUBENTRY_MEDICATION:
                continue
            d = sub.data
            state = saved_meds.get(sub_id, {})
            config_stock = int(d.get(CONF_STOCK, 0))
            # Vorrat in der Konfiguration geändert (Neu konfigurieren) -> übernehmen, sonst gespeicherten Stand.
            if "stock" in state and state.get("config_stock") == config_stock:
                stock = int(state["stock"])
            else:
                stock = config_stock

            # Einnahmen zu gelöschten Zeiten oder Personen fallen weg.
            data_keys = [
                k
                for k in d.get(CONF_INTAKES, [])
                if parse_key(k)[0] in self.slots and (parse_key(k)[1] is None or parse_key(k)[1] in self.persons)
            ] or [
                make_key(next(iter(sorted(self.slots, key=int))), None)
            ]
            saved_taken = state.get("taken", [True] * int(state.get("taken_today", 0)))
            if isinstance(saved_taken, list):  # älterer Speicherstand: nach Position
                saved_taken = dict(zip(data_keys, saved_taken))
            keys = sorted(data_keys, key=self._slot_order)

            self.meds[sub_id] = Medication(
                name=d.get(CONF_NAME) or sub.title,
                stock=stock,
                intakes=keys,
                tablets_per_intake=int(d.get(CONF_TABLETS_PER_INTAKE, 1)),
                low_threshold=int(d.get(CONF_LOW_THRESHOLD, DEFAULT_LOW_THRESHOLD)),
                taken=[bool(saved_taken.get(k, False)) for k in keys],
            )
            self.info[sub_id] = MedInfo(
                name=d.get(CONF_NAME) or sub.title, strength=d.get(CONF_STRENGTH) or None, tag_id=d.get(CONF_TAG_ID), config=dict(d)
            )
            self._config_stock[sub_id] = config_stock
            if tag := d.get(CONF_TAG_ID):
                self.tags.setdefault(tag, (SUBENTRY_MEDICATION, sub_id))

        # Tageswechsel verpasst (z. B. HA war um 04:00 aus) -> jetzt nachholen.
        if saved_day != self.day.isoformat():
            for med in self.meds.values():
                med.reset_day()
        await self.async_save()

    async def async_save(self) -> None:
        await self.store.async_save(
            {
                "day": self.day.isoformat(),
                "meds": {
                    k: {
                        "stock": m.stock,
                        "taken": dict(zip(m.intakes, m.taken)),
                        "config_stock": self._config_stock[k],
                    }
                    for k, m in self.meds.items()
                },
            }
        )

    # --- Namen -------------------------------------------------------------

    def slot_name(self, key: str) -> str:
        return self.slots.get(parse_key(key)[0], "?")

    def person_of(self, key: str) -> Person | None:
        person_id = parse_key(key)[1]
        return self.persons.get(person_id) if person_id else None

    def intake_name(self, key: str) -> str:
        """Anzeigename einer Einnahme, z. B. „Anna Morgens“ oder nur „Morgens“."""
        person = self.person_of(key)
        return f"{person.name} {self.slot_name(key)}" if person else self.slot_name(key)

    def person_intakes(self, person_id: str) -> list[tuple[str, str, bool]]:
        """Alle Einnahmen einer Person: (Medikament-id, Schlüssel, erledigt), in Tagesreihenfolge."""
        result = [
            (sub_id, key, taken)
            for sub_id, med in self.meds.items()
            for key, taken in zip(med.intakes, med.taken)
            if parse_key(key)[1] == person_id
        ]
        return sorted(result, key=lambda r: self._slot_order(r[1]))

    def next_slot_for(self, person_id: str) -> str | None:
        """Früheste Einnahme-Zeit, zu der die Person heute noch etwas offen hat."""
        return next((parse_key(k)[0] for _, k, taken in self.person_intakes(person_id) if not taken), None)

    # --- Änderungen --------------------------------------------------------

    def _notify(self, sub_ids) -> None:
        for sub_id in sub_ids:
            async_dispatcher_send(self.hass, signal(self.entry.entry_id, sub_id))

    def _roll_day(self) -> bool:
        """Status 'heute genommen' zurücksetzen, falls ein neuer Pillbox-Tag begonnen hat."""
        today = logical_today()
        if today == self.day:
            return False
        self.day = today
        for med in self.meds.values():
            med.reset_day()
        return True

    async def _async_change(
        self, changes: dict[str, Callable[[Medication], bool]], rolled: bool = False
    ) -> bool:
        """Änderungen an Medikamenten anwenden, speichern, Entitäten und ggf. low_stock-Event auslösen."""
        rolled = self._roll_day() or rolled
        changed: list[str] = []
        low_now: list[str] = []
        for sub_id, change in changes.items():
            med = self.meds[sub_id]
            was_low = med.low_stock
            if change(med):
                changed.append(sub_id)
                if not was_low and med.low_stock:
                    low_now.append(sub_id)
        if changed or rolled:
            await self.async_save()
            # Personen-Entitäten hängen an allen Medikamenten -> immer mit aktualisieren.
            self._notify([*(self.meds if rolled else changed), *self.persons])
        for sub_id in low_now:
            self.hass.bus.async_fire(EVENT_LOW_STOCK, {"medication": self.info[sub_id].device_name})
        return bool(changed)

    async def async_take(self, sub_id: str) -> bool:
        """Nächste offene Einnahme eines Medikaments erfassen (Tag an der Packung, Button)."""
        return await self._async_change({sub_id: lambda m: m.take()})

    async def async_take_person(self, person_id: str) -> bool:
        """Alle offenen Einnahmen der Person zur frühesten offenen Einnahme-Zeit abhaken (Tag der Person)."""
        rolled = self._roll_day()
        slot = self.next_slot_for(person_id)
        if slot is None:
            return await self._async_change({}, rolled)
        key = make_key(slot, person_id)
        targets = {sub_id: k for sub_id, k, taken in self.person_intakes(person_id) if k == key and not taken}
        return await self._async_change(
            {sub_id: (lambda m, k=k: m.set_intake(m.intakes.index(k), True)) for sub_id, k in targets.items()},
            rolled,
        )

    async def async_set_intake(self, sub_id: str, key: str, taken: bool) -> bool:
        """Eine bestimmte Einnahme abhaken (Vorrat runter) oder zurücknehmen (Vorrat hoch)."""
        return await self._async_change({sub_id: lambda m: m.set_intake(m.intakes.index(key), taken)})

    async def async_refill(self, sub_id: str, stock: int) -> None:
        self.meds[sub_id].refill(stock)
        await self.async_save()
        self._notify([sub_id])

    @callback
    def async_handle_tag(self, event: Event) -> None:
        target = self.tags.get(event.data.get("tag_id"))
        if target is None:
            return
        kind, sub_id = target
        if kind == SUBENTRY_PERSON:
            self.hass.async_create_task(self.async_take_person(sub_id))
        else:
            self.hass.async_create_task(self.async_take(sub_id))

    def expected_unique_ids(self) -> set[str]:
        """Alle unique_ids, die es nach aktueller Konfiguration geben soll."""
        ids: set[str] = set()
        for sub_id, med in self.meds.items():
            ids |= {f"{sub_id}_{k}" for k in MED_ENTITY_KEYS}
            ids |= {intake_unique_id(sub_id, key) for key in med.intakes}
        for person_id in self.persons:
            ids |= {f"{person_id}_{k}" for k in PERSON_ENTITY_KEYS}
        return ids

    @callback
    def async_reset_day(self, _now: datetime) -> None:
        if self._roll_day():
            self.hass.async_create_task(self.async_save())
        self._notify([*self.meds, *self.persons])


def intake_unique_id(sub_id: str, key: str) -> str:
    slot_id, person_id = parse_key(key)
    return f"{sub_id}_intake_{slot_id}_{person_id or 'all'}"


async def async_setup_entry(hass: HomeAssistant, entry: PillboxConfigEntry) -> bool:
    _async_migrate(hass, entry)
    manager = PillboxManager(hass, entry)
    await manager.async_load()
    entry.runtime_data = manager

    entry.async_on_unload(hass.bus.async_listen(EVENT_TAG_SCANNED, manager.async_handle_tag))
    entry.async_on_unload(
        async_track_time_change(hass, manager.async_reset_day, hour=DAY_RESET_HOUR, minute=0, second=0)
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    _async_remove_stale_entities(hass, entry, manager)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # TODO (v0.2): Services pillbox.take / pillbox.refill registrieren (services.yaml)
    return True


@callback
def _async_migrate(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ältere Einträge übernehmen: freie Einnahme-Namen je Medikament -> gemeinsame Einnahme-Zeiten."""
    language = hass.config.language
    slots: dict[str, str] = dict(entry.options.get(CONF_SLOTS) or {})
    slots_changed = not slots
    if not slots:
        slots = default_slots(language)

    for sub in list(entry.subentries.values()):
        if sub.subentry_type != SUBENTRY_MEDICATION:
            continue
        data = dict(sub.data)
        # Titel mit Wirkstärke, damit gleichnamige Packungen unterscheidbar sind.
        if (strength := data.get(CONF_STRENGTH)) and sub.title == data.get(CONF_NAME):
            hass.config_entries.async_update_subentry(entry, sub, title=f"{sub.title} {strength}")
            sub = entry.subentries[sub.subentry_id]
        intakes = data.get(CONF_INTAKES)
        new_format = bool(intakes) and all("|" in str(i) for i in intakes)
        if new_format and not any(f in data for f in LEGACY_FIELDS):
            continue
        new = {k: v for k, v in data.items() if k not in LEGACY_FIELDS}
        if not new_format:
            new[CONF_INTAKES] = _legacy_keys(data, slots, language, sub.title)
            slots_changed = True  # evtl. neue Einnahme-Zeiten ergänzt
        hass.config_entries.async_update_subentry(entry, sub, data=new)

    if slots_changed:
        hass.config_entries.async_update_entry(entry, options={**entry.options, CONF_SLOTS: slots})


def _legacy_keys(data: dict, slots: dict[str, str], language: str | None, title: str) -> list[str]:
    """Alte Einnahme-Namen auf Einnahme-Zeiten abbilden; fehlende Zeiten werden in `slots` ergänzt."""
    keys: list[str] = []
    for name in legacy_intake_names(data, language):
        slot_id = next((sid for sid, sname in slots.items() if sname.casefold() == name.casefold()), None)
        if slot_id is None:
            slot_id = next((str(i) for i in range(1, MAX_SLOTS + 1) if str(i) not in slots), None)
            if slot_id is None:
                _LOGGER.warning("Einnahme „%s“ von %s: keine freie Einnahme-Zeit mehr", name, title)
                continue
            slots[slot_id] = name
        keys.append(make_key(slot_id, None))
    return keys


@callback
def _async_remove_stale_entities(hass: HomeAssistant, entry: ConfigEntry, manager: PillboxManager) -> None:
    """Entitäten entfernen, die es nicht mehr gibt (Einnahme entfernt, alte Versionen)."""
    registry = er.async_get(hass)
    expected = manager.expected_unique_ids()
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.unique_id not in expected:
            registry.async_remove(reg_entry.entity_id)


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PillboxConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
