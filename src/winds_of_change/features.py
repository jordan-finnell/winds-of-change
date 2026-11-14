"""Hourly weather -> change features, per local calendar day.

The headline numbers are always *changes* over a window of ``w`` hours, never absolute values.

- **De-cycling.** Pressure has a twice-daily tide of about 1-2 hPa, and temperature and dew
  point swing every day. Over a 3- or 6-hour window those cycles would look like a "drop"
  every afternoon. ``decycle`` subtracts each hour-of-day's typical deviation from the daily
  mean (over the surrounding ~30 days) and keeps the level. Changes over 24 h or 48 h compare
  the same clock time, so de-cycling barely affects them.
- **One number per day.** For a window ``w`` the day's value is the *peak* signed ``w``-hour
  change ending within that day: the largest move in either direction, sign kept. The same
  definition is used for every window, so switching windows never changes what the number
  means. ``summary="mean"`` gives the day's average change instead; for 24 h that equals the
  day-over-day change of daily means.
- **Resolution.** Model data (e.g. ECMWF IFS) is smooth: fine for 3 h and longer, but it
  misses sub-3-hour jumps such as thunderstorm pressure spikes. Use station observations
  (a separate source) for 1-2 h windows.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

import pandas as pd

DEFAULT_WINDOWS: tuple[int, ...] = (3, 6, 12, 24, 48)
DATE_INDEX = "date"


def change_column(key: str, hours: int) -> str:
    return f"{key}_change_{hours}h"


def _local_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Local calendar date of each timestamp, as naive midnight timestamps."""
    local = index.tz_localize(None) if index.tz is not None else index
    return local.normalize()


def decycle(series: pd.Series, window_days: int = 30) -> pd.Series:
    """Remove the typical daily cycle from an hourly series, keeping its level.

    For each day and hour of day, the deviation from that day's mean is averaged over a
    centred ``window_days`` window and subtracted. DST days (23 or 25 hours) are handled by
    grouping on the local hour.
    """
    if series.empty:
        return series.copy()
    dates = _local_dates(series.index)
    hours = series.index.hour
    deviation = series - series.groupby(dates).transform("mean")
    table = deviation.groupby([dates, hours]).mean().unstack()
    full = pd.date_range(table.index.min(), table.index.max(), freq="D")
    table = table.reindex(index=full, columns=range(24))
    smooth = table.rolling(window_days, center=True, min_periods=max(1, window_days // 3)).mean()
    cycle = smooth.stack(future_stack=True).reindex(pd.MultiIndex.from_arrays([dates, hours]))
    out = series - cycle.fillna(0.0).to_numpy()
    out.name = series.name
    return out


def window_changes(series: pd.Series, hours: int, *, decycled: bool = True) -> pd.Series:
    """x(t) - x(t - hours) on an hourly, tz-aware series (absolute time, so DST-safe)."""
    if hours < 1:
        raise ValueError("hours must be >= 1")
    x = decycle(series) if decycled else series
    earlier = x.shift(freq=pd.Timedelta(hours=hours)).reindex(x.index)
    return x - earlier


def daily_weather(
    hourly: pd.DataFrame,
    windows: Iterable[int] = DEFAULT_WINDOWS,
    *,
    min_hours: int = 18,
    summary: Literal["peak", "mean"] = "peak",
    decycled: bool = True,
) -> pd.DataFrame:
    """One row per local calendar day (naive ``date`` index, every day in range).

    Columns: ``<key>`` (daily mean, context only) and ``change_column(key, w)`` for each
    window. A value is NaN when the day has fewer than ``min_hours`` usable hours.
    """
    windows = tuple(windows)
    if summary not in ("peak", "mean"):
        raise ValueError("summary must be 'peak' or 'mean'")
    if hourly.empty:
        cols = [c for k in hourly.columns for c in (k, *(change_column(k, w) for w in windows))]
        return pd.DataFrame(columns=cols, index=pd.DatetimeIndex([], name=DATE_INDEX))

    dates = _local_dates(hourly.index)
    out: dict[str, pd.Series] = {}
    for key in hourly.columns:
        s = hourly[key]
        groups = s.groupby(dates)
        out[key] = groups.mean().where(groups.count() >= min_hours)
        for w in windows:
            ch = window_changes(s, w, decycled=decycled)
            out[change_column(key, w)] = _summarise(ch, dates, min_hours, summary)

    frame = pd.DataFrame(out)
    full = pd.date_range(frame.index.min(), frame.index.max(), freq="D", name=DATE_INDEX)
    frame = frame.reindex(full)
    frame.attrs = dict(hourly.attrs)
    return frame


def _summarise(ch: pd.Series, dates: pd.DatetimeIndex, min_hours: int, summary: str) -> pd.Series:
    counts = ch.groupby(dates).count()
    if summary == "mean":
        value = ch.groupby(dates).mean()
    else:
        valid = ch.dropna()
        valid_dates = _local_dates(valid.index)
        frame = pd.DataFrame(
            {"v": valid.to_numpy(), "a": valid.abs().to_numpy()}, index=valid_dates
        )
        frame = frame.sort_values("a", kind="stable")
        value = frame.groupby(level=0)["v"].last()
        value = value.reindex(counts.index)
    return value.where(counts >= min_hours)


@dataclass(frozen=True)
class Outlook:
    """Recent and upcoming change for one factor over ``hours``, at ``now``.

    ``*_percentile`` is the share of historical ``hours``-hour changes (up to ``now``) that
    were smaller in size, so 0.9 means "larger than 90% of changes". NaN when unknown, e.g.
    the series doesn't reach ``now + hours``.
    """

    key: str
    hours: int
    now: pd.Timestamp
    last: float
    next: float
    last_percentile: float
    next_percentile: float


def outlook(
    hourly: pd.DataFrame,
    key: str,
    now: pd.Timestamp,
    hours: int = 24,
    *,
    history: pd.DataFrame | None = None,
) -> Outlook:
    """Change over the last and the next ``hours``, from a series reaching past ``now``.

    Both changes are measured within ``hourly`` (e.g. a forecast series), never across two
    sources. Percentiles rank them against ``history`` (e.g. a long archive series) when
    given, otherwise against ``hourly`` itself.
    """
    s = decycle(hourly[key].dropna())
    nan = math.nan
    if s.empty:
        return Outlook(key, hours, now, nan, nan, nan, nan)
    tz = s.index.tz
    now = pd.Timestamp(now)
    now = (now.tz_convert(tz) if now.tzinfo else now.tz_localize(tz)).floor("h")
    step = pd.Timedelta(hours=hours)

    def at(t: pd.Timestamp) -> float:
        return float(s.get(t, nan))

    last = at(now) - at(now - step)
    upcoming = at(now + step) - at(now)
    use_history = history is not None and key in history
    past = decycle(history[key].dropna()) if use_history else s
    if past.index.tz is not None and str(past.index.tz) != str(tz):
        past = past.tz_convert(tz)
    history_changes = window_changes(past, hours, decycled=False).loc[:now].dropna().abs()

    def pct(value: float) -> float:
        if math.isnan(value) or history_changes.empty:
            return nan
        return float((history_changes < abs(value)).mean())

    return Outlook(key, hours, now, last, upcoming, pct(last), pct(upcoming))


def outlooks(
    hourly: pd.DataFrame,
    keys: Sequence[str],
    now: pd.Timestamp,
    hours: int = 24,
    *,
    history: pd.DataFrame | None = None,
) -> list[Outlook]:
    return [outlook(hourly, k, now, hours, history=history) for k in keys if k in hourly]
