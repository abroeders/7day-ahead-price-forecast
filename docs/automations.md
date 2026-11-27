# Use the forecast in Home Assistant

Every [forecast sensor](entities.md#forecast-sensor) carries the whole price series as attributes: `known` (the
published prices) and `forecast` (the expected prices with `p10` and `p90`), each a list of quarter hours with
`start`, `end` and `value`. That is all you need to find cheap moments: put the logic in a template and use the
result in an automation, script or dashboard.

The examples use a sensor called `sensor.purchase`; replace it with the entity of your own sub-controller. Prices
are in the unit of that sensor (EUR/kWh).

!!! note
    Prices that are already published (`known`) are certain; the `forecast` is an expectation and changes with
    every refresh (every 30 minutes). Plan flexible loads on the forecast, but let an automation that must not
    be wrong rely on `known` only (see [Only published prices](#only-published-prices)).

## The cheapest quarter hour
Try this in **Developer tools → Template**:

```jinja
{% set data = (state_attr('sensor.purchase', 'known') or []) + (state_attr('sensor.purchase', 'forecast') or []) %}
{% set now_ts = now().timestamp() %}
{% set ns = namespace(items=[]) %}
{% for p in data if as_timestamp(p.end) > now_ts %}
  {% set ns.items = ns.items + [p] %}
{% endfor %}
{% set cheapest = ns.items | sort(attribute='value') | first %}
{{ cheapest.start }}: {{ cheapest.value }}
```

The `for` loop keeps the quarter hours that have not ended yet, so the past is ignored. `sort` puts the cheapest
first. For the 8 cheapest quarter hours use `(ns.items | sort(attribute='value'))[:8]` instead of `first`.

## The cheapest block of several hours
Heating a boiler, charging a car or running a dishwasher needs a *continuous* block. This template looks at all
blocks of 3 hours (12 quarter hours) within the next 2 days and returns the start of the one with the lowest
average price:

```jinja
{% set n = 12 %}
{% set now_ts = now().timestamp() %}
{% set data = (state_attr('sensor.purchase', 'known') or []) + (state_attr('sensor.purchase', 'forecast') or []) %}
{% set ns = namespace(items=[], best=none, best_avg=none) %}
{% for p in data if as_timestamp(p.end) > now_ts and as_timestamp(p.start) < now_ts + 86400 * 2 %}
  {% set ns.items = ns.items + [p] %}
{% endfor %}
{% for i in range(0, ns.items | length - n + 1) %}
  {% set avg = ns.items[i:i + n] | map(attribute='value') | sum / n %}
  {% if ns.best_avg is none or avg < ns.best_avg %}
    {% set ns.best = ns.items[i] %}
    {% set ns.best_avg = avg %}
  {% endif %}
{% endfor %}
{{ ns.best.start if ns.best else 'unknown' }}
```

Change `n` for another length (4 quarter hours per hour) and `86400 * 2` (seconds) for another search period. To
look further than the published prices, use up to `86400 * 7`.

### As a sensor
Put it in `configuration.yaml` (or a template package) to get a timestamp sensor you can show and trigger on:

```yaml
template:
  - sensor:
      - name: Cheapest 3 hour block
        unique_id: cheapest_3_hour_block
        device_class: timestamp
        state: >
          {% set n = 12 %}
          {% set now_ts = now().timestamp() %}
          {% set data = (state_attr('sensor.purchase', 'known') or []) + (state_attr('sensor.purchase', 'forecast') or []) %}
          {% set ns = namespace(items=[], best=none, best_avg=none) %}
          {% for p in data if as_timestamp(p.end) > now_ts and as_timestamp(p.start) < now_ts + 86400 * 2 %}
            {% set ns.items = ns.items + [p] %}
          {% endfor %}
          {% for i in range(0, ns.items | length - n + 1) %}
            {% set avg = ns.items[i:i + n] | map(attribute='value') | sum / n %}
            {% if ns.best_avg is none or avg < ns.best_avg %}
              {% set ns.best = ns.items[i] %}
              {% set ns.best_avg = avg %}
            {% endif %}
          {% endfor %}
          {{ ns.best.start if ns.best else 'unknown' }}
```

### Start a device at the cheapest block
```yaml
automation:
  - alias: Boiler in the cheapest 3 hours
    triggers:
      - trigger: time
        at: sensor.cheapest_3_hour_block
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.boiler
      - delay: "03:00:00"
      - action: switch.turn_off
        target:
          entity_id: switch.boiler
```

The `time` trigger accepts a timestamp sensor and follows it when it changes. Keep in mind that the sensor looks
from *now* on: once the block has started, the sensor moves on to the next cheapest block, which is why the
automation above switches off after a fixed delay instead of waiting for the sensor.

## A script for the cheapest moment of the coming week
A reusable script that returns the cheapest block within the published prices and the forecast. Create it in
**Settings → Automations & Scenes → Scripts → Add script → Edit in YAML**. It has two fields: the length of the
block in hours (`hours`) and how many days ahead to look (`days`, at most 7):

```yaml
script:
  cheapest_moment:
    alias: Cheapest moment
    description: Finds the cheapest block of consecutive hours in the coming days.
    fields:
      hours:
        name: Block length (hours)
        default: 3
        selector:
          number: { min: 0.25, max: 24, step: 0.25, unit_of_measurement: h }
      days:
        name: Days ahead
        default: 7
        selector:
          number: { min: 1, max: 7, mode: box }
    sequence:
      - variables:
          result: >
            {% set n = (hours | float(3) * 4) | round(0) | int %}
            {% set now_ts = now().timestamp() %}
            {% set until = now_ts + 86400 * (days | int(7)) %}
            {% set data = (state_attr('sensor.purchase', 'known') or []) + (state_attr('sensor.purchase', 'forecast') or []) %}
            {% set ns = namespace(items=[], best=none, best_avg=none) %}
            {% for p in data if as_timestamp(p.end) > now_ts and as_timestamp(p.start) < until %}
              {% set ns.items = ns.items + [p] %}
            {% endfor %}
            {% for i in range(0, ns.items | length - n + 1) %}
              {% set avg = ns.items[i:i + n] | map(attribute='value') | sum / n %}
              {% if ns.best_avg is none or avg < ns.best_avg %}
                {% set ns.best = i %}
                {% set ns.best_avg = avg %}
              {% endif %}
            {% endfor %}
            {% if ns.best is none %}
              {{ {'found': false} }}
            {% else %}
              {{ {
                'found': true,
                'start': ns.items[ns.best].start,
                'end': ns.items[ns.best + n - 1].end,
                'average': ns.best_avg | round(4),
                'is_forecast': ns.items[ns.best:ns.best + n] | selectattr('p10', 'defined') | list | length > 0
              } }}
            {% endif %}
      - stop: Done
        response_variable: result
```

Run it from **Developer tools → Actions** (`script.cheapest_moment`) to see the response, or call it from an
automation and use the answer:

```yaml
actions:
  - action: script.cheapest_moment
    data:
      hours: 4
      days: 7
    response_variable: cheapest
  - condition: template
    value_template: "{{ cheapest.found }}"
  - action: notify.mobile_app_phone
    data:
      message: >
        Cheapest 4 hours this week: {{ cheapest.start | as_datetime | as_local }}
        ({{ (cheapest.average * 100) | round(1) }} ct/kWh).
```

The response holds `start`, `end`, `average` (in the unit of the sensor) and `is_forecast`, which is `true` when
the block includes forecast quarter hours and therefore may still move. Published prices cover only about one
day, so for a longer look ahead the answer is mostly based on the forecast; run the script again after every
refresh, or after about 13:00 when the next day is published.

## Below a price limit
A binary sensor that is on while the current quarter hour is cheaper than the average of the next 24 hours:

```yaml
template:
  - binary_sensor:
      - name: Price below average
        state: >
          {% set now_ts = now().timestamp() %}
          {% set data = (state_attr('sensor.purchase', 'known') or []) + (state_attr('sensor.purchase', 'forecast') or []) %}
          {% set ns = namespace(values=[]) %}
          {% for p in data if as_timestamp(p.end) > now_ts and as_timestamp(p.start) < now_ts + 86400 %}
            {% set ns.values = ns.values + [p.value] %}
          {% endfor %}
          {{ ns.values | length > 0 and states('sensor.purchase') | float(0) < ns.values | average }}
```

## Only published prices
Use `known` alone for decisions that must not depend on a forecast, for example tomorrow's prices after about
13:00 when the new day has been published:

```jinja
{{ state_attr('sensor.purchase', 'known') | map(attribute='value') | list | min }}
```

`known_until` tells you where the published prices end.

## Planning with the band
Each forecast quarter hour has `p10` and `p90`: 80 % of the real prices fall between them. If you want the
block that is cheap *even when the forecast is too low*, rank on `p90` instead of `value`. Published quarter
hours have no band, so fall back to `value` there. Change the first loop of the
[block template](#the-cheapest-block-of-several-hours) so that it stores the ranking value:

```jinja
{% for p in data if as_timestamp(p.end) > now_ts and as_timestamp(p.start) < now_ts + 86400 * 2 %}
  {% set ns.items = ns.items + [{'start': p.start, 'value': p.p90 | default(p.value, true)}] %}
{% endfor %}
```

For a cheap block that is *probably* even cheaper, look at `p10` the same way.

## See it on the dashboard
Show the same series with the [price chart card](card.md); zoom in to the 3-hour block you are planning for.
