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

    assert result["registered"] == ["pillbox-card", "pillbox-intake-card"]
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


RUN_WITH_CONFIG = """
(() => {
  const Card = customElements.get("pillbox-card");
  const card = new Card();
  card.setConfig(JSON.parse(CONFIG_JSON));
  card.hass = JSON.parse(HASS_JSON);
  return card.shadowRoot.innerHTML;
})()
"""


async def _render(hass, quickjs, entry, config):
    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    device_list = dr.async_entries_for_config_entry(devices, entry.entry_id)
    fake_hass = {
        "locale": {"language": "en"},
        "entities": {
            e.entity_id: {"entity_id": e.entity_id, "device_id": e.device_id, "platform": e.platform}
            for e in er.async_entries_for_config_entry(entities, entry.entry_id)
        },
        "devices": {d.id: {"name": d.name, "name_by_user": d.name_by_user} for d in device_list},
        "states": {s.entity_id: {"state": s.state, "attributes": dict(s.attributes)} for s in hass.states.async_all()},
    }
    ctx = quickjs.Context()
    ctx.eval(HARNESS)
    ctx.eval(CARD_PATH.read_text())
    ctx.set("HASS_JSON", json.dumps(fake_hass, default=str))
    ctx.set("CONFIG_JSON", json.dumps(config))
    return ctx.eval(RUN_WITH_CONFIG), {d.name: d.id for d in device_list}


async def test_card_options(hass, freezer):
    quickjs = pytest.importorskip("quickjs")
    entry = _family_entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    await hass.services.async_call("number", "set_value", {"entity_id": "number.magnesium_20_mg_stock", "value": 3}, blocking=True)
    await hass.async_block_till_done()
    _, ids = await _render(hass, quickjs, entry, {})

    # Only Ben, without "Take now"; only low packs, without the stock column.
    html, _ = await _render(hass, quickjs, entry, {
        "people": [ids["Ben"]], "hide_take_now": True, "low_stock_only": True, "hide_columns": ["stock"],
    })
    assert "Ben" in html and "Anna" not in html
    assert "Take now" not in html
    packs = html.split("Packs</h3>")[1]
    assert "Magnesium 20 mg" in packs and "Magnesium 10 mg" not in packs
    assert 'title="Stock"' not in packs and 'title="Lasts"' in packs

    # Configured order of packs; sorting by days left puts the low 20 mg pack first.
    html, _ = await _render(hass, quickjs, entry, {"packs": [ids["Magnesium 20 mg"], ids["Magnesium 10 mg"]], "hide_people": True})
    assert "People" not in html
    assert html.index("Magnesium 20 mg") < html.index("Magnesium 10 mg")
    html, _ = await _render(hass, quickjs, entry, {"packs_sort": "days_left"})
    packs = html.split("Packs</h3>")[1]
    assert packs.index("Magnesium 20 mg") < packs.index("Magnesium 10 mg")

    # Older show_* keys still work.
    html, _ = await _render(hass, quickjs, entry, {"show_packs": False})
    assert "Packs" not in html and "People" in html

    # Everyone done + hide_done_people -> short "all done" note instead of the list.
    for switch in ("anna_magnesium_10_mg_morgens", "anna_magnesium_10_mg_mittags", "ben_magnesium_10_mg_morgens", "ben_magnesium_20_mg_morgens"):
        await hass.services.async_call("switch", "turn_on", {"entity_id": f"switch.{switch}"}, blocking=True)
    await hass.async_block_till_done()
    html, _ = await _render(hass, quickjs, entry, {"hide_done_people": True, "hide_packs": True})
    assert "All done today" in html and "Anna" not in html


def test_card_editor_schema():
    quickjs = pytest.importorskip("quickjs")
    ctx = quickjs.Context()
    ctx.eval(HARNESS)
    ctx.eval(CARD_PATH.read_text())
    form = json.loads(ctx.eval("""
      (() => {
        const f = customElements.get("pillbox-card").getConfigForm();
        const names = [];
        const walk = (s) => s.forEach((i) => (i.schema ? walk(i.schema) : names.push(i.name)));
        walk(f.schema);
        return JSON.stringify({ names, labels: names.map((n) => f.computeLabel({ name: n })) });
      })()
    """))
    assert form["names"] == [
        "title", "hide_people", "people", "hide_done_people", "hide_take_now",
        "hide_packs", "packs", "low_stock_only", "packs_sort", "stock_buttons", "stock_step", "hide_columns",
    ]
    assert all(form["labels"])


