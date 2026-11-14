"""Relate daily weather changes to daily outcomes (symptom ratings, mood scores, ...).

Outcomes are any DataFrame indexed by calendar day (naive dates, one row per day, NaN for
missing days), one column per metric. These are associations, not proof of cause:

- Outcomes are compared with the person's own usual level around that time (``anomaly``),
  so seasons, treatment changes or life events don't masquerade as weather effects. That
  matters because weather variability is itself seasonal.
- Day-to-day weather changes overlap in time, so the day *before* a change is not a clean
  control. Treat days before an event as context, not a placebo.
- Simple standard errors ignore autocorrelation, so they are somewhat optimistic; and with
  many metrics, factors, windows and lags, some cells will look clear by chance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

BIG_DROP, TYPICAL, BIG_RISE = "Big drop", "Typical", "Big rise"
BIN_LABELS: tuple[str, str, str] = (BIG_DROP, TYPICAL, BIG_RISE)
Kind = Literal["drop", "rise"]


def anomaly(outcomes: pd.DataFrame, window: int = 29, min_periods: int = 10) -> pd.DataFrame:
    """Each value minus the mean of the *other* days in a centred ``window``-day window.

    Leave-one-out, so a day never counts towards its own baseline. NaN where fewer than
    ``min_periods`` other days have data.
    """
    if window < 3:
        raise ValueError("window must be >= 3")
    roll = outcomes.rolling(f"{window}D", center=True, min_periods=1)
    total, count = roll.sum(), roll.count()
    others = count - outcomes.notna()
    baseline = (total - outcomes.fillna(0.0)) / others.where(others >= min_periods)
    return outcomes - baseline


def align_lag(change: pd.Series, lag: int, index: pd.Index) -> pd.Series:
    """The weather change ``lag`` days *before* each day in ``index``.

    ``lag=0`` pairs a day with its own change, ``lag=1`` pairs symptoms on day D with the
    change on D-1. Shifts by calendar days, so gaps in the data can't misalign it.
    """
    return change.shift(lag, freq="D").reindex(index)


@dataclass(frozen=True)
class ChangeBins:
    """Thresholds for the steepest ``q`` share of drops and of rises."""

    drop_below: float
    rise_above: float
    q: float
    n: int

    def assign(self, change: pd.Series) -> pd.Series:
        labels = pd.Series(pd.NA, index=change.index, dtype="object")
        if math.isnan(self.drop_below) or math.isnan(self.rise_above):
            return pd.Series(pd.Categorical(labels, categories=BIN_LABELS), index=change.index)
        valid = change.notna()
        labels[valid] = TYPICAL
        labels[valid & (change <= self.drop_below)] = BIG_DROP
        labels[valid & (change >= self.rise_above)] = BIG_RISE
        return pd.Series(pd.Categorical(labels, categories=BIN_LABELS), index=change.index)


def change_bins(change: pd.Series, q: float = 0.2, min_n: int = 10) -> ChangeBins:
    """Bottom ``q`` = "Big drop", top ``q`` = "Big rise", the rest "Typical".

    Compute over the whole span you have, so thresholds are stable and sample sizes large.
    Returns NaN thresholds when fewer than ``min_n`` changes are available.
    """
    if not 0 < q < 0.5:
        raise ValueError("q must be between 0 and 0.5")
    valid = change.dropna()
    if len(valid) < min_n:
        return ChangeBins(math.nan, math.nan, q, len(valid))
    return ChangeBins(float(valid.quantile(q)), float(valid.quantile(1 - q)), q, len(valid))


def response_by_change(
    anomalies: pd.DataFrame,
    change: pd.Series,
    bins: ChangeBins,
    lag: int = 0,
    min_n: int = 10,
) -> pd.DataFrame:
    """Mean anomaly of every metric on big-drop, typical and big-rise days.

    Long format, one row per (metric, bin) in column then bin order: ``metric``, ``bin``,
    ``mean``, ``se``, ``n``, ``z`` (mean / se). ``mean``/``se``/``z`` are NaN below ``min_n``.
    """
    groups = bins.assign(align_lag(change, lag, anomalies.index))
    rows = []
    for metric in anomalies.columns:
        values = anomalies[metric]
        for label in BIN_LABELS:
            v = values[(groups == label).fillna(False).to_numpy()].dropna()
            n = len(v)
            if n >= max(min_n, 2):
                mean = float(v.mean())
                se = float(v.std(ddof=1) / math.sqrt(n))
                z = mean / se if se > 0 else math.nan
            else:
                mean = se = z = math.nan
            rows.append({"metric": metric, "bin": label, "mean": mean, "se": se, "n": n, "z": z})
    return pd.DataFrame(rows, columns=["metric", "bin", "mean", "se", "n", "z"])


def event_days(change: pd.Series, bins: ChangeBins, kind: Kind) -> pd.DatetimeIndex:
    """First day of each run of consecutive big-drop (or big-rise) days."""
    if kind not in ("drop", "rise"):
        raise ValueError("kind must be 'drop' or 'rise'")
    label = BIG_DROP if kind == "drop" else BIG_RISE
    hit = (bins.assign(change) == label).fillna(False).astype(bool)
    before = hit.shift(1, freq="D").reindex(hit.index, fill_value=False).astype(bool)
    return pd.DatetimeIndex(hit.index[(hit & ~before).to_numpy()])


def event_profile(
    anomaly_series: pd.Series,
    change: pd.Series,
    bins: ChangeBins,
    kind: Kind,
    offsets: range = range(-2, 4),
    min_events: int = 5,
) -> pd.DataFrame:
    """Average anomaly from ``offsets[0]`` to ``offsets[-1]`` days around big changes.

    Index ``offset`` (days relative to the event); columns ``mean``, ``ci_low``, ``ci_high``
    (95%, normal approximation) and ``n`` (events with a value that day). ``attrs["events"]``
    holds the number of events inside the outcome's span. All NaN below ``min_events``.
    """
    events = event_days(change, bins, kind)
    observed = anomaly_series.dropna()
    if not observed.empty:
        events = events[(events >= observed.index.min()) & (events <= observed.index.max())]
    else:
        events = events[:0]
    rows = []
    for k in offsets:
        v = anomaly_series.reindex(events + pd.Timedelta(days=k)).dropna()
        n = len(v)
        if len(events) >= min_events and n >= 2:
            mean = float(v.mean())
            half = 1.96 * float(v.std(ddof=1)) / math.sqrt(n)
            rows.append((k, mean, mean - half, mean + half, n))
        else:
            rows.append((k, np.nan, np.nan, np.nan, n))
    out = pd.DataFrame(rows, columns=["offset", "mean", "ci_low", "ci_high", "n"]).set_index(
        "offset"
    )
    out.attrs["events"] = len(events)
    return out
