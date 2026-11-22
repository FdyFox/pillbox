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
 *   stock_buttons: false      # show -/+ buttons next to the stock of each pack
 *   stock_step: 1             # tablets per -/+ press (0.25 steps, e.g. 0.5 for halves)
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
    asNeeded: "as needed",
    stock: "Stock",
    daysLeft: "Lasts",
    days: "days",
    day: "day",
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
    e_stock_buttons: "Show −/+ buttons for the stock",
    e_stock_step: "Tablets per −/+ press",
    editStock: "Set stock",
    stockTablets: "Stock (tablets)",
    save: "Save",
    cancel: "Cancel",
    h_stock_buttons: "Adjust the stock by hand, e.g. after dropping a tablet or a partial refill",
    remove: "Remove",
    add: "Add",
    h_people_select: "Empty = all people, alphabetically",
    h_packs_select: "Empty = all packs",
    // intake card
    i_title: "Take intake",
    i_undo: "Undo",
    i_tablet: "tablet",
    i_tablets: "tablets",
    i_dose: "Dose",
    i_taken: "taken",
    i_none: "No intakes found.",
    i_no_person: "No person",
    e_hide_done: "Hide intakes already taken",
    e_hide_as_needed: "Hide \"as needed\" intakes",
    e_buttons: "Dose buttons (tablets)",
    h_buttons: "One button per amount, e.g. 0.5 and 0.75. Type in your own values. Empty = just 1.",
    e_intake_packs: "Only these medications",
  },
  de: {
    title: "Pillbox",
    people: "Personen",
    packs: "Packungen",
    takeNow: "Jetzt einnehmen",
    allDone: "Heute alles erledigt",
    next: "Als Nächstes",
    asNeeded: "bei Bedarf",
    stock: "Vorrat",
    daysLeft: "Reicht noch",
    days: "Tage",
    day: "Tag",
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
    e_stock_buttons: "Knöpfe −/+ für den Vorrat anzeigen",
    e_stock_step: "Tabletten pro Druck auf −/+",
    editStock: "Vorrat ändern",
    stockTablets: "Vorrat (Tabletten)",
    save: "Speichern",
    cancel: "Abbrechen",
    h_stock_buttons: "Vorrat von Hand anpassen, z. B. nach einer verlorenen Tablette oder einer Teilpackung",
    remove: "Abziehen",
    add: "Hinzufügen",
    h_people_select: "Leer = alle Personen, alphabetisch",
    h_packs_select: "Leer = alle Packungen",
    // intake card
    i_title: "Einnahme",
    i_undo: "Rückgängig",
    i_tablet: "Tablette",
    i_tablets: "Tabletten",
    i_dose: "Dosis",
    i_taken: "genommen",
    i_none: "Keine Einnahmen gefunden.",
    i_no_person: "Ohne Person",
    e_hide_done: "Bereits genommene ausblenden",
    e_hide_as_needed: "Einnahmen „bei Bedarf“ ausblenden",
    e_buttons: "Dosis-Knöpfe (Tabletten)",
    h_buttons: "Ein Knopf pro Menge, z. B. 0,5 und 0,75. Eigene Werte eintippen. Leer = nur 1.",
    e_intake_packs: "Nur diese Medikamente",
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
    stock_step: 1,
    ...c,
  };
};

