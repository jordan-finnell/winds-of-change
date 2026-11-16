# How this library uses Open-Meteo

This page covers what winds-of-change sends, why each choice was made, what the live API actually does with it, and what to keep in mind before changing any of it. The general API behaviour is in the [API reference](api-reference.md), and the models are in [Models and datasets](models.md).

## The two requests
Both sources live in `src/winds_of_change/sources.py` and use `urllib` with the default User-Agent.

| | `OpenMeteoSource` | `OpenMeteoForecastSource` |
|---|---|---|
| Endpoint | `archive-api.open-meteo.com/v1/archive` | `api.open-meteo.com/v1/forecast` |
| Purpose | history, from 2017 to today UTC | outlooks: the last 31 days plus the next 3 |
| Range | `start_date`, `end_date` (clamped to 2017-01-01 … tomorrow UTC) | `past_days=31&forecast_days=3` (limits enforced in code: 0–92 and 1–16) |
| Variables | `hourly=surface_pressure,dew_point_2m,temperature_2m` (from `FACTORS`) | same |
| Model | `models=ecmwf_ifs` | `models=ecmwf_ifs` |
| Time | `timeformat=unixtime`, `timezone=<Location.timezone or auto>` | same |
| Elevation | `elevation=<Location.elevation>` if set | same |
| `attrs["source"]` | `open-meteo` | `open-meteo-forecast` |
| Typical cost ([how costs are counted](open-meteo.md#rate-limits-and-call-costs)) | 1 call per 2 weeks × 0.3; about 77 for 2017 to the end of 2026 | 1.0 |

`parse_open_meteo` turns either response into the standard hourly frame. It converts the unixtime stamps to UTC and then to the returned IANA `timezone`, so DST is handled. It also accepts both plain (`surface_pressure`) and model-suffixed (`surface_pressure_ecmwf_ifs`) column names.

## Why these choices

### One model: `ecmwf_ifs`
- **It is the only dataset with all of these at once:**
  - hourly steps, which 3-hour and 6-hour windows need;
  - a 9 km grid;
  - continuous data from 2017;
  - **no delay**: the archive is updated every 6 hours and reaches the end of today UTC;
  - the same model in the Forecast API, so outlooks can be ranked against history.
- **ERA5 falls short:** it is consistent back to 1940, but it is coarser (25 km) and about 5 days behind. A dashboard would show a gap for the most recent days.
- **Why not `best_match`:** it is a blend. In the archive it matched `ecmwf_ifs` exactly at Greenwich in 2025, but in the Forecast API it is a different blend (a different grid cell, and other models at short lead times), and its make-up can change at any time. Pinning the model makes every series traceable to one model.

### Surface pressure, not sea-level pressure
- **What the body feels** is surface pressure.
- **Sea-level pressure is reduced** with an assumed temperature profile, which adds artefacts in mountain terrain.
- **Surface pressure depends on the downscaling elevation**, about 12 hPa per 100 m ([observed](api-reference.md#location-grid-cells-elevation-and-downscaling)). A constant offset cancels out of every change within one series, but it must be the same offset in every series being compared. That's why `Location.elevation` goes into both sources unchanged.
- **Elevation precision:** `Location` rounds it to 10 m, so the level moves by at most 5 m (about 0.6 hPa) and the changes not at all.

### Rounded coordinates
- **Rounding:** `Location` rounds coordinates to 0.1° (about 11 km, roughly one `ecmwf_ifs` grid cell) before anything leaves the machine.
- **What Open-Meteo picks anyway:** a grid cell near that point (`cell_selection=land` by default), and the reported coordinates are the cell centre. Rounding moves the point by at most about 6 km at mid-latitudes, which can mean a neighbouring 9 km cell.
- **Elevation then matters more:** pass the real elevation so the downscaling reflects where the person is, not the rounded point, which may land on a slope.

### Unixtime and the returned time zone
ISO 8601 timestamps carry a single fixed UTC offset per response, so a range that crosses a DST change would be off by an hour on one side of it. Unixtime plus a `tz_convert` to the returned zone avoids that, and the features' local days of 23 and 25 hours depend on it.

### The archive's last date
- **The limit:** the archive accepts `end_date` up to today's date in UTC. **Observed:** at 00:51 UTC on 16 November it said "out of allowed range from 1940-01-01 to 2026-11-16", and `ecmwf_ifs` already had the whole of 16 November, from the latest run's first hours.
- **The retry:** `OpenMeteoSource.load_hourly` asks for up to tomorrow (UTC). On HTTP 400 containing "out of allowed range" it takes the last ISO date in the message and retries once.
- **If Open-Meteo rewords that message,** the retry stops working and loads fail with "weather service rejected the date range". A test with canned JSON covers the current wording.
- **Local time:** because the limit is in UTC, a time zone ahead of UTC may not get its whole local "today", and one behind it may get some of tomorrow. That's one reason outlooks use the Forecast API instead.

### Outlooks come from the Forecast API, and are never spliced
- **Why a second source:** the archive's horizon is the end of today UTC, which in many time zones and at many times of day is less than 24 h ahead. The Forecast API with the same model always reaches past now.
- **What the outlook measures:** the "next 24 h" change, computed **within the forecast series**: forecast value at now + 24 h minus forecast value at now.
- **What it's ranked against:** a percentile of the archive's own 24 h changes (`outlook(..., history=)`).
- **What it never does:** splice forecast hours onto the archive (`combine` refuses, because the `source` attrs differ).
- **31 past days** give `decycle` its 30-day window, so even short-window changes in the outlook are de-cycled.

## Measured differences between endpoints and models
Measured on 16 November 2026 for Greenwich (51.5, 0.0), with no `elevation` (DEM height, 4 m). For each pair of hourly `surface_pressure` series over the same hours, the table gives the mean, standard deviation and largest absolute difference, plus the largest difference between their 24 h changes:

| Compared with the archive's `ecmwf_ifs` | Period | Mean | SD | Max | Max of 24 h change |
|---|---|---|---|---|---|
| Historical Forecast, `ecmwf_ifs` | Jan–Mar 2025 | 0.00 | 0.00 | 0.00 | 0.00 |
| Archive, `best_match` | Jan–Mar 2025 | 0.00 | 0.00 | 0.00 | 0.00 |
| Forecast `past_days`, `ecmwf_ifs` | last 31 days | +0.01 | 0.08 | 0.8 | 0.8 |
| Archive, `era5` | Jan–Mar 2025 | −0.01 | 0.23 | 1.0 | 1.7 |
| Historical Forecast, `best_match` | Jan–Mar 2025 | −0.13 | 0.31 | 1.2 | 1.8 |
| Historical Forecast, `icon_seamless` | Jan–Mar 2025 | −0.06 | 0.37 | 2.2 | 1.7 |
| Historical Forecast, `gfs_seamless` | Jan–Mar 2025 | −0.28 | 0.32 | 2.4 | 3.0 |

All values are hPa.

What this shows:
- **Same model, any endpoint: identical**, except for the newest day or so. In the forecast-vs-archive comparison, all 27 hours that differed were in the last 30 hours, where the two endpoints held different recent runs.
- **Different models: up to 2–3 hPa apart** at a flat, sea-level site, in both levels and 24 h changes. A big 24 h pressure drop is often 5–10 hPa, so mixing models adds errors of a meaningful fraction of the signal, concentrated at the seam.
- **Terrain and site matter.** An earlier check made while building this library, at a different site, found the archive and the Historical Forecast API 2.1 ± 1.9 hPa apart (max 6.6 hPa) for the same hours. At Greenwich, with both pinned to `ecmwf_ifs`, they match exactly. So the gap depends on the site and on which model each request resolved to, not only on the endpoint. Either way the rule holds: **one source, one model, in every series that is compared or concatenated.**

To re-measure, fetch the same hours from two configurations for a neutral place and compare `diff(24)` as well as levels. Keep the numbers out of the repo unless the place is neutral.

## Pitfalls to remember when changing a source
- **All-`null` columns are not errors.** An ID the API knows but that has no data for the request (wrong endpoint, before the model's start, a variable the model lacks) comes back 200 with `null`s. `parse_open_meteo` turns them into NaN without complaint. If you add a model or a variable, check the null count for a neutral place first ([examples](api-reference.md#errors-and-missing-data)).
- **Native time steps.** `ecmwf_ifs` is hourly only to 90 h of lead time, then 3-hourly, then 6-hourly beyond 144 h, and Open-Meteo interpolates in between. `forecast_days=3` stays almost entirely within the hourly part, because the latest run is at most about 12 h old. Past about 3.5 days, 3 h and 6 h changes in an outlook are interpolation artefacts. Keep long outlooks to 24 h and 48 h windows.
- **Elevation and grid cells differ between models.** Changing the model changes the grid cell and the downscaling, so the surface-pressure level shifts. Never compare levels across models; compare changes within each one.
- **Daily aggregates** (`surface_pressure_mean` and so on) use the request's fixed UTC offset and hide the timing of a change. The library computes everything from hourly data on purpose.
- **The documented `past_days` limit (92)** is looser in practice (93 was accepted). The library enforces 0–92 itself, so the documented limit governs it.
- **Costs grow with span and variables.** Full history costs about 77 calls. That's fine within 10 000 a day, but consumers should cache loaded frames, not refetch on every page view.
- **Error messages must stay private.** Every failure is raised as `WeatherError(...) from None`, with no URL and no coordinates. Keep that true for any new request path, including retries and logging.
- **Attribution must travel with the data.** Any new display of weather needs "Weather data by Open-Meteo.com" (CC BY 4.0) next to it ([licence](open-meteo.md#licence-and-attribution)).

## Ideas that fit the library
These follow the same rules: one model per series, changes within a series, nothing sent but rounded coordinates.

- **Ensemble outlook.** `ensemble-api` with `models=ecmwf_ifs025` gives 51 members of the same model family. You could compute each member's next-24 h change within its own series and report the share of members beyond the archive's "big drop" threshold (e.g. "38 of 51 members"), instead of a single number. Cost: every member counts as a variable, so 3 variables × 51 members ≈ 15 calls per refresh. Caveat: the ensemble is 0.25° and 3-hourly, a different model configuration from HRES, so rank its changes against its own spread, or against the archive only loosely.
- **Forecast skill check.** The Previous Runs API (`surface_pressure_previous_day1` … `_day3`, `models=ecmwf_ifs`) shows how often a forecast big drop 1–3 days ahead actually happened. `ecmwf_ifs` previous runs only begin around October 2025, so for longer evaluation use `ecmwf_ifs025`, which reaches back to at least mid-2024.
- **Long baselines from ERA5.** Climatological thresholds (e.g. "the steepest 20 % of 24 h drops in this month over 30 years") could come from `era5` back to 1940, as a separate series used only for ranking, never joined to IFS.
- **Single-run outlooks.** If outlook values ever need to be reproducible (for a notebook or a paper), take them from the Single Runs API with an explicit `run=` instead of whatever run is newest.
