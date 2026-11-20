"""Config-Flow.

- Ein Eintrag „Pillbox“; seine Optionen legen die Einnahme-Zeiten des Tages fest (Morgens, Mittags, …).
- Untereinheit „Person“: wer etwas einnimmt, optional mit eigenem NFC-Tag.
- Untereinheit „Medikament“: eine Packung mit Vorrat; Einnahmen = Einnahme-Zeit × (optional) Person.
"""
from __future__ import annotations

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
    CONF_SLOTS,
    CONF_STOCK,
    CONF_STRENGTH,
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
)

_NUM = lambda lo, hi: selector.NumberSelector(  # noqa: E731
    selector.NumberSelectorConfig(min=lo, max=hi, step=1, mode=selector.NumberSelectorMode.BOX)
)

_ADVANCED_FIELDS = (CONF_TABLETS_PER_INTAKE, CONF_LOW_THRESHOLD)
_INT_FIELDS = (CONF_STOCK, CONF_TABLETS_PER_INTAKE, CONF_LOW_THRESHOLD)


# --- Hilfen -----------------------------------------------------------------


def _slots(entry: ConfigEntry, hass: HomeAssistant) -> dict[str, str]:
    return dict(entry.options.get(CONF_SLOTS) or default_slots(hass.config.language))


def _persons(entry: ConfigEntry) -> list[tuple[str, str]]:
    """(subentry_id, Name) aller Personen, alphabetisch."""
    return sorted(
        ((sid, sub.title) for sid, sub in entry.subentries.items() if sub.subentry_type == SUBENTRY_PERSON),
        key=lambda p: p[1].casefold(),
    )


def _tag_in_use(entry: ConfigEntry, tag: str | None, own_subentry_id: str | None) -> bool:
    """Ist der Tag schon einer anderen Person oder einem anderen Medikament zugeordnet?"""
    if not tag:
        return False
    return any(
        sub.data.get(CONF_TAG_ID) == tag
        for sid, sub in entry.subentries.items()
        if sid != own_subentry_id
    )


def _tag_selector(hass: HomeAssistant) -> selector.SelectSelector:
    """Dropdown mit allen in HA bekannten NFC-Tags (Name -> Tag-ID), eigene Eingabe erlaubt."""
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


def _intake_options(slots: dict[str, str], persons: list[tuple[str, str]]) -> list[selector.SelectOptionDict]:
    """Alle wählbaren Einnahmen: je Einnahme-Zeit „ohne Person“ und je Person."""
    options: list[selector.SelectOptionDict] = []
    for slot_id, slot_name in ordered_slots(slots):
        options.append(selector.SelectOptionDict(value=make_key(slot_id, None), label=slot_name))
        options.extend(
            selector.SelectOptionDict(value=make_key(slot_id, pid), label=f"{slot_name} · {pname}")
            for pid, pname in persons
        )
    return options


# --- Pillbox-Eintrag --------------------------------------------------------


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
    """Einnahme-Zeiten des Tages: bis zu MAX_SLOTS Namen, Reihenfolge = Tagesablauf."""

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
                for key in sub.data.get(CONF_INTAKES, [])
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


# --- Person -----------------------------------------------------------------


def _person_schema(hass: HomeAssistant) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME): str,
            vol.Optional(CONF_HA_PERSON): selector.EntitySelector(selector.EntitySelectorConfig(domain="person")),
            vol.Optional(CONF_TAG_ID): _tag_selector(hass),
        }
    )


