"""Ein Schalter je Einnahme.

Einnahmen einer Person hängen am Gerät der Person (z. B. „Anna“ → „Magnesium 10 mg Morgens“),
damit dort sichtbar ist, was sie heute noch nehmen muss. Einnahmen ohne Person hängen an der Packung.

An = Einnahme erledigt, Vorrat sinkt um „Tabletten pro Einnahme“.
Aus = zurückgenommen (z. B. versehentlich abgehakt), die Tabletten kommen zurück in den Vorrat.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PillboxConfigEntry, PillboxManager, intake_unique_id
from .const import parse_key
from .entity import PillboxEntity, person_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: PillboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    manager = entry.runtime_data
    for pack_id, med in manager.meds.items():
        for key in med.intakes:
            person_id = parse_key(key)[1]
            # Der Untereinheit zuordnen, an deren Gerät der Schalter hängt (Personen oder Medikament).
            subentry = manager.persons[person_id].sub_id if person_id else manager.info[pack_id].sub_id
            async_add_entities([IntakeSwitch(manager, pack_id, key)], config_subentry_id=subentry)


class IntakeSwitch(PillboxEntity, SwitchEntity):
    _attr_icon = "mdi:pill"

    def __init__(self, manager: PillboxManager, pack_id: str, key: str) -> None:
        super().__init__(manager, pack_id, "intake")
        self.key = key
        self._attr_unique_id = intake_unique_id(pack_id, key)
        self._attr_translation_key = None
        if person_id := parse_key(key)[1]:
            self._attr_device_info = person_device_info(manager, person_id)
            self._attr_name = f"{manager.info[pack_id].device_name} {manager.slot_name(key)}"
        else:
            self._attr_name = manager.slot_name(key)

    @property
    def is_on(self) -> bool:
        return self.med.taken[self.med.intakes.index(self.key)]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        person = self.manager.person_of(self.key)
        return {
            "medication": self.manager.info[self.sub_id].device_name,
            "intake": self.manager.intake_name(self.key),
            "slot": self.manager.slot_name(self.key),
            "slot_id": parse_key(self.key)[0],
            "person": person.name if person else None,
            "ha_person": person.ha_person if person else None,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.manager.async_set_intake(self.sub_id, self.key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.manager.async_set_intake(self.sub_id, self.key, False)
