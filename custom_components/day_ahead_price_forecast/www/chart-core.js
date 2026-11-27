// Pure chart logic for day-ahead-price-forecast-card. No DOM access.

const QUARTER_MS = 15 * 60 * 1000;
const HOUR_MS = 60 * 60 * 1000;

const partsCache = new Map();

function formatter(timeZone) {
  let f = partsCache.get(timeZone);
  if (!f) {
    f = new Intl.DateTimeFormat("en-US", {
      timeZone,
      hourCycle: "h23",
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "numeric",
      minute: "numeric",
      second: "numeric",
    });
    partsCache.set(timeZone, f);
  }
  return f;
}

/** Wall-clock parts of an instant (ms) in a time zone. */
export function localParts(ms, timeZone) {
  const out = {};
  for (const p of formatter(timeZone).formatToParts(new Date(ms))) {
    if (p.type !== "literal") out[p.type] = Number(p.value);
  }
  return out;
}

/** Instant (ms) of a wall-clock time in a time zone (month 1-12, day may overflow). */
export function wallToInstant(y, mo, d, h, mi, timeZone) {
  const wall = Date.UTC(y, mo - 1, d, h, mi);
  let guess = wall;
  for (let i = 0; i < 3; i++) {
    const p = localParts(guess, timeZone);
    const seen = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute);
    const diff = wall - seen;
    if (diff === 0) break;
    guess += diff;
  }
  return guess;
}

/** Local day key "YYYY-MM-DD" of an instant. */
export function dayKey(ms, timeZone) {
  const p = localParts(ms, timeZone);
  return `${p.year}-${String(p.month).padStart(2, "0")}-${String(p.day).padStart(2, "0")}`;
}

/** Instant that lies `days` local calendar days after `ms`, at the same wall-clock time. */
export function addLocalDays(ms, days, timeZone) {
  const p = localParts(ms, timeZone);
  return wallToInstant(p.year, p.month, p.day + days, p.hour, p.minute, timeZone);
}

/** Convert API items (ISO strings) to points with millisecond timestamps. */
export function toPoints(items) {
  return (items || [])
    .map((i) => ({
      start: Date.parse(i.start),
      end: Date.parse(i.end),
      value: i.value,
      p10: i.p10 ?? null,
      p90: i.p90 ?? null,
    }))
    .filter((p) => Number.isFinite(p.start) && Number.isFinite(p.end) && typeof p.value === "number");
}

/** Drop forecast points starting at or after knownUntil + days local calendar days. */
export function cutForecast(forecast, knownUntil, days, timeZone) {
  const limit = addLocalDays(knownUntil, days, timeZone);
  return forecast.filter((p) => p.start < limit);
}

/** Round a step up to 1, 2, 2.5, 5 times a power of ten. */
export function niceStep(rawStep) {
  if (!(rawStep > 0)) return 1;
  const pow = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const f = rawStep / pow;
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
  return nice * pow;
}

/** Y domain with nice ticks; always includes 0. */
export function yScale(known, forecast, maxTicks = 6) {
  let lo = 0;
  let hi = 0;
  for (const p of known) {
    lo = Math.min(lo, p.value);
    hi = Math.max(hi, p.value);
  }
  for (const p of forecast) {
    for (const v of [p.value, p.p10, p.p90]) {
      if (typeof v !== "number") continue;
      lo = Math.min(lo, v);
      hi = Math.max(hi, v);
    }
  }
  if (hi === lo) hi = lo + 1;
  const step = niceStep((hi - lo) / Math.max(1, maxTicks - 1));
  const min = Math.floor(lo / step + 1e-9) * step;
  const max = Math.ceil(hi / step - 1e-9) * step;
  const ticks = [];
  const n = Math.round((max - min) / step);
  for (let i = 0; i <= n; i++) ticks.push(Number((min + i * step).toPrecision(12)));
  return { min, max, step, ticks };
}

/** Linear mapping from domain [d0, d1] to range [r0, r1]. */
export function linearScale(d0, d1, r0, r1) {
  const span = d1 - d0 || 1;
  return (v) => r0 + ((v - d0) / span) * (r1 - r0);
}

/** Step path: every value holds for its own interval. Gaps start a new subpath. */
export function stepPath(points, x, y) {
  let d = "";
  let prevEnd = null;
  for (const p of points) {
    const x0 = x(p.start);
    const x1 = x(p.end);
    const yy = y(p.value);
    if (prevEnd === null || p.start !== prevEnd.end) {
      d += `${d ? " " : ""}M${fmt(x0)},${fmt(yy)}`;
    } else {
      d += ` L${fmt(x0)},${fmt(yy)}`;
    }
    d += ` L${fmt(x1)},${fmt(yy)}`;
    prevEnd = p;
  }
  return d;
}

/** One closed rectangle per forecast point that has p10 and p90, as a single path string. */
export function bandPolygon(points, x, y) {
  const parts = [];
  for (const p of points) {
    if (typeof p.p10 !== "number" || typeof p.p90 !== "number") continue;
    const x0 = fmt(x(p.start));
    const x1 = fmt(x(p.end));
    const top = fmt(y(Math.max(p.p10, p.p90)));
    const bottom = fmt(y(Math.min(p.p10, p.p90)));
    parts.push(`M${x0},${top} L${x1},${top} L${x1},${bottom} L${x0},${bottom} Z`);
  }
  return parts.join(" ");
}

function fmt(n) {
  return String(Math.round(n * 100) / 100);
}

/** Per local day: time-weighted average, cheapest and most expensive full clock hour. */
export function dayStats(points, timeZone) {
  const days = new Map();
  for (const p of points) {
    const key = dayKey(p.start, timeZone);
    let d = days.get(key);
    if (!d) {
      d = { day: key, start: p.start, sum: 0, weight: 0, hours: new Map(), forecast: false };
      days.set(key, d);
    }
    const w = p.end - p.start;
    d.sum += p.value * w;
    d.weight += w;
    if (p.isForecast) d.forecast = true;
    const hourStart = Math.floor(p.start / HOUR_MS) * HOUR_MS;
    let h = d.hours.get(hourStart);
    if (!h) {
      h = { start: hourStart, sum: 0, weight: 0 };
      d.hours.set(hourStart, h);
    }
    h.sum += p.value * w;
    h.weight += w;
  }
  const out = [];
  for (const d of days.values()) {
    const full = [...d.hours.values()]
      .filter((h) => h.weight === HOUR_MS)
      .map((h) => ({ start: h.start, value: h.sum / h.weight }));
    let min = null;
    let max = null;
    for (const h of full) {
      if (!min || h.value < min.value) min = h;
      if (!max || h.value > max.value) max = h;
    }
    out.push({
      day: d.day,
      start: d.start,
      average: d.weight ? d.sum / d.weight : null,
      cheapest: min,
      mostExpensive: max,
      forecast: d.forecast,
    });
  }
  return out.sort((a, b) => a.start - b.start);
}

/** Point whose interval contains t, or the nearest one when t is in a gap or outside. */
export function nearestPoint(points, t) {
  if (!points.length) return null;
  let lo = 0;
  let hi = points.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (points[mid].end <= t) lo = mid + 1;
    else hi = mid;
  }
  const cand = points[lo];
  if (t >= cand.start && t < cand.end) return cand;
  const prev = lo > 0 ? points[lo - 1] : null;
  const dist = (p) => (t < p.start ? p.start - t : t - p.end);
  if (prev && dist(prev) <= dist(cand)) return prev;
  return cand;
}

export { QUARTER_MS, HOUR_MS };
