"""Gemeinsame Basis für alle Pillbox-Entitäten (ein Gerät je Medikament und je Person)."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, signal
from .logic import Medication

if TYPE_CHECKING:
    from . import Person, PillboxConfigEntry, PillboxManager


class _BaseEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: PillboxManager, sub_id: str, key: str) -> None:
        self.manager = manager
        self.sub_id = sub_id
        self._attr_unique_id = f"{sub_id}_{key}"
        self._attr_translation_key = key

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal(self.manager.entry.entry_id, self.sub_id), self.async_write_ha_state
            )
        )


class PillboxEntity(_BaseEntity):
    """Entität eines Medikaments (Packung)."""

    def __init__(self, manager: PillboxManager, sub_id: str, key: str) -> None:
        super().__init__(manager, sub_id, key)
        info = manager.info[sub_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sub_id)},
            name=info.device_name,
            manufacturer="Pillbox",
            model="Medikament",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def med(self) -> Medication:
        return self.manager.meds[self.sub_id]


class PersonEntity(_BaseEntity):
    """Entität einer Person."""

    def __init__(self, manager: PillboxManager, sub_id: str, key: str) -> None:
        super().__init__(manager, sub_id, key)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sub_id)},
            name=manager.persons[sub_id].name,
            manufacturer="Pillbox",
            model="Person",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def person(self) -> Person:
        return self.manager.persons[self.sub_id]


def add_per_medication(
    entry: PillboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: Callable[[PillboxManager, str], Iterable[Entity]],
) -> None:
    """Entitäten je Medikament anlegen und der jeweiligen Untereinheit zuordnen."""
    manager = entry.runtime_data
    for sub_id in manager.meds:
        async_add_entities(factory(manager, sub_id), config_subentry_id=sub_id)


def add_per_person(
    entry: PillboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: Callable[[PillboxManager, str], Iterable[Entity]],
) -> None:
    """Entitäten je Person anlegen und der jeweiligen Untereinheit zuordnen."""
    manager = entry.runtime_data
    for sub_id in manager.persons:
        async_add_entities(factory(manager, sub_id), config_subentry_id=sub_id)
