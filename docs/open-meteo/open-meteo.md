# Open-Meteo, the service

[Open-Meteo](https://open-meteo.com/) is an open-source weather API. It downloads output from national weather services (ECMWF, NOAA, DWD, Météo-France, the UK Met Office, JMA and others), reprocesses it into its own time-series format and serves it over plain HTTP GET. Non-commercial use needs no account and no API key.

- **Server code:** Swift, [AGPLv3](https://github.com/open-meteo/open-meteo) ("or any later version").
- **Data:** CC BY 4.0, with attribution required (see [Licence and attribution](#licence-and-attribution)).
- **Volume:** the features page says more than 5 TB of model output is downloaded and processed each day. Most global models update every 6 hours, and some regional ones every 1–3 hours.
- **Output formats:** JSON by default, plus CSV and XLSX (`format=csv` / `format=xlsx`) and FlatBuffers, which the official SDKs use. CORS is enabled, so browsers can call it directly.

## The APIs
Each API has its own host. Unless noted, they share the same parameter conventions (see the [API reference](api-reference.md)).

| API | Endpoint | What it serves |
|---|---|---|
| Forecast | `https://api.open-meteo.com/v1/forecast` | The latest forecast, up to 16 days ahead. With `past_days` it also covers up to about 3 months back. Hourly, daily, 15-minutely and current values. |
| Historical Weather | `https://archive-api.open-meteo.com/v1/archive` | Reanalysis and analysis archives: ERA5 from 1940, ERA5-Land from 1950, ECMWF IFS from 2017, CERRA (Europe, 1985–2021). |
| Historical Forecast | `https://historical-forecast-api.open-meteo.com/v1/forecast` | The Forecast API's own archive: the first hours of every successive model run, stitched into one hourly series. Same parameters as Forecast. |
| Previous Runs | `https://previous-runs-api.open-meteo.com/v1/forecast` | What each model forecast 1–7 days *before* each hour (`<variable>_previous_dayN`). For checking forecast skill. |
| Single Runs | `https://single-runs-api.open-meteo.com/v1/forecast` | One complete model run, chosen with `run=YYYY-MM-DDThh:mm` (UTC initialisation time). |
| Ensemble | `https://ensemble-api.open-meteo.com/v1/ensemble` | Every member of ensemble forecasts (for example 51 for ECMWF IFS), up to 35 days. For uncertainty and probabilities. |
| Seasonal | (see the docs) | ECMWF SEAS5 (to 9 months) and EC46 (to 6 weeks), 51 members. |
| Climate | `https://climate-api.open-meteo.com/v1/climate` | Daily CMIP6 projections, 1950–2050, downscaled to 10 km and bias-corrected against ERA5-Land. Not observations. |
| Air Quality | `https://air-quality-api.open-meteo.com/v1/air-quality` | CAMS pollutants, pollen (Europe), dust, UV, and European and US AQI. Forecast up to 7 days, past up to 92 days. |
| Marine | `https://marine-api.open-meteo.com/v1/marine` | Waves, swell, sea-surface temperature, currents and sea level. The docs say it is not for coastal navigation. |
| Flood | `https://flood-api.open-meteo.com/v1/flood` | GloFAS simulated river discharge, from 1984 to a 7-month forecast. It picks the largest river within 5 km. |
| Satellite Radiation | `https://satellite-api.open-meteo.com/v1/archive` | Solar radiation from geostationary satellites (MTG, MSG, Himawari, GOES), at 10–30 minute steps. |
| Geocoding | `https://geocoding-api.open-meteo.com/v1/search` | Place name or postcode → coordinates, time zone, elevation and admin areas (GeoNames). |
| Elevation | `https://api.open-meteo.com/v1/elevation` | Terrain height from the Copernicus GLO-90 DEM (90 m). Up to 100 points per request. |

winds-of-change uses only the **Historical Weather** and **Forecast** APIs. The other weather APIs are described in [Models and datasets](models.md) because they are natural next steps (see [Ideas](in-this-library.md#ideas-that-fit-the-library)). The non-weather APIs are listed only so the catalogue is complete.

**Never send a real person's place name to the Geocoding API from this library.** A free-text query is personal data in exactly the way coordinates are, and this library only ever sends rounded coordinates.

## Terms of use
Open-Meteo's own words are in its [terms](https://open-meteo.com/en/terms); this is a summary.

- **The free tier is non-commercial only.** The terms follow the Creative Commons reading of non-commercial. Examples that qualify:
  - private or non-profit sites and apps without subscriptions or advertising;
  - personal home automation;
  - research at public institutions;
  - education.

  A voluntary donation or tip jar is fine. Anything with subscriptions, ads, or commercial promotion needs a paid plan, even though the data itself is CC BY.
- **Fair use.** Open-Meteo may block applications and IP addresses that misuse the service, without warning. Limits apply per IP address and per application. Shared hosts (Vercel, Netlify, Render, Google Apps Script) can hit them earlier because many users share an IP.
- **No uptime guarantee** on the free tier. Paid plans target 99.9 %.
- **Caching and storage** are not addressed in the terms. CC BY permits copying and redistribution with attribution. The Python SDK recommends a one-hour HTTP cache.

## Rate limits and call costs
Free-tier limits (documented): **600 calls per minute, 5 000 per hour, 10 000 per day, 300 000 per month.**

A "call" is not always one request. Documented rule: a request asking for more than 10 variables, or covering more than 2 weeks for one location, counts as more than one call, fractionally. For example, 15 variables over 2 weeks counts as 1.5 calls.

**Observed:** every response carries headers that show what the request cost:

```
X-RateLimit-Cost: 1.0
X-RateLimit-Limit: 600.0
X-RateLimit-Remaining: 599.0
X-RateLimit-Reset: 1794790382      # Unix time when the window resets
X-RateLimit-Window: 60             # seconds (the per-minute window)
```

The measured costs fit `cost = max(1, max(1, days / 14) × variables / 10)` for each location. In that formula, every ensemble member and every `_previous_dayN` column counts as a variable, and `days` is the whole span returned, past plus forecast. Examples measured on 16 November 2026:

| Request | Cost |
|---|---|
| Forecast, 3 variables, default 7 days | 1.0 |
| Forecast, 3 variables, `past_days=31&forecast_days=3` (what `OpenMeteoForecastSource` sends) | 1.0 |
| Forecast, 11 variables, 7 days | 1.1 |
| Forecast, 3 variables, 2 locations in one request | 2.0 |
| Archive, 3 variables, 14 days | 1.0 |
| Archive, 3 variables, 1 year | 7.8 |
| Archive, 3 variables, 2017-01-01 to 2026-11-15 (what a full-history `OpenMeteoSource` load costs) | 77.3 |
| Ensemble, 1 variable × 51 ECMWF members, 7 days | 5.1 |
| Previous Runs, 4 columns, 37 days | 1.06 |

The Ensemble API docs say a typical example request "is equivalent to 4.0 calls", and the Climate API example costs 1 844.5 calls. Members and long spans add up quickly.

The terms don't say what happens when a limit is exceeded; HTTP 429 is the usual convention but isn't documented. The pricing FAQ says monthly budgets are not yet hard-enforced: you get e-mail alerts at 80, 90 and 100 %.

## Paid plans
Commercial use goes through `customer-api.open-meteo.com`, `customer-archive-api.open-meteo.com` and so on (a `customer-` prefix on each host), with `&apikey=…`. Every other parameter is the same. Prices aren't listed on the page.

| Plan | Use | Volume | Notes |
|---|---|---|---|
| Free | non-commercial | 10 000/day | no uptime guarantee |
| Standard | commercial | 1 M calls/month | no historical, ensemble, climate, satellite or seasonal APIs |
| Professional | commercial | 5 M calls/month | all APIs |
| Enterprise | commercial | > 50 M calls/month | custom |

The pricing page's comparison table shows the historical and ensemble APIs as free-tier ✅, but its FAQ says they need Professional for *commercial* use. Read it that way: free for non-commercial, Professional for commercial.

## Licence and attribution
- **Data:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Give credit, link to the licence and say whether you changed the data. Open-Meteo asks for a link next to any place the data is displayed, for example:

  ```html
  <a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a>
  ```
- **Upstream sources** keep their own terms:
  - ECMWF, DWD and GeoNames are CC BY.
  - Most European services (MET Norway, KNMI, DMI, MeteoSwiss and others) are CC BY 4.0.
  - The UK Met Office is CC BY-SA 4.0.
  - NOAA, Météo-France, JMA and CMC have their own licences.
  - Copernicus (ERA5, CAMS, GloFAS, the DEM) has its own licence documents.

  ECMWF real-time forecasts have been open data since 1 October 2025.
- **Citation:** Zippenfenig, P. (2023). *Open-Meteo.com Weather API.* Zenodo. <https://doi.org/10.5281/ZENODO.7970649>
- **This library** credits "Weather data by Open-Meteo.com (CC BY 4.0), from ECMWF IFS forecasts and analyses" in its README and source docstrings. Apps built on it, such as the health-log-dashboard's Weather page, must show the credit next to the charts.

## SDKs and clients
- **Plain HTTP** is all you need: one GET and a JSON body. winds-of-change uses `urllib` from the standard library on purpose, to keep its dependencies to pandas and numpy and to send nothing but the default User-Agent.
- **[`openmeteo-requests`](https://pypi.org/project/openmeteo-requests/)** is the official Python client (MIT, by Open-Meteo's author, still marked alpha). It asks for FlatBuffers instead of JSON, for zero-copy numpy, pandas and polars arrays. Values are reached through accessors (`response.Hourly().Variables(0).ValuesAsNumpy()`). Its README recommends `requests-cache` (one hour) and `retry-requests` (5 retries, backoff 0.2). Official SDKs also exist for TypeScript, Swift and other languages; the schemas are at [github.com/open-meteo/sdk](https://github.com/open-meteo/sdk).

## Self-hosting
The [open-meteo repo](https://github.com/open-meteo/open-meteo) supports Docker or a prebuilt Ubuntu 22.04 package. A self-hosted node can read Open-Meteo's public database remotely and cache what it uses, so it doesn't need full model downloads. See `docs/getting-started.md` in that repo. That is the route if the free limits or terms ever stop fitting, but nothing here needs it.
