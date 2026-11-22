"""Pillbox – medication tracking with tag scans, stock and coverage.

Model: a medication has one pack (with stock) per strength. A pack's intakes combine a
time of day (shared by the whole Pillbox, e.g. morning/noon) with an optional person.
Several people can share one pack.

Core logic: logic.py (tested). Here: wiring with Home Assistant.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AS_NEEDED,
    CONF_DOSES,
    CONF_HA_PERSON,
    CONF_INTAKES,
    CONF_LOW_THRESHOLD,
    CONF_PACK_ID,
    CONF_PACKS,
    CONF_PERSONS,
    CONF_SLOTS,
    CONF_STOCK,
    CONF_STRENGTH,
    CONF_TABLETS_PER_INTAKE,
    CONF_TAG_ID,
    DAY_RESET_HOUR,
    DEFAULT_LOW_THRESHOLD,
    DOMAIN,
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
    ordered_slots,
    parse_key,
    persons_title,
    signal,
)
from .logic import Medication, tidy
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

# Fixed entities (key = unique_id suffix); plus one switch per intake.
MED_ENTITY_KEYS = ("stock", "days_left", "runs_out_on", "taken_count", "low_stock", "complete_today", "take")
PERSON_ENTITY_KEYS = ("take_now", "open_intakes")

type PillboxConfigEntry = ConfigEntry["PillboxManager"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


CARD_URL = f"/{DOMAIN}/pillbox-card.js"
CARD_PATH = Path(__file__).parent / "frontend" / "pillbox-card.js"
BLUEPRINTS_DIR = Path(__file__).parent / "blueprints"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up services and the dashboard card (once, independent of config entries)."""
    async_setup_services(hass)
    await _async_register_card(hass)
    return True


BLUEPRINT_SLOTS_MARKER = "options: []  # pillbox:slots"


