# Changelog

## v0.2.0
- **`OpenMeteoForecastSource`:** the forecast API with the same model (last 31 days plus the next 3). The archive's last allowed date is "today" in UTC, so in many time zones it doesn't reach 24 h past now. Outlooks now come from this series. It is labelled as a separate source, so `combine` refuses to splice it into archive history.
- **`outlook(..., history=)`:** measures changes within one series and ranks them against a longer history.

## v0.1.0
First release.

- **Sources:** the Open-Meteo archive pinned to ECMWF IFS (hourly, 2017 to the end of today UTC), offline synthetic weather, and a seam guard (`combine`) that refuses to splice different sources or models.
- **Factors:** surface pressure, dew point and temperature, with °C/°F conversion.
- **Features:** de-cycled `w`-hour changes (default 3/6/12/24/48 h) summarised per local day as the peak signed change, and next/last-window outlooks with percentiles.
- **Analysis:** leave-one-out personal baseline, big-drop/typical/big-rise bins, day-based lags, per-bin response tables and event profiles.
- **CLI:** `woc features` exports daily features to CSV.