/** Tablet amounts with fractions: 24.5 -> "24½", 0.25 -> "¼". Other values stay as they are. */
const FRACTIONS = { 0.25: "¼", 0.5: "½", 0.75: "¾" };
const formatAmount = (value) => {
  const n = Number(value);
  if (value === null || value === undefined || value === "" || !Number.isFinite(n)) return String(value ?? "");
  const whole = Math.floor(n);
  const fraction = FRACTIONS[Math.round((n - whole) * 10000) / 10000];
  if (fraction) return `${whole || ""}${fraction}`;
  return String(Math.round(n * 10000) / 10000);
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
    if (!this._dialogOpen) this._render(); // re-rendering would remove the open stock dialog
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
            { name: "stock_buttons", selector: bool },
            { name: "stock_step", selector: { number: { min: 0.25, max: 100, step: 0.25, mode: "box" } } },
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
          stock_buttons: t("e_stock_buttons"),
          stock_step: t("e_stock_step"),
        })[schema.name],
      computeHelper: (schema) =>
        ({ people: t("h_people_select"), packs: t("h_packs_select"), stock_buttons: t("h_stock_buttons") })[schema.name],
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
        stockEntity: stock.entity_id,
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
        const asNeeded = a.as_needed === true;
        const next = !done && !asNeeded && a.slot === person.nextSlot;
        const cls = ["chip", done ? "done" : "open", next ? "next" : "", asNeeded ? "as-needed" : ""].filter(Boolean).join(" ");
        const dose = a.dose !== undefined && Number(a.dose) !== 1 ? `<span class="dose">${escapeHtml(formatAmount(a.dose))}×</span>` : "";
        const title = asNeeded ? `${a.friendly_name} (${this._t("asNeeded")})` : a.friendly_name;
        return `<button class="${cls}" data-toggle="${escapeHtml(i.entity_id)}" title="${escapeHtml(title)}">
            <span class="mark">${done ? "✓" : ""}</span>
            <span class="slot">${escapeHtml(a.slot)}</span>
            ${dose}<span class="med">${escapeHtml(a.medication)}</span>
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
    // Fixed, right-aligned columns so the values line up across rows.
    const column = (key, title, value) =>
      hidden.has(key) ? "" : `<span class="value col-${key}" title="${title}">${value}</span>`;
    const step = this._step();
    const adjust = (delta, label, symbol) =>
      `<button class="adj" data-adjust="${escapeHtml(pack.stockEntity)}" data-delta="${delta}" title="${label} (${step})" aria-label="${label} ${step}">${symbol}</button>`;
    const stock = this._config.stock_buttons
      ? `<span class="stock">${adjust(-step, this._t("remove"), "−")}<span class="value col-stock" title="${this._t("stock")}">${escapeHtml(formatAmount(pack.stock))}</span>${adjust(step, this._t("add"), "+")}</span>`
      : column("stock", this._t("stock"), escapeHtml(formatAmount(pack.stock)));
    // Packs taken only as needed have no days left ("unknown").
    const daysLeft = Number(pack.daysLeft);
    const days =
      Number.isFinite(daysLeft) && pack.daysLeft !== ""
        ? `${escapeHtml(pack.daysLeft)} ${this._t(daysLeft === 1 ? "day" : "days")}`
        : "–";
    return `<div class="pack ${pack.low ? "low" : ""}">
        <span class="name"><button class="link" data-edit="${escapeHtml(pack.stockEntity)}" data-name="${escapeHtml(pack.name)}" title="${this._t("editStock")}">${escapeHtml(pack.name)}</button>${pack.low ? ` <span class="badge">${this._t("low")}</span>` : ""}</span>
        ${stock}
        ${column("days_left", this._t("daysLeft"), days)}
        ${column("runs_out", this._t("until"), this._formatDate(pack.runsOut))}
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

  _step() {
    const step = Math.round(Number(this._config.stock_step) * 4) / 4; // quarters
    return Number.isFinite(step) && step >= 0.25 ? step : 1;
  }

  _onClick(ev) {
    const target = ev.target.closest ? ev.target.closest("[data-toggle],[data-press],[data-adjust],[data-edit]") : null;
    if (!target) return;
    if (target.dataset.edit) {
      this._openStockDialog(target.dataset.edit, target.dataset.name);
    } else if (target.dataset.adjust) {
      const entityId = target.dataset.adjust;
      const current = Number(this._hass.states[entityId]?.state);
      if (!Number.isFinite(current)) return;
      const value = Math.round(Math.min(10000, Math.max(0, current + Number(target.dataset.delta))) * 10000) / 10000;
      if (value !== current) this._hass.callService("number", "set_value", { entity_id: entityId, value });
    } else if (target.dataset.toggle) {
      this._hass.callService("switch", "toggle", { entity_id: target.dataset.toggle });
    } else if (target.dataset.press) {
      this._hass.callService("button", "press", { entity_id: target.dataset.press });
    }
  }

  /** Popup for typing in the stock of a pack (tap on the pack's name). */
  _openStockDialog(entityId, name) {
    const current = this._hass.states[entityId]?.state;
    if (typeof document === "undefined" || !this.shadowRoot?.appendChild) {
      this._editing = { entityId, name, value: current }; // no DOM (tests)
      return;
    }
    const dialog = document.createElement("dialog");
    dialog.className = "stock-dialog";
    dialog.innerHTML = `<form>
        <h2>${escapeHtml(name)}</h2>
        <label>${this._t("stockTablets")}
          <input type="number" name="stock" min="0" max="10000" step="0.25" inputmode="decimal" required value="${escapeHtml(current)}">
        </label>
        <div class="dialog-buttons">
          <button type="button" class="secondary" data-cancel>${this._t("cancel")}</button>
          <button type="submit" class="action">${this._t("save")}</button>
        </div>
      </form>`;
    const close = () => dialog.close();
    dialog.querySelector("[data-cancel]").addEventListener("click", close);
    dialog.querySelector("form").addEventListener("submit", (ev) => {
      ev.preventDefault();
      if (this._saveStock(entityId, dialog.querySelector("input").value)) close();
    });
    dialog.addEventListener("close", () => {
      dialog.remove();
      this._dialogOpen = false;
      this._render();
    });
    this.shadowRoot.appendChild(dialog);
    this._dialogOpen = true;
    dialog.showModal();
    const input = dialog.querySelector("input");
    input.focus();
    input.select();
  }

  /** Set the stock from typed text ("12,5" or "12.5"); false if it is not a valid amount. */
  _saveStock(entityId, text) {
    const value = Math.round(Number(String(text).trim().replace(",", ".")) * 10000) / 10000;
    if (String(text).trim() === "" || !Number.isFinite(value) || value < 0 || value > 10000) return false;
    if (value !== Number(this._hass.states[entityId]?.state)) {
      this._hass.callService("number", "set_value", { entity_id: entityId, value });
    }
    return true;
  }

  static get styles() {
    return `
      .content { padding: 0 16px 16px; }
      .link { border: none; background: none; padding: 0; color: inherit; font: inherit; font-weight: 500; text-align: left; cursor: pointer; }
      .link:hover { text-decoration: underline; }
      .stock-dialog { border: none; border-radius: var(--ha-card-border-radius, 12px); padding: 20px 24px; min-width: min(280px, 80vw); background: var(--card-background-color, #fff); color: var(--primary-text-color); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4); }
      .stock-dialog::backdrop { background: rgba(0, 0, 0, 0.5); }
      .stock-dialog h2 { margin: 0 0 16px; font-size: 1.2em; font-weight: 500; }
      .stock-dialog label { display: flex; flex-direction: column; gap: 6px; color: var(--secondary-text-color); font-size: 0.9em; }
      .stock-dialog input { font: inherit; font-size: 1.2em; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--secondary-background-color, transparent); color: var(--primary-text-color); }
      .dialog-buttons { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
      .secondary { border: 1px solid var(--divider-color); border-radius: 16px; padding: 3px 12px; background: none; color: var(--primary-text-color); cursor: pointer; }
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
      .chip.as-needed { border-style: dashed; }
      .chip.as-needed.done { border-style: solid; }
      .chip .dose { font-variant-numeric: tabular-nums; font-weight: 500; }
      .action { border: none; border-radius: 16px; padding: 4px 12px; background: var(--primary-color); color: var(--text-primary-color, #fff); }
      /* One line per pack: the name column shrinks and wraps (badge below the name), the value columns never move. */
      .pack { display: grid; grid-template-columns: minmax(0, 1fr); grid-auto-flow: column; grid-auto-columns: auto; align-items: center; column-gap: 12px; padding: 6px 0; border-bottom: 1px solid var(--divider-color); }
      .pack .name { min-width: 0; overflow-wrap: anywhere; }
      .pack:last-of-type { border-bottom: none; }
      .pack .value { color: var(--secondary-text-color); font-variant-numeric: tabular-nums; text-align: right; }
      .pack .col-stock { min-width: 2.2em; }
      .pack .stock .col-stock { text-align: center; }
      .pack .col-days_left { min-width: 4.8em; }
      .pack .col-runs_out { min-width: 4.6em; }
      .pack.low .name, .pack.low .value { color: var(--error-color, #db4437); }
      .stock { display: inline-flex; align-items: center; gap: 4px; }
      .adj { width: 28px; height: 28px; border-radius: 50%; border: 1px solid var(--divider-color); background: none; color: var(--primary-text-color); line-height: 1; padding: 0; }
      .adj:hover { border-color: var(--primary-color); }
      .pack .name .badge { display: inline-block; margin-left: 6px; font-weight: normal; vertical-align: middle; white-space: nowrap; }
      .badge { font-size: 0.8em; border-radius: 10px; padding: 2px 8px; background: var(--error-color, #db4437); color: var(--text-primary-color, #fff); }
      .empty { color: var(--secondary-text-color); }
    `;
  }
}

