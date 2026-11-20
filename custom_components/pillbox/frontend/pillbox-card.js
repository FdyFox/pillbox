/*
 * Pillbox card: overview of people (open intakes today) and packs (stock, coverage).
 * Served by the integration itself and registered automatically, no build step.
 * All options can be set in the card editor (getConfigForm); all of them are optional:
 *
 *   type: custom:pillbox-card
 *   title: Pillbox
 *   hide_people: false        # hide the people section
 *   people: [<device_id>]     # only these people, in this order (default: all, alphabetically)
 *   hide_done_people: false   # hide people with nothing left to take today
 *   hide_take_now: false      # hide the "Take now" button
 *   hide_packs: false         # hide the packs section
 *   packs: [<device_id>]      # only these packs, in this order (default: all)
 *   low_stock_only: false     # only packs with low stock
 *   packs_sort: name          # name | days_left
 *   hide_columns: []          # stock | days_left | runs_out
 *
 * Older keys show_people / show_packs are still understood.
 */

const STRINGS = {
  en: {
    title: "Pillbox",
    people: "People",
    packs: "Packs",
    takeNow: "Take now",
    allDone: "All done today",
    next: "Next",
    stock: "Stock",
    daysLeft: "Lasts",
    days: "days",
    until: "until",
    low: "Low stock",
    empty: "No Pillbox entities found.",
    noLowStock: "No pack is running low.",
    // editor
    e_title: "Title",
    e_people: "People",
    e_packs: "Packs",
    e_hide_people: "Hide people",
    e_people_select: "Only these people (in this order)",
    e_hide_done_people: "Hide people with everything done",
    e_hide_take_now: "Hide \"Take now\" button",
    e_hide_packs: "Hide packs",
    e_packs_select: "Only these packs (in this order)",
    e_low_stock_only: "Only packs with low stock",
    e_packs_sort: "Sort packs by",
    e_sort_name: "Name",
    e_sort_days_left: "Days left (shortest first)",
    e_hide_columns: "Hide columns",
    e_col_stock: "Stock",
    e_col_days_left: "Days left",
    e_col_runs_out: "Lasts until",
    h_people_select: "Empty = all people, alphabetically",
    h_packs_select: "Empty = all packs",
  },
  de: {
    title: "Pillbox",
    people: "Personen",
    packs: "Packungen",
    takeNow: "Jetzt einnehmen",
    allDone: "Heute alles erledigt",
    next: "Als Nächstes",
    stock: "Vorrat",
    daysLeft: "Reicht noch",
    days: "Tage",
    until: "bis",
    low: "Vorrat niedrig",
    empty: "Keine Pillbox-Entitäten gefunden.",
    noLowStock: "Keine Packung wird knapp.",
    // editor
    e_title: "Titel",
    e_people: "Personen",
    e_packs: "Packungen",
    e_hide_people: "Personen ausblenden",
    e_people_select: "Nur diese Personen (in dieser Reihenfolge)",
    e_hide_done_people: "Personen ausblenden, die alles erledigt haben",
    e_hide_take_now: "Knopf „Jetzt einnehmen“ ausblenden",
    e_hide_packs: "Packungen ausblenden",
    e_packs_select: "Nur diese Packungen (in dieser Reihenfolge)",
    e_low_stock_only: "Nur Packungen mit niedrigem Vorrat",
    e_packs_sort: "Packungen sortieren nach",
    e_sort_name: "Name",
    e_sort_days_left: "Reichweite (kürzeste zuerst)",
    e_hide_columns: "Spalten ausblenden",
    e_col_stock: "Vorrat",
    e_col_days_left: "Reicht noch",
    e_col_runs_out: "Reicht bis",
    h_people_select: "Leer = alle Personen, alphabetisch",
    h_packs_select: "Leer = alle Packungen",
  },
};

/** UI language outside of a card instance (editor labels), falls back to English. */
const uiLanguage = () => {
  const hass = typeof document !== "undefined" ? document.querySelector("home-assistant")?.hass : undefined;
  const lang = hass?.locale?.language || hass?.language || (typeof navigator !== "undefined" ? navigator.language : "en");
  return String(lang || "en").split("-")[0];
};
const tr = (key, lang = uiLanguage()) => (STRINGS[lang] || STRINGS.en)[key] ?? STRINGS.en[key] ?? key;