class PersonSubentryFlow(ConfigSubentryFlow):
    """Person anlegen oder ändern."""

    def _validate(self, user_input: dict[str, Any], own_id: str | None) -> tuple[dict[str, Any], dict[str, str]]:
        data = {**user_input, CONF_NAME: user_input[CONF_NAME].strip()}
        errors: dict[str, str] = {}
        if not data[CONF_NAME]:
            errors[CONF_NAME] = "no_name"
        if _tag_in_use(self._get_entry(), data.get(CONF_TAG_ID), own_id):
            errors[CONF_TAG_ID] = "tag_in_use"
        return data, errors

    async def async_step_user(self, user_input=None) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        schema = _person_schema(self.hass)
        if user_input is not None:
            data, errors = self._validate(user_input, None)
            if not errors:
                return self.async_create_entry(title=data[CONF_NAME], data=data)
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(self, user_input=None) -> SubentryFlowResult:
        sub = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        suggested: dict[str, Any] = dict(sub.data)
        if user_input is not None:
            data, errors = self._validate(user_input, sub.subentry_id)
            if not errors:
                return self.async_update_and_abort(self._get_entry(), sub, title=data[CONF_NAME], data=data)
            suggested = user_input
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(_person_schema(self.hass), suggested),
            errors=errors,
        )


# --- Medikament -------------------------------------------------------------


def _medication_schema(hass: HomeAssistant, entry: ConfigEntry) -> vol.Schema:
    slots = _slots(entry, hass)
    first_slot = ordered_slots(slots)[0][0]
    return vol.Schema(
        {
            vol.Required(CONF_NAME): str,
            vol.Optional(CONF_STRENGTH): str,
            vol.Required(CONF_STOCK): _NUM(0, 1000),
            vol.Required(CONF_INTAKES, default=[make_key(first_slot, None)]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_intake_options(slots, _persons(entry)),
                    multiple=True,
                    sort=False,
                    mode=selector.SelectSelectorMode.LIST,
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


def _suggested(data: dict[str, Any]) -> dict[str, Any]:
    """Gespeicherte (flache) Daten als Vorbelegung fürs Formular, Abschnitt verschachtelt."""
    values = {k: v for k, v in data.items() if k not in _ADVANCED_FIELDS}
    values[SECTION_ADVANCED] = {k: data[k] for k in _ADVANCED_FIELDS if k in data}
    return values


class MedicationSubentryFlow(ConfigSubentryFlow):
    """Medikament (Packung) anlegen oder ändern."""

    def _validate(self, user_input: dict[str, Any], own_id: str | None) -> tuple[dict[str, Any], dict[str, str]]:
        data = {k: v for k, v in user_input.items() if k != SECTION_ADVANCED}
        data.update(user_input.get(SECTION_ADVANCED, {}))
        data[CONF_NAME] = data[CONF_NAME].strip()
        if CONF_STRENGTH in data:
            data[CONF_STRENGTH] = str(data[CONF_STRENGTH]).strip()
            if not data[CONF_STRENGTH]:
                del data[CONF_STRENGTH]
        for key in _INT_FIELDS:
            if key in data:
                data[key] = int(data[key])  # NumberSelector liefert float
        data[CONF_INTAKES] = list(dict.fromkeys(data.get(CONF_INTAKES, [])))

        errors: dict[str, str] = {}
        if not data[CONF_NAME]:
            errors[CONF_NAME] = "no_name"
        if not data[CONF_INTAKES]:
            errors[CONF_INTAKES] = "no_intakes"
        if _tag_in_use(self._get_entry(), data.get(CONF_TAG_ID), own_id):
            errors[CONF_TAG_ID] = "tag_in_use"
        return data, errors

    def _title(self, data: dict[str, Any]) -> str:
        return data[CONF_NAME]

    async def async_step_user(self, user_input=None) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        schema = _medication_schema(self.hass, self._get_entry())
        if user_input is not None:
            data, errors = self._validate(user_input, None)
            if not errors:
                return self.async_create_entry(title=self._title(data), data=data)
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(self, user_input=None) -> SubentryFlowResult:
        sub = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        suggested = _suggested(dict(sub.data))
        if user_input is not None:
            data, errors = self._validate(user_input, sub.subentry_id)
            if not errors:
                return self.async_update_and_abort(self._get_entry(), sub, title=self._title(data), data=data)
            suggested = user_input
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(_medication_schema(self.hass, self._get_entry()), suggested),
            errors=errors,
        )