/*
 * Pillbox intake card: check off an intake with the amount actually taken, by one dose button per amount.
 * The amount only applies to today; the stock drops by it, "Undo" puts exactly it back.
 * Tapping another button on an intake already taken corrects the amount.
 *
 *   type: custom:pillbox-intake-card
 *   title: Take intake
 *   buttons: [0.25, 0.5, 0.75, 1]   # dose buttons in tablets (default: [1])
 *   people: [<device_id>]           # only intakes of these people (default: all)
 *   packs: [<device_id>]            # only intakes of these packs (default: all)
 *   hide_done: false                # hide intakes already taken today
 *   hide_as_needed: false           # hide "as needed" intakes
 */
const DEFAULT_BUTTONS = [1];
const BUTTON_CHOICES = [0.25, 0.5, 0.75, 1, 1.5, 2];

/** Dose buttons from the config: numbers or texts like "0,75"; positive, unique, ascending. */
const parseButtons = (value) => {
  const list = (Array.isArray(value) ? value : value === undefined || value === null ? [] : [value])
    .map((v) => Math.round(Number(String(v).replace(",", ".")) * 10000) / 10000)
    .filter((v) => Number.isFinite(v) && v > 0 && v <= 100);
  const unique = [...new Set(list)].sort((a, b) => a - b);
  return unique.length ? unique : DEFAULT_BUTTONS;
};