/** Normalize a card config: defaults plus the older show_* keys. */
const normalizeConfig = (config) => {
  const c = { ...(config || {}) };
  if (c.show_people === false && c.hide_people === undefined) c.hide_people = true;
  if (c.show_packs === false && c.hide_packs === undefined) c.hide_packs = true;
  return {
    people: [],
    packs: [],
    hide_columns: [],
    packs_sort: "name",
    ...c,
  };
};

const escapeHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

class PillboxCard extends HTMLElement {
  setConfig(config) {
    this._config = normalizeConfig(config);
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  static getStubConfig() {
    return {};
  }

  /** Card editor, drawn by Home Assistant from this schema. */
  static getConfigForm() {
    const t = (key) => tr(key);
    const devices = (model) => ({ device: { multiple: true, filter: { integration: "pillbox", model } } });
    const bool = { boolean: {} };
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        {
          type: "expandable",
          name: "",
          title: t("e_people"),
          flatten: true,
          schema: [
            { name: "hide_people", selector: bool },
            { name: "people", selector: devices("Person") },
            { name: "hide_done_people", selector: bool },
            { name: "hide_take_now", selector: bool },
          ],
        },
        {
          type: "expandable",
          name: "",
          title: t("e_packs"),
          flatten: true,
          schema: [
            { name: "hide_packs", selector: bool },
            { name: "packs", selector: devices("Medikament") },
            { name: "low_stock_only", selector: bool },
            {
              name: "packs_sort",
              selector: {
                select: {
                  mode: "dropdown",
                  options: [
                    { value: "name", label: t("e_sort_name") },
                    { value: "days_left", label: t("e_sort_days_left") },
                  ],
                },
              },
            },
            {
              name: "hide_columns",
              selector: {
                select: {
                  multiple: true,
                  options: [
                    { value: "stock", label: t("e_col_stock") },
                    { value: "days_left", label: t("e_col_days_left") },
                    { value: "runs_out", label: t("e_col_runs_out") },
                  ],
                },
              },
            },
          ],
        },
      ],
      computeLabel: (schema) =>
        ({
          title: t("e_title"),
          hide_people: t("e_hide_people"),
          people: t("e_people_select"),
          hide_done_people: t("e_hide_done_people"),
          hide_take_now: t("e_hide_take_now"),
          hide_packs: t("e_hide_packs"),
          packs: t("e_packs_select"),
          low_stock_only: t("e_low_stock_only"),
          packs_sort: t("e_packs_sort"),
          hide_columns: t("e_hide_columns"),
        })[schema.name],
      computeHelper: (schema) => ({ people: t("h_people_select"), packs: t("h_packs_select") })[schema.name],
    };
  }

  _t(key) {
    const lang = (this._hass?.locale?.language || this._hass?.language || "en").split("-")[0];
    return tr(key, lang);
  }

  /** Keep the configured order of selected devices; without a selection use the default order. */
  _select(items, selected, compare) {
    if (!selected?.length) return items.sort(compare);
    const order = new Map(selected.map((id, i) => [id, i]));
    return items.filter((i) => order.has(i.deviceId)).sort((a, b) => order.get(a.deviceId) - order.get(b.deviceId));
  }

  /** Pillbox entities grouped by device: { device_id: [ {entity_id, domain, state} ] } */
  _collect() {
    const hass = this._hass;
    const byDevice = {};
    for (const [entityId, entry] of Object.entries(hass.entities || {})) {
      if (entry.platform !== "pillbox" || !entry.device_id) continue;
      const state = hass.states[entityId];
      if (!state) continue;
      (byDevice[entry.device_id] ||= []).push({ entity_id: entityId, domain: entityId.split(".")[0], state });
    }
    return byDevice;
  }

  _deviceName(deviceId, fallback) {
    const device = this._hass.devices?.[deviceId];
    return device?.name_by_user || device?.name || fallback;
  }

  _people(byDevice) {
    const people = [];
    for (const [deviceId, entities] of Object.entries(byDevice)) {
      const open = entities.find((e) => e.domain === "sensor" && "next_slot" in e.state.attributes);
      if (!open) continue;
      const intakes = entities
        .filter((e) => e.domain === "switch")
        .sort(
          (a, b) =>
            Number(a.state.attributes.slot_id) - Number(b.state.attributes.slot_id) ||
            String(a.state.attributes.medication).localeCompare(String(b.state.attributes.medication))
        );
      people.push({
        deviceId,
        name: this._deviceName(deviceId, open.state.attributes.friendly_name),
        nextSlot: open.state.attributes.next_slot,
        intakes,
        takeNow: entities.find((e) => e.domain === "button"),
      });
    }
    return this._select(people, this._config.people, (a, b) => a.name.localeCompare(b.name));
  }

  _packs(byDevice) {
    const packs = [];
    for (const [deviceId, entities] of Object.entries(byDevice)) {
      const stock = entities.find((e) => e.domain === "number");
      if (!stock) continue;
      const sensor = (deviceClass) =>
        entities.find((e) => e.domain === "sensor" && e.state.attributes.device_class === deviceClass);
      packs.push({
        deviceId,
        name: this._deviceName(deviceId, stock.state.attributes.friendly_name),
        stock: stock.state.state,
        daysLeft: sensor("duration")?.state.state,
        runsOut: sensor("date")?.state.state,
        low: entities.some(
          (e) => e.domain === "binary_sensor" && e.state.attributes.device_class === "problem" && e.state.state === "on"
        ),
      });
    }
    const byName = (a, b) => a.name.localeCompare(b.name);
    let result = this._select(packs, this._config.packs, byName);
    if (this._config.low_stock_only) result = result.filter((p) => p.low);
    if (this._config.packs_sort === "days_left") {
      const days = (p) => (Number.isFinite(Number(p.daysLeft)) ? Number(p.daysLeft) : Infinity);
      result = [...result].sort((a, b) => days(a) - days(b) || byName(a, b));
    }
    return result;
  }

  _formatDate(value) {
    if (!value || value === "unknown" || value === "unavailable") return "–";
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleDateString(this._hass?.locale?.language || undefined, { day: "numeric", month: "short" });
  }

  _renderPerson(person) {
    const chips = person.intakes
      .map((i) => {
        const a = i.state.attributes;
        const done = i.state.state === "on";
        const next = !done && a.slot === person.nextSlot;
        const cls = ["chip", done ? "done" : "open", next ? "next" : ""].join(" ").trim();
        return `<button class="${cls}" data-toggle="${escapeHtml(i.entity_id)}" title="${escapeHtml(a.friendly_name)}">
            <span class="mark">${done ? "✓" : ""}</span>
            <span class="slot">${escapeHtml(a.slot)}</span>
            <span class="med">${escapeHtml(a.medication)}</span>
          </button>`;
      })
      .join("");
    const status = person.nextSlot
      ? `${this._t("next")}: <b>${escapeHtml(person.nextSlot)}</b>`
      : `<span class="ok">${this._t("allDone")}</span>`;
    const takeNow =
      !this._config.hide_take_now && person.takeNow && person.nextSlot
        ? `<button class="action" data-press="${escapeHtml(person.takeNow.entity_id)}">${this._t("takeNow")}</button>`
        : "";
    return `<div class="person">
        <div class="row"><span class="name">${escapeHtml(person.name)}</span><span class="status">${status}</span>${takeNow}</div>
        <div class="chips">${chips}</div>
      </div>`;
  }

  _renderPack(pack) {
    const hidden = new Set(this._config.hide_columns || []);
    const column = (key, title, value) => (hidden.has(key) ? "" : `<span class="value" title="${title}">${value}</span>`);
    return `<div class="pack ${pack.low ? "low" : ""}">
        <span class="name">${escapeHtml(pack.name)}</span>
        ${column("stock", this._t("stock"), escapeHtml(pack.stock))}
        ${column("days_left", this._t("daysLeft"), `${escapeHtml(pack.daysLeft ?? "–")} ${this._t("days")}`)}
        ${column("runs_out", this._t("until"), this._formatDate(pack.runsOut))}
        ${pack.low ? `<span class="badge">${this._t("low")}</span>` : ""}
      </div>`;
  }

  _render() {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    }
    const c = this._config;
    const byDevice = this._collect();
    const allPeople = c.hide_people ? [] : this._people(byDevice);
    const people = c.hide_done_people ? allPeople.filter((p) => p.nextSlot) : allPeople;
    const packs = c.hide_packs ? [] : this._packs(byDevice);
    const anyPacks = !c.hide_packs && Object.values(byDevice).some((list) => list.some((e) => e.domain === "number"));

    let peopleHtml = "";
    if (people.length) peopleHtml = people.map((p) => this._renderPerson(p)).join("");
    else if (allPeople.length) peopleHtml = `<p class="ok">${this._t("allDone")}</p>`;
    let packsHtml = "";
    if (packs.length) packsHtml = packs.map((p) => this._renderPack(p)).join("");
    else if (anyPacks && c.low_stock_only) packsHtml = `<p class="ok">${this._t("noLowStock")}</p>`;

    const body =
      peopleHtml || packsHtml
        ? `${peopleHtml ? `<h3>${this._t("people")}</h3>${peopleHtml}` : ""}
           ${packsHtml ? `<h3>${this._t("packs")}</h3>${packsHtml}` : ""}`
        : `<p class="empty">${this._t("empty")}</p>`;
    this.shadowRoot.innerHTML = `<style>${PillboxCard.styles}</style>
      <ha-card header="${escapeHtml(this._config.title ?? this._t("title"))}"><div class="content">${body}</div></ha-card>`;
  }

  _onClick(ev) {
    const target = ev.target.closest ? ev.target.closest("[data-toggle],[data-press]") : null;
    if (!target) return;
    if (target.dataset.toggle) {
      this._hass.callService("switch", "toggle", { entity_id: target.dataset.toggle });
    } else if (target.dataset.press) {
      this._hass.callService("button", "press", { entity_id: target.dataset.press });
    }
  }

  static get styles() {
    return `
      .content { padding: 0 16px 16px; }
      h3 { margin: 12px 0 6px; font-size: 0.9em; font-weight: 500; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: 0.04em; }
      .person { padding: 8px 0; border-bottom: 1px solid var(--divider-color); }
      .person:last-of-type { border-bottom: none; }
      .row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
      .name { font-weight: 500; flex: 1 1 auto; }
      .status { color: var(--secondary-text-color); font-size: 0.9em; }
      .ok { color: var(--success-color, #43a047); }
      .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
      button { font: inherit; cursor: pointer; }
      .chip { display: inline-flex; align-items: center; gap: 6px; border-radius: 16px; padding: 4px 10px; border: 1px solid var(--divider-color); background: none; color: var(--primary-text-color); }
      .chip .mark { width: 1em; text-align: center; }
      .chip .slot { color: var(--secondary-text-color); font-size: 0.85em; }
      .chip.done { background: var(--success-color, #43a047); border-color: transparent; color: var(--text-primary-color, #fff); }
      .chip.done .slot { color: inherit; opacity: 0.85; }
      .chip.next { border-color: var(--primary-color); border-width: 2px; }
      .action { border: none; border-radius: 16px; padding: 4px 12px; background: var(--primary-color); color: var(--text-primary-color, #fff); }
      .pack { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 6px 0; border-bottom: 1px solid var(--divider-color); }
      .pack:last-of-type { border-bottom: none; }
      .pack .value { color: var(--secondary-text-color); font-variant-numeric: tabular-nums; }
      .pack.low .name, .pack.low .value { color: var(--error-color, #db4437); }
      .badge { font-size: 0.8em; border-radius: 10px; padding: 2px 8px; background: var(--error-color, #db4437); color: var(--text-primary-color, #fff); }
      .empty { color: var(--secondary-text-color); }
    `;
  }
}

if (!customElements.get("pillbox-card")) {
  customElements.define("pillbox-card", PillboxCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "pillbox-card",
    name: "Pillbox",
    description: "People with their open intakes and packs with stock and coverage.",
  });
}
