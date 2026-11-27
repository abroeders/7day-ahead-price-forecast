# Architecture

Code structure of the integration, as UML (Mermaid). The forecast itself is made by the forecast module of the
Lectoraat Smart Energie of MNEXT; the integration only reads it.

## Classes
```mermaid
classDiagram
  class ForecastProvider {
    <<interface>>
    +fetch(zone) Forecast
  }
  class RemoteProvider {
    -servers: list~str~
    +fetch(zone) Forecast
  }
  class Forecast {
    +points: list~PricePoint~
    +known: list~PricePoint~
    +accuracy: dict
  }
  class PricePoint {
    +start
    +end
    +value
    +p10
    +p90
  }
  class Formula {
    +evaluate(p) float
    +is_monotonic() bool
  }
  class FormulaParser {
    <<function parse>>
    +parse(text) Formula
  }
  class FormulaError {
    +message
    +position
  }
  class PriceCalculator {
    -variants: list~FormulaVariant~
    +allow_negative: bool
    +apply(forecast) Forecast
  }
  class FormulaVariant {
    +valid_from
    +start_time
    +end_time
    +weekdays
    +formula
    +matches(start) bool
  }
  class ForecastCoordinator {
    <<base controller>>
    +zone: str
    +node: str
    -provider: ForecastProvider
    +refresh()
  }
  class ForecastSensor {
    <<sub-controller, config subentry>>
    -calculator: PriceCalculator
    +native_value: current price
    +attributes: known, forecast
  }
  class ServiceStateSensor {
    +native_value: ok / stale / unavailable
  }
  class AccuracySensor {
    <<diagnostic>>
    +metric: mae / bias / coverage
    +native_value: mean over the days
    +attributes: per_day, hours
  }
  class ControllerSubentryFlow {
    +validates formula
  }
  class ZonePlugin {
    <<interface>>
    +code
    +name
    +country
    +timezone
    +currency
    +is_valid_price(value) bool
  }
  class NetherlandsZone
  ZonePlugin <|.. NetherlandsZone
  ForecastProvider <|.. RemoteProvider
  ForecastCoordinator --> ForecastProvider
  ForecastSensor --> ForecastCoordinator
  ServiceStateSensor --> ForecastCoordinator
  AccuracySensor --> ForecastCoordinator
  ControllerSubentryFlow ..> FormulaParser
  ForecastSensor --> FormulaVariant
  FormulaVariant --> FormulaParser
  FormulaParser ..> Formula
  FormulaParser ..> FormulaError
  PriceCalculator --> FormulaVariant
  ForecastSensor --> PriceCalculator
  ForecastProvider ..> Forecast
  AccuracySensor ..> Forecast
  Forecast --> PricePoint
```

## Refresh with failover
```mermaid
sequenceDiagram
  participant C as ForecastCoordinator
  participant Sensors as Forecast sensors
  participant P as RemoteProvider
  participant S1 as Server (picked at random)
  participant S2 as Other server
  C->>P: fetch(zone)
  P->>P: shuffle server list
  P->>S1: GET forecast
  alt answers and is fresh
    S1-->>P: forecast
  else error, time-out or too old
    P->>S2: GET forecast
    S2-->>P: forecast
  end
  P-->>C: Forecast
  C-->>Sensors: listeners notified
  Sensors->>Sensors: each forecast sensor applies its formula
```

## Sub-controller lifecycle
A sub-controller is a config subentry of the base controller entry. The config flow offers *Add sub-controller*
(name, formula, "prices can be negative") followed by a menu to add variants (formula plus optional start date,
time range and weekdays) and finish; every formula is parsed when submitted and rejected when invalid or
decreasing. Variants are stored as JSON in the subentry and turned into `FormulaVariant` objects by the sensor. Changing a subentry reloads the entry, which rebuilds the sensors.

```mermaid
stateDiagram-v2
  [*] --> Form: add / reconfigure
  Form --> Form: invalid formula
  Form --> Stored: valid
  Stored --> Loaded: entry reload
  Loaded --> Stored: reconfigure
  Stored --> [*]: delete
```

## Lovelace card
The card is a plain JavaScript web component served by the integration. `async_setup` registers the static path
and loads the module in every dashboard; the card reads the forecast sensor's attributes and draws an SVG.
Pure chart logic lives in `chart-core.js` (tested with `node --test`).

```mermaid
classDiagram
  class DayAheadPriceForecastCard {
    +setConfig(config)
    +hass
    -draw()
    -onPointerMove(event)
    -onWheel(event)
  }
  class DayAheadPriceForecastCardEditor
  class ChartCore {
    <<module>>
    +cutForecast()
    +yScale()
    +stepPath()
    +bandPolygon()
    +dayStats()
    +nearestPoint()
    +visibleSlice()
    +clampView()
    +zoomView()
    +panView()
    +xTicks()
  }
  DayAheadPriceForecastCard ..> ChartCore
  DayAheadPriceForecastCard --> DayAheadPriceForecastCardEditor : getConfigElement
```

```mermaid
sequenceDiagram
  participant HA as Home Assistant
  participant Card
  participant Core as chart-core
  participant U as User
  HA->>Card: hass (sensor changed)
  Card->>Core: toPoints, cutForecast(forecast_days)
  Card->>Core: yScale, stepPath, bandPolygon, dayStats
  Card->>Card: draw SVG and table
  U->>Card: pointermove
  Card->>Core: nearestPoint(time)
  Card->>Card: move hairline, show tooltip
  U->>Card: Ctrl+wheel, pinch, drag or buttons
  Card->>Core: zoomView / panView, clampView
  Card->>Core: visibleSlice, yScale, xTicks
  Card->>Card: redraw the window
```

## Design patterns
| Pattern | Where |
|---|---|
| Strategy | `ForecastProvider`, `ZonePlugin` |
| Interpreter | `FormulaParser` |
| Module (pure functions) | `chart-core.js`, the logic of the card |
| Facade | `ForecastCoordinator` (one refresh shared by all sub-controllers) |
| Chain of fallbacks | server list in `RemoteProvider`, shuffled per refresh (load spreading) |
