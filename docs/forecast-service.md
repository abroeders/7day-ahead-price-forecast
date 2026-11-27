# Forecast service API

For developers and integrators who read the forecast over HTTP. The Home Assistant integration is one such client;
the forecast itself comes from the forecast module of the Lectoraat Smart Energie of MNEXT.
The contract below is **version 1**; new fields may appear without a version change, so ignore fields you do not know.

## What you get
For a bidding zone (today: `NL`) the service returns:

- **`known`**: the day-ahead prices that are already published (the last two days);
- **`forecast`**: the expected price for the **7 days after the last known day**, every **15 minutes**, with a
  **P10–P90 band** (the real price should fall inside the band about 8 times out of 10);
- **`accuracy`**: how far earlier forecasts were off, per horizon.

All prices are the **bare EPEX day-ahead market price in EUR/kWh**: no supplier margin, no energy tax, no VAT, no
grid costs. Add your own surcharges and VAT on your side. Times are ISO 8601 with the local UTC offset
(`+01:00` / `+02:00`, so DST days have 92 or 100 quarter hours).

## Endpoints
Read-only JSON over HTTPS, no account, no API key. Two independent servers serve the same contract:

| Node | Base URL |
|---|---|
| `a` | `https://day-ahead-price-forecast.sendlab.nl` |
| `b` | `https://day-ahead-price-forecast.jrcb.nl` |

The examples use node `a`; any request works on either node.

| Request | Answer |
|---|---|
| `GET /v1/forecast?zone=NL` | the forecast below. `zone` is optional (default: the first zone) and case-insensitive |
| `GET /v1/zones` | the zones served, e.g. `["NL"]` |
| `GET /v1/status` | node, version, health, forecast age, last training, data coverage |
| `GET /healthz` | `{"ok": true}` with `200` when a fresh forecast can be served, otherwise `503` |

Errors are JSON `{"error": "..."}`: `404` unknown zone or path, `503` no forecast yet (a node that just started).
Rate limit: 60 requests per minute per IP; you never need more than one request per 15 minutes.

### `/v1/forecast` response
```json
{
  "schema": 1,
  "node": "a",
  "zone": "NL",
  "unit": "EUR/kWh",
  "created": "2026-11-27T12:15:20+00:00",
  "trained": "2026-11-27T03:32:39+00:00",
  "stale": false,
  "known_until": "2026-11-28T00:00:00+01:00",
  "known": [
    {"start": "2026-11-26T00:00:00+01:00", "end": "2026-11-26T00:15:00+01:00", "value": 0.102}
  ],
  "forecast": [
    {"start": "2026-11-28T00:00:00+01:00", "end": "2026-11-28T00:15:00+01:00",
     "value": 0.148, "p10": 0.111, "p90": 0.203, "h": 1}
  ],
  "accuracy": {"mae": {"1": 0.021, "2": 0.027}, "bias": {"1": 0.002, "2": 0.004},
               "coverage": {"1": 0.79, "2": 0.78}, "hours": 600}
}
```

| Field | Meaning |
|---|---|
| `schema` | contract version (`1`); repeated for clients that cache |
| `node` | which server answered (`a`, `b`); informational |
| `created` / `trained` | when this forecast was computed / when its models were trained |
| `stale` | `true` when the forecast is older than 3 hours: treat it as unreliable and try another server |
| `known_until` | end of the last published day; the forecast starts here |
| `known[]` | published prices, 192 quarter hours (two days) |
| `forecast[]` | 672 quarter hours: `value` (median), `p10`, `p90` and `h` |
| `h` | days after the last known day, `1`..`7`. `h=1` is the day after `known_until` |
| `accuracy` | over the last `hours` realised hours: `mae` mean absolute error (EUR/kWh), `bias` mean (forecast − actual), `coverage` share of actual prices inside P10–P90, each per `h` |

`value`, `p10` and `p90` always satisfy `p10 <= value <= p90`.

## Caching and failover
Answers carry `ETag` and `Cache-Control: max-age=300`. Send the ETag back as `If-None-Match`; `304 Not Modified`
means nothing changed. Send `Accept-Encoding: gzip`: the body is about 40 kB uncompressed.

The forecast is served by independent servers with the same contract. Recommended client behaviour (the Home Assistant integration does this):

1. Shuffle the server list for each refresh and try the first.
2. Go to the next server on a connection error, a timeout (5 s), HTTP `>= 500`, invalid JSON, an unknown `schema` or `"stale": true`.
3. If all fail, keep showing your last forecast and mark it stale.

Poll every 15 minutes at most. New day-ahead prices appear around 13:00–14:00 local time, after which the
service refreshes within a quarter of an hour.

## Examples

