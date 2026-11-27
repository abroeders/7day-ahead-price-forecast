# Installation

## Requirements
- Home Assistant 2026.3 or newer.
- Internet access from Home Assistant to the forecast service (see [Forecast service API](forecast-service.md)).
  No account or API key is needed.

## Install with HACS
1. Open HACS, choose **Custom repositories** and add `https://github.com/abroeders/7day-ahead-price-forecast`
   as category *Integration*.
2. Search for **Day-ahead price forecast**, download it and restart Home Assistant.

## Set up
1. Go to **Settings → Devices & services → Add integration** and choose **Day-ahead price forecast**.
2. Choose the market zone (for now only the Netherlands). This creates the *base controller*: it fetches the
   bare market price forecast and shares it with all sub-controllers.
3. Add one or more [sub-controllers](configuration.md#sub-controllers) to get price entities.

Each zone can be added once.

## Show the forecast on a dashboard
The [price chart card](card.md) is installed with the integration. Add a sub-controller first, then add the card
to a dashboard and choose its forecast sensor. No resource has to be added by hand.

## Updating
Update through HACS and restart Home Assistant. Reload the browser page afterwards so the dashboard loads the new
version of the card.

![Choosing the market zone](images/zone-form.png)

![The integration page with the base controller](images/integration-page.png)
