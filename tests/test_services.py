"""Services pillbox.take and pillbox.refill."""
import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from custom_components.pillbox.const import DOMAIN

from .test_init import _at, _family_entry, _setup, _state


def _device(hass, ident: str) -> str:
    return dr.async_get(hass).async_get_device(identifiers={(DOMAIN, ident)}).id


async def _call(hass, service, **data):
    await hass.services.async_call(DOMAIN, service, data, blocking=True)
    await hass.async_block_till_done()


async def test_take_for_person_and_pack(hass, freezer):
    entry = _family_entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    await _call(hass, "take", device_id=_device(hass, "anna"))
    assert _state(hass, "switch.anna_magnesium_10_mg_morgens") == "on"
    assert _state(hass, "switch.anna_magnesium_10_mg_mittags") == "off"
    # Pack device: next open intake of the pack (Ben's morning intake on 20 mg).
    await _call(hass, "take", device_id=[_device(hass, "m20")])
    assert _state(hass, "switch.ben_magnesium_20_mg_morgens") == "on"
    assert _state(hass, "number.magnesium_20_mg_stock") == "9"


async def test_refill_add_and_set(hass, freezer):
    entry = _family_entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    await _call(hass, "refill", device_id=_device(hass, "m10"), add=50)
    assert _state(hass, "number.magnesium_10_mg_stock") == "80"
    await _call(hass, "refill", device_id=_device(hass, "m10"), stock=12)
    assert _state(hass, "number.magnesium_10_mg_stock") == "12"
    assert _state(hass, "binary_sensor.magnesium_10_mg_low_stock") == "on"


async def test_service_errors(hass, freezer):
    entry = _family_entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "refill", device_id=_device(hass, "anna"), add=5)
    assert err.value.translation_key == "not_a_pack"
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "take", device_id="does-not-exist")
    assert err.value.translation_key == "unknown_device"
    with pytest.raises(Exception):
        await _call(hass, "refill", device_id=_device(hass, "m10"))  # neither add nor stock
