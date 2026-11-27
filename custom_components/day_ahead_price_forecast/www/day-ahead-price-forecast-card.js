import {
  toPoints,
  cutForecast,
  yScale,
  linearScale,
  stepPath,
  bandPolygon,
  dayStats,
  nearestPoint,
} from "./chart-core.js";

const CARD_TAG = "day-ahead-price-forecast-card";
const EDITOR_TAG = "day-ahead-price-forecast-card-editor";

const LABELS = {
  en: {
    forecast: "forecast",
    known: "published",
    now: "now",
    day: "Day",
    average: "Average",
    cheapest: "Cheapest hour",
    expensive: "Most expensive hour",
    noData: "No data available",
    notFound: "Entity not found",
    entity: "Entity",
    forecastDays: "Forecast days (1-7)",
    description: "Chart of published and forecast day-ahead prices",
  },
  nl: {
    forecast: "verwachting",
    known: "gepubliceerd",
    now: "nu",
    day: "Dag",
    average: "Gemiddeld",
    cheapest: "Goedkoopste uur",
    expensive: "Duurste uur",
    noData: "Geen gegevens beschikbaar",
    notFound: "Entiteit niet gevonden",
    entity: "Entiteit",
    forecastDays: "Verwachtingsdagen (1-7)",
    description: "Grafiek van gepubliceerde en verwachte day-ahead-prijzen",
  },
};

const W = 600;
const H = 260;
const M = { top: 12, right: 12, bottom: 24, left: 48 };

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

function clampDays(v) {
  const n = Math.round(Number(v));
  if (!Number.isFinite(n)) return 7;
  return Math.min(7, Math.max(1, n));
}

class DayAheadPriceForecastCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  static getStubConfig(hass) {
    const entity = Object.keys((hass && hass.states) || {}).find(
      (id) => id.startsWith("sensor.") && hass.states[id].attributes && "forecast" in hass.states[id].attributes,
    );
    return { entity: entity || "", forecast_days: 7 };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._lastUpdated = null;
    this._model = null;
    this._timer = null;
    this._resize = new ResizeObserver(() => this._draw());
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error("entity is required");
    this._config = {
      show_table: true,
      ...config,
      forecast_days: clampDays(config.forecast_days ?? 7),
    };
    this._lastUpdated = null;
    this._update();
  }

  set hass(hass) {
    this._hass = hass;
    const st = this._config && hass.states[this._config.entity];
    const stamp = st ? st.last_updated : undefined;
    if (stamp !== this._lastUpdated || !this._model) {
      this._lastUpdated = stamp;
      this._update();
    }
  }

  getCardSize() {
    return this._config && this._config.show_table !== false ? 8 : 5;
  }

  connectedCallback() {
    this._resize.observe(this);
    this._timer = setInterval(() => this._updateNow(), 60000);
    this._draw();
  }

  disconnectedCallback() {
    this._resize.disconnect();
    clearInterval(this._timer);
    this._timer = null;
  }

  get _t() {
    const lang = ((this._hass && this._hass.locale && this._hass.locale.language) || "en").slice(0, 2);
    return LABELS[lang] || LABELS.en;
  }

  get _tz() {
    return (this._hass && this._hass.config && this._hass.config.time_zone) ||
      Intl.DateTimeFormat().resolvedOptions().timeZone;
  }

  get _locale() {
    return (this._hass && this._hass.locale && this._hass.locale.language) || "en";
  }

  _update() {
    if (!this._config || !this._hass) return;
    const st = this._hass.states[this._config.entity];
    if (!st) {
      this._model = { error: "notFound" };
    } else {
      const a = st.attributes || {};
      const known = toPoints(a.known);
      let forecast = toPoints(a.forecast);
      const knownUntil = Date.parse(a.known_until);
      const from = Number.isFinite(knownUntil)
        ? knownUntil
        : known.length
          ? known[known.length - 1].end
          : forecast.length
            ? forecast[0].start
            : null;
      if (from !== null) forecast = cutForecast(forecast, from, this._config.forecast_days, this._tz);
      forecast.forEach((p) => (p.isForecast = true));
      this._model = {
        known,
        forecast,
        unit: a.unit_of_measurement || "",
        all: [...known, ...forecast],
      };
    }
    this._draw();
  }

  _fmtValue(v) {
    return new Intl.NumberFormat(this._locale, { maximumFractionDigits: 4 }).format(v);
  }

  _fmtDateTime(ms) {
    return new Intl.DateTimeFormat(this._locale, {
      timeZone: this._tz,
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(ms));
  }

  _fmtTime(ms) {
    return new Intl.DateTimeFormat(this._locale, { timeZone: this._tz, hour: "2-digit", minute: "2-digit" }).format(
      new Date(ms),
    );
  }

  _fmtDay(ms) {
    return new Intl.DateTimeFormat(this._locale, {
      timeZone: this._tz,
      weekday: "short",
      day: "numeric",
      month: "short",
    }).format(new Date(ms));
  }

  _geometry() {
    const m = this._model;
    const width = Math.max(240, this.clientWidth || W);
    const height = H;
    const t0 = m.all[0].start;
    const t1 = m.all[m.all.length - 1].end;
    const ys = yScale(m.known, m.forecast);
    const x = linearScale(t0, t1, M.left, width - M.right);
    const y = linearScale(ys.min, ys.max, height - M.bottom, M.top);
    return { width, height, t0, t1, ys, x, y };
  }

  _draw() {
    const root = this.shadowRoot;
    if (!this._config) return;
    const t = this._t;
    const title = this._config.title ? `<div class="title">${esc(this._config.title)}</div>` : "";
    const style = `<style>
      :host { display: block; }
      ha-card { padding: 16px; }
      .title { font-size: 1.2em; margin-bottom: 8px; color: var(--primary-text-color); }
      .msg { color: var(--secondary-text-color); padding: 16px 0; }
      .wrap { position: relative; touch-action: pan-y; }
      svg { width: 100%; height: auto; display: block; }
      .grid { stroke: var(--divider-color); stroke-width: 1; }
      .axis { fill: var(--secondary-text-color); font-size: 11px; }
      .known { fill: none; stroke: var(--primary-color); stroke-width: 2; }
      .fc { fill: none; stroke: var(--primary-color); stroke-width: 2; stroke-dasharray: 5 4; }
      .band { fill: var(--primary-color); opacity: 0.18; stroke: none; }
      .now { stroke: var(--secondary-text-color); stroke-width: 1; stroke-dasharray: 2 3; }
      .hair { stroke: var(--primary-text-color); stroke-width: 1; }
      .tip { position: absolute; pointer-events: none; padding: 4px 8px; border-radius: 6px; font-size: 12px;
        background: var(--card-background-color, #fff); color: var(--primary-text-color);
        border: 1px solid var(--divider-color); box-shadow: 0 2px 6px rgba(0,0,0,.2); white-space: nowrap; }
      table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 0.9em; color: var(--primary-text-color); }
      th, td { text-align: right; padding: 4px 6px; border-bottom: 1px solid var(--divider-color); }
      th:first-child, td:first-child { text-align: left; }
      th { color: var(--secondary-text-color); font-weight: 500; }
      td small { color: var(--secondary-text-color); }
      .fcday td:first-child { font-style: italic; }
    </style>`;
    if (!this._model) {
      root.innerHTML = `${style}<ha-card>${title}<div class="msg">…</div></ha-card>`;
      return;
    }
    if (this._model.error || !this._model.all.length) {
      root.innerHTML = `${style}<ha-card>${title}<div class="msg">${t[this._model.error || "noData"]}</div></ha-card>`;
      return;
    }
    const g = this._geometry();
    this._g = g;
    const { known, forecast, unit } = this._model;
    const ticks = g.ys.ticks
      .map(
        (v) =>
          `<line class="grid" x1="${M.left}" x2="${g.width - M.right}" y1="${g.y(v)}" y2="${g.y(v)}"/>` +
          `<text class="axis" x="${M.left - 6}" y="${g.y(v) + 4}" text-anchor="end">${this._fmtValue(v)}</text>`,
      )
      .join("");
    const xt = this._xTicks(g)
      .map(
        (ms) =>
          `<line class="grid" x1="${g.x(ms)}" x2="${g.x(ms)}" y1="${M.top}" y2="${g.height - M.bottom}"/>` +
          `<text class="axis" x="${g.x(ms) + 3}" y="${g.height - 8}">${esc(this._fmtDay(ms))}</text>`,
      )
      .join("");
    root.innerHTML = `${style}<ha-card>${title}
      <div class="wrap">
        <svg viewBox="0 0 ${g.width} ${g.height}" role="img" aria-label="${esc(unit)}">
          ${ticks}${xt}
          <path class="band" d="${bandPolygon(forecast, g.x, g.y)}"/>
          <path class="known" d="${stepPath(known, g.x, g.y)}"/>
          <path class="fc" d="${stepPath(forecast, g.x, g.y)}"/>
          <line class="now" y1="${M.top}" y2="${g.height - M.bottom}" visibility="hidden"/>
          <line class="hair" y1="${M.top}" y2="${g.height - M.bottom}" visibility="hidden"/>
        </svg>
        <div class="tip" hidden></div>
      </div>
      ${this._config.show_table !== false ? this._table() : ""}
    </ha-card>`;
    const wrap = root.querySelector(".wrap");
    wrap.addEventListener("pointermove", (e) => this._onPointer(e));
    wrap.addEventListener("pointerleave", () => this._hideHover());
    wrap.addEventListener("pointerdown", (e) => this._onPointer(e));
    this._updateNow();
  }

  _xTicks(g) {
    // Local midnights inside the shown range.
    const out = [];
    let last = null;
    for (let ms = g.t0; ms <= g.t1; ms += 15 * 60 * 1000) {
      const key = new Intl.DateTimeFormat("en-CA", { timeZone: this._tz }).format(new Date(ms));
      if (key !== last) {
        if (last !== null) out.push(ms);
        last = key;
      }
    }
    return out;
  }

  _table() {
    const t = this._t;
    const rows = dayStats(this._model.all, this._tz)
      .map((d) => {
        const hour = (h) => (h ? `${this._fmtValue(h.value)} <small>${this._fmtTime(h.start)}</small>` : "–");
        return `<tr class="${d.forecast ? "fcday" : ""}"><td>${esc(this._fmtDay(d.start))}${
          d.forecast ? ` <small>(${t.forecast})</small>` : ""
        }</td><td>${this._fmtValue(d.average)}</td><td>${hour(d.cheapest)}</td><td>${hour(d.mostExpensive)}</td></tr>`;
      })
      .join("");
    return `<table><thead><tr><th>${t.day}</th><th>${t.average}</th><th>${t.cheapest}</th><th>${t.expensive}</th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  _updateNow() {
    const line = this.shadowRoot.querySelector(".now");
    if (!line || !this._g) return;
    const now = Date.now();
    if (now < this._g.t0 || now > this._g.t1) {
      line.setAttribute("visibility", "hidden");
      return;
    }
    const xx = this._g.x(now);
    line.setAttribute("x1", xx);
    line.setAttribute("x2", xx);
    line.setAttribute("visibility", "visible");
  }

  _onPointer(e) {
    if (!this._g || !this._model) return;
    const svg = this.shadowRoot.querySelector("svg");
    const rect = svg.getBoundingClientRect();
    const scale = this._g.width / rect.width;
    const px = (e.clientX - rect.left) * scale;
    const tms = this._g.t0 + ((px - M.left) / (this._g.width - M.left - M.right)) * (this._g.t1 - this._g.t0);
    const p = nearestPoint(this._model.all, tms);
    if (!p) return;
    const t = this._t;
    const xx = this._g.x(p.start);
    const hair = this.shadowRoot.querySelector(".hair");
    hair.setAttribute("x1", xx);
    hair.setAttribute("x2", xx);
    hair.setAttribute("visibility", "visible");
    const unit = this._model.unit;
    let text = `<b>${esc(this._fmtDateTime(p.start))}</b><br>${this._fmtValue(p.value)} ${esc(unit)}`;
    if (p.isForecast) {
      if (typeof p.p10 === "number" && typeof p.p90 === "number") {
        text += `<br>P10–P90: ${this._fmtValue(p.p10)} – ${this._fmtValue(p.p90)}`;
      }
      text += `<br><i>${t.forecast}</i>`;
    }
    const tip = this.shadowRoot.querySelector(".tip");
    tip.innerHTML = text;
    tip.hidden = false;
    const left = xx / scale;
    const flip = left > rect.width / 2;
    tip.style.left = flip ? "" : `${left + 8}px`;
    tip.style.right = flip ? `${rect.width - left + 8}px` : "";
    tip.style.top = `${M.top}px`;
  }

  _hideHover() {
    const hair = this.shadowRoot.querySelector(".hair");
    const tip = this.shadowRoot.querySelector(".tip");
    if (hair) hair.setAttribute("visibility", "hidden");
    if (tip) tip.hidden = true;
  }
}

class DayAheadPriceForecastCardEditor extends HTMLElement {
  constructor() {
    super();
    this._config = {};
    this._hass = null;
    this._built = false;
  }

  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass) return;
    const lang = ((this._hass.locale && this._hass.locale.language) || "en").slice(0, 2);
    const t = LABELS[lang] || LABELS.en;
    if (!this._built) {
      this._built = true;
      this.innerHTML = `<div style="display:flex;flex-direction:column;gap:16px">
        <ha-entity-picker allow-custom-entity></ha-entity-picker>
        <ha-textfield type="number" min="1" max="7" step="1" id="days"></ha-textfield>
      </div>`;
      this._picker = this.querySelector("ha-entity-picker");
      this._days = this.querySelector("#days");
      this._picker.addEventListener("value-changed", (e) => {
        e.stopPropagation();
        this._fire({ ...this._config, entity: e.detail.value });
      });
      this._days.addEventListener("change", () => {
        this._fire({ ...this._config, forecast_days: clampDays(this._days.value) });
      });
    }
    this._picker.hass = this._hass;
    this._picker.includeDomains = ["sensor"];
    this._picker.entityFilter = (st) => !!(st.attributes && "forecast" in st.attributes);
    this._picker.label = t.entity;
    this._picker.value = this._config.entity || "";
    this._days.label = t.forecastDays;
    this._days.value = String(this._config.forecast_days ?? 7);
  }

  _fire(config) {
    this._config = config;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, DayAheadPriceForecastCard);
if (!customElements.get(EDITOR_TAG)) customElements.define(EDITOR_TAG, DayAheadPriceForecastCardEditor);

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === CARD_TAG)) {
  window.customCards.push({
    type: CARD_TAG,
    name: "Day-ahead price forecast",
    description: LABELS.en.description,
    preview: false,
  });
}
