import { test } from "node:test";
import assert from "node:assert/strict";
import {
  localParts,
  toPoints,
  cutForecast,
  clampDays,
  integrationDays,
  niceStep,
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
  wallToInstant,
  QUARTER_MS,
  HOUR_MS,
} from "../../custom_components/day_ahead_price_forecast/www/chart-core.js";

const TZ = "Europe/Amsterdam";

function quarters(startIso, count, valueFn = () => 1) {
  const s = Date.parse(startIso);
  return Array.from({ length: count }, (_, i) => ({
    start: s + i * QUARTER_MS,
    end: s + (i + 1) * QUARTER_MS,
    value: valueFn(i),
    p10: null,
    p90: null,
  }));
}

test("toPoints parses ISO strings and drops invalid items", () => {
  const pts = toPoints([
    { start: "2026-01-01T00:00:00Z", end: "2026-01-01T00:15:00Z", value: 0.1 },
    { start: "bad", end: "x", value: 1 },
  ]);
  assert.equal(pts.length, 1);
  assert.equal(pts[0].end - pts[0].start, QUARTER_MS);
  assert.equal(pts[0].p10, null);
});

test("cutForecast keeps N local calendar days after known_until", () => {
  const knownUntil = Date.parse("2026-01-10T23:00:00Z"); // 11 Jan 00:00 local
  const fc = quarters("2026-01-10T23:00:00Z", 96 * 3);
  const cut = cutForecast(fc, knownUntil, 2, TZ);
  assert.equal(cut.length, 96 * 2);
  assert.equal(cut.at(-1).end, Date.parse("2026-01-12T23:00:00Z"));
});

test("cutForecast is DST-safe on the spring-forward day (23 h)", () => {
  const knownUntil = Date.parse("2026-03-28T23:00:00Z"); // 29 Mar 00:00 CET, 29 Mar has 23 h
  const fc = quarters("2026-03-28T23:00:00Z", 96 * 3);
  const cut = cutForecast(fc, knownUntil, 1, TZ);
  assert.equal(cut.length, 92);
  assert.equal(cut.at(-1).end, Date.parse("2026-03-29T22:00:00Z")); // 30 Mar 00:00 CEST
});

test("cutForecast is DST-safe on the fall-back day (25 h)", () => {
  const knownUntil = Date.parse("2026-10-24T22:00:00Z"); // 25 Oct 00:00 CEST
  const fc = quarters("2026-10-24T22:00:00Z", 96 * 3);
  const cut = cutForecast(fc, knownUntil, 1, TZ);
  assert.equal(cut.length, 100);
  assert.equal(cut.at(-1).end, Date.parse("2026-10-25T23:00:00Z"));
});

test("niceStep rounds up to 1/2/2.5/5 x 10^n", () => {
  assert.equal(niceStep(0.03), 0.05);
  assert.equal(niceStep(0.11), 0.2);
  assert.equal(niceStep(3), 5);
  assert.equal(niceStep(7), 10);
});

test("yScale always includes 0 and covers p10/p90", () => {
  const known = quarters("2026-01-01T00:00:00Z", 2, () => 0.12);
  const fc = [{ start: 0, end: 1, value: 0.2, p10: 0.1, p90: 0.31 }];
  const s = yScale(known, fc);
  assert.equal(s.min, 0);
  assert.ok(s.max >= 0.31);
  assert.equal(s.ticks[0], 0);
  assert.equal(s.ticks.at(-1), s.max);
});

test("yScale includes 0 for negative prices and for all-positive data", () => {
  const neg = yScale(quarters("2026-01-01T00:00:00Z", 2, (i) => -0.05 * (i + 1)), []);
  assert.ok(neg.min <= -0.1 && neg.max >= 0);
  const pos = yScale(quarters("2026-01-01T00:00:00Z", 2, () => 100), []);
  assert.equal(pos.min, 0);
});

test("linearScale maps the domain onto the range", () => {
  const f = linearScale(10, 20, 0, 100);
  assert.equal(f(10), 0);
  assert.equal(f(15), 50);
  assert.equal(linearScale(0, 1, 100, 0)(1), 0);
});

test("stepPath holds each value for its interval and breaks on gaps", () => {
  const x = (v) => v;
  const y = (v) => v;
  const pts = [
    { start: 0, end: 10, value: 5 },
    { start: 10, end: 20, value: 8 },
    { start: 30, end: 40, value: 2 },
  ];
  assert.equal(stepPath(pts, x, y), "M0,5 L10,5 L10,8 L20,8 M30,2 L40,2");
  assert.equal(stepPath([], x, y), "");
});