### curl
```bash
# the whole forecast, compressed
curl -s --compressed "https://day-ahead-price-forecast.sendlab.nl/v1/forecast?zone=NL" -o forecast.json

# only what changed: save the ETag, ask again with it
curl -si --compressed "https://day-ahead-price-forecast.sendlab.nl/v1/forecast?zone=NL" | grep -i '^etag'
curl -si --compressed -H 'If-None-Match: "<etag>"' "https://day-ahead-price-forecast.sendlab.nl/v1/forecast?zone=NL" | head -1   # HTTP/2 304

# which zones, is the node healthy, how old is the forecast
curl -s https://day-ahead-price-forecast.sendlab.nl/v1/zones                         # ["NL"]
curl -s https://day-ahead-price-forecast.sendlab.nl/healthz                          # {"ok":true}
curl -s https://day-ahead-price-forecast.sendlab.nl/v1/status | jq '{node, version, healthy, zones}'
```

### jq: the cheapest quarter hours of the next day
```bash
curl -s --compressed "https://day-ahead-price-forecast.sendlab.nl/v1/forecast?zone=NL" |
  jq -r '[.forecast[] | select(.h == 1)] | sort_by(.value) | .[:4][]
         | "\(.start)  \(.value) EUR/kWh  (\(.p10)..\(.p90))"'
```

### Python (standard library only), with failover
```python
import gzip
import json
import random
import urllib.request

SERVERS = ["https://day-ahead-price-forecast.sendlab.nl", "https://day-ahead-price-forecast.jrcb.nl"]


def fetch_forecast(zone: str = "NL") -> dict:
    servers = random.sample(SERVERS, k=len(SERVERS))  # spread the load
    for base in servers:
        try:
            request = urllib.request.Request(f"{base}/v1/forecast?zone={zone}",
                                             headers={"Accept-Encoding": "gzip"})
            with urllib.request.urlopen(request, timeout=5) as response:
                body = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
            data = json.loads(body)
            if data.get("schema") == 1 and not data.get("stale"):
                return data
        except (OSError, ValueError):  # network error, HTTP error, invalid JSON
            continue
    raise RuntimeError("no server gave a fresh forecast")


def all_in(price: float, surcharge: float = 0.11, vat: float = 0.21) -> float:
    """Bare market price to consumer price: your own surcharges and VAT."""
    return (price + surcharge) * (1 + vat)


forecast = fetch_forecast()
day2 = [p for p in forecast["forecast"] if p["h"] == 2]
best = min(day2, key=lambda p: p["value"])
print(f'cheapest quarter on day 2: {best["start"]} at {all_in(best["value"]):.3f} EUR/kWh '
      f'(band {all_in(best["p10"]):.3f} to {all_in(best["p90"]):.3f})')
```

### JavaScript
```javascript
const res = await fetch("https://day-ahead-price-forecast.sendlab.nl/v1/forecast?zone=NL");
if (!res.ok) throw new Error(`${res.status} ${(await res.json()).error}`);
const { forecast, known_until } = await res.json();
const hourly = Object.values(Object.groupBy(forecast, p => p.start.slice(0, 13)))
  .map(q => ({ hour: q[0].start, value: q.reduce((s, p) => s + p.value, 0) / q.length }));
```

### Error answers
```
GET /v1/forecast?zone=XX   ->  404 {"error":"unknown zone: XX"}
GET /v1/forecast           ->  503 {"error":"no forecast available yet"}   (node just started)
```

## How the forecast works
The prices for the next day are fixed by the EPEX day-ahead auction around 13:00. For the days after that the
service **predicts** them from what has driven prices in the past:

- the **calendar** (weekday, season, public holidays);
- the **recent price level** and daily shape;
- **fuel prices** (gas and CO2), which set the price in most hours;
- the **weather forecast** (wind, sun, temperature) for the coming week, which is the main driver of the
  difference between a cheap and an expensive day.

The model is retrained regularly and the forecast is recomputed after every data refresh.

### Reading the numbers
- `value` is the **median**: half of the time the real price is lower, half higher. Use the band for decisions
  that depend on risk (for example, only start a heat pump at a time when even `p90` is acceptable).
- The band is **calibrated**: about 80 % of the real prices should fall inside P10–P90. The `coverage` figures in
  `accuracy` let you check this on live data.
- **Accuracy falls with the horizon.** Day 1 mostly follows the known price level; by day 7 the weather forecast
  dominates and the band is much wider. Compare `accuracy.mae` per `h`.
- Individual quarter hours are noisy; **averages per hour or per day are more reliable** than a single slot.
- Events nobody can foresee (outages, market incidents, fuel price shocks) show up as errors outside the band.
- `bias` close to 0 means no systematic over- or underestimation.

## Good to know
- This is a forecast, not a promise and not financial advice.
- Servers work independently, so their answers can differ slightly (`created`, rounding); all are valid.
- Prices are for the whole bidding zone, not for one supplier, region or contract.
- Breaking changes will get a new path (`/v2/...`); `/v1` stays available until clients have moved.
