import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from winds_of_change import (
    BIN_LABELS,
    SyntheticWeatherSource,
    align_lag,
    anomaly,
    change_bins,
    daily_weather,
    event_days,
    event_profile,
    response_by_change,
)


def days(n, start="2025-01-01"):
    return pd.date_range(start, periods=n, freq="D", name="date")


def test_anomaly_is_leave_one_out():
    idx = days(60)
    s = pd.Series(3.0, index=idx)
    s.iloc[30] = 8.0
    a = anomaly(s.to_frame("x"))["x"]
    assert a.iloc[30] == pytest.approx(5.0)  # the spike isn't in its own baseline
    assert a.iloc[25] < 0  # neighbours see it in theirs
    assert a.iloc[0] == pytest.approx(0.0)


def test_anomaly_needs_enough_other_days():
    s = pd.Series(np.nan, index=days(40))
    s.iloc[[5, 6, 7]] = 2.0
    assert anomaly(s.to_frame("x"), min_periods=10)["x"].isna().all()


def test_lag_direction_and_gaps():
    idx = days(10)
    change = pd.Series(0.0, index=idx)
    change.iloc[4] = -9.0  # big drop on day 5
    sparse = idx.delete([6, 7])  # outcomes missing two days
    assert align_lag(change, 1, idx).iloc[5] == -9.0  # day 6 sees day 5's change
    assert align_lag(change, 0, idx).iloc[4] == -9.0
    aligned = align_lag(change, 1, sparse)
    assert aligned.loc[idx[5]] == -9.0 and aligned.drop(idx[5]).abs().max() == 0


def test_bins_thresholds_and_labels():
    change = pd.Series(np.arange(-50.0, 50.0), index=days(100))
    bins = change_bins(change, q=0.2)
    assert bins.drop_below == pytest.approx(change.quantile(0.2))
    labels = bins.assign(change)
    assert list(labels.cat.categories) == list(BIN_LABELS)
    assert (labels == "Big drop").sum() == 20 and (labels == "Big rise").sum() == 20
    assert labels.iloc[50] == "Typical"
    few = change_bins(change.iloc[:5])
    assert math.isnan(few.drop_below) and few.assign(change).isna().all()


def _drop_then_symptom(n=300, seed=0):
    rng = np.random.default_rng(seed)
    idx = days(n)
    change = pd.Series(rng.normal(0, 3, n), index=idx)
    outcome = pd.Series(rng.normal(3, 0.5, n), index=idx)
    big = change <= change.quantile(0.2)
    outcome[big.shift(1, fill_value=False).to_numpy()] += 2  # worse the day after a big drop
    return change, outcome


def test_response_finds_a_next_day_effect_only_at_lag_one():
    change, outcome = _drop_then_symptom()
    anoms = anomaly(outcome.to_frame("headache"))
    bins = change_bins(change)
    lag1 = response_by_change(anoms, change, bins, lag=1).set_index("bin")
    lag0 = response_by_change(anoms, change, bins, lag=0).set_index("bin")
    assert list(lag1.columns) == ["metric", "mean", "se", "n", "z"]
    assert lag1.loc["Big drop", "mean"] > 1.2 and lag1.loc["Big drop", "z"] > 5
    assert abs(lag0.loc["Big drop", "mean"]) < 0.6
    assert lag1.loc["Big drop", "n"] == pytest.approx(60, abs=2)


def test_response_blanks_small_cells():
    change, outcome = _drop_then_symptom(n=40)
    resp = response_by_change(anomaly(outcome.to_frame("x")), change, change_bins(change), min_n=10)
    small = resp[resp["n"] < 10]
    assert not small.empty and small["mean"].isna().all()


def test_event_days_keep_only_the_first_day_of_a_run():
    change = pd.Series([0, -9, -9, 0, 0, -9, 0, 9, 9, 0] * 3, index=days(30), dtype=float)
    bins = change_bins(change, q=0.2)
    drops = event_days(change, bins, "drop")
    assert list(drops.day[:2]) == [2, 6]
    assert len(event_days(change, bins, "rise")) == 3


def test_event_profile_peaks_after_the_event():
    change, outcome = _drop_then_symptom(n=400, seed=1)
    anom = anomaly(outcome.to_frame("x"))["x"]
    prof = event_profile(anom, change, change_bins(change), "drop")
    assert list(prof.index) == [-2, -1, 0, 1, 2, 3]
    assert prof["mean"].idxmax() == 1
    assert prof.loc[1, "ci_low"] > 0
    assert prof.attrs["events"] >= 5
    none = event_profile(anom, change, change_bins(change), "drop", min_events=10_000)
    assert none["mean"].isna().all()


def test_end_to_end_on_synthetic_weather():
    hourly = SyntheticWeatherSource(seed=9).load_hourly(date(2024, 1, 1), date(2024, 12, 31))
    daily = daily_weather(hourly, windows=(24,))
    change = daily["pressure_change_24h"]
    rng = np.random.default_rng(2)
    outcome = pd.Series(rng.normal(4, 1, len(daily)), index=daily.index)
    outcome += 0.4 * (-change.shift(1).clip(upper=0)).fillna(0)  # pain after pressure falls
    resp = response_by_change(anomaly(outcome.to_frame("pain")), change, change_bins(change), lag=1)
    by_bin = resp.set_index("bin")["mean"]
    assert by_bin["Big drop"] > by_bin["Typical"] > by_bin["Big rise"] - 0.3
    assert by_bin["Big drop"] > 0.5
