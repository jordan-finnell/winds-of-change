import math

import numpy as np
import pandas as pd
import pytest

from winds_of_change import (
    Units,
    change_column,
    convert,
    daily_weather,
    decycle,
    outlook,
    window_changes,
)


def hourly(values, start="2025-01-01", tz="UTC", key="pressure"):
    index = pd.date_range(start, periods=len(values), freq="h", tz=tz, name="time")
    return pd.DataFrame({key: np.asarray(values, dtype=float)}, index=index)


def tide(n, amplitude=0.8):
    hours = np.arange(n)
    return amplitude * np.cos(2 * np.pi * (hours - 10) / 12)


def test_decycle_removes_the_twice_daily_tide():
    s = hourly(1000 + tide(60 * 24))["pressure"]
    raw = window_changes(s, 6, decycled=False)
    clean = window_changes(s, 6)
    middle = slice(20 * 24, 40 * 24)
    assert raw.iloc[middle].abs().max() > 1.5
    assert clean.iloc[middle].abs().max() < 0.05
    assert decycle(s).mean() == pytest.approx(1000, abs=0.01)  # level is kept


def test_peak_keeps_its_sign_and_short_fronts_are_not_diluted():
    values = np.full(10 * 24, 1000.0)
    day5 = 5 * 24
    values[day5 + 6 : day5 + 12] = np.linspace(1000, 994, 6)  # 6 hPa fall over ~6 h
    values[day5 + 12 : day5 + 18] = np.linspace(994, 997, 6)  # partly back by evening
    values[day5 + 18 :] = 997
    daily = daily_weather(hourly(values), windows=(6, 24), decycled=False)
    day = pd.Timestamp("2025-01-06")
    assert daily.loc[day, change_column("pressure", 6)] == pytest.approx(-6, abs=0.01)
    mean24 = daily_weather(hourly(values), windows=(24,), decycled=False, summary="mean")
    assert abs(mean24.loc[day, change_column("pressure", 24)]) < 3  # diluted by the day's average


def test_daily_index_and_columns():
    daily = daily_weather(hourly(np.arange(72.0)), windows=(3, 24))
    assert daily.index.name == "date" and daily.index.tz is None
    assert list(daily.index) == list(pd.date_range("2025-01-01", periods=3, freq="D"))
    assert list(daily.columns) == ["pressure", "pressure_change_3h", "pressure_change_24h"]


def test_incomplete_days_are_missing_not_partial():
    values = np.arange(96.0)
    frame = hourly(values)
    frame.iloc[30:40] = np.nan  # day 2 keeps 14 hours
    daily = daily_weather(frame, windows=(24,), decycled=False)
    assert math.isnan(daily["pressure"].iloc[1])
    assert math.isnan(daily["pressure_change_24h"].iloc[1])
    assert math.isnan(daily["pressure_change_24h"].iloc[0])  # nothing 24 h earlier
    assert daily["pressure"].iloc[2] == pytest.approx(values[48:72].mean())


@pytest.mark.parametrize("day, hours", [("2025-03-30", 23), ("2025-10-26", 25)])
def test_dst_days(day, hours):
    start = pd.Timestamp(day) - pd.Timedelta(days=3)
    index = pd.date_range(start, pd.Timestamp(day) + pd.Timedelta(days=3), freq="h",
                          tz="Europe/London", inclusive="left", name="time")  # fmt: skip
    frame = pd.DataFrame({"pressure": np.arange(len(index), dtype=float)}, index=index)
    assert (frame.index.normalize().tz_localize(None) == pd.Timestamp(day)).sum() == hours
    daily = daily_weather(frame, windows=(24,), decycled=False)
    # Absolute-time shift: a steady 1 hPa/h rise is exactly +24 over any 24 h, DST or not.
    assert daily.loc[pd.Timestamp(day), "pressure_change_24h"] == pytest.approx(24)
    assert not math.isnan(daily.loc[pd.Timestamp(day), "pressure"])


def test_mean_summary_for_24h_is_the_day_over_day_change_of_means():
    rng = np.random.default_rng(0)
    values = 1000 + np.cumsum(rng.normal(0, 0.5, 20 * 24))
    frame = hourly(values)
    daily = daily_weather(frame, windows=(24,), decycled=False, summary="mean")
    expected = daily["pressure"].diff()
    pd.testing.assert_series_equal(
        daily["pressure_change_24h"].iloc[1:], expected.iloc[1:], check_names=False
    )


def test_outlook_last_and_next_with_percentiles():
    frame = hourly(1000 + 0.5 * np.arange(30 * 24))  # steady rise, no cycle
    now = frame.index[20 * 24]
    o = outlook(frame, "pressure", now, hours=24)
    assert o.last == pytest.approx(12, abs=0.05) and o.next == pytest.approx(12, abs=0.05)
    assert 0 <= o.last_percentile <= 1
    late = outlook(frame, "pressure", frame.index[-2], hours=24)
    assert math.isnan(late.next) and math.isnan(late.next_percentile)


def test_outlook_accepts_naive_now_and_floors_to_the_hour():
    frame = hourly(1000 + 0.5 * np.arange(10 * 24), tz="America/Chicago")
    o = outlook(frame, "pressure", pd.Timestamp("2025-01-05 12:34"), hours=6)
    assert o.now == pd.Timestamp("2025-01-05 12:00", tz="America/Chicago")


def test_convert_temperatures_and_changes_follow():
    index = pd.date_range("2025-01-01", periods=48, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {"pressure": 1000.0, "dew_point": np.linspace(0, 10, 48), "temperature": 20.0},
        index=index,
    )
    frame.attrs = {"source": "synthetic", "model": "x", "temperature_unit": "C"}
    f = convert(frame, Units("F"))
    assert f["temperature"].iloc[0] == pytest.approx(68)
    assert f["pressure"].iloc[0] == 1000
    assert f.attrs["temperature_unit"] == "F" and f.attrs["source"] == "synthetic"
    pd.testing.assert_frame_equal(convert(f, Units("C")), frame, check_like=True, atol=1e-9)
    c = window_changes(frame["dew_point"], 24, decycled=False).dropna()
    fdelta = window_changes(f["dew_point"], 24, decycled=False).dropna()
    assert np.allclose(fdelta, c * 1.8)
    assert Units("F").unit_for(__import__("winds_of_change").PRESSURE) == "hPa"
    with pytest.raises(ValueError):
        Units("K")  # type: ignore[arg-type]


def test_outlook_ranks_against_a_separate_history():
    calm = hourly(1000 + 0.05 * np.arange(60 * 24))  # tiny changes in the long history
    recent = hourly(1000 + 0.5 * np.arange(5 * 24), start="2025-03-02")  # big steady rise
    now = recent.index[2 * 24]
    own = outlook(recent, "pressure", now, hours=24)
    ranked = outlook(recent, "pressure", now, hours=24, history=calm)
    assert ranked.next == pytest.approx(12, abs=0.05)  # change measured within `recent`
    assert ranked.next_percentile == pytest.approx(1.0)  # larger than every calm change
    assert own.next_percentile < 0.5  # vs. its own (all similar) changes
