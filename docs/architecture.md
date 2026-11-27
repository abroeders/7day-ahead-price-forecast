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
  class SubController {
    +variants: list~FormulaVariant~
    +allow_negative: bool
    +apply(forecast) Forecast
  }
  class BaseController {
    +zone: ZonePlugin
    +provider: ForecastProvider
    +refresh()
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
  BaseController --> ForecastProvider
  BaseController --> ZonePlugin
  BaseController "1" --> "*" SubController
  SubController --> FormulaVariant
  FormulaVariant --> FormulaParser
  FormulaParser ..> Formula
  FormulaParser ..> FormulaError
  PriceCalculator --> FormulaVariant
  SubController --> PriceCalculator
  ForecastProvider ..> Forecast
  Forecast --> PricePoint
```

## Refresh with failover
```mermaid
sequenceDiagram
  participant C as Coordinator
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
  C->>C: each sub-controller applies its formula
```

## Design patterns
| Pattern | Where |
|---|---|
| Strategy | `ForecastProvider`, `ZonePlugin` |
| Interpreter | `FormulaParser` |
| Facade | `BaseController` |
| Chain of fallbacks | server list in `RemoteProvider`, shuffled per refresh (load spreading) |