test("bandPolygon builds one rectangle per point with p10 and p90", () => {
  const x = (v) => v;
  const y = (v) => 100 - v;
  const pts = [
    { start: 0, end: 10, value: 5, p10: 2, p90: 8 },
    { start: 10, end: 20, value: 5, p10: null, p90: null },
  ];
  assert.equal(bandPolygon(pts, x, y), "M0,92 L10,92 L10,98 L0,98 Z");
});

test("dayStats gives time-weighted average and cheapest/most expensive clock hour", () => {
  const pts = [
    ...quarters("2026-01-10T23:00:00Z", 4, () => 1), // 00:00 local
    ...quarters("2026-01-11T00:00:00Z", 4, () => 5),
    ...quarters("2026-01-11T01:00:00Z", 2, () => 3), // incomplete hour
  ];
  const [d] = dayStats(pts, TZ);
  assert.equal(d.day, "2026-01-11");
  assert.equal(d.average, (4 * 1 + 4 * 5 + 2 * 3) / 10);
  assert.deepEqual(d.cheapest, { start: Date.parse("2026-01-10T23:00:00Z"), value: 1 });
  assert.deepEqual(d.mostExpensive, { start: Date.parse("2026-01-11T00:00:00Z"), value: 5 });
});

test("dayStats groups by local day and flags forecast days", () => {
  const known = quarters("2026-01-10T23:00:00Z", 96, () => 1);
  const fc = quarters("2026-01-11T23:00:00Z", 96, () => 2).map((p) => ({ ...p, isForecast: true }));
  const days = dayStats([...known, ...fc], TZ);
  assert.deepEqual(days.map((d) => [d.day, d.forecast]), [["2026-01-11", false], ["2026-01-12", true]]);
});

test("nearestPoint snaps to the containing quarter hour", () => {
  const pts = quarters("2026-01-01T00:00:00Z", 4);
  const s = pts[0].start;
  assert.equal(nearestPoint(pts, s + 20 * 60000), pts[1]);
  assert.equal(nearestPoint(pts, s), pts[0]);
  assert.equal(nearestPoint(pts, s - 5 * 60000), pts[0]);
  assert.equal(nearestPoint(pts, s + 10 * HOUR_MS), pts[3]);
  assert.equal(nearestPoint([], 0), null);
});

test("nearestPoint picks the closer side of a gap", () => {
  const pts = [
    { start: 0, end: 10, value: 1 },
    { start: 100, end: 110, value: 2 },
  ];
  assert.equal(nearestPoint(pts, 20), pts[0]);
  assert.equal(nearestPoint(pts, 90), pts[1]);
});

const BOUNDS = { min: 1000 * HOUR_MS, max: 1100 * HOUR_MS };
const MIN_SPAN = 3 * HOUR_MS;

test("visibleSlice returns points overlapping the window", () => {
  const pts = quarters("2026-06-01T00:00:00Z", 8);
  const s = Date.parse("2026-06-01T00:00:00Z");
  const vis = visibleSlice(pts, s + 20 * 60000, s + 50 * 60000);
  assert.deepEqual(vis, pts.slice(1, 4));
  assert.deepEqual(visibleSlice(pts, s + 2 * HOUR_MS, s + 3 * HOUR_MS), []);
  assert.deepEqual(visibleSlice(pts, s + 30 * 60000, s + 30 * 60000 + 1), [pts[2]]);
});

test("clampView shifts inside bounds at both edges and limits the span", () => {
  assert.deepEqual(clampView(BOUNDS.min - 5 * HOUR_MS, BOUNDS.min + 5 * HOUR_MS, BOUNDS.min, BOUNDS.max, MIN_SPAN), {
    v0: BOUNDS.min,
    v1: BOUNDS.min + 10 * HOUR_MS,
  });
  assert.deepEqual(clampView(BOUNDS.max - 5 * HOUR_MS, BOUNDS.max + 5 * HOUR_MS, BOUNDS.min, BOUNDS.max, MIN_SPAN), {
    v0: BOUNDS.max - 10 * HOUR_MS,
    v1: BOUNDS.max,
  });
  const small = clampView(BOUNDS.min + HOUR_MS, BOUNDS.min + 2 * HOUR_MS, BOUNDS.min, BOUNDS.max, MIN_SPAN);
  assert.equal(small.v1 - small.v0, MIN_SPAN);
  const big = clampView(BOUNDS.min - HOUR_MS, BOUNDS.max + HOUR_MS, BOUNDS.min, BOUNDS.max, MIN_SPAN);
  assert.deepEqual(big, { v0: BOUNDS.min, v1: BOUNDS.max });
});

