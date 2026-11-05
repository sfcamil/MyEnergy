// MyEnergy offers card - shipped with the myenergy integration, no manual resource needed.
const CARD_TYPE = "myenergy-offers-card";

const TEXTS = {
  fr: { fixed: "Contrats fixes", variable: "Contrats variables", provider: "Fournisseur", product: "Produit",
        year: "€/an", own: "Votre contrat", ownBest: "Meilleure offre", savings: "Économie possible",
        perYear: "€/an", cheaper: "Votre contrat est déjà moins cher de", source: "Source", updated: "mis à jour", none: "Aucune offre disponible",
        notFound: "Aucun capteur MyEnergy avec des offres trouvé." },
  nl: { fixed: "Vaste contracten", variable: "Variabele contracten", provider: "Leverancier", product: "Product",
        year: "€/jaar", own: "Uw contract", ownBest: "Beste aanbod", savings: "Mogelijke besparing",
        perYear: "€/jaar", cheaper: "Uw contract is al goedkoper met", source: "Bron", updated: "bijgewerkt", none: "Geen aanbiedingen beschikbaar",
        notFound: "Geen MyEnergy-sensor met aanbiedingen gevonden." },
  en: { fixed: "Fixed contracts", variable: "Variable contracts", provider: "Provider", product: "Product",
        year: "€/year", own: "Your contract", ownBest: "Best offer", savings: "Possible savings",
        perYear: "€/year", cheaper: "Your contract is already cheaper by", source: "Source", updated: "updated", none: "No offers available",
        notFound: "No MyEnergy sensor with offers found." },
};

function findOfferSensors(hass) {
  return Object.keys(hass.states)
    .filter((id) => id.startsWith("sensor.") && Array.isArray(hass.states[id].attributes.offers))
    .sort();
}

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

class MyEnergyOffersCard extends HTMLElement {
  static getStubConfig(hass) {
    return { entities: hass ? findOfferSensors(hass) : [], max_offers: 10 };
  }

  setConfig(config) {
    this._config = { max_offers: 10, ...config };
  }

  getCardSize() {
    return 2 + this._entities().length * ((this._config.max_offers || 10) + 3);
  }

  _entities() {
    if (!this._hass) return [];
    const configured = this._config.entities;
    return Array.isArray(configured) && configured.length ? configured : findOfferSensors(this._hass);
  }

  set hass(hass) {
    const previous = this._hass;
    this._hass = hass;
    const ids = this._entities();
    if (previous && ids.every((id) => previous.states[id] === hass.states[id])) return;
    this._render();
  }

  _t() {
    const lang = (this._hass?.locale?.language || this._hass?.language || "en").slice(0, 2);
    return TEXTS[lang] || TEXTS.en;
  }

  _fmt(value, digits) {
    const lang = this._hass?.locale?.language || "fr-BE";
    return typeof value === "number"
      ? value.toLocaleString(lang, { minimumFractionDigits: digits, maximumFractionDigits: digits })
      : "–";
  }

  _section(entityId, t) {
    const stateObj = this._hass.states[entityId];
    if (!stateObj) return `<div class="warn">${esc(entityId)} ?</div>`;
    const a = stateObj.attributes;
    const offers = (a.offers || []).slice(0, this._config.max_offers || 10);
    const own = a["current provider offer"];
    const title = this._config.titles?.[entityId]
      || ((a["contract type"] || "").toLowerCase() === "fixed" ? t.fixed : t.variable);
    const isOwn = (o) => own && o.provider === own.provider && o.product === own.product;
    const rows = offers.map((o, i) => `
      <tr class="${i === 0 ? "best" : ""} ${isOwn(o) ? "own" : ""}">
        <td>${i + 1}</td>
        <td>${esc(o.provider)}</td>
        <td><a href="${esc(o.url)}" target="_blank" rel="noopener">${esc(o.product)}</a></td>
        <td class="num">${this._fmt(o.price_kwh, 4)}</td>
        <td class="num">${this._fmt(o.price_year, 0)}</td>
      </tr>`).join("");
    const savings = a["savings per year"];
    const ownLine = own ? `
      <div class="own-line">
        ${t.own} : <b>${esc(own.provider)} – ${esc(own.product)}</b> : ${this._fmt(own.price_kwh, 4)} €/kWh
        (${this._fmt(own.price_year, 0)} ${t.perYear})
        ${typeof savings === "number" && savings > 0
          ? ` → ${t.savings} <b class="save">${this._fmt(savings, 0)} ${t.perYear}</b>` : ""}
        ${typeof savings === "number" && savings < 0
          ? ` → ${t.cheaper} <b class="save">${this._fmt(-savings, 0)} ${t.perYear}</b>` : ""}
      </div>` : "";
    return `
      <h3>${esc(title)}</h3>
      ${offers.length ? `
      <table>
        <thead><tr><th>#</th><th>${t.provider}</th><th>${t.product}</th><th class="num">€/kWh</th><th class="num">${t.year}</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>` : `<div class="warn">${t.none}</div>`}
      ${ownLine}`;
  }

  _render() {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const t = this._t();
    const ids = this._entities();
    const first = ids.length ? this._hass.states[ids[0]] : undefined;
    const updated = first?.attributes["last update"]
      ? new Date(first.attributes["last update"]).toLocaleString(this._hass?.locale?.language || "fr-BE",
          { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
      : "";
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 12px 16px 8px; }
        h3 { margin: 12px 0 6px; font-size: 1.05em; }
        h3:first-of-type { margin-top: 0; }
        table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
        th, td { padding: 4px 6px; text-align: left; border-bottom: 1px solid var(--divider-color); }
        th { color: var(--secondary-text-color); font-weight: 500; }
        .num { text-align: right; white-space: nowrap; }
        tr.best td { font-weight: 600; color: var(--success-color, #43a047); }
        tr.own td { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.12); }
        a { color: var(--primary-color); text-decoration: none; }
        .own-line { margin: 6px 0 4px; font-size: 0.9em; }
        .save { color: var(--success-color, #43a047); }
        .warn { color: var(--secondary-text-color); font-style: italic; padding: 4px 0; }
        .footer { margin-top: 8px; font-size: 0.75em; color: var(--secondary-text-color); }
      </style>
      <ha-card header="${esc(this._config.title || "")}">
        ${ids.length ? ids.map((id) => this._section(id, t)).join("") : `<div class="warn">${t.notFound}</div>`}
        <div class="footer">${t.source} : <a href="https://www.compacwape.be/" target="_blank" rel="noopener">compacwape.be</a>${updated ? ` – ${t.updated} ${esc(updated)}` : ""}</div>
      </ha-card>`;
  }
}

if (!customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, MyEnergyOffersCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_TYPE,
    name: "MyEnergy offers",
    description: "Compare energy offers from the MyEnergy integration (top offers, your contract, possible savings).",
    preview: true,
  });
}
