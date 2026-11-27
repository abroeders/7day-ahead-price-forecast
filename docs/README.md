# Day-Ahead Price Forecast

A Home Assistant integration with a chart card, on top of a public, read-only API that forecasts the day-ahead electricity price for the **7 days after the last known
price day**, every 15 minutes, with a **P10–P90 uncertainty band**. It is the forecast module of the Lectoraat
Smart Energie of MNEXT. No account or API key is needed.

| Page | What |
|---|---|
| [Installation](installation.md), [Configuration](configuration.md), [Entities](entities.md), [FAQ](faq.md) | the Home Assistant integration |
| [Price chart card](card.md) | the Lovelace card: published prices, dashed forecast, P10–P90 band, hairline and day table |
| [Forecast service API](forecast-service.md) | endpoints, response fields, caching and failover, example calls, and how to read the forecast |

Quick start:

```bash
curl -s --compressed "https://day-ahead-price-forecast.sendlab.nl/v1/forecast?zone=NL"
```
