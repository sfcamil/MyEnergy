// Carte « Offres MyEnergy » : livrée avec l'intégration myenergy, aucune ressource à ajouter à la main.
const TYPE_CARTE = "myenergy-offers-card";

function capteursAvecOffres(hass) {
  return Object.keys(hass.states)
    .filter((id) => id.startsWith("sensor.") && Array.isArray(hass.states[id].attributes.offres))
    .sort();
}

const echapper = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

class CarteOffresMyEnergy extends HTMLElement {
  static getStubConfig(hass) {
    return { entities: hass ? capteursAvecOffres(hass) : [], max_offers: 10 };
  }

  setConfig(config) {
    this._config = { max_offers: 10, ...config };
  }

  getCardSize() {
    return 2 + this._entites().length * ((this._config.max_offers || 10) + 3);
  }

  _entites() {
    if (!this._hass) return [];
    const configurees = this._config.entities;
    return Array.isArray(configurees) && configurees.length ? configurees : capteursAvecOffres(this._hass);
  }

  set hass(hass) {
    const precedent = this._hass;
    this._hass = hass;
    if (precedent && this._entites().every((id) => precedent.states[id] === hass.states[id])) return;
    this._afficher();
  }

  _nombre(valeur, decimales) {
    return typeof valeur === "number"
      ? valeur.toLocaleString("fr-BE", { minimumFractionDigits: decimales, maximumFractionDigits: decimales })
      : "–";
  }

  _section(idEntite) {
    const etat = this._hass.states[idEntite];
    if (!etat) return `<div class="info">Entité introuvable : ${echapper(idEntite)}</div>`;
    const a = etat.attributes;
    const offres = (a.offres || []).slice(0, this._config.max_offers || 10);
    const contrat = a["votre contrat"];
    const economie = a["économie par an"];
    const titre = this._config.titles?.[idEntite]
      || `${a["énergie"] || ""} – contrats ${(a["type de contrat"] || "").toLowerCase() === "fixe" ? "fixes" : "variables"}`;
    const estLeContrat = (o) => contrat && o.fournisseur === contrat.fournisseur && o.produit === contrat.produit;
    const lignes = offres.map((o, i) => `
      <tr class="${i === 0 ? "meilleure" : ""} ${estLeContrat(o) ? "contrat" : ""}">
        <td>${i + 1}</td>
        <td>${echapper(o.fournisseur)}</td>
        <td><a href="${echapper(o.url)}" target="_blank" rel="noopener">${echapper(o.produit)}</a></td>
        <td class="num">${this._nombre(o.prix_kwh, 4)}</td>
        <td class="num">${this._nombre(o.prix_an, 0)}</td>
      </tr>`).join("");
    let comparaison = "";
    if (typeof economie === "number" && economie > 0) {
      comparaison = ` → économie possible <b class="vert">${this._nombre(economie, 0)} €/an</b>`;
    } else if (typeof economie === "number" && economie < 0) {
      comparaison = ` → votre contrat est déjà moins cher de <b class="vert">${this._nombre(-economie, 0)} €/an</b>`;
    }
    const ligneContrat = contrat ? `
      <div class="ligne-contrat">
        Votre contrat : <b>${echapper(contrat.fournisseur)} – ${echapper(contrat.produit)}</b> :
        ${this._nombre(contrat.prix_kwh, 4)} €/kWh (${this._nombre(contrat.prix_an, 0)} €/an)${comparaison}
      </div>` : "";
    const prixEnergie = a["prix énergie (€/kWh)"];
    const prixReseau = a["prix réseau et taxes (€/kWh)"];
    const ligneDetail = typeof prixEnergie === "number" && typeof prixReseau === "number" ? `
      <div class="ligne-detail">
        Meilleure offre : énergie ${this._nombre(prixEnergie, 4)} + réseau et taxes ${this._nombre(prixReseau, 4)}
        = ${this._nombre(prixEnergie + prixReseau, 4)} €/kWh
      </div>` : "";
    return `
      <h3>${echapper(titre)}</h3>
      ${offres.length ? `
      <table>
        <thead><tr><th>#</th><th>Fournisseur</th><th>Produit</th><th class="num">€/kWh</th><th class="num">€/an</th></tr></thead>
        <tbody>${lignes}</tbody>
      </table>` : `<div class="info">Aucune offre disponible pour le moment.</div>`}
      ${ligneDetail}
      ${ligneContrat}`;
  }

  _afficher() {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const ids = this._entites();
    const premier = ids.length ? this._hass.states[ids[0]] : undefined;
    const miseAJour = premier?.attributes["mise à jour"]
      ? new Date(premier.attributes["mise à jour"]).toLocaleString("fr-BE",
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
        tr.meilleure td { font-weight: 600; color: var(--success-color, #43a047); }
        tr.contrat td { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.12); }
        a { color: var(--primary-color); text-decoration: none; }
        .ligne-contrat { margin: 6px 0 4px; font-size: 0.9em; }
        .ligne-detail { margin: 6px 0 0; font-size: 0.85em; color: var(--secondary-text-color); }
        .vert { color: var(--success-color, #43a047); }
        .info { color: var(--secondary-text-color); font-style: italic; padding: 4px 0; }
        .pied { margin-top: 8px; font-size: 0.75em; color: var(--secondary-text-color); }
      </style>
      <ha-card header="${echapper(this._config.title || "")}">
        ${ids.length ? ids.map((id) => this._section(id)).join("") : `<div class="info">Aucun capteur MyEnergy avec des offres trouvé.</div>`}
        <div class="pied">Source : <a href="https://www.compacwape.be/" target="_blank" rel="noopener">comparateur CWaPE</a>
          – prix TVA et frais de réseau compris${miseAJour ? ` – mis à jour le ${echapper(miseAJour)}` : ""}</div>
      </ha-card>`;
  }
}

if (!customElements.get(TYPE_CARTE)) {
  customElements.define(TYPE_CARTE, CarteOffresMyEnergy);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: TYPE_CARTE,
    name: "Offres MyEnergy",
    description: "Compare les offres d'énergie (meilleures offres, votre contrat, économie possible).",
    preview: true,
  });
}
