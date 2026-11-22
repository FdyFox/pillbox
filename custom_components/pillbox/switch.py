"""One switch per intake.

A person's intakes belong to the person's device (e.g. "Anna" -> "Magnesium 10 mg Morning"),
so it shows what they still need to take today. Intakes without a person belong to the pack.

On = intake done, stock drops by the intake's dose.
Off = undone (e.g. checked off by mistake), the tablets go back into stock.
"As needed" intakes work the same, but are never open (attribute `as_needed`).
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PillboxConfigEntry, PillboxManager, intake_unique_id
from .const import SERVICE_TAKE_INTAKE, parse_key
from .entity import PillboxEntity, person_device_info

ATTR_AMOUNT = "amount"


async def async_setup_entry(
    hass: HomeAssistant, entry: PillboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    # pillbox.take_intake: check off this intake, optionally with another amount than its dose (today only).
    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_TAKE_INTAKE,
        {vol.Optional(ATTR_AMOUNT): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=100))},
        "async_take_intake",
    )
    manager = entry.runtime_data
    for pack_id, med in manager.meds.items():
        for key in med.intakes:
            person_id = parse_key(key)[1]
            # Assign to the subentry whose device the switch belongs to (people or medication).
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
            "dose": self.manager.dose(self.sub_id, self.key),
            "as_needed": self.manager.is_as_needed(self.sub_id, self.key),
            "taken_amount": self.manager.amount(self.sub_id, self.key),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.manager.async_set_intake(self.sub_id, self.key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.manager.async_set_intake(self.sub_id, self.key, False)

    async def async_take_intake(self, amount: float | None = None) -> None:
        """Check off with `amount` tablets (default: the dose); on a taken intake, correct the amount."""
        await self.manager.async_set_intake(self.sub_id, self.key, True, amount)
