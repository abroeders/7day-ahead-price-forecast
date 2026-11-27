import {
  toPoints,
  cutForecast,
  yScale,
  linearScale,
  stepPath,
  bandPolygon,
  dayStats,
  nearestPoint,
  visibleSlice,
  clampView,
  zoomView,
  panView,
  xTicks,
  HOUR_MS,
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
    zoomIn: "Zoom in",
    zoomOut: "Zoom out",
    zoomReset: "Show full range",
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
    zoomIn: "Inzoomen",
    zoomOut: "Uitzoomen",
    zoomReset: "Hele periode tonen",
  },
};

const W = 600;
const H = 260;
const M = { top: 12, right: 12, bottom: 24, left: 48 };
const MIN_SPAN_MS = 3 * HOUR_MS;
const DRAG_THRESHOLD_PX = 4;

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
    this._view = null;
    this._pointers = new Map();
    this._gesture = null;
    this._timer = null;
    this._resize = new ResizeObserver(() => this._draw());
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error("entity is required");
    const prev = this._config;
    if (!prev || prev.entity !== config.entity || prev.forecast_days !== clampDays(config.forecast_days ?? 7)) {
      this._view = null;
    }
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

  get _bounds() {
    const all = this._model.all;
    return { min: all[0].start, max: all[all.length - 1].end };
  }

  // The view is kept across refreshes and clamped to the current range.
  _currentView() {
    const b = this._bounds;
    if (!this._view) return { v0: b.min, v1: b.max };
    return clampView(this._view.v0, this._view.v1, b.min, b.max, MIN_SPAN_MS);
  }

  _setView(view) {
    this._view = view;
    this._renderChart();
  }

  _geometry() {
    const m = this._model;
    const width = Math.max(240, this.clientWidth || W);
    const height = H;
    const { min: t0, max: t1 } = this._bounds;
    const { v0, v1 } = this._currentView();
    const known = visibleSlice(m.known, v0, v1);
    const forecast = visibleSlice(m.forecast, v0, v1);
    const ys = yScale(known, forecast);
    const x = linearScale(v0, v1, M.left, width - M.right);
    const y = linearScale(ys.min, ys.max, height - M.bottom, M.top);
    return { width, height, t0, t1, v0, v1, known, forecast, ys, x, y };
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
      .wrap { position: relative; touch-action: pan-y; user-select: none; -webkit-user-select: none; }
      .zoom { position: absolute; top: 2px; right: 2px; display: flex; gap: 4px; }
      .zoom button { width: 26px; height: 26px; padding: 0; line-height: 1; font-size: 15px; cursor: pointer;
        border-radius: 6px; border: 1px solid var(--divider-color); color: var(--primary-text-color);
        background: var(--card-background-color, #fff); opacity: 0.85; }
      .zoom button:hover, .zoom button:focus-visible { opacity: 1; border-color: var(--primary-color); }
      svg { width: 100%; height: auto; display: block; }
      .grid { stroke: var(--divider-color); stroke-width: 1; }
      .axis { fill: var(--secondary-text-color); font-size: 11px; }
      .known { fill: none; stroke: var(--primary-color); stroke-width: 2; }
      .fc { fill: none; stroke: var(--primary-color); stroke-width: 2; stroke-dasharray: 5 4; }
      .band { fill: var(--primary-color); opacity: 0.18; stroke: none; }
      .now { stroke: var(--secondary-text-color); stroke-width: 1; stroke-dasharray: 2 3; }
      .grabbing { cursor: grabbing; }
      .boxing { cursor: crosshair; }
      .sel { position: absolute; pointer-events: none; box-sizing: border-box;
        background: color-mix(in srgb, var(--primary-color) 18%, transparent);
        border: 1px solid var(--primary-color); }
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
    root.innerHTML = `${style}<ha-card>${title}
      <div class="wrap">
        <svg role="img"></svg>
        <div class="zoom">
          <button type="button" data-zoom="in" aria-label="${esc(t.zoomIn)}" title="${esc(t.zoomIn)}">+</button>
          <button type="button" data-zoom="out" aria-label="${esc(t.zoomOut)}" title="${esc(t.zoomOut)}">&minus;</button>
          <button type="button" data-zoom="reset" aria-label="${esc(t.zoomReset)}" title="${esc(t.zoomReset)}">&#x2922;</button>
        </div>
        <div class="tip" hidden></div>
        <div class="sel" hidden></div>
      </div>
      ${this._config.show_table !== false ? this._table() : ""}
    </ha-card>`;
    const wrap = root.querySelector(".wrap");
    wrap.addEventListener("pointermove", (e) => this._onPointerMove(e));
    wrap.addEventListener("pointerleave", () => {
      if (!this._pointers.size) this._hideHover();
    });
    wrap.addEventListener("pointerdown", (e) => this._onPointerDown(e));
    wrap.addEventListener("pointerup", (e) => this._onPointerEnd(e));
    wrap.addEventListener("pointercancel", (e) => this._onPointerEnd(e));
    wrap.addEventListener("dblclick", (e) => {
      if (!e.target.closest(".zoom")) this._setView(null);
    });
    wrap.addEventListener("wheel", (e) => this._onWheel(e), { passive: false });
    root.querySelector(".zoom").addEventListener("click", (e) => {
      const action = e.target.closest("button") && e.target.closest("button").dataset.zoom;
      if (!action) return;
      const v = this._currentView();
      if (action === "reset") this._setView(null);
      else this._setView(zoomView(v, action === "in" ? 0.5 : 2, (v.v0 + v.v1) / 2, this._bounds, MIN_SPAN_MS));
    });
    this._renderChart();
  }

  _renderChart() {
    const svg = this.shadowRoot.querySelector("svg");
    if (!svg || !this._model || !this._model.all.length) return;
    const g = this._geometry();
    this._g = g;
    const { unit } = this._model;
    const plotW = g.width - M.left - M.right;
    const ticks = g.ys.ticks
      .map(
        (v) =>
          `<line class="grid" x1="${M.left}" x2="${g.width - M.right}" y1="${g.y(v)}" y2="${g.y(v)}"/>` +
          `<text class="axis" x="${M.left - 6}" y="${g.y(v) + 4}" text-anchor="end">${this._fmtValue(v)}</text>`,
      )
      .join("");
    const xt = xTicks(g.v0, g.v1, plotW, this._tz)
      .map(
        ({ ms, kind }) =>
          `<line class="grid" x1="${g.x(ms)}" x2="${g.x(ms)}" y1="${M.top}" y2="${g.height - M.bottom}"/>` +
          // The label starts at its tick; skip it when it would run past the chart.
          (g.x(ms) + 70 <= g.width
            ? `<text class="axis" x="${g.x(ms) + 3}" y="${g.height - 8}">${esc(
                kind === "day" ? this._fmtDay(ms) : this._fmtTime(ms),
              )}</text>`
            : ""),
      )
      .join("");
    svg.setAttribute("viewBox", `0 0 ${g.width} ${g.height}`);
    svg.setAttribute("aria-label", unit);
    svg.innerHTML = `<defs><clipPath id="plot-clip"><rect x="${M.left}" y="${M.top}" width="${plotW}" height="${
      g.height - M.top - M.bottom
    }"/></clipPath></defs>
          ${ticks}${xt}
          <g clip-path="url(#plot-clip)">
            <path class="band" d="${bandPolygon(g.forecast, g.x, g.y)}"/>
            <path class="known" d="${stepPath(g.known, g.x, g.y)}"/>
            <path class="fc" d="${stepPath(g.forecast, g.x, g.y)}"/>
          </g>
          <line class="now" y1="${M.top}" y2="${g.height - M.bottom}" visibility="hidden"/>
          <line class="hair" y1="${M.top}" y2="${g.height - M.bottom}" visibility="hidden"/>`;
    this._hideHover();
    this._updateNow();
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
    if (now < this._g.v0 || now > this._g.v1) {
      line.setAttribute("visibility", "hidden");
      return;
    }
    const xx = this._g.x(now);
    line.setAttribute("x1", xx);
    line.setAttribute("x2", xx);
    line.setAttribute("visibility", "visible");
  }

  // Pixels per svg unit, and the plot area width in svg units.
  _metrics() {
    const rect = this.shadowRoot.querySelector("svg").getBoundingClientRect();
    return { rect, scale: this._g.width / (rect.width || this._g.width), plotW: this._g.width - M.left - M.right };
  }

  _timeAt(clientX) {
    const { rect, scale, plotW } = this._metrics();
    const px = (clientX - rect.left) * scale;
    return this._g.v0 + ((px - M.left) / plotW) * (this._g.v1 - this._g.v0);
  }

  _onWheel(e) {
    if (!this._g || !this._model) return;
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const factor = Math.exp(Math.max(-100, Math.min(100, e.deltaY)) * 0.002);
      this._setView(zoomView(this._currentView(), factor, this._timeAt(e.clientX), this._bounds, MIN_SPAN_MS));
      return;
    }
    const delta = e.shiftKey ? e.deltaX || e.deltaY : Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : 0;
    if (!delta) return;
    const v = this._currentView();
    const { scale, plotW } = this._metrics();
    this._setView(panView(v, ((delta * scale) / plotW) * (v.v1 - v.v0), this._bounds));
  }

  _onPointerDown(e) {
    if (!this._g || !this._model || e.target.closest(".zoom")) return;
    if (e.pointerType === "mouse" && e.button !== 0) return;
    this._pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch (_) {
      // Capture is optional; dragging still works while the pointer stays over the chart.
    }
    this._startGesture();
    if (this._pointers.size === 1) this._showHover(e);
  }

  _startGesture() {
    const pts = [...this._pointers.values()];
    this._gesture = { view: this._currentView(), start: { x: pts[0].x, y: pts[0].y }, moved: this._gesture ? this._gesture.moved : false };
    if (pts.length >= 2) this._gesture.dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
  }

  _onPointerMove(e) {
    if (!this._g || !this._model) return;
    const ptr = this._pointers.get(e.pointerId);
    if (!ptr) {
      if (e.pointerType !== "touch") this._showHover(e);
      return;
    }
    ptr.x = e.clientX;
    ptr.y = e.clientY;
    const gst = this._gesture;
    const pts = [...this._pointers.values()];
    if (pts.length >= 2) {
      const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      if (gst.dist > 0 && dist > 0) {
        const cx = (pts[0].x + pts[1].x) / 2;
        this._hideHover();
        gst.moved = true;
        this._setView(zoomView(this._currentView(), gst.dist / dist, this._timeAt(cx), this._bounds, MIN_SPAN_MS));
      }
      gst.dist = dist;
      return;
    }
    const dx = e.clientX - gst.start.x;
    if (!gst.moved && Math.abs(dx) < DRAG_THRESHOLD_PX) return;
    gst.moved = true;
    this._hideHover();
    if (e.pointerType === "mouse" && !e.shiftKey) {
      // Desktop: drag a box over the area to zoom in on (hold Shift to pan instead).
      gst.box = true;
      this._drawBox(gst.start.x, e.clientX);
      return;
    }
    this.shadowRoot.querySelector(".wrap").classList.add("grabbing");
    const { scale, plotW } = this._metrics();
    const span = gst.view.v1 - gst.view.v0;
    this._setView(panView(gst.view, (-(dx * scale) / plotW) * span, this._bounds));
  }

  _onPointerEnd(e) {
    if (!this._pointers.delete(e.pointerId)) return;
    if (this._pointers.size) {
      this._startGesture();
      return;
    }
    const gst = this._gesture;
    this._gesture = null;
    const wrap = this.shadowRoot.querySelector(".wrap");
    if (wrap) wrap.classList.remove("grabbing");
    const sel = this.shadowRoot.querySelector(".sel");
    if (sel) sel.hidden = true;
    if (gst && gst.box && e.type === "pointerup" && this._g) {
      const a = this._timeAt(gst.start.x);
      const b = this._timeAt(e.clientX);
      if (Math.abs(e.clientX - gst.start.x) >= 2 * DRAG_THRESHOLD_PX) {
        this._setView(clampView(Math.min(a, b), Math.max(a, b), this._bounds.min, this._bounds.max, MIN_SPAN_MS));
      }
    }
  }

  // Selection box over the plot area, between two client x positions.
  _drawBox(x0, x1) {
    const { rect, scale } = this._metrics();
    const wrapRect = this.shadowRoot.querySelector(".wrap").getBoundingClientRect();
    const lo = rect.left + M.left / scale;
    const hi = rect.left + (this._g.width - M.right) / scale;
    const a = Math.min(hi, Math.max(lo, Math.min(x0, x1)));
    const b = Math.min(hi, Math.max(lo, Math.max(x0, x1)));
    const sel = this.shadowRoot.querySelector(".sel");
    sel.style.left = `${a - wrapRect.left}px`;
    sel.style.width = `${b - a}px`;
    sel.style.top = `${rect.top - wrapRect.top + M.top / scale}px`;
    sel.style.height = `${(this._g.height - M.top - M.bottom) / scale}px`;
    sel.hidden = false;
  }

  _showHover(e) {
    const { rect, scale } = this._metrics();
    const visible = visibleSlice(this._model.all, this._g.v0, this._g.v1);
    const p = nearestPoint(visible, this._timeAt(e.clientX));
    if (!p) return;
    const t = this._t;
    const xx = Math.min(this._g.width - M.right, Math.max(M.left, this._g.x(p.start)));
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
    this._form = null;
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
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) => this._labels[schema.name] || schema.name;
      this._form.addEventListener("value-changed", (e) => {
        e.stopPropagation();
        const v = e.detail.value || {};
        this._fire({ ...this._config, entity: v.entity, forecast_days: clampDays(v.forecast_days) });
      });
      this.appendChild(this._form);
    }
    this._labels = { entity: t.entity, forecast_days: t.forecastDays };
    this._form.hass = this._hass;
    this._form.schema = [
      {
        name: "entity",
        required: true,
        selector: { entity: { domain: "sensor", filter: { domain: "sensor" } } },
      },
      { name: "forecast_days", selector: { number: { min: 1, max: 7, step: 1, mode: "box" } } },
    ];
    this._form.data = {
      entity: this._config.entity || "",
      forecast_days: this._config.forecast_days ?? 7,
    };
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
