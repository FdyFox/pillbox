"""Einnahme erfassen: je Medikament (nächste offene) und je Person (wie der Tag der Person)."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PillboxConfigEntry
from .entity import PersonEntity, PillboxEntity, add_per_medication, add_per_person


async def async_setup_entry(
    hass: HomeAssistant, entry: PillboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    add_per_medication(entry, async_add_entities, lambda m, s: [TakeButton(m, s, "take")])
    add_per_person(entry, async_add_entities, lambda m, s: [PersonTakeButton(m, s, "take_now")])


class TakeButton(PillboxEntity, ButtonEntity):
    _attr_icon = "mdi:pill"

    async def async_press(self) -> None:
        await self.manager.async_take(self.sub_id)


class PersonTakeButton(PersonEntity, ButtonEntity):
    """Alle Einnahmen der Person zur nächsten offenen Einnahme-Zeit abhaken."""

    _attr_icon = "mdi:account-check"

    async def async_press(self) -> None:
        await self.manager.async_take_person(self.sub_id)