async def test_card_stock_buttons(hass, freezer):
    quickjs = pytest.importorskip("quickjs")
    entry = _family_entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    html, _ = await _render(hass, quickjs, entry, {})
    assert "data-adjust" not in html  # off by default

    html, _ = await _render(hass, quickjs, entry, {"stock_buttons": True, "stock_step": 5})
    assert 'data-adjust="number.magnesium_10_mg_stock" data-delta="-5"' in html
    assert 'data-adjust="number.magnesium_10_mg_stock" data-delta="5"' in html

    # Clicks set the stock via the pack's number entity, never below 0.
    ctx = quickjs.Context()
    ctx.eval(HARNESS)
    ctx.eval(CARD_PATH.read_text())
    calls = json.loads(ctx.eval("""
      (() => {
        const card = new (customElements.get("pillbox-card"))();
        const calls = [];
        card.setConfig({ stock_buttons: true, stock_step: 5 });
        card._hass = { states: { "number.a": { state: "30" }, "number.b": { state: "3" } },
                       callService: (d, s, data) => calls.push([d, s, data]) };
        const click = (entity, delta) => card._onClick({ target: { closest: () => ({ dataset: { adjust: entity, delta: String(delta) } }) } });
        click("number.a", 5); click("number.a", -5); click("number.b", -5);
        return JSON.stringify(calls);
      })()
    """))
    assert calls == [
        ["number", "set_value", {"entity_id": "number.a", "value": 35}],
        ["number", "set_value", {"entity_id": "number.a", "value": 25}],
        ["number", "set_value", {"entity_id": "number.b", "value": 0}],
    ]


async def test_card_doses_and_as_needed(hass, freezer):
    from .test_doses import _entry

    quickjs = pytest.importorskip("quickjs")
    entry = _entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.anna_magnesium_10_mg_morgens"}, blocking=True)
    await hass.async_block_till_done()
    html, _ = await _render(hass, quickjs, entry, {"stock_buttons": True, "stock_step": 0.5})
    # Anna's dose is shown in her chip, Ben's evening intake is "as needed" and never "next".
    assert '<span class="dose">½×</span>' in html
    assert 'class="chip open as-needed" data-toggle="switch.ben_magnesium_10_mg_abends"' in html
    assert 'class="chip open next" data-toggle="switch.ben_magnesium_10_mg_morgens"' in html
    # Stock with fractions; -/+ by half a tablet.
    assert ">19½</span>" in html
    assert 'data-delta="-0.5"' in html


async def test_card_pack_only_as_needed(hass, freezer):
    from .test_init import MED_DATA, _make_entry

    quickjs = pytest.importorskip("quickjs")
    entry = _make_entry(hass, {**MED_DATA, "as_needed": ["1|"]})
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    html, _ = await _render(hass, quickjs, entry, {})
    assert 'title="Lasts">–</span>' in html
    assert "unknown" not in html


async def test_card_days_singular(hass, freezer):
    from .test_init import MED_DATA, _make_entry

    quickjs = pytest.importorskip("quickjs")
    entry = _make_entry(hass, {**MED_DATA, "stock": 1})
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    html, _ = await _render(hass, quickjs, entry, {})
    assert 'title="Lasts">1 day</span>' in html


RUN_INTAKE_CARD = """
(() => {
  const card = new (customElements.get("pillbox-intake-card"))();
  const calls = [];
  const hass = JSON.parse(HASS_JSON);
  hass.callService = (domain, service, data) => calls.push([domain, service, data]);
  card.setConfig(JSON.parse(CONFIG_JSON));
  card.hass = hass;
  const click = (dataset) => card._onClick({ target: { closest: () => ({ dataset }) } });
  click({ take: "switch.ben_magnesium_10_mg_morgens", value: "0.75" });
  click({ undo: "switch.anna_magnesium_10_mg_morgens" });
  return JSON.stringify({ html: card.shadowRoot.innerHTML, calls, buttons: card._buttons });
})()
"""


