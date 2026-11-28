"""Constants of the Day-ahead price forecast integration."""

from datetime import timedelta

DOMAIN = "day_ahead_price_forecast"

DEFAULT_SERVERS = (
    "https://day-ahead-price-forecast.sendlab.nl",
    "https://day-ahead-price-forecast.jrcb.nl",
)

CONF_ZONE = "zone"
CONF_FORMULA = "formula"
CONF_ALLOW_NEGATIVE = "allow_negative"
CONF_VARIANTS = "variants"
CONF_FORECAST_DAYS = "forecast_days"
DEFAULT_FORECAST_DAYS = 7
MAX_FORECAST_DAYS = 7

SUBENTRY_CONTROLLER = "controller"
DEFAULT_FORMULA = "P"
UPDATE_INTERVAL = timedelta(minutes=30)
