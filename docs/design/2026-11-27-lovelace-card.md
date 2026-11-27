# Design: Lovelace price chart card

Status: **draft** (issue #8)

## Goal
A Lovelace card that charts the quarter-hour prices of one forecast sensor (sub-controller): published
prices as a solid line, the forecast as a dashed line with a P10–P90 band per quarter hour.

## Requirements
See issue #8. Out of scope: all-in price (the price is whatever the sub-controller's formula yields), several
entities in one chart, zoom and pan.

## Card configuration
```yaml
type: custom:day-ahead-price-forecast-card
entity: sensor.price_forecast   # a forecast sensor of a sub-controller
forecast_days: 5                # 1-7, days of forecast after the last known price day (default 7)
```
- `entity` is required. The visual editor (`getConfigElement`) offers an entity picker (domain `sensor`, filtered
  on sensors that have a `forecast` attribute) and a number selector for `forecast_days`.
- The known prices are always shown in full. `forecast_days` counts calendar days after `known_until`: day 1 is
  the first day without published prices. Forecast points with a start at or after `known_until` + N days
  (local calendar days, so DST-safe) are dropped.
- Optional: `title`, `show_table` (default true).

## Data contract
Read from the sensor attributes (see `docs/entities.md`): `known_until`, `known[]` and `forecast[]` with
`start`, `end`, `value` and, for the forecast, `p10` and `p90`. No new integration data is needed; the card
does not call services.

## Rendering
Plain TypeScript-free ES module (`custom_components/day_ahead_price_forecast/www/day-ahead-price-forecast-card.js`),
a `HTMLElement` web component with shadow DOM and inline SVG; no runtime dependencies, no build step.
- **Scales:** x = time over the shown range, y = price in the sensor's unit with a "nice" tick step; the y range
  covers known values and the P10/P90 of the shown forecast, and always includes 0.
- **Known:** solid path as a step line (each value holds for its quarter hour).
- **Forecast:** dashed step path of `value`, directly after the known path.
- **Band:** filled polygon between P10 and P90, built per quarter hour, low opacity of the line colour. Points
  without p10/p90 get no band.
- **Hairline:** a vertical line in the SVG that follows `pointermove` (mouse and touch) and snaps to the quarter
  hour under the pointer; a tooltip shows start time, value and, for forecast points, P10–P90 and the label
  "forecast". It hides on `pointerleave`.
- **Now marker:** vertical line at the current time, updated every minute.
- **Day table:** per local day: average (time-weighted over the quarter hours), cheapest and most expensive hour
  (average over the four quarters of each full clock hour). Forecast days are marked.
- **Theme:** colours from HA CSS variables (`--primary-color`, `--primary-text-color`, `--divider-color`,
  `--secondary-text-color`); works in light and dark. Labels in en and nl via `hass.locale.language`.
- The chart redraws when `hass` updates and the entity's `last_updated` changed, and on resize
  (`ResizeObserver`).

## Delivery
The integration serves the file with `hass.http.async_register_static_paths` at
`/day_ahead_price_forecast/<file>.js?v=<version>` and registers it as a Lovelace module resource
(`add_extra_js_url` for storage-mode dashboards), so no manual resource entry is needed. The card also registers
in `window.customCards` so it shows in the card picker. The version query string comes from `manifest.json` to
bust browser caches on release; the card's `package.json` (if any) carries the same version.

## Code layout
`__init__.py` gets `async_setup` (once per HA run) that registers the static path and the extra JS URL. Pure
chart maths (range cut, scales, day statistics) lives in separate functions of the module so they can be unit
tested with Node's built-in test runner (`node --test`) in CI, without a browser.

## Testing
- Node tests for range cut by `forecast_days` (including DST days), scales, step paths, band polygon, day
  statistics and hairline snapping.
- Python test that the static path and extra JS URL are registered on setup.
- Screenshots (English, light theme, made-up data) in `docs/images/`: card, tooltip and editor.

## Documentation
New `docs/card.md` (install-free usage, options, screenshots); mention in `docs/entities.md`, `docs/README.md`
and `mkdocs.yml`; sequence and class diagrams in `docs/architecture.md`.
