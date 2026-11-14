# winds-of-change

A small Python library that turns hourly weather into daily **change** features (pressure, dew point, temperature over 3–48 h windows) and relates them to daily health-log outcomes. It is a **public GitHub repo** (portfolio piece), so it must never contain anyone's location, health data or credentials.

Consumers:
- `~/project/pain_tracker` (the health-log-dashboard) depends on it from PyPI and builds its Weather page on this library.
- `~/project/migraine` notebooks may use it, or the `woc` CLI's CSV export.

## Commands
```bash
uv sync
uv run pytest                     # offline; conftest blocks urllib
uv run ruff check . && uv run ruff format .
uv run pre-commit run --all-files # ruff, gitleaks, hygiene
uv build
```
Add dependencies with `uv add` / `uv add --dev`, never by editing `uv.lock`. The core stays pandas + numpy + stdlib: no Streamlit, Plotly or requests. A future explorer app would go behind an optional `[app]` extra.

## Layout
`src/winds_of_change/`:
- `location`: `Location` rounds to 0.1° and 10 m and hides coordinates in its repr.
- `factors`: `FACTORS`, `Units`, `convert`.
- `sources`: `OpenMeteoSource` (archive), `OpenMeteoForecastSource` (outlooks), `SyntheticWeatherSource`, `combine`, `WeatherError`.
- `features`: `decycle`, `window_changes`, `daily_weather`, `outlook`.
- `analysis`: `anomaly`, `change_bins`, `align_lag`, `response_by_change`, `event_profile`.
- `cli`: `woc features`.

Public API is re-exported in `__init__`.

Hourly frame contract: tz-aware local `time` index, factor-key columns, canonical hPa/°C, `attrs` with `source`, `model` and `temperature_unit`. Daily frames have a naive `date` index covering every day.

## Rules
- **Privacy.**
  - Never put real coordinates, a city, station IDs or any weather fetched for a real place into code, tests, docs, examples or commit messages. Examples use neutral places (e.g. Greenwich 51.5, 0.0).
  - Tests use synthetic weather or hand-built frames and canned JSON only.
  - Error messages and reprs never include coordinates or the request URL (`raise WeatherError(...) from None`).
  - Requests use the default urllib User-Agent, nothing tied to this project.
- **Never copy values** from `~/project/migraine` (MigraineBuddy exports, NOAA station CSVs) or from pain_tracker's `data/` into this repo.
- **One source, one model.** Never splice weather from different endpoints or models into one series: Open-Meteo's archive and historical-forecast APIs differed by 2.1 ± 1.9 hPa (max 6.6 hPa) for the same hours, as large as the signal. `OpenMeteoSource` pins `models=ecmwf_ifs`, and `combine` enforces the rule. `OpenMeteoForecastSource` (same model) exists only for outlooks: measure each change within it, rank it against archive history (`outlook(..., history=)`), and never splice it into the archive (its `source` attr differs).
- **Changes, not levels.** Window changes are de-cycled first (diurnal cycle, pressure tide), and the daily value is the peak signed change. Keep that definition the same for every window.
- **Honest analysis.** Keep the caveats in the docstrings: association not cause, the day before is not a placebo, and SEs are optimistic under autocorrelation.
- Every commit passes pre-commit (gitleaks + ruff). Never use `--no-verify`. CI also runs gitleaks over the full history.

## Conventions
- Default branch is **`trunk`**.
- Commits use the user's global git identity. Keep messages short and imperative; explain why in the body.
- Python 3.13, type hints on public functions, ruff (line length 100).
- Releases: bump `version`, update `CHANGELOG.md`, tag `vX.Y.Z`. `release.yml` checks the tag matches, builds, publishes to PyPI (trusted publishing from the `pypi` environment, which only `v*` tags can deploy to; no token) and attaches the wheel and sdist to a GitHub Release. Consumers then run `uv lock --upgrade-package winds-of-change`. A PyPI version can never be re-uploaded, only yanked: a mistake means a new version number.
- GitHub: two accounts are logged into `gh`. Confirm `jordan-finnell` is active (`gh auth status`) before pushing or releasing.
