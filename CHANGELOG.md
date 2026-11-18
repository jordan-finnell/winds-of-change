# Changelog

## v0.3.0
- **Dose-response:** `change_bands` splits daily changes into five bands from the steepest drops to the steepest rises (by default the steepest 10% each way, the next 15%, and the middle half; the outer bands are the same days as `change_bins(q=big)`). `response_by_band` gives each metric's mean anomaly per band with a 95% interval. Intervals are clustered by spell (days of one band within 2 days of each other), because weather comes in runs.

## v0.2.1
- Published to [PyPI](https://pypi.org/project/winds-of-change/): `uv add winds-of-change`. No code changes.

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
