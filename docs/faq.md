# FAQ and troubleshooting

**The sensor shows *unknown*.** No price covers the current quarter hour yet; wait for the first refresh. If the
service state sensor says `unavailable`, Home Assistant cannot reach the servers.

**Service state `stale`.** The forecast is older than 3 hours on every server. The last forecast stays visible but
should be treated as unreliable.

**My formula is rejected.** Check that it only uses `P`, numbers, `+ - * /`, parentheses, `min` and `max`, and that
it does not decrease when `P` increases. `-P` and `1 - P` are therefore invalid.

**Which price does the forecast describe?** The bare day-ahead market price in EUR/kWh per quarter hour. Taxes,
surcharges and VAT come from your formula.

**How accurate is it?** See the [accuracy sensors](entities.md#accuracy-sensors). The error grows with the
horizon: day 1 mostly follows the known price level, by day 7 the weather forecast dominates and the band is wide.

**Where does the forecast come from?** From the forecast module of the Lectoraat Smart Energie of MNEXT, see
[Forecast service API](forecast-service.md).
