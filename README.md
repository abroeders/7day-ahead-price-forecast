# 7-Day-Ahead Price Forecast

[![Marketplace: default](https://img.shields.io/badge/Marketplace-default-41BDF5.svg)](docs/installation.md)
[![Release](https://img.shields.io/github/v/release/abroeders/7day-ahead-price-forecast)](https://github.com/abroeders/7day-ahead-price-forecast/releases)
[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://hacs.xyz)
[![License](https://img.shields.io/github/license/abroeders/7day-ahead-price-forecast)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://abroeders.github.io/7day-ahead-price-forecast/)
[![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-ffdd00?logo=buymeacoffee&logoColor=black)](https://www.buymeacoffee.com/abroeders)

**Know tomorrow's electricity price before it is published, and next week's too.** A Home Assistant integration
that forecasts the day-ahead price **per quarter hour for up to 7 days after the last known price day**, with a
P10–P90 uncertainty band, and a Lovelace chart card that shows it.

![The price chart card: published prices solid, forecast dashed with its band](docs/images/card.png)

## How accurate?
The forecast is made by a model of the Lectoraat Smart Energy of MNEXT.

Checked against the published day-ahead prices over a full year, the forecast is on average only
**1.6 ct/kWh off for the first forecast day and 2.5 ct/kWh for the seventh**, per quarter hour. (Forecast day 1
is the day right after the published day-ahead prices.) That is
**26 to 50 % smaller error** than assuming the last known day repeats, and the P10–P90 band shows how sure each
quarter hour is.

![Average error per forecast day: 1.62 ct/kWh on day 1 up to 2.45 on day 7, against 2.74 to 3.65 for repeating the last known day](docs/images/accuracy.svg)

The shape of the day is predicted best, so the cheapest hours and blocks are found reliably. See
[Accuracy](https://abroeders.github.io/7day-ahead-price-forecast/accuracy/) for the details and the periods
that are harder.

## Features
- **Seven days ahead, per quarter hour.** The forecast starts where the published day-ahead prices end, so you
  always see the full picture: what is known and what is expected.
- **An honest band.** Every quarter hour has a P10–P90 range, calibrated so that about 80 % of the real prices
  fall inside it. You see how sure the forecast is, not just a line.
- **Your price, not the market price.** Add sub-controllers with your own formula, for example
  `(P + 0.02 + 0.09) * 1.21` for purchase or `P - 0.02` for feed-in. Each one gets its own sensor.
- **Tariff variants.** Formulas by start date, time of day and weekday, ready for dynamic grid tariffs.
- **Chart card included.** Solid line for published prices, dashed line for the forecast, a hairline that follows
  your mouse, a "now" marker and a table with the average and cheapest/most expensive hour per day. Zoom in
  to see every quarter-hour step. Nothing to install separately.
- **Reliable.** Two redundant servers with automatic failover; the sensors keep their last forecast when the
  service is down. No account or API key.
- **Made for automations.** The whole series is an attribute of the sensor: plan the battery, the heat pump or
  the dishwasher on the cheapest hours of the coming days. The documentation has [ready-made templates](https://abroeders.github.io/7day-ahead-price-forecast/automations/)
  for the cheapest block of N hours.

![Zoomed in: every quarter hour is a visible step](docs/images/card-zoomed.png)

## Installation
1. *Settings → Marketplace* → search for **Day-ahead price forecast** → **Install** (Home Assistant 2026.11 and
   later). On Home Assistant 2026.3 to 2026.10 use HACS instead: search for it there and download it (or use the
   button below).
2. Restart Home Assistant and add the integration under **Settings → Devices & services**.
3. Add a sub-controller with your formula and put the **Day-ahead price forecast** card on a dashboard.

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=abroeders&repository=7day-ahead-price-forecast&category=integration)

Requires Home Assistant 2026.3 or newer. Currently the Netherlands; more market zones can be added.

<p>
  <img src="docs/images/zone-form.png" alt="Choosing the market zone" width="32%">
  <img src="docs/images/subcontroller-form.png" alt="Adding a sub-controller with a formula" width="32%">
  <img src="docs/images/base-device.png" alt="Service state and accuracy sensors" width="32%">
</p>

## Documentation
**Full user documentation: <https://abroeders.github.io/7day-ahead-price-forecast/>**: installation,
configuration, entities, the chart card, automations, accuracy and FAQ.

## Support

If this project is useful to you, please consider buying me a coffee. Your support lets me keep developing it. Thank you!

<a href="https://www.buymeacoffee.com/abroeders"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy me a coffee" height="50"></a>

## License
Apache-2.0
