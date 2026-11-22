"""Doses per intake (e.g. half tablets) and intakes taken only as needed."""
from homeassistant.data_entry_flow import FlowResultType

from custom_components.pillbox.const import DOMAIN

from .test_init import MED_DATA, _at, _call, _make_entry, _scan, _setup, _state, _sub


def _entry(hass):
    """Anna takes half a tablet in the morning; Ben one in the morning and one in the evening if needed."""
    return _make_entry(
        hass,
        subs=[
            _sub("people", {"persons": [{"id": "anna", "name": "Anna", "tag_id": "tag-anna"}, {"id": "ben", "name": "Ben", "tag_id": "tag-ben"}]}, "person", "People"),
            _sub(
                "mag",
                {
                    "name": "Magnesium",
                    "packs": [
                        {
                            "id": "m10",
                            "strength": "10 mg",
                            "stock": 20,
                            "intakes": ["1|anna", "1|ben", "3|ben"],
                            "doses": {"1|anna": 0.5},
                            "as_needed": ["3|ben"],
                        }
                    ],
                },
            ),
        ],
    )


async def test_doses_and_as_needed(hass, freezer):
    entry = _entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    # Daily consumption 1.5 (the evening "as needed" intake does not count).
    assert _state(hass, "sensor.magnesium_10_mg_days_left") == "13"
    anna = hass.states.get("switch.anna_magnesium_10_mg_morgens")
    assert anna.attributes["dose"] == 0.5 and anna.attributes["as_needed"] is False
    ben_evening = hass.states.get("switch.ben_magnesium_10_mg_abends")
    assert ben_evening.attributes["dose"] == 1 and ben_evening.attributes["as_needed"] is True
    ben = hass.states.get("sensor.ben_open_intakes")
    assert ben.state == "1"
    assert ben.attributes["open"] == ["Magnesium 10 mg (Morgens)"]
    assert ben.attributes["as_needed"] == ["Magnesium 10 mg (Abends)"]
    count = hass.states.get("sensor.magnesium_10_mg_intakes_today")
    assert count.attributes["total"] == 2
    assert count.attributes["as_needed"] == ["Ben Abends"]

    await _scan(hass, "tag-anna")
    assert _state(hass, "number.magnesium_10_mg_stock") == "19.5"
    await _scan(hass, "tag-ben")
    assert _state(hass, "number.magnesium_10_mg_stock") == "18.5"
    assert _state(hass, "switch.ben_magnesium_10_mg_abends") == "off"  # person tag skips "as needed"
    assert _state(hass, "sensor.ben_open_intakes") == "0"
    assert hass.states.get("sensor.ben_open_intakes").attributes["next_slot"] is None
    assert _state(hass, "binary_sensor.magnesium_10_mg_complete_today") == "on"
    await _scan(hass, "tag-ben")
    assert _state(hass, "number.magnesium_10_mg_stock") == "18.5"

    # Ben needs one in the evening.
    await _call(hass, "switch", "turn_on", "switch.ben_magnesium_10_mg_abends")
    assert _state(hass, "number.magnesium_10_mg_stock") == "17.5"
    assert _state(hass, "sensor.magnesium_10_mg_days_left") == "11"

    # Stock with fractions can be set directly.
    await _call(hass, "number", "set_value", "number.magnesium_10_mg_stock", value=12.25)
    assert _state(hass, "number.magnesium_10_mg_stock") == "12.25"


async def test_only_as_needed_pack(hass, freezer):
    entry = _make_entry(hass, {**MED_DATA, "stock": 10, "as_needed": ["1|"]})
    freezer.move_to(_at("2026-11-18 09:00:00"))
    await _setup(hass, entry)
    assert _state(hass, "sensor.vitamin_d_days_left") == "unknown"
    assert _state(hass, "sensor.vitamin_d_runs_out_on") == "unknown"
    assert _state(hass, "binary_sensor.vitamin_d_complete_today") == "on"
    await _scan(hass, "tag-vitamin_d")
    assert _state(hass, "switch.vitamin_d_morgens") == "on"
    assert _state(hass, "number.vitamin_d_stock") == "9"


async def test_stored_fractional_stock_is_kept(hass, hass_storage, freezer):
    from .test_init import _store

    entry = _make_entry(hass, {**MED_DATA, "tablets_per_intake": 0.5})
    _store(hass_storage, entry, {"day": "2026-11-18", "meds": {"sub1": {"stock": 41.5, "taken": {"1|": True}, "config_stock": 53}}})
    freezer.move_to(_at("2026-11-18 09:00:00"))
    await _setup(hass, entry)
    assert _state(hass, "number.vitamin_d_stock") == "41.5"
    await _call(hass, "switch", "turn_off", "switch.vitamin_d_morgens")
    assert _state(hass, "number.vitamin_d_stock") == "42"


