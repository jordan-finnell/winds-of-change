# Open-Meteo API reference

This page covers the parameters, responses and behaviour shared by the weather endpoints (Forecast, Historical Weather, Historical Forecast, Previous Runs, Single Runs, Ensemble), then each endpoint's differences. "Observed" means checked against the live API on 16 November 2026 for Greenwich (51.5, 0.0). Everything else is from Open-Meteo's docs.

Contents:
- [A request](#a-request)
- [Common parameters](#common-parameters)
- [Location: grid cells, elevation and downscaling](#location-grid-cells-elevation-and-downscaling)
- [Time: ranges, time zones and timestamps](#time-ranges-time-zones-and-timestamps)
- [Response format](#response-format)
- [Errors and missing data](#errors-and-missing-data)
- [Variables](#variables)
- [Endpoints](#endpoints)
- [Checking a claim](#checking-a-claim)

## A request
```
https://api.open-meteo.com/v1/forecast?latitude=51.5&longitude=0.0
    &hourly=surface_pressure,dew_point_2m,temperature_2m
    &models=ecmwf_ifs&timezone=auto&timeformat=unixtime
    &past_days=31&forecast_days=3
```

A request is one HTTP GET. There's no authentication, and the body is JSON. Lists are comma-separated (`hourly=a,b,c`); repeating the parameter (`hourly=a&hourly=b`) also works.

## Common parameters
| Parameter | Default | Values | Notes |
|---|---|---|---|
| `latitude`, `longitude` | required | WGS84 decimal degrees | Comma-separated lists request [several locations](#several-locations). Longitude is negative west of Greenwich. |
| `elevation` | from a 90 m DEM | metres, or `nan` | Height used for [downscaling](#location-grid-cells-elevation-and-downscaling). Comma-separated for several locations. |
| `cell_selection` | `land` | `land`, `sea`, `nearest` | Which grid cell to use (see below). Air Quality and Flood default to `nearest`, Marine to `sea`. |
| `hourly` | none | variable names | See [Variables](#variables). |
| `daily` | none | variable names | The docs say `timezone` is required with `daily`. **Observed:** omitting it works and uses GMT days. |
| `current` | none | variable names | Forecast API only. Current conditions, from the 15-minutely data. |
| `minutely_15` | none | variable names | Forecast API only. Native in Central Europe and North America, interpolated from hourly elsewhere. |
| `models` | `best_match` | model IDs, comma-separated | See [Models and datasets](models.md). With more than one model, every column gets a `_<model>` suffix. |
| `temperature_unit` | `celsius` | `fahrenheit` | |
| `wind_speed_unit` | `kmh` | `ms`, `mph`, `kn` | |
| `precipitation_unit` | `mm` | `inch` | |
| `timeformat` | `iso8601` | `unixtime` | See [Timestamps](#timestamps). |
| `timezone` | `GMT` | IANA name, or `auto` | `auto` resolves the zone from the coordinates. Comma-separated for several locations. |
| `format` | JSON | `csv`, `xlsx`, `flatbuffers` | FlatBuffers is what the official SDKs use. |
| `apikey` | none | key | Commercial plans only, on `customer-` hosts. |

Pressure is always in hPa, and there is no unit parameter for it.

## Location: grid cells, elevation and downscaling
Weather models work on a grid, so a request for a point gets the values of one grid cell, adjusted to the requested point:

1. **Cell choice** (`cell_selection`):
   - `land` (default): picks a nearby land cell with similar elevation, using the 90 m DEM. This avoids taking a sea cell for a coastal town.
   - `sea`: prefers sea cells.
   - `nearest`: takes the closest cell whatever its type.
2. **Response coordinates:** `latitude`/`longitude` in the response are the **centre of that grid cell**, so they can be a few kilometres from the request and differ from one model to the next. **Observed** for 51.5, 0.0: `ecmwf_ifs` returned 51.494, 0.0, while `best_match` in the Forecast API returned 51.508, 0.014.
3. **Elevation and downscaling:** the response's `elevation` is the height used. By default it comes from the 90 m Copernicus DEM at the requested point. Passing `elevation=` overrides it, and `elevation=nan` is documented to turn downscaling off and use the grid cell's average height.

**Observed: the elevation changes `surface_pressure`, not `pressure_msl`.** Same hour, same model (`ecmwf_ifs`), Greenwich:

| `elevation=` | Response `elevation` | `surface_pressure` | `pressure_msl` | `temperature_2m` |
|---|---|---|---|---|
| not set | 4 m (DEM) | 999.0 | 999.5 | 6.8 |
| `nan` | 22 m (cell average) | 996.8 | 999.5 | 6.8 |
| `100` | 100 m | 987.4 | 999.5 | 6.8 |
| `300` | 300 m | 963.5 | 999.5 | 5.0 |

- **Surface pressure** falls by about 12 hPa per 100 m, the hydrostatic adjustment. **Sea-level pressure** doesn't move, because it is already reduced to sea level.
- **Temperature** is lapse-rate adjusted, but only past some height difference. `ecmwf_ifs` left it unchanged at 100 m and adjusted it at 300 m, while `best_match` adjusted it at 100 m.
- **`elevation=nan` isn't consistent:** with `best_match` in the Forecast API it still returned the DEM height (4 m), not the cell average.
- **Same elevation everywhere.** If two requests send different elevations, their surface pressures differ by a constant offset. Within one series that offset cancels out of every change, but across series it shows up as a step. So send the same `elevation` (or none) to every endpoint you compare.

### Several locations
`latitude=51.5,48.9&longitude=0.0,2.3` returns a **JSON list** with one object per location, in request order. Each costs a call ([costs](open-meteo.md#rate-limits-and-call-costs)). **Observed:** every object after the first has a `location_id` (1, 2, …), and the first omits it. CSV and XLSX output add a `location_id` column. winds-of-change always asks for one location.

## Time: ranges, time zones and timestamps

### Choosing the range
Use **either** a relative range or explicit dates, not both:

- **Relative (Forecast-style endpoints):**
  - `forecast_days` (Forecast 0–16, default 7; Ensemble 0–35) and `past_days` (0–92, default 0).
  - **Observed:** `past_days=93` was accepted and returned 93 days, so the documented limit isn't enforced exactly. Don't rely on it.
  - The days are calendar days in the requested time zone: the series starts at 00:00 local today minus `past_days` and runs to 24:00 on the last forecast day. The default response "starts at 0:00 today and contains 168 hours".
- **Hours instead of days:** `forecast_hours`, `past_hours` (and `forecast_minutely_15`, `past_minutely_15`) count from the current hour (or 15-minute step) instead of from midnight.
- **Explicit:**
  - `start_date`/`end_date` as `yyyy-mm-dd`, both inclusive, local days.
  - `start_hour`/`end_hour` (and `start_minutely_15`/`end_minutely_15`) as `yyyy-mm-ddThh:mm`.
  - The Historical Weather API *requires* `start_date` and `end_date`.

### Time zones
- **`timezone=GMT` (default):** every day boundary is UTC, so daily aggregates and `past_days`/`forecast_days` are UTC days.
- **`timezone=auto`** resolves the zone from the coordinates. The response then gives `timezone` (IANA name, e.g. `Europe/London`) and `timezone_abbreviation` (e.g. `GMT`, `BST`).
- **`utc_offset_seconds` is fixed for the whole response.** It is resolved at request time, and **DST changes inside the range are ignored**. ISO 8601 timestamps across a DST change are therefore off by an hour on one side of it, and daily aggregates use the fixed offset.

### Timestamps
- **`timeformat=iso8601`** (default) returns local wall-clock strings without an offset, e.g. `2026-11-16T00:00`. Daily values are `yyyy-mm-dd`, and 15-minutely values follow the same pattern. Treat them as naive local time at `utc_offset_seconds`.
- **`timeformat=unixtime`** returns integer seconds since 1970-01-01 00:00 UTC. This is the DST-safe choice: convert to UTC, then to the returned IANA `timezone`, as `parse_open_meteo` does:

  ```python
  times = pd.to_datetime(hourly["time"], unit="s", utc=True).tz_convert(payload["timezone"])
  ```

  The docs suggest this for DST-aware local times. To reproduce the API's own wall-clock labels instead, add `utc_offset_seconds`.
- **Hourly values are instantaneous unless the variable says otherwise.** Precipitation, radiation and sunshine are sums or means over the **preceding** hour, so the value stamped 13:00 covers 12:00–13:00.

## Response format
**Observed** (one location, `timeformat=unixtime`, `timezone=auto`):

```json
{
  "latitude": 51.493847,
  "longitude": 0.0,
  "generationtime_ms": 0.094,
  "utc_offset_seconds": 0,
  "timezone": "Europe/London",
  "timezone_abbreviation": "GMT",
  "elevation": 4.0,
  "hourly_units": {"time": "unixtime", "surface_pressure": "hPa"},
  "hourly": {"time": [1794787200, 1794790800, ...], "surface_pressure": [999.0, 998.8, ...]}
}
```

- **Each block** (`hourly`, `daily`, `minutely_15`) is a dict of equal-length arrays with `time` first, plus a matching `*_units` dict. `current` is a dict of scalars, with `time` and `interval` (seconds, e.g. 900).
- **Missing values are `null`.** A whole column can be `null`: see [Errors and missing data](#errors-and-missing-data).
- **Several models** suffix every column with the model ID, e.g. `models=ecmwf_ifs,gfs_seamless` gives `surface_pressure_ecmwf_ifs` and `surface_pressure_gfs_seamless` (**observed**). One model gives plain names. `parse_open_meteo` accepts both.
- **Ensemble responses** give the control run under the plain name, and one column per perturbed member as `<variable>_member01` … `_member50` (**observed**).
- **CSV** starts with a location header block (latitude, longitude, elevation, offset, zone), then a blank line, then the data with units in the column names, e.g. `time,surface_pressure (hPa)`.

## Errors and missing data
**Invalid requests return HTTP 400** with a JSON body (documented and observed):

```json
{"error": true, "reason": "Forecast days is invalid. Allowed range 0 to 16. Given 17."}
```

Reasons seen on 16 November 2026:

| Cause | `reason` |
|---|---|
| Unknown model ID | `Invalid value: Cannot initialize MultiDomains from invalid String value not_a_model` |
| Unknown variable | `Invalid value: Cannot initialize SurfacePressureAndHeightVariable<…> from invalid String value tempeture_2m` |
| `forecast_days` too large | `Forecast days is invalid. Allowed range 0 to 16. Given 17.` |
| Archive date past the limit | `Parameter 'end_date' is out of allowed range from 1940-01-01 to 2026-11-16` |
| Single run that doesn't exist | `The requested model run is not available. Model: ecmwf_ifs, run: 2026-11-10T03:00Z` |

`OpenMeteoSource` depends on the archive's wording, `out of allowed range from <first> to <last>`. It takes the last date in that message and retries once ([details](in-this-library.md#the-archives-last-date)).

Rate-limit errors aren't documented. Expect HTTP 429 and handle any non-200 status as a failure.

**A valid request can still return no data. Always check for all-`null` columns.** The server accepts every model ID it knows on every weather endpoint, and returns `null` where that model has nothing to give. **Observed:**

| Request | Result |
|---|---|
| Forecast API, `models=ecmwf_aifs025` or `ecmwf_ifs04` | 200, every value `null`. Use `ecmwf_aifs025_single`; IFS 0.4° has been replaced by 0.25°. |
| Archive, `models=cerra` for 2025 | 200, all `null`. CERRA ends in June 2021 and covers Europe only. |
| Archive, `models=era5_land&hourly=surface_pressure` | 200, all `null`. ERA5-Land has temperature and humidity, but not pressure. |
| Forecast API, `models=era5` | 200, all `null`. Reanalyses live in the Historical Weather API. |
| Archive, `ecmwf_ifs` from 2016-12-31 | 200, `null` until 2017-01-01 00:00 UTC. |
| Previous Runs, `ecmwf_ifs`, any date before October 2025 | 200, all `null`. |

Partial `null`s are normal at the ends of a range: the latest hours of a delayed reanalysis, the hours past a forecast's horizon, or a model's start date.

## Variables
Names are the same across endpoints where a variable exists in both, except soil levels and wind heights (see below).

### Hourly, surface
| Group | Variables | Notes |
|---|---|---|
| Pressure | `surface_pressure`, `pressure_msl` | hPa, instantaneous. Surface pressure depends on elevation ([above](#location-grid-cells-elevation-and-downscaling)). |
| Temperature | `temperature_2m`, `apparent_temperature`, `dew_point_2m` | °C/°F. Wet-bulb temperature is listed too. |
| Humidity | `relative_humidity_2m`, `vapour_pressure_deficit` (kPa) | RH follows the day's temperature, while dew point does not. |
| Precipitation | `precipitation`, `rain`, `showers`, `snowfall` (cm), `snow_depth` (m), `precipitation_probability` | Sums over the preceding hour. For snowfall, divide cm by 7 for mm of water. Probability comes from ensembles, Forecast API only. |
| Clouds | `cloud_cover`, `cloud_cover_low` (< 3 km), `cloud_cover_mid` (3–8 km), `cloud_cover_high` (> 8 km) | % |
| Wind | `wind_speed_10m`, `wind_direction_10m`, `wind_gusts_10m` | The Forecast API also has 80, 120 and 180 m; the archive has 100 m. Gusts are the maximum over the preceding hour. |
| Radiation | `shortwave_radiation`, `direct_radiation`, `diffuse_radiation`, `direct_normal_irradiance`, `global_tilted_irradiance`, `terrestrial_radiation`, `sunshine_duration` | W/m², means over the preceding hour. `*_instant` variants exist. Tilted irradiance needs `tilt` and `azimuth`. |
| Other | `weather_code` (WMO), `visibility`, `uv_index`, `cape`, `lifted_index`, `convective_inhibition`, `freezing_level_height`, `boundary_layer_height`, `is_day`, `et0_fao_evapotranspiration` | Not every model has every variable. |
| Soil | Forecast: `soil_temperature_0cm/6cm/18cm/54cm`, `soil_moisture_0_to_1cm` … `27_to_81cm`. Archive: `soil_temperature_0_to_7cm` … `100_to_255cm`, `soil_moisture_0_to_7cm` … | The level names differ by endpoint. |

### Hourly, pressure levels
`<variable>_<level>hPa`, e.g. `temperature_850hPa` or `geopotential_height_500hPa`. Variables: temperature, relative humidity, dew point, cloud cover, wind speed and direction, geopotential height. Levels: 1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50 and 30 hPa. Forecast-style endpoints only, and not from ECMWF IFS HRES 9 km (use `ecmwf_ifs025` or `ecmwf_aifs025_single`).

### Previous-run variants
`<variable>_previous_day1` … `_previous_day7` give the value forecast 24 … 168 h before the valid time, and `_previous_day0` is the latest run. Previous Runs API only.

### Daily
Daily values are aggregated from hourly values over local days in the requested `timezone` ("a simple 24-hour aggregation"):

- `temperature_2m_max/_min/_mean`, `apparent_temperature_max/_min/_mean`
- `precipitation_sum`, `rain_sum`, `showers_sum`, `snowfall_sum`, `precipitation_hours`, `precipitation_probability_max/_mean/_min`
- `weather_code` (the most severe), `sunrise`, `sunset`, `sunshine_duration`, `daylight_duration`
- `wind_speed_10m_max`, `wind_gusts_10m_max`, `wind_direction_10m_dominant`
- `shortwave_radiation_sum` (MJ/m²), `et0_fao_evapotranspiration`, `uv_index_max`, `uv_index_clear_sky_max`
- **Observed** in both the Forecast and archive APIs: `pressure_msl_mean/_min/_max`, `surface_pressure_mean/_min/_max`, `dew_point_2m_mean/_min/_max`, `relative_humidity_2m_mean/_min/_max`.

winds-of-change doesn't use daily variables. A daily mean or range hides *when* the change happened, and the library's features are built from hourly data instead (see the [main README](../../README.md#what-the-features-mean)).

### 15-minutely and current
- **`minutely_15`:** temperature, humidity, dew point, precipitation, snowfall, wind, gusts, visibility, CAPE, `lightning_potential`, radiation and `weather_code`. **Observed:** `surface_pressure` also works, although the docs don't list it. Outside Central Europe and North America these values are interpolated from hourly data and add nothing.
- **`current`:** a snapshot of a short list (temperature, humidity, precipitation, `weather_code`, cloud cover, `pressure_msl`, `surface_pressure`, wind) at the latest 15-minute step.

### WMO weather codes
`weather_code` uses WMO codes:

| Code | Meaning |
|---|---|
| 0 | clear |
| 1–3 | mainly clear to overcast |
| 45, 48 | fog |
| 51–57 | drizzle |
| 61–67 | rain |
| 71–77 | snow |
| 80–82 | rain showers |
| 85, 86 | snow showers |
| 95 | thunderstorm |
| 96, 99 | thunderstorm with hail (only from models that forecast hail) |

## Endpoints

### Forecast — `api.open-meteo.com/v1/forecast`
- The latest run of each model, "seamlessly" continued. A `*_seamless` model, or `best_match`, blends a provider's high-resolution regional model at short lead times with its global model further out.
- Up to 16 days ahead, and up to about 92 days back with `past_days`.
- The past hours are the model's archived first hours, the same values as the archive. **Observed** for `ecmwf_ifs`: the two match exactly except for roughly the last day, where each comes from a different recent run. See the [measurements](in-this-library.md#measured-differences-between-endpoints-and-models).
- All data is interpolated to hourly steps. ECMWF IFS HRES is natively hourly to 90 h, 3-hourly to 144 h and 6-hourly beyond, so hourly values past 90 h are interpolated. **Observed:** with `forecast_days=16`, `ecmwf_ifs` returns values to 360 h after the latest run and `null` after that.

### Historical Weather — `archive-api.open-meteo.com/v1/archive`
- Needs `start_date` and `end_date`. The datasets and their delays are in [Models and datasets](models.md#historical-weather-api-reanalysis-and-analysis).
- **The last allowed `end_date` is today's date in UTC.** **Observed** at 00:51 UTC: "out of allowed range from 1940-01-01 to 2026-11-16". For `ecmwf_ifs`, the values for that day were already complete, filled from the latest run's first hours.
- The default `best_match` blends ECMWF IFS, ERA5 and ERA5-Land. **Observed:** for Greenwich in 2025 it was identical to `ecmwf_ifs`. Pin the model anyway, because what `best_match` means can change.
- Official guidance: use ERA5 or ERA5-Land alone for multi-decade work, because they are one consistent model version. Use ECMWF IFS (from 2017) for the highest resolution in recent years.

### Historical Forecast — `historical-forecast-api.open-meteo.com/v1/forecast`
- Identical to the Forecast API in parameters and response, but it serves the archive. Each model's first hours from every run are stitched into a continuous series.
- Coverage depends on the model. `ecmwf_ifs` is available from 2017-01-01, which was **observed** (2016 is all `null`). Most other models start in 2021–2022. Per-model dates are in [Models and datasets](models.md#forecast-models).
- Open-Meteo's guidance: it tracks real conditions closely, because every run starts from fresh observations, but it isn't consistent over long periods because models are upgraded.
- **Observed:** with `models=ecmwf_ifs`, the Historical Forecast API and the archive returned exactly the same hourly values for January–March 2025.

### Previous Runs — `previous-runs-api.open-meteo.com/v1/forecast`
- The Forecast API's parameters, plus `_previous_dayN` variables (N = 0…7).
- For example, `hourly=surface_pressure,surface_pressure_previous_day1,surface_pressure_previous_day3&past_days=30&models=ecmwf_ifs` compares what happened with what was forecast 1 and 3 days earlier.
- **Coverage:**
  - Most models from January 2024 (GFS 2 m temperature from 2021, JMA from 2018).
  - **Observed:** `ecmwf_ifs` only from about **2025-10-01**, and all `null` before that. This lines up with ECMWF's real-time HRES becoming open data on 1 October 2025.
  - `ecmwf_ifs025`, `gfs_seamless` and `best_match` have data from at least June 2024.
- These are per-lead-time slices, not a continuous series from one run. For full runs use Single Runs.

### Single Runs — `single-runs-api.open-meteo.com/v1/forecast`
- The Forecast API's parameters, plus a **required** `run=YYYY-MM-DDThh:mm`. That is the model's UTC *initialisation* time, not when it was published.
- The run must be a real cycle, e.g. 00/06/12/18 UTC for ECMWF IFS. **Observed:** `03:00` returns 400 "The requested model run is not available".
- **Coverage:** ECMWF IFS HRES from 14 March 2024 (IFS cycle 49r1 hindcasts; runs from 12 May 2026 06 UTC use cycle 50r1). Other models from 2 April 2026.
- Runs appear 4–6 h after initialisation for global models and 1–3 h for regional ones.
- **Observed:** the default length was 168 h. With `forecast_days=16` and `ecmwf_ifs` there were 361 non-`null` hours (15 days).

### Ensemble — `ensemble-api.open-meteo.com/v1/ensemble`
- `models` is required. `forecast_days` is 0–35 (default 7), and past data goes back up to about 3 days. All members are interpolated to hourly.
- Columns: `<variable>` (control) plus `<variable>_member01` … `_memberNN`. Costs scale with members ([costs](open-meteo.md#rate-limits-and-call-costs)).
- Hourly variables include `surface_pressure`, `pressure_msl`, `temperature_2m`, `dew_point_2m`, precipitation and wind. Daily aggregates such as `surface_pressure_mean` exist too.
- Model IDs and member counts are in [Models and datasets](models.md#ensembles).

## Checking a claim
Use a neutral place and a small range, and look at the status, the `reason` and the null count:

```bash
curl -s "https://archive-api.open-meteo.com/v1/archive?latitude=51.5&longitude=0.0\
&hourly=surface_pressure&start_date=2025-01-01&end_date=2025-01-01&models=era5" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('reason') or \
sum(v is not None for v in d['hourly']['surface_pressure']), 'non-null')"
```

Add `-D -` to see the `X-RateLimit-Cost` header. Never run such checks for a real person's location from this repo, and never paste their output into it.