async def _async_install_blueprints(hass: HomeAssistant, slots: list[str] | None = None) -> None:
    """Copy the reminder blueprints to /config/blueprints/automation/pillbox/ (new or updated versions).

    HACS and the Marketplace only install custom_components/, so the integration brings them along.
    The times of day are filled in as dropdown options (a blueprint cannot read them itself).
    """
    dest_dir = Path(hass.config.path("blueprints", "automation", DOMAIN))
    options = "options: " + json.dumps(list(slots or []), ensure_ascii=False)

    def render(source: Path) -> bytes:
        lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
        for i, line in enumerate(lines):
            if BLUEPRINT_SLOTS_MARKER in line:
                indent = line[: len(line) - len(line.lstrip())]
                lines[i] = f"{indent}{options}\n"
        return "".join(lines).encode("utf-8")

    def install() -> list[str]:
        installed = []
        for source in sorted(BLUEPRINTS_DIR.glob("*.yaml")):
            dest = dest_dir / source.name
            content = render(source)
            if dest.is_file() and dest.read_bytes() == content:
                continue
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            installed.append(source.name)
        return installed

    try:
        if installed := await hass.async_add_executor_job(install):
            _LOGGER.info("Installed blueprints %s in %s", ", ".join(installed), dest_dir)
    except OSError as err:
        _LOGGER.warning("Could not install the reminder blueprints in %s: %s", dest_dir, err)


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve pillbox-card.js and load it in the frontend, so no manual resource is needed."""
    if getattr(hass, "http", None) is None:
        return  # e.g. in tests without http
    from homeassistant.components.http import StaticPathConfig  # noqa: PLC0415

    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(CARD_PATH), True)])
    if "frontend" in hass.config.components:
        from homeassistant.components.frontend import add_extra_js_url  # noqa: PLC0415

        version = (await async_get_integration(hass, DOMAIN)).version
        add_extra_js_url(hass, f"{CARD_URL}?v={version}")  # version busts the browser cache after updates


def logical_today(now: datetime | None = None) -> date:
    """Current Pillbox day: changes at DAY_RESET_HOUR instead of midnight."""
    now = now or dt_util.now()
    return (now - timedelta(hours=DAY_RESET_HOUR)).date()


@dataclass
class Person:
    name: str
    sub_id: str  # "People" subentry the person belongs to
    tag_id: str | None = None
    ha_person: str | None = None


@dataclass
class MedInfo:
    """Display info of a pack (medication + strength)."""

    name: str
    sub_id: str  # medication subentry the pack belongs to
    strength: str | None = None
    tag_id: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def device_name(self) -> str:
        return f"{self.name} {self.strength}" if self.strength else self.name


class PillboxManager:
    """Holds packs and people in memory, persists stock/status, handles scans."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store: Store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}")
        self.slots: dict[str, str] = dict(entry.options.get(CONF_SLOTS) or default_slots(hass.config.language))
        self.persons: dict[str, Person] = {}  # key = subentry_id
        # Packs: key = pack id (for migrated entries = old subentry_id)
        self.meds: dict[str, Medication] = {}
        self.info: dict[str, MedInfo] = {}
        self.tags: dict[str, tuple[str, str]] = {}  # tag_id -> ("medication"|"person", pack/person id)
        self._config_stock: dict[str, float] = {}  # stock from the configuration last applied
        self.day: date = logical_today()

    # --- Load / save -------------------------------------------------------

    def _slot_order(self, key: str) -> tuple[int, str]:
        slot_id, person_id = parse_key(key)
        person = self.persons.get(person_id) if person_id else None
        return (int(slot_id) if slot_id.isdigit() else 99, person.name.casefold() if person else "")

    async def async_load(self) -> None:
        saved = await self.store.async_load() or {}
        saved_meds: dict[str, dict] = saved.get("meds", {})
        saved_day = saved.get("day")

        for sub_id, sub in self.entry.subentries.items():
            if sub.subentry_type != SUBENTRY_PERSON:
                continue
            for p in sub.data.get(CONF_PERSONS, []):
                person_id = p[CONF_PACK_ID]
                self.persons[person_id] = Person(
                    name=p[CONF_NAME], sub_id=sub_id, tag_id=p.get(CONF_TAG_ID), ha_person=p.get(CONF_HA_PERSON)
                )
                if tag := p.get(CONF_TAG_ID):
                    self.tags[tag] = (SUBENTRY_PERSON, person_id)

        for sub_id, sub in self.entry.subentries.items():
            if sub.subentry_type != SUBENTRY_MEDICATION:
                continue
            name = sub.data.get(CONF_NAME) or sub.title
            for pack in sub.data.get(CONF_PACKS, []):
                self._load_pack(sub_id, name, pack, saved_meds.get(pack[CONF_PACK_ID], {}))

        # Missed day change (e.g. HA was off at 04:00) -> catch up now.
        if saved_day != self.day.isoformat():
            for med in self.meds.values():
                med.reset_day()
        await self.async_save()

    def _load_pack(self, sub_id: str, name: str, d: dict[str, Any], state: dict[str, Any]) -> None:
        pack_id = d[CONF_PACK_ID]
        config_stock = tidy(d.get(CONF_STOCK, 0))
        # Stock changed in the configuration (edit) -> apply it, otherwise keep the stored value.
        if "stock" in state and state.get("config_stock") == config_stock:
            stock = tidy(state["stock"])
        else:
            stock = config_stock

        # Intakes of deleted times of day or people are dropped.
        data_keys = [
            k
            for k in d.get(CONF_INTAKES, [])
            if parse_key(k)[0] in self.slots and (parse_key(k)[1] is None or parse_key(k)[1] in self.persons)
        ] or [make_key(next(iter(sorted(self.slots, key=int))), None)]
        saved_taken = state.get("taken", [True] * int(state.get("taken_today", 0)))
        if isinstance(saved_taken, list):  # older stored state: by position
            saved_taken = dict(zip(data_keys, saved_taken))
        keys = sorted(data_keys, key=self._slot_order)

        default_dose = tidy(d.get(CONF_TABLETS_PER_INTAKE, 1))
        doses = d.get(CONF_DOSES) or {}
        as_needed = set(d.get(CONF_AS_NEEDED) or [])
        self.meds[pack_id] = Medication(
            name=name,
            stock=stock,
            intakes=keys,
            tablets_per_intake=default_dose,
            low_threshold=tidy(d.get(CONF_LOW_THRESHOLD, DEFAULT_LOW_THRESHOLD)),
            taken=[bool(saved_taken.get(k, False)) for k in keys],
            amounts=[tidy(state.get("amounts", {}).get(k, 0)) for k in keys],
            doses=[tidy(doses.get(k, default_dose)) for k in keys],
            as_needed=[k in as_needed for k in keys],
        )
        self.info[pack_id] = MedInfo(
            name=name, sub_id=sub_id, strength=d.get(CONF_STRENGTH) or None, tag_id=d.get(CONF_TAG_ID), config=dict(d)
        )
        self._config_stock[pack_id] = config_stock
        if tag := d.get(CONF_TAG_ID):
            self.tags.setdefault(tag, (SUBENTRY_MEDICATION, pack_id))

    async def async_save(self) -> None:
        await self.store.async_save(
            {
                "day": self.day.isoformat(),
                "meds": {
                    k: {
                        "stock": m.stock,
                        "taken": dict(zip(m.intakes, m.taken)),
                        "amounts": {k: a for k, a, t in zip(m.intakes, m.amounts, m.taken) if t},
                        "config_stock": self._config_stock[k],
                    }
                    for k, m in self.meds.items()
                },
            }
        )

    # --- Names -------------------------------------------------------------

    def slot_name(self, key: str) -> str:
        return self.slots.get(parse_key(key)[0], "?")

    def person_of(self, key: str) -> Person | None:
        person_id = parse_key(key)[1]
        return self.persons.get(person_id) if person_id else None

    def intake_name(self, key: str) -> str:
        """Display name of an intake, e.g. "Anna Morning" or just "Morning"."""
        person = self.person_of(key)
        return f"{person.name} {self.slot_name(key)}" if person else self.slot_name(key)

    def is_as_needed(self, pack_id: str, key: str) -> bool:
        med = self.meds[pack_id]
        return med.as_needed[med.intakes.index(key)]

    def dose(self, pack_id: str, key: str) -> float:
        med = self.meds[pack_id]
        return med.doses[med.intakes.index(key)]

    def person_intakes(self, person_id: str) -> list[tuple[str, str, bool]]:
        """All intakes of a person: (pack id, key, taken), in order of the day."""
        result = [
            (sub_id, key, taken)
            for sub_id, med in self.meds.items()
            for key, taken in zip(med.intakes, med.taken)
            if parse_key(key)[1] == person_id
        ]
        return sorted(result, key=lambda r: self._slot_order(r[1]))

    def next_slot_for(self, person_id: str) -> str | None:
        """Earliest time of day at which the person still has something open today ("as needed" never is)."""
        return next(
            (
                parse_key(k)[0]
                for sub_id, k, taken in self.person_intakes(person_id)
                if not taken and not self.is_as_needed(sub_id, k)
            ),
            None,
        )

    # --- Changes -----------------------------------------------------------

    def _notify(self, sub_ids) -> None:
        for sub_id in sub_ids:
            async_dispatcher_send(self.hass, signal(self.entry.entry_id, sub_id))

    def _roll_day(self) -> bool:
        """Reset the 'taken today' status if a new Pillbox day has started."""
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
        """Apply changes to packs, save, update entities and fire low_stock if needed."""
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
            # Person entities depend on all packs -> always update them too.
            self._notify([*(self.meds if rolled else changed), *self.persons])
        for sub_id in low_now:
            self.hass.bus.async_fire(EVENT_LOW_STOCK, {"medication": self.info[sub_id].device_name})
        return bool(changed)

    async def async_take(self, sub_id: str) -> bool:
        """Record the next open intake of a pack (tag on the pack, button)."""
        return await self._async_change({sub_id: lambda m: m.take()})

    async def async_take_person(self, person_id: str) -> bool:
        """Check off all open intakes of the person at their earliest open time of day (person's tag)."""
        rolled = self._roll_day()
        slot = self.next_slot_for(person_id)
        if slot is None:
            return await self._async_change({}, rolled)
        key = make_key(slot, person_id)
        targets = {
            sub_id: k
            for sub_id, k, taken in self.person_intakes(person_id)
            if k == key and not taken and not self.is_as_needed(sub_id, k)
        }
        return await self._async_change(
            {sub_id: (lambda m, k=k: m.set_intake(m.intakes.index(k), True)) for sub_id, k in targets.items()},
            rolled,
        )

    def amount(self, pack_id: str, key: str) -> float:
        """Tablets taken today for this intake (0 = not taken)."""
        med = self.meds[pack_id]
        return med.amounts[med.intakes.index(key)]

    async def async_set_intake(self, sub_id: str, key: str, taken: bool, amount: float | None = None) -> bool:
        """Check off a specific intake (stock down) or undo it (stock up)."""
        return await self._async_change({sub_id: lambda m: m.set_intake(m.intakes.index(key), taken, amount)})

    async def async_refill(self, sub_id: str, stock: float) -> None:
        """Set the stock (number entity, refill service, card buttons); fires low_stock when crossing the threshold."""

        def change(med: Medication) -> bool:
            before = med.stock
            med.refill(stock)
            return med.stock != before

        await self._async_change({sub_id: change})

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
        """All unique_ids that should exist for the current configuration."""
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
    # Blueprints with the current times of day as dropdown options (again after every change).
    await _async_install_blueprints(hass, [name for _, name in ordered_slots(manager.slots)])
    entry.runtime_data = manager

    entry.async_on_unload(hass.bus.async_listen(EVENT_TAG_SCANNED, manager.async_handle_tag))
    entry.async_on_unload(
        async_track_time_change(hass, manager.async_reset_day, hour=DAY_RESET_HOUR, minute=0, second=0)
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    _async_remove_stale_entities(hass, entry, manager)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


@callback
def _async_migrate(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate older entries: times of day, packs per strength, merge entries with the same name."""
    language = hass.config.language
    slots: dict[str, str] = dict(entry.options.get(CONF_SLOTS) or {})
    slots_changed = not slots
    if not slots:
        slots = default_slots(language)

    # 1. Single pack (old, flat data) -> medication with a list of packs.
    for sub in list(entry.subentries.values()):
        if sub.subentry_type != SUBENTRY_MEDICATION or CONF_PACKS in sub.data:
            continue
        data = {k: v for k, v in sub.data.items() if k not in LEGACY_FIELDS}
        intakes = data.get(CONF_INTAKES)
        if not (intakes and all("|" in str(i) for i in intakes)):
            data[CONF_INTAKES] = _legacy_keys(sub.data, slots, language, sub.title)
            slots_changed = True  # new times of day may have been added
        name = data.pop(CONF_NAME, None) or sub.title
        pack = {CONF_PACK_ID: sub.subentry_id, **data}  # old subentry_id -> stock and entities are kept
        hass.config_entries.async_update_subentry(entry, sub, title=name, data={CONF_NAME: name, CONF_PACKS: [pack]})

    # 2. Single people (formerly one entry each) -> list; the id stays the old subentry_id.
    for sub in list(entry.subentries.values()):
        if sub.subentry_type != SUBENTRY_PERSON or CONF_PERSONS in sub.data:
            continue
        person = {CONF_PACK_ID: sub.subentry_id, CONF_NAME: sub.data.get(CONF_NAME) or sub.title}
        person |= {k: v for k, v in sub.data.items() if k in (CONF_HA_PERSON, CONF_TAG_ID)}
        hass.config_entries.async_update_subentry(entry, sub, data={CONF_PERSONS: [person]})

    # 3. All people into one "People" subentry.
    person_subs = [s for s in entry.subentries.values() if s.subentry_type == SUBENTRY_PERSON]
    if person_subs:
        keep, *others = person_subs
        persons = [p for s in person_subs for p in s.data[CONF_PERSONS]]
        hass.config_entries.async_update_subentry(
            entry, keep, title=persons_title(language), data={CONF_PERSONS: persons}
        )
        for other in others:
            _move_to_subentry(hass, entry, other.subentry_id, keep.subentry_id)
            hass.config_entries.async_remove_subentry(entry, other.subentry_id)

    # 4. Merge medications with the same name (formerly one entry per strength).
    by_name: dict[str, list] = {}
    for sub in entry.subentries.values():
        if sub.subentry_type == SUBENTRY_MEDICATION:
            by_name.setdefault(sub.data[CONF_NAME].casefold(), []).append(sub)
    for subs in by_name.values():
        if len(subs) < 2:
            continue
        keep, *others = subs
        packs = [p for s in subs for p in s.data[CONF_PACKS]]
        packs.sort(key=lambda p: str(p.get(CONF_STRENGTH, "")))
        hass.config_entries.async_update_subentry(entry, keep, data={**keep.data, CONF_PACKS: packs})
        for other in others:
            _move_to_subentry(hass, entry, other.subentry_id, keep.subentry_id)
            hass.config_entries.async_remove_subentry(entry, other.subentry_id)

    if slots_changed:
        hass.config_entries.async_update_entry(entry, options={**entry.options, CONF_SLOTS: slots})


@callback
def _move_to_subentry(hass: HomeAssistant, entry: ConfigEntry, old: str, new: str) -> None:
    """Move entities and devices of a subentry before it is removed (IDs are kept)."""
    entities = er.async_get(hass)
    for reg in er.async_entries_for_config_entry(entities, entry.entry_id):
        if reg.config_subentry_id == old:
            entities.async_update_entity(reg.entity_id, config_subentry_id=new)
    devices = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(devices, entry.entry_id):
        if old in device.config_entries_subentries.get(entry.entry_id, set()):
            devices.async_update_device(
                device.id, add_config_entry_id=entry.entry_id, add_config_subentry_id=new
            )
            devices.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id, remove_config_subentry_id=old
            )


def _legacy_keys(data: dict, slots: dict[str, str], language: str | None, title: str) -> list[str]:
    """Map old intake names to times of day; missing times are added to `slots`."""
    keys: list[str] = []
    for name in legacy_intake_names(data, language):
        slot_id = next((sid for sid, sname in slots.items() if sname.casefold() == name.casefold()), None)
        if slot_id is None:
            slot_id = next((str(i) for i in range(1, MAX_SLOTS + 1) if str(i) not in slots), None)
            if slot_id is None:
                _LOGGER.warning("Intake '%s' of %s: no free time of day left", name, title)
                continue
            slots[slot_id] = name
        keys.append(make_key(slot_id, None))
    return keys


@callback
def _async_remove_stale_entities(hass: HomeAssistant, entry: ConfigEntry, manager: PillboxManager) -> None:
    """Remove entities that no longer exist (intake removed, old versions)."""
    registry = er.async_get(hass)
    expected = manager.expected_unique_ids()
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.unique_id not in expected:
            registry.async_remove(reg_entry.entity_id)
    # Devices of removed packs
    devices = dr.async_get(hass)
    known = {*manager.meds, *manager.persons}
    for device in dr.async_entries_for_config_entry(devices, entry.entry_id):
        if not any(domain == DOMAIN and ident in known for domain, ident in device.identifiers):
            devices.async_remove_device(device.id)


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PillboxConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