async def test_flow_as_needed_and_doses(hass):
    entry = _entry(hass)
    await _setup(hass, entry)
    result = await hass.config_entries.subentries.async_init((entry.entry_id, "medication"), context={"source": "user"})
    page = {
        "name": "Vitamin D",
        "strengths": [],
        "stock": 30.5,
        "intakes": ["1|anna", "1|ben"],
        "as_needed": ["3|ben"],
        "advanced": {"tablets_per_intake": 1, "individual_doses": True, "low_threshold": 5},
    }
    bad = await hass.config_entries.subentries.async_configure(result["flow_id"], {**page, "intakes": [], "as_needed": []})
    assert bad["errors"] == {"intakes": "no_intakes"}
    # "As needed" alone is enough; it need not be selected under "Intakes" as well.
    result = await hass.config_entries.subentries.async_configure(bad["flow_id"], {**page, "intakes": ["1|anna"], "as_needed": ["1|ben"]})
    # Second page: one dose per intake, labelled with the intake.
    assert result["step_id"] == "doses"
    assert result["last_step"] is True
    assert [str(k) for k in result["data_schema"].schema] == ["Morgens · Anna", "Morgens · Ben"]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"Morgens · Anna": 0.25, "Morgens · Ben": 1.0}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    sub = next(s for s in entry.subentries.values() if s.title == "Vitamin D")
    pack = sub.data["packs"][0]
    assert {k: v for k, v in pack.items() if k != "id"} == {
        "stock": 30.5,
        "intakes": ["1|anna", "1|ben"],
        "as_needed": ["1|ben"],
        "tablets_per_intake": 1,
        "low_threshold": 5,
        "doses": {"1|anna": 0.25},  # only doses that differ from the default
    }
    assert _state(hass, "sensor.vitamin_d_days_left") == "122"  # 30.5 / 0.25

    # Editing: the checkbox is set and the doses page is prefilled.
    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    advanced = next(v for k, v in result["data_schema"].schema.items() if str(k) == "advanced")
    suggested = {str(k): (k.description or {}).get("suggested_value") for k in advanced.schema.schema}
    assert suggested["individual_doses"] is True
    top = {str(k): (k.description or {}).get("suggested_value") for k in result["data_schema"].schema}
    assert top["intakes"] == ["1|anna"] and top["as_needed"] == ["1|ben"]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**page, "as_needed": [], "advanced": {**page["advanced"], "tablets_per_intake": 0.5}}
    )
    assert result["step_id"] == "doses"
    defaults = {str(k): k.default() for k in result["data_schema"].schema}
    assert defaults == {"Morgens · Anna": 0.25, "Morgens · Ben": 0.5}
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], defaults)
    assert result["reason"] == "reconfigure_successful"
    pack = entry.subentries[sub.subentry_id].data["packs"][0]
    assert "as_needed" not in pack
    assert pack["tablets_per_intake"] == 0.5 and pack["doses"] == {"1|anna": 0.25}

    # Unchecking "different dose per intake" drops the own doses.
    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**page, "as_needed": [], "advanced": {"tablets_per_intake": 1, "individual_doses": False, "low_threshold": 5}}
    )
    assert result["reason"] == "reconfigure_successful"
    assert "doses" not in entry.subentries[sub.subentry_id].data["packs"][0]


async def test_refill_with_halves(hass, freezer):
    from homeassistant.helpers import device_registry as dr

    entry = _entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "m10")}).id
    await hass.services.async_call(DOMAIN, "refill", {"device_id": device, "add": 0.5}, blocking=True)
    await hass.async_block_till_done()
    assert _state(hass, "number.magnesium_10_mg_stock") == "20.5"


async def test_take_intake_with_amount(hass, hass_storage, freezer):
    entry = _entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    switch = "switch.ben_magnesium_10_mg_morgens"
    await hass.services.async_call(DOMAIN, "take_intake", {"entity_id": switch, "amount": 0.75}, blocking=True)
    await hass.async_block_till_done()
    assert _state(hass, switch) == "on"
    assert hass.states.get(switch).attributes["taken_amount"] == 0.75
    assert _state(hass, "number.magnesium_10_mg_stock") == "19.25"
    # Correct the amount; without an amount the dose is used.
    await hass.services.async_call(DOMAIN, "take_intake", {"entity_id": switch, "amount": 1.25}, blocking=True)
    await hass.services.async_call(DOMAIN, "take_intake", {"entity_id": "switch.anna_magnesium_10_mg_morgens"}, blocking=True)
    await hass.async_block_till_done()
    assert _state(hass, "number.magnesium_10_mg_stock") == "18.25"
    assert hass.states.get("switch.anna_magnesium_10_mg_morgens").attributes["taken_amount"] == 0.5

    # The amount survives a restart and is given back on undo.
    stored = hass_storage[f"pillbox.state.{entry.entry_id}"]["data"]["meds"]["m10"]
    assert stored["amounts"] == {"1|anna": 0.5, "1|ben": 1.25}
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(switch).attributes["taken_amount"] == 1.25
    await _call(hass, "switch", "turn_off", switch)
    assert _state(hass, "number.magnesium_10_mg_stock") == "19.5"
    assert hass.states.get(switch).attributes["taken_amount"] == 0
