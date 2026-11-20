"""Config flow.

- One "Pillbox" entry; its options define the times of day (morning, noon, ...).
- Subentry "People": everyone who takes something, each optionally with their own NFC tag.
- Subentry "Medication": one pack with stock per strength; intakes = time of day x (optional) person.
"""
from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_HA_PERSON,
    CONF_INTAKES,
    CONF_LOW_THRESHOLD,
    CONF_PACK_ID,
    CONF_PACKS,
    CONF_PERSONS,
    CONF_SLOTS,
    CONF_STOCK,
    CONF_STRENGTH,
    CONF_STRENGTHS,
    CONF_TABLETS_PER_INTAKE,
    CONF_TAG_ID,
    DEFAULT_LOW_THRESHOLD,
    DOMAIN,
    MAX_SLOTS,
    SECTION_ADVANCED,
    SUBENTRY_MEDICATION,
    SUBENTRY_PERSON,
    default_slots,
    make_key,
    ordered_slots,
    parse_key,
    persons_title,
)

_NUM = lambda lo, hi: selector.NumberSelector(  # noqa: E731
    selector.NumberSelectorConfig(min=lo, max=hi, step=1, mode=selector.NumberSelectorMode.BOX)
)

_ADVANCED_FIELDS = (CONF_TABLETS_PER_INTAKE, CONF_LOW_THRESHOLD)
_INT_FIELDS = (CONF_STOCK, CONF_TABLETS_PER_INTAKE, CONF_LOW_THRESHOLD)


# --- Helpers ----------------------------------------------------------------


def _slots(entry: ConfigEntry, hass: HomeAssistant) -> dict[str, str]:
    return dict(entry.options.get(CONF_SLOTS) or default_slots(hass.config.language))


def _persons(entry: ConfigEntry) -> list[tuple[str, str]]:
    """(person id, name) of all people, alphabetically."""
    return sorted(
        (
            (p[CONF_PACK_ID], p[CONF_NAME])
            for sub in entry.subentries.values()
            if sub.subentry_type == SUBENTRY_PERSON
            for p in sub.data.get(CONF_PERSONS, [])
        ),
        key=lambda p: p[1].casefold(),
    )


def _tag_in_use(entry: ConfigEntry, tag: str | None, own_subentry_id: str | None) -> bool:
    """Is the tag already assigned to another person or pack?"""
    if not tag:
        return False
    for sid, sub in entry.subentries.items():
        if sid == own_subentry_id:
            continue
        items = [sub.data, *sub.data.get(CONF_PACKS, []), *sub.data.get(CONF_PERSONS, [])]
        tags = [i.get(CONF_TAG_ID) for i in items]
        if tag in tags:
            return True
    return False


def _tag_selector(hass: HomeAssistant) -> selector.SelectSelector:
    """Dropdown with all NFC tags known to HA (name -> tag ID); custom input allowed."""
    options = sorted(
        (
            selector.SelectOptionDict(value=e.unique_id, label=e.name or e.original_name or e.unique_id)
            for e in er.async_get(hass).entities.values()
            if e.domain == "tag" and e.platform == "tag"
        ),
        key=lambda o: o["label"].casefold(),
    )
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options, mode=selector.SelectSelectorMode.DROPDOWN, custom_value=True, sort=False
        )
    )


def _intake_options(
    slots: dict[str, str], persons: list[tuple[str, str]], selected: list[str] | None = None
) -> list[selector.SelectOptionDict]:
    """Selectable intakes: per time of day and person.

    Intakes without a person are only offered while no people exist (or if one is already selected).
    """
    selected = selected or []
    options: list[selector.SelectOptionDict] = []
    for slot_id, slot_name in ordered_slots(slots):
        if not persons or make_key(slot_id, None) in selected:
            options.append(selector.SelectOptionDict(value=make_key(slot_id, None), label=slot_name))
        options.extend(
            selector.SelectOptionDict(value=make_key(slot_id, pid), label=f"{slot_name} · {pname}")
            for pid, pname in persons
        )
    return options


# --- Pillbox entry ----------------------------------------------------------


class PillboxConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(
                title="Pillbox", data={}, options={CONF_SLOTS: default_slots(self.hass.config.language)}
            )
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PillboxOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry):
        return {SUBENTRY_MEDICATION: MedicationSubentryFlow, SUBENTRY_PERSON: PersonSubentryFlow}