async def test_intake_card(hass, freezer):
    from .test_doses import _entry

    quickjs = pytest.importorskip("quickjs")
    entry = _entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    await hass.services.async_call("pillbox", "take_intake", {"entity_id": "switch.anna_magnesium_10_mg_morgens", "amount": 0.25}, blocking=True)
    await hass.async_block_till_done()
    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    device_list = dr.async_entries_for_config_entry(devices, entry.entry_id)
    ids = {d.name: d.id for d in device_list}
    fake_hass = {
        "locale": {"language": "de"},
        "entities": {e.entity_id: {"entity_id": e.entity_id, "device_id": e.device_id, "platform": e.platform} for e in er.async_entries_for_config_entry(entities, entry.entry_id)},
        "devices": {d.id: {"name": d.name, "name_by_user": d.name_by_user} for d in device_list},
        "states": {s.entity_id: {"state": s.state, "attributes": dict(s.attributes)} for s in hass.states.async_all()},
    }

    def run(config):
        ctx = quickjs.Context()
        ctx.eval(HARNESS)
        ctx.eval(CARD_PATH.read_text())
        ctx.set("HASS_JSON", json.dumps(fake_hass, default=str))
        ctx.set("CONFIG_JSON", json.dumps(config))
        return json.loads(ctx.eval(RUN_INTAKE_CARD))

    # Default: one button "1".
    result = run({})
    html = result["html"]
    assert result["buttons"] == [1]
    assert 'data-take="switch.ben_magnesium_10_mg_morgens" data-value="1"' in html
    assert 'data-value="0.5"' not in html
    # Anna took a quarter: shown as taken, with "Undo"; "bei Bedarf" for Ben's evening intake.
    assert "✓ ¼ genommen" in html and 'data-undo="switch.anna_magnesium_10_mg_morgens"' in html
    assert "bei Bedarf" in html
    assert '<span class="name">Magnesium 10 mg</span>' in html
    # Two people -> one section each; the name is in the heading, not in every row.
    assert html.index("<h3>Anna</h3>") < html.index("<h3>Ben</h3>")
    assert "Abends · Dosis 1 · bei Bedarf" in html and "Ben · Abends" not in html
    assert result["calls"] == [
        ["pillbox", "take_intake", {"entity_id": "switch.ben_magnesium_10_mg_morgens", "amount": 0.75}],
        ["switch", "turn_off", {"entity_id": "switch.anna_magnesium_10_mg_morgens"}],
    ]

    # Own buttons (also typed in as text with a comma), sorted; the amount taken is highlighted.
    result = run({"buttons": ["0,75", 0.25, "1", 0.25, "x"]})
    assert result["buttons"] == [0.25, 0.75, 1]
    html = result["html"]
    assert '>¾</button>' in html
    assert 'class="dose current" data-take="switch.anna_magnesium_10_mg_morgens" data-value="0.25"' in html

    # Filters: only Ben, without "as needed" and without intakes already taken.
    html = run({"people": [ids["Ben"]], "hide_as_needed": True, "hide_done": True})["html"]
    assert "switch.ben_magnesium_10_mg_morgens" in html
    assert "<h3>" not in html and "Ben · Morgens" in html  # one person: no sections, name in the row
    assert "switch.ben_magnesium_10_mg_abends" not in html and "switch.anna" not in html
    html = run({"packs": [ids["Magnesium 10 mg"]]})["html"]
    assert "switch.anna_magnesium_10_mg_morgens" in html


async def test_card_stock_dialog(hass, freezer):
    quickjs = pytest.importorskip("quickjs")
    entry = _family_entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    html, _ = await _render(hass, quickjs, entry, {})
    # The pack name opens the stock dialog.
    assert 'data-edit="number.magnesium_10_mg_stock" data-name="Magnesium 10 mg"' in html

    ctx = quickjs.Context()
    ctx.eval(HARNESS)
    ctx.eval(CARD_PATH.read_text())
    result = json.loads(ctx.eval("""
      (() => {
        const card = new (customElements.get("pillbox-card"))();
        const calls = [];
        card.setConfig({});
        card._hass = { states: { "number.a": { state: "30" } }, callService: (d, s, data) => calls.push([d, s, data]) };
        card._onClick({ target: { closest: () => ({ dataset: { edit: "number.a", name: "Magnesium 10 mg" } }) } });
        const saved = [card._saveStock("number.a", "12,5"), card._saveStock("number.a", "30"),
                       card._saveStock("number.a", ""), card._saveStock("number.a", "-1"), card._saveStock("number.a", "abc")];
        return JSON.stringify({ editing: card._editing, saved, calls });
      })()
    """))
    assert result["editing"] == {"entityId": "number.a", "name": "Magnesium 10 mg", "value": "30"}
    assert result["saved"] == [True, True, False, False, False]
    # Only a changed value is sent.
    assert result["calls"] == [["number", "set_value", {"entity_id": "number.a", "value": 12.5}]]