class PillboxIntakeCard extends HTMLElement {
  setConfig(config) {
    this._config = { people: [], packs: [], ...(config || {}) };
    this._buttons = parseButtons(this._config.buttons);
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 3;
  }

  static getStubConfig() {
    return {};
  }

  static getConfigForm() {
    const t = (key) => tr(key);
    const devices = (model) => ({ device: { multiple: true, filter: { integration: "pillbox", model } } });
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        {
          name: "buttons",
          selector: {
            select: {
              multiple: true,
              custom_value: true,
              mode: "dropdown",
              options: BUTTON_CHOICES.map((v) => ({ value: String(v), label: formatAmount(v) })),
            },
          },
        },
        { name: "people", selector: devices("Person") },
        { name: "packs", selector: devices("Medikament") },
        { name: "hide_done", selector: { boolean: {} } },
        { name: "hide_as_needed", selector: { boolean: {} } },
      ],
      computeLabel: (schema) =>
        ({
          title: t("e_title"),
          buttons: t("e_buttons"),
          people: t("e_people_select"),
          packs: t("e_intake_packs"),
          hide_done: t("e_hide_done"),
          hide_as_needed: t("e_hide_as_needed"),
        })[schema.name],
      computeHelper: (schema) =>
        ({ buttons: t("h_buttons"), people: t("h_people_select"), packs: t("h_packs_select") })[schema.name],
    };
  }

  _t(key) {
    const lang = (this._hass?.locale?.language || this._hass?.language || "en").split("-")[0];
    return tr(key, lang);
  }

  /** Intake switches of Pillbox (they carry the attribute "dose"), filtered by the card options. */
  _intakes() {
    const hass = this._hass;
    const c = this._config;
    const devices = hass.devices || {};
    const packNames = new Set((c.packs || []).map((id) => devices[id]?.name).filter(Boolean));
    const result = [];
    for (const [entityId, entry] of Object.entries(hass.entities || {})) {
      if (entry.platform !== "pillbox" || !entityId.startsWith("switch.")) continue;
      const state = hass.states[entityId];
      const a = state?.attributes;
      if (!a || a.dose === undefined) continue;
      if (c.people?.length && !c.people.includes(entry.device_id)) continue;
      if (c.packs?.length && !c.packs.includes(entry.device_id) && !packNames.has(a.medication)) continue;
      const done = state.state === "on";
      if (c.hide_done && done) continue;
      if (c.hide_as_needed && a.as_needed) continue;
      result.push({ entityId, a, done });
    }
    return result.sort(
      (x, y) =>
        String(x.a.person ?? "").localeCompare(String(y.a.person ?? "")) ||
        Number(x.a.slot_id) - Number(y.a.slot_id) ||
        String(x.a.medication).localeCompare(String(y.a.medication))
    );
  }

  _renderIntake(intake, grouped = false) {
    const { entityId, a, done } = intake;
    const id = escapeHtml(entityId);
    const taken = Number(a.taken_amount);
    // Medication first; person and time of day are often the same for every row (e.g. in the card title).
    // In a group the person is in the heading already.
    const details = [a.person && !grouped ? `${escapeHtml(a.person)} · ${escapeHtml(a.slot)}` : escapeHtml(a.slot)];
    details.push(`${this._t("i_dose")} ${escapeHtml(formatAmount(a.dose))}`);
    if (a.as_needed) details.push(this._t("asNeeded"));
    if (done) details.push(`✓ ${escapeHtml(formatAmount(taken))} ${this._t("i_taken")}`);
    const buttons = this._buttons
      .map((amount) => {
        const current = done && amount === taken;
        const label = `${formatAmount(amount)} ${this._t(amount === 1 ? "i_tablet" : "i_tablets")}`;
        return `<button class="dose ${current ? "current" : ""}" data-take="${id}" data-value="${amount}" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}">${escapeHtml(formatAmount(amount))}</button>`;
      })
      .join("");
    const undo = done ? `<button class="secondary" data-undo="${id}">${this._t("i_undo")}</button>` : "";
    return `<div class="intake ${done ? "done" : ""} ${a.as_needed ? "as-needed" : ""}">
        <div class="info">
          <span class="name">${escapeHtml(a.medication)}</span>
          <span class="details">${details.join(" · ")}</span>
        </div>
        <span class="doses">${buttons}</span>
        ${undo}
      </div>`;
  }

  _render() {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    }
    const intakes = this._intakes();
    // Several people -> one section per person (intakes are sorted by person already).
    const groups = [];
    for (const intake of intakes) {
      const person = intake.a.person ?? null;
      if (!groups.length || groups[groups.length - 1].person !== person) groups.push({ person, intakes: [] });
      groups[groups.length - 1].intakes.push(intake);
    }
    let body = `<p class="empty">${this._t("i_none")}</p>`;
    if (groups.length > 1) {
      body = groups
        .map(
          (g) => `<section class="group">
            <h3>${escapeHtml(g.person ?? this._t("i_no_person"))}</h3>
            ${g.intakes.map((i) => this._renderIntake(i, g.person !== null)).join("")}
          </section>`
        )
        .join("");
    } else if (intakes.length) {
      body = intakes.map((i) => this._renderIntake(i)).join("");
    }
    this.shadowRoot.innerHTML = `<style>${PillboxIntakeCard.styles}</style>
      <ha-card header="${escapeHtml(this._config.title ?? this._t("i_title"))}"><div class="content">${body}</div></ha-card>`;
  }

  _onClick(ev) {
    const target = ev.target.closest ? ev.target.closest("[data-take],[data-undo]") : null;
    if (!target) return;
    if (target.dataset.take) {
      const amount = Number(target.dataset.value);
      if (!Number.isFinite(amount) || amount <= 0) return;
      this._hass.callService("pillbox", "take_intake", { entity_id: target.dataset.take, amount });
    } else if (target.dataset.undo) {
      this._hass.callService("switch", "turn_off", { entity_id: target.dataset.undo });
    }
  }

  static get styles() {
    return `
      .content { padding: 0 16px 16px; }
      button { font: inherit; cursor: pointer; }
      .intake { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px 0; border-bottom: 1px solid var(--divider-color); }
      .intake:last-of-type { border-bottom: none; }
      /* One block per person: tinted box, name with an accent bar, space between the blocks. */
      .group { background: var(--secondary-background-color, rgba(127, 127, 127, 0.08)); border-radius: 12px; padding: 10px 12px 4px; }
      .group + .group { margin-top: 12px; }
      h3 { margin: 0 0 2px; padding-left: 8px; border-left: 3px solid var(--primary-color); font-size: 1.05em; font-weight: 600; color: var(--primary-text-color); line-height: 1.3; }
      .info { display: flex; flex-direction: column; flex: 1 1 10em; min-width: 0; }
      .name { font-weight: 500; }
      .details { color: var(--secondary-text-color); font-size: 0.85em; }
      .intake.done .details { color: var(--success-color, #43a047); }
      .doses { display: inline-flex; flex-wrap: wrap; gap: 6px; }
      .dose { min-width: 40px; height: 32px; border-radius: 16px; border: none; padding: 0 10px; background: var(--primary-color); color: var(--text-primary-color, #fff); font-variant-numeric: tabular-nums; font-weight: 500; }
      .intake.done .dose { background: none; border: 1px solid var(--divider-color); color: var(--primary-text-color); }
      .intake.done .dose.current { background: var(--success-color, #43a047); border-color: transparent; color: var(--text-primary-color, #fff); }
      .secondary { border: 1px solid var(--divider-color); border-radius: 16px; padding: 3px 12px; background: none; color: var(--primary-text-color); }
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

if (!customElements.get("pillbox-intake-card")) {
  customElements.define("pillbox-intake-card", PillboxIntakeCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "pillbox-intake-card",
    name: "Pillbox intake",
    description: "Check off an intake with the amount actually taken, e.g. 0.75 instead of 1.",
  });
}
