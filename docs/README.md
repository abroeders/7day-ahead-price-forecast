# 7-Day-Ahead Price Forecast

A Home Assistant integration that forecasts the day-ahead electricity price per hour for the days after the
last known price day, with a P10–P90 uncertainty band. Price components such as energy tax, supplier markup
and VAT are added by configurable sub-controllers, so the forecast entity shows the price you actually pay.

!!! note "Work in progress"
    The integration is being designed. See the [designs](design/) and the [architecture](architecture.md). The forecast comes from the forecast module of the Lectoraat Smart Energie of MNEXT.

| Page | What |
|---|---|
| [Architecture](architecture.md) | code structure with UML diagrams, for developers |
| [Designs](design/) | the design of each feature, as approved before it was built |

## Support

If this project is useful to you, please consider buying me a coffee. Your support lets me keep developing it. Thank you!

<a href="https://www.buymeacoffee.com/abroeders"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy me a coffee" height="50"></a>
