# Configurable number of forecast days

Status: approved

## Goal

Let the user choose how many forecast days are fetched and exposed, so that less data is transferred and stored
when, for example, only two days are needed.

## Contract

The forecast service accepts an optional query parameter:

```
GET /v1/forecast?zone=NL&days=N
```

- `days` is an integer from 1 to 7. When absent it is 7 (current behaviour). Other values give HTTP 400.
- `days` counts **calendar days after the last known price day** (`known_until`), in the zone's local time. This is
  the same rule the card already uses for `forecast_days`.
- Only the forecast points are cut; known prices and metadata are unchanged.

The client also trims the received forecast to the same limit. A service that ignores the parameter therefore still
yields a correct result, only without the data saving.

## Integration

- `const.py`: `CONF_FORECAST_DAYS = "forecast_days"`, `DEFAULT_FORECAST_DAYS = 7`, `MAX_FORECAST_DAYS = 7`.
- Base controller (the zone config entry) gets the setting in the user step and in `async_step_reconfigure`
  (number selector 1-7, default 7). Saving a change reloads the entry. Entries without the key use 7.
- `ForecastProvider.fetch(zone, days)`; `RemoteProvider` appends `&days=N`; the coordinator trims the result.
- `core/models.py`: `Forecast.limited_to(days, tz)` (tz is a `tzinfo`, loaded asynchronously by the coordinator) returns a copy with the points cut at `known_until` + N local
  calendar days (pure Python, no Home Assistant imports, unit tested including DST days).
- `ForecastCoordinator` reads the setting from the entry and passes it to the provider.
- Forecast sensors expose the attribute `forecast_days`; their `forecast` attribute holds only those days.

## Card

- The card reads `forecast_days` from the entity attributes and uses `min(config.forecast_days, attribute)`.
- The editor limits the `forecast_days` input to that maximum and shows it in the helper text. Without the
  attribute (older sensors) the maximum stays 7.

## Documentation

`docs/configuration.md` (setting), `docs/card.md` (limit), `docs/entities.md` (attribute), `README.md`,
`docs/architecture.md` (class and sequence diagrams: `fetch(zone, days)`, `Forecast.limited_to`),
`CHANGELOG.md`, and a screenshot of the changed form in `docs/images/` (English, light theme, demo data).
The docs only describe the query parameter as part of the client contract; no server details.

## Tests

- `tests/core`: `limited_to` (1, 7 days, DST days, `days` beyond the available data).
- `tests/providers/test_remote.py`: URL contains `days`, URL contains `days`; the client-side trim is tested in `tests/ha` via the coordinator.
- `tests/ha`: config flow and reconfigure, entry reload, sensor attribute.
- `tests/card`: clamping of `forecast_days` to the attribute.

## Out of scope

Server implementation (separate issue in the server repository), the per-day accuracy sensors.
