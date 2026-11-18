import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from winds_of_change import (
    BAND_LABELS,
    BIN_LABELS,
    SyntheticWeatherSource,
    align_lag,
    anomaly,
    change_bands,
    change_bins,
    daily_weather,
    event_days,
    event_profile,
    response_by_band,
    response_by_change,
)
from winds_of_change.analysis import _spells, _t975


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


def test_bands_split_signed_quantiles_and_match_the_bins():
    change = pd.Series(np.arange(-50.0, 50.0), index=days(100))
    bands = change_bands(change, big=0.1, moderate=0.25)
    labels = bands.assign(change)
    assert list(labels.cat.categories) == list(BAND_LABELS)
    counts = labels.value_counts()
    assert (counts["Big drop"], counts["Drop"], counts["Steady"]) == (10, 15, 50)
    assert (counts["Rise"], counts["Big rise"]) == (15, 10)
    bins = change_bins(change, q=0.1)  # the outer bands are the same days as the bins
    assert ((labels == "Big drop") == (bins.assign(change) == "Big drop")).all()
    assert ((labels == "Big rise") == (bins.assign(change) == "Big rise")).all()
    few = change_bands(change.iloc[:5])
    assert not few.ready and few.assign(change).isna().all()
    with pytest.raises(ValueError):
        change_bands(change, big=0.3, moderate=0.25)


def _dose(n=400, seed=1, effect=-0.4):
    """Next-day outcome falls in proportion to the size of a drop; rises do nothing."""
    rng = np.random.default_rng(seed)
    idx = days(n)
    change = pd.Series(rng.normal(0, 3, n), index=idx)
    outcome = pd.Series(rng.normal(5, 0.5, n), index=idx)
    drop_size = -change.clip(upper=0).shift(1, fill_value=0.0)  # >= 0, yesterday's drop
    return change, outcome + effect * drop_size  # lower the day after a bigger drop


def test_response_by_band_shows_a_dose_response():
    change, outcome = _dose()
    anoms = anomaly(outcome.to_frame("energy"))
    resp = response_by_band(anoms, change, change_bands(change), lag=1).set_index("band")
    assert list(resp.index) == list(BAND_LABELS)
    assert list(resp.columns) == [
        "metric", "change", "mean", "se", "ci_low", "ci_high", "n", "spells"
    ]  # fmt: skip
    means = resp["mean"]
    assert means["Big drop"] < means["Drop"] < means["Steady"]  # graded, not just big/small
    assert abs(means["Big rise"] - means["Rise"]) < 0.5  # rises do nothing
    assert resp.loc["Big drop", "ci_high"] < 0 < resp.loc["Steady", "ci_high"]
    assert resp["change"].is_monotonic_increasing  # median change runs drop -> rise
    assert resp.loc["Big drop", "n"] == pytest.approx(40, abs=2)


def test_spells_cluster_nearby_days_and_widen_the_interval():
    idx = days(200)
    # Five 4-day runs of big drops; inside a run the outcome moves together.
    change = pd.Series(0.0, index=idx)
    outcome = pd.Series(np.random.default_rng(3).normal(0, 0.3, 200), index=idx)
    shared = [1.5, -0.5, 1.0, 2.0, 0.0]
    for k, start in enumerate(range(20, 200, 36)):
        change.iloc[start : start + 4] = -10.0
        outcome.iloc[start : start + 4] += shared[k]
    change.iloc[::7] += 5.0  # rises elsewhere so the quantiles split
    bands = change_bands(change, big=0.1, moderate=0.2)
    resp = response_by_band(outcome.to_frame("x"), change, bands, min_n=10, min_spells=5)
    big = resp.set_index("band").loc["Big drop"]
    assert big["n"] == 20 and big["spells"] == 5
    naive_se = outcome[change <= bands.big_drop_below].std(ddof=1) / math.sqrt(20)
    assert big["se"] > 1.5 * naive_se  # four days of one spell aren't four observations
    assert big["ci_high"] - big["mean"] == pytest.approx(_t975(4) * big["se"])


def test_spells_and_t_values():
    d = pd.DatetimeIndex(["2025-01-01", "2025-01-02", "2025-01-04", "2025-01-08"])
    assert list(_spells(d, gap=2)) == [0, 0, 0, 1]
    assert list(_spells(d, gap=1)) == [0, 0, 1, 2]
    assert len(_spells(d[:0], gap=2)) == 0
    for df, exact in ((3, 3.182), (4, 2.776), (30, 2.042), (31, 2.040), (60, 2.000)):
        assert _t975(df) == pytest.approx(exact, abs=0.001)


def test_response_by_band_blanks_thin_bands():
    change, outcome = _dose(n=60)
    resp = response_by_band(anomaly(outcome.to_frame("x")), change, change_bands(change))
    thin = resp[(resp["n"] < 10) | (resp["spells"] < 5)]
    assert not thin.empty and thin[["mean", "se", "ci_low", "ci_high"]].isna().all().all()
