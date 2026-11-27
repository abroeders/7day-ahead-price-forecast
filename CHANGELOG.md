# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow Home Assistant's scheme: `YEAR.MONTH.N`.

## [Unreleased]

### Changed

- Installation: the steps describe the built-in Marketplace (*Add from link*, with a My Home Assistant button) for
  Home Assistant 2026.11 and later; the HACS steps stay for older versions.

### Added

- Docs: a script that finds the cheapest block of consecutive hours in the coming days.

## [2026.11.2] - 2026-11-27

### Added

- Card: drag a box over the chart with the mouse to zoom in on that time range. Panning with the mouse is now
  `Shift` + drag; touch is unchanged.

### Fixed

- Card editor: the number of forecast days was not shown in recent Home Assistant versions; the editor now uses
  the standard form component.
- Card: dragging the chart with the mouse or a finger did not pan, because the start of the drag moved along
  with the pointer.

## [2026.11.1] - 2026-11-27

### Added

- Lovelace price chart card, served by the integration: published prices as a solid line, the forecast as a
  dashed line with a P10–P90 band per quarter hour, a hairline with tooltip, a now marker, a per-day table and
  a configurable number of forecast days, and zoom and pan on the time axis to see the quarter-hour steps.
  The card is installed with the integration and needs no resource to be added by hand.
- Documentation: a page for the card, automation and template examples (cheapest quarter hours and blocks of
  several hours, with and without the band) and an accuracy page with the measured deviations against the
  published day-ahead prices.

### Changed

- The documentation site now covers the integration only. Forecast day 1 is explicitly the first day after the
  published day-ahead prices.
- The README has screenshots, a feature list and the accuracy figures.

## [2026.11.0] - 2026-11-27

### Added

- First release. Day-ahead electricity price forecast for the 7 days after the last known price day, per quarter
  hour with a P10–P90 band, read from the forecast service with automatic failover between two servers.
- Config flow with a base controller per zone (Netherlands) and sub-controllers that apply your own surcharges,
  VAT and formula variants to the bare market price.
- Forecast sensor (prices and band as attributes), service state sensor and accuracy sensors (mean absolute
  error, bias, band coverage) per controller.
