"""Services: pillbox.take and pillbox.refill.

Both act on Pillbox devices: a pack device (e.g. "Magnesium 10 mg") or a person device (e.g. "Anna").
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN, SERVICE_REFILL, SERVICE_TAKE

if TYPE_CHECKING:
    from . import PillboxManager

ATTR_DEVICE_ID = "device_id"
ATTR_ADD = "add"
ATTR_STOCK = "stock"

TAKE_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string])})
REFILL_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
            vol.Exclusive(ATTR_ADD, "amount"): vol.All(vol.Coerce(int), vol.Range(min=1, max=10000)),
            vol.Exclusive(ATTR_STOCK, "amount"): vol.All(vol.Coerce(int), vol.Range(min=0, max=10000)),
        }
    ),
    cv.has_at_least_one_key(ATTR_ADD, ATTR_STOCK),
)


def _resolve(hass: HomeAssistant, device_id: str) -> tuple[PillboxManager, str]:
    """Device id -> (manager, pack or person id)."""
    device = dr.async_get(hass).async_get(device_id)
    if device is not None:
        ids = [ident for domain, ident in device.identifiers if domain == DOMAIN]
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is not ConfigEntryState.LOADED or entry.entry_id not in device.config_entries:
                continue
            manager: PillboxManager = entry.runtime_data
            for ident in ids:
                if ident in manager.meds or ident in manager.persons:
                    return manager, ident
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="unknown_device", translation_placeholders={"device_id": device_id}
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    async def async_take(call: ServiceCall) -> None:
        """Pack device: next open intake. Person device: all intakes at the next open time of day."""
        for device_id in call.data[ATTR_DEVICE_ID]:
            manager, ident = _resolve(hass, device_id)
            if ident in manager.persons:
                await manager.async_take_person(ident)
            else:
                await manager.async_take(ident)

    async def async_refill(call: ServiceCall) -> None:
        """Add tablets to a pack (`add`) or set its stock (`stock`)."""
        targets = [_resolve(hass, device_id) for device_id in call.data[ATTR_DEVICE_ID]]
        for manager, ident in targets:
            if ident not in manager.meds:
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_a_pack")
        for manager, ident in targets:
            if ATTR_ADD in call.data:
                await manager.async_refill(ident, manager.meds[ident].stock + call.data[ATTR_ADD])
            else:
                await manager.async_refill(ident, call.data[ATTR_STOCK])

    hass.services.async_register(DOMAIN, SERVICE_TAKE, async_take, schema=TAKE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_REFILL, async_refill, schema=REFILL_SCHEMA)
