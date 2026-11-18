# winds-of-change

Weather-**change** features for relating weather to a personal health log: how much did air pressure, humidity and temperature move over the last 3, 6, 12, 24 or 48 hours, summarised per day, plus helpers that compare those changes with daily symptom ratings.

It exists because people with migraines (and other weather-sensitive conditions) often report that a *change* in the weather sets them off, not the weather itself. A personal log can test that, but only with features built carefully. Naive features invent patterns: the daily temperature swing, the twice-daily pressure tide, or two weather datasets spliced together all produce fake changes.

The core depends only on pandas and numpy. The [health-log-dashboard](https://github.com/jordan-finnell/health-log-dashboard) uses it for its Weather page.

## Install
From [PyPI](https://pypi.org/project/winds-of-change/):

```bash
uv add winds-of-change      # or: pip install winds-of-change
```

## Quick start
Synthetic weather works offline and needs no location:

```python
from datetime import date
import winds_of_change as woc

hourly = woc.SyntheticWeatherSource(seed=1).load_hourly(date(2025, 1, 1), date(2025, 6, 30))
hourly = woc.convert(hourly, woc.Units(temperature="F"))
daily = woc.daily_weather(hourly)  # pressure_change_24h, dew_point_change_6h, ...

# Real weather (Open-Meteo, no API key). Coordinates are rounded to 0.1 degrees first.
source = woc.OpenMeteoSource(woc.Location(latitude=51.5, longitude=0.0))
```

Relate the changes to a daily outcome frame (one row per day, one column per metric):

```python
anoms = woc.anomaly(outcomes)  # vs. your own usual level that month
change = daily["pressure_change_24h"]
bins = woc.change_bins(change)  # steepest 20% of drops / rises
woc.response_by_change(anoms, change, bins, lag=1)  # next-day effect per metric
woc.event_profile(anoms["headache"], change, bins, "drop")  # 2 days before .. 3 after

# Dose-response: five bands from the steepest drops to the steepest rises.
bands = woc.change_bands(change, big=0.1, moderate=0.25)
woc.response_by_band(anoms, change, bands, lag=1)  # mean, 95% CI, days and spells per band
```

For an outlook, use the forecast series (same model, through the next ~2 days), measuring the change within it and ranking it against the archive:

```python
recent = woc.OpenMeteoForecastSource(woc.Location(latitude=51.5, longitude=0.0)).load_recent()
look = woc.outlook(recent, "pressure", now, hours=24, history=hourly)  # .next, .next_percentile
```

From the shell, `woc features --lat 51.5 --lon 0.0 --start 2025-01-01 --end 2025-06-30 -o weather.csv` writes the daily features to a CSV. Use `--synthetic SEED` in place of the coordinates to work offline.

## What the features mean
| Factor | Variable | Why this one |
|---|---|---|
| Pressure | surface pressure, hPa | What the body actually experiences. Sea-level-adjusted pressure adds temperature artefacts in mountain terrain. |
| Humidity | dew point | Moisture in the air. Relative humidity rises and falls with each day's temperature, so its changes partly repeat temperature changes. |
| Temperature | 2 m air temperature | Commonly reported trigger. |

- **`<factor>_change_<w>h`** is the *peak* signed `w`-hour change ending within the day: the biggest move in either direction, with its sign. The definition is the same for every window.
- **De-cycling.** Each hour's typical deviation from the daily mean, over the surrounding 30 days, is removed first. Otherwise a 6-hour window would show a "drop" every afternoon (pressure tide, daytime warming). 24-hour and 48-hour changes compare the same clock time, so de-cycling barely affects them.
- **Days** are local calendar days, and daylight-saving days of 23 or 25 hours are handled.
- **Resolution.** Model data is smooth: good for 3 hours and longer, but it misses sub-3-hour jumps such as thunderstorm pressure spikes.

## Doing the comparison honestly
- **Personal baseline.** `anomaly` compares each day with the mean of the *other* days in the surrounding 29 days. Seasons, treatment changes and life events then don't masquerade as weather effects. This matters because weather variability is itself seasonal.
- **Thresholds:** `change_bins` uses the steepest 20% of drops and of rises over the whole span, so they adapt to the local climate.
- **Dose-response.** `change_bands` splits days into five bands (by default the steepest 10% each way, the next 15% and the middle half), and `response_by_band` gives the mean anomaly per band. A steady slope across the bands says more than a single big-vs-typical gap. Its intervals count days of the same band within 2 days of each other as one spell (clustered standard errors, *t* with spells − 1 degrees of freedom), because weather comes in runs.
- **Lags** shift by calendar days (`lag=1` means symptoms on day D vs. the change on D−1), so gaps in a log can't misalign them.
- **These are associations, not proof.** Day-to-day changes overlap in time, so the day *before* an event is context, not a clean control. Standard errors ignore autocorrelation, except that `response_by_band` clusters by spell, which narrows the gap without closing it. With many metrics × factors × windows × lags, some cells will look clear by chance.

## Data source and privacy
- **Source:** the [Open-Meteo](https://open-meteo.com/) historical archive, pinned to the ECMWF IFS model. It is hourly from 2017 through the end of today (UTC), updated every 6 hours.
- **Outlooks** come from the Open-Meteo forecast API with the same model. The archive's last allowed date is "today" in UTC, so it doesn't always reach 24 hours ahead.
- **One model only.** Different models and endpoints disagree by a few hPa at the same hour, as large as the changes being measured, so `combine` refuses to splice different sources or models.
- **What leaves the machine:** coordinates rounded to 0.1° (about 11 km, comparable to the 9 km model grid), an optional elevation rounded to 10 m, a date range and variable names, with the default urllib User-Agent.
- **What it never does:**
  - sends outcome data anywhere;
  - writes weather to disk;
  - shows coordinates in reprs or error messages.

  Weather for a real place reveals where someone lives, so keep exported CSVs private.
- **Terms:** Open-Meteo's free API is for non-commercial use.
- **Attribution:** weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0), from ECMWF IFS forecasts and analyses.

## Documentation
[`docs/open-meteo/`](https://github.com/jordan-finnell/winds-of-change/tree/trunk/docs/open-meteo) is a reference to Open-Meteo, written for working on or extending this library:

- [Open-Meteo, the service](https://github.com/jordan-finnell/winds-of-change/blob/trunk/docs/open-meteo/open-meteo.md): its APIs, terms, rate limits and call costs, licence and attribution.
- [API reference](https://github.com/jordan-finnell/winds-of-change/blob/trunk/docs/open-meteo/api-reference.md): parameters, responses, time zones, elevation and grid cells, errors and variables.
- [Models and datasets](https://github.com/jordan-finnell/winds-of-change/blob/trunk/docs/open-meteo/models.md): forecast models, reanalyses and ensembles, with `models=` IDs and coverage.
- [How this library uses Open-Meteo](https://github.com/jordan-finnell/winds-of-change/blob/trunk/docs/open-meteo/in-this-library.md): the requests it sends and why, measured differences between endpoints and models, and pitfalls.

## Development
```bash
uv sync
uv run pytest                     # offline: tests block the network
uv run ruff check . && uv run ruff format .
uv run pre-commit run --all-files # ruff, gitleaks, hygiene hooks
uv build
```
To release, bump `version` in `pyproject.toml`, update `CHANGELOG.md`, then tag `vX.Y.Z` and push the tag. CI publishes the wheel and sdist to PyPI and attaches them to a GitHub Release.

## License
MIT. See [LICENSE](https://github.com/jordan-finnell/winds-of-change/blob/trunk/LICENSE).
