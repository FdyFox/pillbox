/*
 * Pillbox card: overview of people (open intakes today) and packs (stock, coverage).
 * Served by the integration itself and registered automatically, no build step.
 *
 *   type: custom:pillbox-card
 *   title: Pillbox          # optional
 *   show_people: true       # optional
 *   show_packs: true        # optional
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
  },
};

const escapeHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

class PillboxCard extends HTMLElement {
  setConfig(config) {
    this._config = { show_people: true, show_packs: true, ...(config || {}) };
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

  _t(key) {
    const lang = (this._hass?.locale?.language || this._hass?.language || "en").split("-")[0];
    return (STRINGS[lang] || STRINGS.en)[key];
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
        name: this._deviceName(deviceId, open.state.attributes.friendly_name),
        nextSlot: open.state.attributes.next_slot,
        intakes,
        takeNow: entities.find((e) => e.domain === "button"),
      });
    }
    return people.sort((a, b) => a.name.localeCompare(b.name));
  }

  _packs(byDevice) {
    const packs = [];
    for (const [deviceId, entities] of Object.entries(byDevice)) {
      const stock = entities.find((e) => e.domain === "number");
      if (!stock) continue;
      const sensor = (deviceClass) =>
        entities.find((e) => e.domain === "sensor" && e.state.attributes.device_class === deviceClass);
      packs.push({
        name: this._deviceName(deviceId, stock.state.attributes.friendly_name),
        stock: stock.state.state,
        daysLeft: sensor("duration")?.state.state,
        runsOut: sensor("date")?.state.state,
        low: entities.some(
          (e) => e.domain === "binary_sensor" && e.state.attributes.device_class === "problem" && e.state.state === "on"
        ),
      });
    }
    return packs.sort((a, b) => a.name.localeCompare(b.name));
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
      person.takeNow && person.nextSlot
        ? `<button class="action" data-press="${escapeHtml(person.takeNow.entity_id)}">${this._t("takeNow")}</button>`
        : "";
    return `<div class="person">
        <div class="row"><span class="name">${escapeHtml(person.name)}</span><span class="status">${status}</span>${takeNow}</div>
        <div class="chips">${chips}</div>
      </div>`;
  }

  _renderPack(pack) {
    return `<div class="pack ${pack.low ? "low" : ""}">
        <span class="name">${escapeHtml(pack.name)}</span>
        <span class="value" title="${this._t("stock")}">${escapeHtml(pack.stock)}</span>
        <span class="value" title="${this._t("daysLeft")}">${escapeHtml(pack.daysLeft ?? "–")} ${this._t("days")}</span>
        <span class="value" title="${this._t("until")}">${this._formatDate(pack.runsOut)}</span>
        ${pack.low ? `<span class="badge">${this._t("low")}</span>` : ""}
      </div>`;
  }

  _render() {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    }
    const byDevice = this._collect();
    const people = this._config.show_people ? this._people(byDevice) : [];
    const packs = this._config.show_packs ? this._packs(byDevice) : [];
    const body =
      people.length || packs.length
        ? `${people.length ? `<h3>${this._t("people")}</h3>${people.map((p) => this._renderPerson(p)).join("")}` : ""}
           ${packs.length ? `<h3>${this._t("packs")}</h3>${packs.map((p) => this._renderPack(p)).join("")}` : ""}`
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
