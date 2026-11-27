# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow Home Assistant's scheme: `YEAR.MONTH.N`.

## [Unreleased]

### Added

- Lovelace price chart card, served by the integration: published prices as a solid line, the forecast as a
  dashed line with a P10–P90 band per quarter hour, a hairline with tooltip, a now marker, a per-day table and
  a configurable number of forecast days.

## [2026.11.0] - 2026-11-27

### Added

- First release. Day-ahead electricity price forecast for the 7 days after the last known price day, per quarter
  hour with a P10–P90 band, read from the forecast service with automatic failover between two servers.
- Config flow with a base controller per zone (Netherlands) and sub-controllers that apply your own surcharges,
  VAT and formula variants to the bare market price.
- Forecast sensor (prices and band as attributes), service state sensor and accuracy sensors (mean absolute
  error, bias, band coverage) per controller.
