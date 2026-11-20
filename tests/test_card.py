"""Dashboard card: served by the integration and rendered with real states (via QuickJS)."""
import json

import pytest
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.pillbox import CARD_PATH, CARD_URL

from .test_init import _at, _family_entry, _setup

HARNESS = """
class HTMLElement {}
HTMLElement.prototype.attachShadow = function () {
  this.shadowRoot = { innerHTML: "", addEventListener() {} };
  return this.shadowRoot;
};
const __registry = {};
var customElements = { get: (n) => __registry[n], define: (n, c) => { __registry[n] = c; } };
var window = {};
"""

RUN = """
(() => {
  const Card = customElements.get("pillbox-card");
  const card = new Card();
  const calls = [];
  const hass = JSON.parse(HASS_JSON);
  hass.callService = (domain, service, data) => calls.push([domain, service, data]);
  card.setConfig({});
  card.hass = hass;
  const html = card.shadowRoot.innerHTML;
  card._onClick({ target: { closest: () => ({ dataset: { toggle: "switch.anna_magnesium_10_mg_morgens" } }) } });
  card._onClick({ target: { closest: () => ({ dataset: { press: "button.anna_take_now" } }) } });
  return JSON.stringify({ html, calls, registered: window.customCards.map((c) => c.type) });
})()
"""


async def test_card_is_served(hass, hass_client, freezer):
    assert await async_setup_component(hass, "http", {})
    entry = _family_entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    client = await hass_client()
    resp = await client.get(CARD_URL)
    assert resp.status == 200
    assert 'customElements.define("pillbox-card"' in await resp.text()


async def test_card_renders_people_and_packs(hass, freezer):
    quickjs = pytest.importorskip("quickjs")
    entry = _family_entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.ben_magnesium_10_mg_morgens"}, blocking=True)
    await hass.services.async_call("number", "set_value", {"entity_id": "number.magnesium_20_mg_stock", "value": 3}, blocking=True)
    await hass.async_block_till_done()

    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    pillbox_entities = er.async_entries_for_config_entry(entities, entry.entry_id)
    fake_hass = {
        "locale": {"language": "de"},
        "entities": {e.entity_id: {"entity_id": e.entity_id, "device_id": e.device_id, "platform": e.platform} for e in pillbox_entities},
        "devices": {d.id: {"name": d.name, "name_by_user": d.name_by_user} for d in dr.async_entries_for_config_entry(devices, entry.entry_id)},
        "states": {
            s.entity_id: {"state": s.state, "attributes": dict(s.attributes)}
            for s in hass.states.async_all()
        },
    }

    ctx = quickjs.Context()
    ctx.eval(HARNESS)
    ctx.eval(CARD_PATH.read_text())
    ctx.set("HASS_JSON", json.dumps(fake_hass, default=str))
    result = json.loads(ctx.eval(RUN))
    html = result["html"]

    assert result["registered"] == ["pillbox-card"]
    # People with their intakes; Ben's morning intake is done, Anna's next slot is "Morgens".
    assert "Anna" in html and "Ben" in html
    assert "Als Nächstes: <b>Morgens</b>" in html
    assert 'class="chip done" data-toggle="switch.ben_magnesium_10_mg_morgens"' in html
    assert 'class="chip open next" data-toggle="switch.anna_magnesium_10_mg_morgens"' in html
    assert "Jetzt einnehmen" in html
    # Packs with stock; 20 mg is low.
    assert "Magnesium 10 mg" in html and "Magnesium 20 mg" in html
    assert '<div class="pack low">' in html and "Vorrat niedrig" in html
    # Clicks call the right services.
    assert result["calls"] == [
        ["switch", "toggle", {"entity_id": "switch.anna_magnesium_10_mg_morgens"}],
        ["button", "press", {"entity_id": "button.anna_take_now"}],
    ]