test("zoomView keeps the anchor at the same relative position and respects min span", () => {
  const view = { v0: BOUNDS.min + 20 * HOUR_MS, v1: BOUNDS.min + 60 * HOUR_MS };
  const anchor = view.v0 + 10 * HOUR_MS;
  const z = zoomView(view, 0.5, anchor, BOUNDS, MIN_SPAN);
  assert.equal(z.v1 - z.v0, 20 * HOUR_MS);
  assert.equal((anchor - z.v0) / (z.v1 - z.v0), 0.25);
  const tiny = zoomView(view, 0.001, anchor, BOUNDS, MIN_SPAN);
  assert.equal(tiny.v1 - tiny.v0, MIN_SPAN);
  const out = zoomView(view, 100, anchor, BOUNDS, MIN_SPAN);
  assert.deepEqual(out, { v0: BOUNDS.min, v1: BOUNDS.max });
});

test("panView stops at the bounds and keeps the span", () => {
  const view = { v0: BOUNDS.min + 10 * HOUR_MS, v1: BOUNDS.min + 30 * HOUR_MS };
  assert.deepEqual(panView(view, 5 * HOUR_MS, BOUNDS), { v0: view.v0 + 5 * HOUR_MS, v1: view.v1 + 5 * HOUR_MS });
  assert.deepEqual(panView(view, -100 * HOUR_MS, BOUNDS), { v0: BOUNDS.min, v1: BOUNDS.min + 20 * HOUR_MS });
  assert.deepEqual(panView(view, 500 * HOUR_MS, BOUNDS), { v0: BOUNDS.max - 20 * HOUR_MS, v1: BOUNDS.max });
});

test("xTicks gives hourly ticks for a 1 day window", () => {
  const v0 = wallToInstant(2026, 6, 10, 0, 0, TZ);
  const v1 = wallToInstant(2026, 6, 11, 0, 0, TZ);
  const ticks = xTicks(v0, v1, 540, TZ);
  // 540 px / 24 h = 22.5 px per hour, so a 3 hour step.
  assert.deepEqual(ticks.map((t) => (t.ms - v0) / HOUR_MS), [0, 3, 6, 9, 12, 15, 18, 21, 24]);
  assert.equal(ticks[0].kind, "day");
  assert.equal(ticks[8].kind, "day");
  assert.equal(ticks[1].kind, "hour");
});

test("xTicks gives midnights for a 7 day window", () => {
  const v0 = wallToInstant(2026, 6, 10, 6, 0, TZ);
  const v1 = wallToInstant(2026, 6, 17, 6, 0, TZ);
  const ticks = xTicks(v0, v1, 540, TZ);
  assert.equal(ticks.length, 7);
  assert.ok(ticks.every((t) => t.kind === "day" && localParts(t.ms, TZ).hour === 0));
});

test("xTicks is DST-safe on a 23 hour day", () => {
  const v0 = wallToInstant(2026, 3, 29, 0, 0, TZ);
  const v1 = wallToInstant(2026, 3, 30, 0, 0, TZ);
  assert.equal((v1 - v0) / HOUR_MS, 23);
  const ticks = xTicks(v0, v1, 1380, TZ);
  assert.equal(ticks.length, 24);
  assert.deepEqual(
    ticks.map((t) => localParts(t.ms, TZ).hour),
    [0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 0],
  );
  const coarse = xTicks(v0, v1, 400, TZ);
  assert.deepEqual(
    coarse.map((t) => localParts(t.ms, TZ).hour),
    [0, 6, 12, 18, 0],
  );
});

test("clampDays limits to the integration maximum", () => {
  assert.equal(clampDays(7, 2), 2);
  assert.equal(clampDays(0, 2), 1);
  assert.equal(clampDays("x", 3), 3);
  assert.equal(clampDays(5), 5);
});

test("integrationDays reads the sensor attribute", () => {
  assert.equal(integrationDays({ forecast_days: 2 }), 2);
  assert.equal(integrationDays({ forecast_days: 99 }), 7);
  assert.equal(integrationDays({}), 7);
  assert.equal(integrationDays(undefined), 7);
});
