# 7-Day-Ahead Price Forecast

[![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-ffdd00?logo=buymeacoffee&logoColor=black)](https://www.buymeacoffee.com/abroeders)

Home Assistant integration and Lovelace card that forecast day-ahead electricity prices up to seven days
ahead, with an uncertainty band.

## Features
- Forecast of the day-ahead electricity price per quarter hour for the 7 days after the last known price day,
  with a P10–P90 band.
- Sub-controllers with your own formula (surcharges, VAT, variants) on the market price.
- Lovelace chart card: published prices as a solid line, the forecast dashed with its band, a hairline for
  analysis and a per-day table. Shipped with the integration.

## Documentation
**Full user documentation: <https://abroeders.github.io/7day-ahead-price-forecast/>**: installation,
configuration, entities, the chart card, FAQ and the forecast service API.

## Support

If this project is useful to you, please consider buying me a coffee. Your support lets me keep developing it. Thank you!

<a href="https://www.buymeacoffee.com/abroeders"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy me a coffee" height="50"></a>

## License
Apache-2.0
