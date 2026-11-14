"""Hourly weather sources.

Every source returns the same shape: a DataFrame indexed by tz-aware local time (hourly,
name ``time``), one column per factor key, canonical units (hPa, °C). ``attrs`` records the
``source`` and ``model`` so series from different providers can't be stitched together by
accident (see ``combine``).

**One source, one model.** Different weather models disagree by a few hPa at the same hour,
which is as large as the day-to-day changes this package measures. Splicing two of them
creates fake pressure jumps at the seam.
"""

from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

import numpy as np
import pandas as pd

from .factors import FACTORS, Factor
from .location import Location

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# ECMWF IFS (9 km): hourly from 2017, updated every 6 h with no delay, and the archive serves
# it through the end of "today" (UTC), so one series covers history and the next ~day.
OPEN_METEO_MODEL = "ecmwf_ifs"
EARLIEST = date(2017, 1, 1)
TIME_INDEX = "time"


class WeatherError(RuntimeError):
    """Weather could not be loaded. Messages never include the request URL or coordinates."""


class WeatherSource(Protocol):
    def load_hourly(self, start: date, end: date) -> pd.DataFrame: ...


# ----------------------------------------------------------------------------- Open-Meteo


@dataclass(frozen=True)
class OpenMeteoSource:
    """Open-Meteo historical archive, pinned to one model (``ecmwf_ifs``).

    Sends only the rounded coordinates, optional elevation, a date range and variable names,
    with the default urllib User-Agent. Free for non-commercial use; data is CC BY 4.0
    ("Weather data by Open-Meteo.com").
    """

    location: Location
    timeout: float = 10.0
    factors: tuple[Factor, ...] = FACTORS
    opener: Callable[..., Any] | None = field(default=None, repr=False, compare=False)

    def url(self, start: date, end: date) -> str:
        params: dict[str, object] = {
            "latitude": self.location.latitude,
            "longitude": self.location.longitude,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": ",".join(f.api_var for f in self.factors),
            "models": OPEN_METEO_MODEL,
            "timeformat": "unixtime",
            "timezone": self.location.timezone or "auto",
        }
        if self.location.elevation is not None:
            params["elevation"] = self.location.elevation
        return f"{ARCHIVE_URL}?{urllib.parse.urlencode(params)}"

    def load_hourly(self, start: date, end: date) -> pd.DataFrame:
        start = max(start, EARLIEST)
        # The archive's last allowed end_date is about today (UTC); ask for tomorrow and, if
        # refused, retry once with the limit the service reports.
        end = min(end, datetime.now(UTC).date() + timedelta(days=1))
        if start > end:
            raise WeatherError("empty date range")
        try:
            payload = self._get(start, end)
        except _OutOfRange as exc:
            if exc.max_end is None or exc.max_end < start or exc.max_end >= end:
                raise WeatherError("weather service rejected the date range") from None
            payload = self._get(start, exc.max_end)
        return parse_open_meteo(payload, self.factors)

    def _get(self, start: date, end: date) -> dict:
        return _fetch(self.opener, self.url(start, end), self.timeout)


@dataclass(frozen=True)
class OpenMeteoForecastSource:
    """Open-Meteo forecast API, same model (``ecmwf_ifs``): the last ``past_days`` and the
    next ``forecast_days``, always reaching past "now" whatever the time zone.

    Use it for outlooks only, computing each change *within* this series. It is labelled
    as a different source from the archive, so ``combine`` refuses to splice the two: the
    endpoints disagree by a few hPa at the same hour. 31 past days are enough for
    ``decycle`` to remove the daily cycle from short-window changes.
    """

    location: Location
    past_days: int = 31
    forecast_days: int = 3
    timeout: float = 10.0
    factors: tuple[Factor, ...] = FACTORS
    opener: Callable[..., Any] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not 0 <= self.past_days <= 92 or not 1 <= self.forecast_days <= 16:
            raise ValueError("past_days must be 0-92 and forecast_days 1-16")

    def url(self) -> str:
        params: dict[str, object] = {
            "latitude": self.location.latitude,
            "longitude": self.location.longitude,
            "past_days": self.past_days,
            "forecast_days": self.forecast_days,
            "hourly": ",".join(f.api_var for f in self.factors),
            "models": OPEN_METEO_MODEL,
            "timeformat": "unixtime",
            "timezone": self.location.timezone or "auto",
        }
        if self.location.elevation is not None:
            params["elevation"] = self.location.elevation
        return f"{FORECAST_URL}?{urllib.parse.urlencode(params)}"

    def load_recent(self) -> pd.DataFrame:
        payload = _fetch(self.opener, self.url(), self.timeout)
        return parse_open_meteo(payload, self.factors, source="open-meteo-forecast")


