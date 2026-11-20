"""Ein Schalter je Einnahme eines Medikaments (z. B. „Anna Morgens“ an „Magnesium 10 mg“).

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
from .entity import PillboxEntity, add_per_medication


async def async_setup_entry(
    hass: HomeAssistant, entry: PillboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    add_per_medication(
        entry, async_add_entities, lambda m, s: [IntakeSwitch(m, s, key) for key in m.meds[s].intakes]
    )


class IntakeSwitch(PillboxEntity, SwitchEntity):
    _attr_icon = "mdi:pill"

    def __init__(self, manager: PillboxManager, sub_id: str, key: str) -> None:
        super().__init__(manager, sub_id, "intake")
        self.key = key
        self._attr_unique_id = intake_unique_id(sub_id, key)
        self._attr_translation_key = None
        self._attr_name = manager.intake_name(key)

    @property
    def is_on(self) -> bool:
        return self.med.taken[self.med.intakes.index(self.key)]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        person = self.manager.person_of(self.key)
        return {
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
