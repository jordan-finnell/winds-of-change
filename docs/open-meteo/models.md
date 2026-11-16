# Models and datasets

Open-Meteo serves many weather models, and each comes from a different organisation, grid, time step and update cycle. For this library the model matters more than the endpoint, because two models disagree by about as much as the pressure changes being measured ([measurements](in-this-library.md#measured-differences-between-endpoints-and-models)). Pick one model and keep it.

"Observed" IDs were checked against the live API on 16 November 2026 for Greenwich. An ID counts as working only if it returned non-`null` values, because the server accepts every ID it knows, even where that model has no data ([why](api-reference.md#errors-and-missing-data)).

## ECMWF IFS, the model this library uses
The European Centre for Medium-Range Weather Forecasts runs the **Integrated Forecasting System**, widely regarded as the most accurate global model. Open-Meteo offers it in several forms:

| Form | `models=` | Grid | Native time step | Length | Updates |
|---|---|---|---|---|---|
| IFS HRES 9 km | `ecmwf_ifs` | 9 km (O1280 octahedral) | 1 h to 90 h, 3 h to 144 h, 6 h after | 15 days | every 6 h (00/06/12/18 UTC) |
| IFS 0.25° open data | `ecmwf_ifs025` | ~25 km | 3 h, then 6 h after 144 h | 15 days | every 6 h |
| AIFS Single 0.25° (machine-learned) | `ecmwf_aifs025_single` | ~28 km | 6 h | 15 days | every 6 h |
| IFS 0.4° (superseded) | `ecmwf_ifs04` | ~44 km | 3 h | — | **observed:** accepted, all `null` in the Forecast API |

- **HRES has the most detail,** but it has no pressure-level fields; use the 0.25° models for upper-air variables.
- **AIFS** is ECMWF's AI model. The plain ID `ecmwf_aifs025` returns `null` in the Forecast API; use `ecmwf_aifs025_single`, while `ecmwf_aifs025` is the ensemble ID.
- **Open data:** ECMWF's real-time forecasts have been open data (CC BY 4.0) since 1 October 2025. Open-Meteo's ECMWF page defaults to 10 forecast days, up to 15.
- **All forms are interpolated to hourly steps.** Hourly values between coarse native steps are interpolated, not modelled, so short-window changes (3–6 h) far into a forecast are smoother than real ones.

`ecmwf_ifs` in each API:

| API | What `ecmwf_ifs` gives | Range |
|---|---|---|
| Forecast | the latest runs, seamless | about 92 days back, 15 days ahead |
| Historical Weather (archive) | "ECMWF IFS": stitched from the 00/06/12/18 UTC runs | **2017-01-01** (observed) to today UTC, "every 6 hours with no delay" |
| Historical Forecast | the first hours of each run | 2017-01-01 (observed) |
| Previous Runs | values forecast 1–7 days ahead | **observed** from about 2025-10-01 |
| Single Runs | complete individual runs | from 2024-03-14 (cycle 49r1; 50r1 from 2026-05-12 06 UTC) |

**Observed:** for January–March 2025 at Greenwich, the archive and the Historical Forecast API returned exactly the same `ecmwf_ifs` values. In the overlap, the Forecast API's `past_days` hours matched the archive too, apart from the most recent day or so, which came from a newer run in one of them.

## Forecast models
`best_match` (the default) picks the best models for the location and blends them by lead time. A provider's `*_seamless` ID blends that provider's regional and global models. Both are convenient for display, but **not for change features**: what goes into the blend depends on the location and the lead time, and it changes when Open-Meteo adds or retires models.

**Observed** to return data at Greenwich in the Forecast API:

| `models=` | Provider | Notes |
|---|---|---|
| `best_match` | Open-Meteo's choice | default |
| `ecmwf_ifs`, `ecmwf_ifs025`, `ecmwf_aifs025_single` | ECMWF | see above |
| `gfs_seamless`, `gfs_global` | NOAA NCEP | GFS: 16 days, 0.11° (~12 km) |
| `icon_seamless`, `icon_global` | DWD (Germany) | ICON global 0.1°; 7.5 days |
| `meteofrance_seamless` | Météo-France | ARPEGE/AROME; about 4 days |
| `ukmo_seamless` | UK Met Office | about 7 days |
| `jma_seamless` | JMA (Japan) | GSM and MSM; about 11 days |
| `gem_seamless` | Environment Canada | about 10 days |
| `knmi_seamless`, `dmi_seamless`, `metno_seamless` | KNMI, DMI, MET Norway | regional models "with ECMWF" for the longer range |

The docs list about 90 forecast models in all: national models from China (CMA), Korea (KMA), Italy, Switzerland, Austria, Czechia and others; NOAA's HRRR, NAM, RRFS and NBM; and AI models such as AIGFS. They also mark several as discontinued: some DWD ICON and NOAA HRRR variants on 2026-11-30, KMA on 2026-03-31, BOM ACCESS-G on 2025-06-26, and NCEP NAM on 2026-11-01. **Don't build on a model without checking its status on the docs page.**

Update cycles and lengths from the provider table:

| Provider | Forecast length | Updates |
|---|---|---|
| ECMWF | 15 days | every 6 h |
| NOAA GFS | 16 days | every 6 h (RRFS and HRRR hourly) |
| DWD ICON | 7.5 days | every 3 h |
| GEM | 10 days | every 6 h |
| JMA | 11 days | |
| UK Met Office | 7 days | |
| Météo-France | 4 days | |

Historical Forecast archive start dates from the docs (pass the same IDs to that endpoint):
- ECMWF IFS HRES 9 km: 2017-01-01
- ECMWF IFS 0.4°: 2022-11-07
- ECMWF IFS 0.25°: 2024-02-03
- ECMWF AIFS 0.25° Single: 2025-02-20
- GFS 0.11°: 2021-03-23
- HRRR: 2018-01-01
- ICON global: 2022-11-24
- JMA GSM/MSM: 2016-01-01
- UKMO global 10 km: 2022-03-01
- MET Nordic: 2022-11-15
- GEM global: 2022-11-23

## Historical Weather API (reanalysis and analysis)
A **reanalysis** re-runs one frozen model version over the past and assimilates every available observation. The result is consistent across decades, but coarse and a few days behind. An **analysis/forecast archive** such as ECMWF IFS has finer detail, but it changes whenever the operational model is upgraded.

| Dataset | `models=` (observed) | Region | Grid | Step | From | Delay |
|---|---|---|---|---|---|---|
| ECMWF IFS | `ecmwf_ifs` | global | 9 km | 1 h | 2017-01-01 | none: through today UTC, every 6 h |
| ECMWF IFS assimilation long-window | `ecmwf_ifs_analysis_long_window` | global | 9 km | 6 h | 2024 | about 2 days (observed: last value 2 days before) |
| ERA5 | `era5` | global | 0.25° (~25 km) | 1 h | 1940 | about 5 days (observed: last value 2026-11-10 23:00 on 11-16) |
| ERA5-Land | `era5_land` | global land | 0.1° (~11 km) | 1 h | 1950 | about 5 days |
| ERA5-Ensemble | `era5_ensemble` | global | 0.5° (~55 km) | 3 h | 1940 | about 5 days |
| ERA5-Seamless | `era5_seamless` | global | 0.1°/0.25° | 1 h | 1940 | about 5 days |
| CERRA | `cerra` | Europe | 5 km | 1 h | 1985 | ended June 2021 |
| Best match | `best_match` (default) | | | | | blends IFS, ERA5 and ERA5-Land |

- **ERA5-Land** is driven by ERA5 ("forcing") and carries only land-surface variables: temperature, humidity, soil and snow. **Observed:** `surface_pressure` is all `null`, and wind, radiation and precipitation are missing too.
- **ERA5-Seamless** combines temperature and humidity from ERA5-Land with wind and radiation from ERA5.
- **CERRA** has data only to June 2021; the docs say it will join best match once it gets real-time updates.
- **The long-window assimilation** has no precipitation or gusts.
- **For decades of consistent data** use ERA5 alone. ECMWF IFS gives "the highest resolution and precision" since 2017, but it isn't one model version: ECMWF upgrades IFS about once a year (cycles 47r3, 48r1, 49r1, 50r1, …).

## Ensembles
An ensemble runs a model many times from slightly perturbed starting conditions. How much the members spread is a direct measure of forecast uncertainty. **Observed** IDs on the Ensemble API, each returning a control run plus perturbed members:

| `models=` (aliases) | Members | Grid / step | Length |
|---|---|---|---|
| `ecmwf_ifs025` (`ecmwf_ifs025_ensemble`) | 51 | 0.25°, 3 h | 15 days |
| `ecmwf_aifs025` (`ecmwf_aifs025_ensemble`) | 51 | 0.25°, 6 h | 15 days |
| `gfs025`, `gfs_seamless` | 31 | 0.25° | 10 days (0.5° to 35 days) |
| `icon_seamless` (`icon_seamless_eps`, `dwd_icon_seamless_eps`) | 40 | ICON-EPS | 7.5 days |

Others from the docs:
- ICON-EU-EPS (40 members, 5 days) and ICON-D2-EPS (20, 2 days)
- GEM (21, 16 days)
- MOGREPS-G (18, 8 days) and MOGREPS-UK (3, 5 days)
- MeteoSwiss ICON-CH1 and ICON-CH2 (11 and 21 members, short range)
- NOAA AIGFS (31, 16 days) and RRFS (5, 2.5 days)
- ECMWF IFS and AIFS Europe at native resolution (51)
- Google WeatherNext 2 (64, 15 days)
- BOM ACCESS-GE (18), with no updates since 2025-06-26

The **Seasonal** API adds ECMWF SEAS5 (to 9 months) and EC46 (to 6 weeks), at 36 km with 51 members.

## Choosing a model
| You need | Use |
|---|---|
| Hourly change features over recent years | `ecmwf_ifs` in the archive: hourly, 9 km, from 2017, no delay. **This library's choice.** |
| An outlook consistent with that history | `ecmwf_ifs` in the Forecast API, with the change measured within that series |
| Decades of consistent data | `era5` (1940+), never spliced to IFS |
| Forecast uncertainty | the Ensemble API, `ecmwf_ifs025` (51 members) |
| How good the forecasts actually were | the Previous Runs API (`ecmwf_ifs` from about October 2025, other models earlier) |
| Upper-air fields | `ecmwf_ifs025` or `ecmwf_aifs025_single` (HRES has no pressure levels) |
| Only "the best weather here" for display | `best_match` |