def _fetch(opener: Callable[..., Any] | None, url: str, timeout: float) -> dict:
    opener = opener or urllib.request.urlopen  # looked up late so tests can block it
    try:
        with opener(url, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = _read_error_body(exc)
        if exc.code == 400 and "out of allowed range" in body:
            raise _OutOfRange(_max_end(body)) from None
        raise WeatherError(f"weather service returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise WeatherError("could not reach the weather service") from None
    except ValueError:
        raise WeatherError("weather service sent an unreadable response") from None


class _OutOfRange(Exception):
    def __init__(self, max_end: date | None) -> None:
        self.max_end = max_end


def _read_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", "replace")
    except Exception:
        return ""


def _max_end(body: str) -> date | None:
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", body)
    try:
        return date.fromisoformat(dates[-1]) if dates else None
    except ValueError:
        return None


def parse_open_meteo(
    payload: dict, factors: Sequence[Factor] = FACTORS, *, source: str = "open-meteo"
) -> pd.DataFrame:
    """Turn an Open-Meteo response (``timeformat=unixtime``) into the standard hourly frame."""
    try:
        hourly = payload["hourly"]
        zone = payload.get("timezone") or "UTC"
        times = pd.to_datetime(np.asarray(hourly["time"], dtype="int64"), unit="s", utc=True)
        columns = {}
        for f in factors:
            # A single pinned model normally returns plain names; tolerate the suffixed form.
            values = hourly.get(f.api_var, hourly.get(f"{f.api_var}_{OPEN_METEO_MODEL}"))
            if values is None:
                raise KeyError(f.api_var)
            columns[f.key] = pd.to_numeric(pd.Series(values, dtype="object"), errors="coerce")
    except (KeyError, TypeError, ValueError):
        raise WeatherError("weather response is missing expected fields") from None

    index = pd.DatetimeIndex(times.tz_convert(zone), name=TIME_INDEX)
    frame = pd.DataFrame({k: v.to_numpy(dtype="float64") for k, v in columns.items()}, index=index)
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    frame.attrs = {"source": source, "model": OPEN_METEO_MODEL, "temperature_unit": "C"}
    return frame


# ------------------------------------------------------------------------------ synthetic


@dataclass(frozen=True)
class SyntheticWeatherSource:
    """Plausible invented weather for demos and tests. No network, no real place.

    Generated hour by hour from a fixed epoch (2017-01-01), so any date range is the same
    slice of one long series no matter who asks for it.

    - Pressure: a quasi-periodic (~6-day) synoptic process whose swings are larger in winter,
      plus the twice-daily atmospheric tide.
    - Dew point: seasonal, lower when pressure is high (dry air under highs), slow noise.
    - Temperature: seasonal and diurnal, also nudged by the pressure pattern. Never below the
      dew point.
    """

    seed: int = 0
    timezone: str = "UTC"
    base_pressure: float = 1013.0

    def load_hourly(self, start: date, end: date) -> pd.DataFrame:
        if start > end:
            raise WeatherError("empty date range")
        if start < EARLIEST:
            raise WeatherError("synthetic weather starts on 2017-01-01")
        epoch = pd.Timestamp(EARLIEST, tz=self.timezone)
        stop = pd.Timestamp(end + timedelta(days=1), tz=self.timezone)
        index = pd.date_range(epoch, stop, freq="h", inclusive="left", name=TIME_INDEX)
        frame = self._generate(index)
        frame = frame.loc[pd.Timestamp(start, tz=self.timezone) :]
        frame.attrs = {"source": "synthetic", "model": f"seed-{self.seed}", "temperature_unit": "C"}
        return frame

    def _generate(self, index: pd.DatetimeIndex) -> pd.DataFrame:
        n = len(index)
        hours = np.arange(n, dtype="float64")
        doy = index.day_of_year.to_numpy(dtype="float64")
        hour = index.hour.to_numpy(dtype="float64")
        winter = np.cos(2 * np.pi * (doy - 15) / 365.25)  # +1 mid-Jan, -1 mid-Jul

        # Synoptic pressure: AR(2) on a 3-hour grid, unit stationary variance, then scaled.
        steps = n // 3 + 2
        period, damping = 48.0, 0.985  # 48 x 3 h = 6 days
        a1, a2 = 2 * damping * math.cos(2 * math.pi / period), -(damping**2)
        noise = np.random.default_rng([self.seed, 0]).normal(size=steps)
        synoptic = _ar2(noise, a1, a2) / math.sqrt(_ar2_variance(a1, a2))
        synoptic = np.interp(hours, np.arange(steps) * 3.0, synoptic)
        pressure_sd = 3.2 + 1.4 * winter  # hPa: stormier winters, calmer summers
        tide = 0.8 * np.cos(2 * np.pi * (hour - 10) / 12)
        pressure = self.base_pressure + pressure_sd * synoptic + tide

        days = n // 24 + 2
        dew_noise = np.random.default_rng([self.seed, 1]).normal(size=days)
        dew_slow = np.interp(hours, np.arange(days) * 24.0, _ar1(dew_noise, 0.75) * 1.8)
        season = np.sin(2 * np.pi * (doy - 110) / 365.25)  # +1 late Jul, -1 late Jan
        dew = 3 + 8 * season - 1.4 * synoptic + dew_slow + 0.6 * np.sin(2 * np.pi * hour / 24)

        temp_noise = np.random.default_rng([self.seed, 2]).normal(size=days)
        temp_slow = np.interp(hours, np.arange(days) * 24.0, _ar1(temp_noise, 0.7) * 2.2)
        diurnal = 6 * np.cos(2 * np.pi * (hour - 15) / 24)
        temperature = 11 + 11 * season + diurnal - 1.0 * synoptic + temp_slow
        dew = np.minimum(dew, temperature - 0.5)

        return pd.DataFrame(
            {
                "pressure": np.round(pressure, 1),
                "dew_point": np.round(dew, 1),
                "temperature": np.round(temperature, 1),
            },
            index=index,
        )


def _ar1(noise: np.ndarray, phi: float) -> np.ndarray:
    out = np.empty_like(noise)
    x = 0.0
    for i, e in enumerate(noise):
        x = phi * x + e * math.sqrt(1 - phi**2)
        out[i] = x
    return out


def _ar2(noise: np.ndarray, a1: float, a2: float) -> np.ndarray:
    out = np.empty_like(noise)
    x1 = x2 = 0.0
    for i, e in enumerate(noise):
        x = a1 * x1 + a2 * x2 + e
        out[i] = x
        x1, x2 = x, x1
    return out


def _ar2_variance(a1: float, a2: float) -> float:
    """Stationary variance of an AR(2) driven by unit-variance noise."""
    return (1 - a2) / ((1 + a2) * ((1 - a2) ** 2 - a1**2))


# ---------------------------------------------------------------------------- seam guard


def combine(*frames: pd.DataFrame) -> pd.DataFrame:
    """Concatenate hourly frames from the *same* source and model, e.g. cached chunks.

    Raises ``WeatherError`` when sources or models differ: their offsets would show up as
    fake jumps exactly where one series hands over to the next.
    """
    if not frames:
        raise ValueError("nothing to combine")
    origins = {(f.attrs.get("source"), f.attrs.get("model")) for f in frames}
    if len(origins) != 1 or None in next(iter(origins)):
        raise WeatherError("refusing to combine weather from different sources or models")
    units = {f.attrs.get("temperature_unit", "C") for f in frames}
    if len(units) != 1:
        raise WeatherError("refusing to combine weather in different units")
    out = pd.concat(frames)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out.attrs = dict(frames[-1].attrs)
    return out