class PillboxOptionsFlow(OptionsFlow):
    """Times of day: up to MAX_SLOTS names, order = order of the day."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        slots = _slots(self.config_entry, self.hass)
        errors: dict[str, str] = {}
        if user_input is not None:
            new = {
                str(i): str(user_input.get(f"slot_{i}", "")).strip()
                for i in range(1, MAX_SLOTS + 1)
            }
            new = {k: v for k, v in new.items() if v}
            used = {
                parse_key(key)[0]
                for sub in self.config_entry.subentries.values()
                if sub.subentry_type == SUBENTRY_MEDICATION
                for pack in sub.data.get(CONF_PACKS, [])
                for key in pack.get(CONF_INTAKES, [])
            }
            if not new:
                errors["base"] = "no_slots"
            elif len({v.casefold() for v in new.values()}) != len(new):
                errors["base"] = "duplicate_slots"
            elif missing := sorted(used - new.keys(), key=int):
                errors[f"slot_{missing[0]}"] = "slot_in_use"
            if not errors:
                return self.async_create_entry(data={**self.config_entry.options, CONF_SLOTS: new})
            slots = new
        schema = vol.Schema(
            {
                vol.Optional(f"slot_{i}", description={"suggested_value": slots.get(str(i), "")}): str
                for i in range(1, MAX_SLOTS + 1)
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)


# --- People -----------------------------------------------------------------
#
# One "People" subentry for everyone; each person becomes a device below it.
# Step 1: list of people. Step 2 ("person"): name, HA person and tag per person.


def _persons_schema(existing: list[str]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_PERSONS, default=[]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=existing, multiple=True, custom_value=True, mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
        }
    )


def _person_schema(hass: HomeAssistant) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME): str,
            vol.Optional(CONF_HA_PERSON): selector.EntitySelector(selector.EntitySelectorConfig(domain="person")),
            vol.Optional(CONF_TAG_ID): _tag_selector(hass),
        }
    )


class PersonSubentryFlow(ConfigSubentryFlow):
    """Create or edit people (all in one subentry)."""

    def __init__(self) -> None:
        self._names: list[str] = []
        self._existing: dict[str, dict[str, Any]] = {}  # name (casefold) -> stored person
        self._persons: list[dict[str, Any]] = []
        self._reconfigure = False

    def _own_id(self) -> str | None:
        return self._get_reconfigure_subentry().subentry_id if self._reconfigure else None

    async def _async_step_persons(self, step_id: str, user_input, suggested: dict[str, Any]):
        errors: dict[str, str] = {}
        if user_input is not None:
            names = [str(n).strip() for n in user_input.get(CONF_PERSONS, [])]
            self._names = list(dict.fromkeys(n for n in names if n))
            if not self._names:
                errors[CONF_PERSONS] = "no_persons"
            elif len({n.casefold() for n in self._names}) != len(self._names):
                errors[CONF_PERSONS] = "duplicate_names"
            else:
                self._persons = []
                return await self.async_step_person()
            suggested = user_input
        existing = [p[CONF_NAME] for p in self._existing.values()]
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(_persons_schema(existing), suggested),
            errors=errors,
        )

    async def async_step_user(self, user_input=None) -> SubentryFlowResult:
        if any(s.subentry_type == SUBENTRY_PERSON for s in self._get_entry().subentries.values()):
            return self.async_abort(reason="persons_exist")
        return await self._async_step_persons("user", user_input, {})

    async def async_step_reconfigure(self, user_input=None) -> SubentryFlowResult:
        self._reconfigure = True
        persons = self._get_reconfigure_subentry().data.get(CONF_PERSONS, [])
        self._existing = {p[CONF_NAME].casefold(): p for p in persons}
        suggested = {CONF_PERSONS: [p[CONF_NAME] for p in persons]}
        return await self._async_step_persons("reconfigure", user_input, suggested)

    async def async_step_person(self, user_input=None) -> SubentryFlowResult:
        """Edit one person (name can change; their intakes are kept)."""
        name = self._names[len(self._persons)]
        existing = self._existing.get(name.casefold())
        errors: dict[str, str] = {}
        suggested = {k: v for k, v in (existing or {CONF_NAME: name}).items() if k != CONF_PACK_ID}

        if user_input is not None:
            person = {**user_input, CONF_NAME: user_input[CONF_NAME].strip()}
            tag = person.get(CONF_TAG_ID)
            other_names = {p[CONF_NAME].casefold() for p in self._persons} | {
                n.casefold() for n in self._names[len(self._persons) + 1 :]
            }
            if not person[CONF_NAME]:
                errors[CONF_NAME] = "no_name"
            elif person[CONF_NAME].casefold() in other_names:
                errors[CONF_NAME] = "duplicate_names"
            if tag and (
                _tag_in_use(self._get_entry(), tag, self._own_id())
                or any(p.get(CONF_TAG_ID) == tag for p in self._persons)
            ):
                errors[CONF_TAG_ID] = "tag_in_use"
            if not errors:
                person_id = existing[CONF_PACK_ID] if existing else uuid.uuid4().hex[:12]
                self._persons.append({CONF_PACK_ID: person_id, **person})
                if len(self._persons) < len(self._names):
                    return await self.async_step_person()
                return self._async_finish()
            suggested = user_input

        return self.async_show_form(
            step_id="person",
            data_schema=self.add_suggested_values_to_schema(_person_schema(self.hass), suggested),
            errors=errors,
            description_placeholders={
                "person": name,
                "position": str(len(self._persons) + 1),
                "count": str(len(self._names)),
            },
            last_step=len(self._persons) + 1 == len(self._names),
        )

    @callback
    def _async_finish(self) -> SubentryFlowResult:
        data = {CONF_PERSONS: self._persons}
        title = persons_title(self.hass.config.language)
        if self._reconfigure:
            return self.async_update_and_abort(
                self._get_entry(), self._get_reconfigure_subentry(), title=title, data=data
            )
        return self.async_create_entry(title=title, data=data)


# --- Medication -------------------------------------------------------------
#
# Step 1 ("user" or "reconfigure"): name and strengths.
# Step 2 ("pack"): one page per strength with stock, intakes, tag and dosage.


def _medication_schema(entry: ConfigEntry) -> vol.Schema:
    strengths = sorted(
        {
            str(p.get(CONF_STRENGTH))
            for sub in entry.subentries.values()
            if sub.subentry_type == SUBENTRY_MEDICATION
            for p in sub.data.get(CONF_PACKS, [])
            if p.get(CONF_STRENGTH)
        }
    )
    return vol.Schema(
        {
            vol.Required(CONF_NAME): str,
            vol.Optional(CONF_STRENGTHS, default=[]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=strengths, multiple=True, custom_value=True, mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
        }
    )


def _pack_schema(hass: HomeAssistant, entry: ConfigEntry, selected: list[str] | None = None) -> vol.Schema:
    slots = _slots(entry, hass)
    persons = _persons(entry)
    # Without people: preselect the first time of day; with people, let the user choose.
    default = [] if persons else [make_key(ordered_slots(slots)[0][0], None)]
    return vol.Schema(
        {
            vol.Required(CONF_STOCK): _NUM(0, 1000),
            vol.Required(CONF_INTAKES, default=default): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_intake_options(slots, persons, selected),
                    multiple=True,
                    sort=False,
                    mode=selector.SelectSelectorMode.DROPDOWN,  # chips instead of a long checkbox list
                )
            ),
            vol.Optional(CONF_TAG_ID): _tag_selector(hass),
            vol.Required(SECTION_ADVANCED): section(
                vol.Schema(
                    {
                        vol.Required(CONF_TABLETS_PER_INTAKE, default=1): _NUM(1, 10),
                        vol.Required(CONF_LOW_THRESHOLD, default=DEFAULT_LOW_THRESHOLD): _NUM(0, 1000),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


def _pack_suggested(pack: dict[str, Any]) -> dict[str, Any]:
    """Stored (flat) pack as form defaults, with the section nested."""
    values = {k: v for k, v in pack.items() if k not in (*_ADVANCED_FIELDS, CONF_PACK_ID, CONF_STRENGTH)}
    values[SECTION_ADVANCED] = {k: pack[k] for k in _ADVANCED_FIELDS if k in pack}
    return values


class MedicationSubentryFlow(ConfigSubentryFlow):
    """Create or edit a medication; one pack (device) per strength."""

    def __init__(self) -> None:
        self._name = ""
        self._strengths: list[str] = []
        self._existing: dict[str, dict[str, Any]] = {}  # strength (casefold) -> stored pack
        self._packs: list[dict[str, Any]] = []
        self._reconfigure = False

    def _own_id(self) -> str | None:
        return self._get_reconfigure_subentry().subentry_id if self._reconfigure else None

    async def _async_step_medication(self, step_id: str, user_input, suggested: dict[str, Any]):
        errors: dict[str, str] = {}
        if user_input is not None:
            self._name = user_input[CONF_NAME].strip()
            strengths = [str(x).strip() for x in user_input.get(CONF_STRENGTHS, [])]
            self._strengths = list(dict.fromkeys(x for x in strengths if x)) or [""]
            if not self._name:
                errors[CONF_NAME] = "no_name"
            elif len({x.casefold() for x in self._strengths}) != len(self._strengths):
                errors[CONF_STRENGTHS] = "duplicate_strengths"
            else:
                self._packs = []
                return await self.async_step_pack()
            suggested = user_input
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(_medication_schema(self._get_entry()), suggested),
            errors=errors,
        )

    async def async_step_user(self, user_input=None) -> SubentryFlowResult:
        return await self._async_step_medication("user", user_input, {})

    async def async_step_reconfigure(self, user_input=None) -> SubentryFlowResult:
        self._reconfigure = True
        sub = self._get_reconfigure_subentry()
        packs = sub.data.get(CONF_PACKS, [])
        self._existing = {str(p.get(CONF_STRENGTH, "")).casefold(): p for p in packs}
        suggested = {
            CONF_NAME: sub.data.get(CONF_NAME, sub.title),
            CONF_STRENGTHS: [p[CONF_STRENGTH] for p in packs if p.get(CONF_STRENGTH)],
        }
        return await self._async_step_medication("reconfigure", user_input, suggested)

    async def async_step_pack(self, user_input=None) -> SubentryFlowResult:
        """Edit one pack (strength); then the next one or finish."""
        strength = self._strengths[len(self._packs)]
        existing = self._existing.get(strength.casefold())
        entry = self._get_entry()
        errors: dict[str, str] = {}
        suggested = _pack_suggested(existing) if existing else {}

        if user_input is not None:
            pack: dict[str, Any] = {k: v for k, v in user_input.items() if k != SECTION_ADVANCED}
            pack.update(user_input.get(SECTION_ADVANCED, {}))
            for key in _INT_FIELDS:
                if key in pack:
                    pack[key] = int(pack[key])  # NumberSelector returns float
            pack[CONF_INTAKES] = list(dict.fromkeys(pack.get(CONF_INTAKES, [])))
            tag = pack.get(CONF_TAG_ID)
            if not pack[CONF_INTAKES]:
                errors[CONF_INTAKES] = "no_intakes"
            if tag and (
                _tag_in_use(entry, tag, self._own_id()) or any(p.get(CONF_TAG_ID) == tag for p in self._packs)
            ):
                errors[CONF_TAG_ID] = "tag_in_use"
            if not errors:
                pack_id = existing[CONF_PACK_ID] if existing else uuid.uuid4().hex[:12]
                self._packs.append({CONF_PACK_ID: pack_id, CONF_STRENGTH: strength, **pack})
                if len(self._packs) < len(self._strengths):
                    return await self.async_step_pack()
                return self._async_finish()
            suggested = user_input

        selected = list(existing.get(CONF_INTAKES, [])) if existing else []
        return self.async_show_form(
            step_id="pack",
            data_schema=self.add_suggested_values_to_schema(_pack_schema(self.hass, entry, selected), suggested),
            errors=errors,
            description_placeholders={
                "medication": f"{self._name} {strength}".strip(),
                "position": str(len(self._packs) + 1),
                "count": str(len(self._strengths)),
            },
            last_step=len(self._packs) + 1 == len(self._strengths),
        )

    @callback
    def _async_finish(self) -> SubentryFlowResult:
        packs = [{k: v for k, v in p.items() if not (k == CONF_STRENGTH and not v)} for p in self._packs]
        data = {CONF_NAME: self._name, CONF_PACKS: packs}
        if self._reconfigure:
            return self.async_update_and_abort(
                self._get_entry(), self._get_reconfigure_subentry(), title=self._name, data=data
            )
        return self.async_create_entry(title=self._name, data=data)
