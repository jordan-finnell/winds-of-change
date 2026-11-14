import io
import json
import urllib.error
from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import numpy as np
import pandas as pd
import pytest

from winds_of_change import (
    OPEN_METEO_MODEL,
    Location,
    OpenMeteoSource,
    SyntheticWeatherSource,
    WeatherError,
    combine,
    parse_open_meteo,
)

LOC = Location(51.4567, -0.0123, elevation=23.0)
START = 1_735_689_600  # 2025-01-01T00:00Z


def payload(hours=48, zone="Europe/London", suffix=""):
    times = [START + 3600 * i for i in range(hours)]
    return {
        "timezone": zone,
        "hourly": {
            "time": times,
            f"surface_pressure{suffix}": [1000.0 + i * 0.1 for i in range(hours)],
            f"dew_point_2m{suffix}": [1.0] * hours,
            f"temperature_2m{suffix}": [5.0] * (hours - 1) + [None],
        },
    }


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Recorder:
    """Fake urlopen: records URLs and replays queued results (dicts or exceptions)."""

    def __init__(self, *results):
        self.results = list(results)
        self.urls = []

    def __call__(self, url, timeout=None):
        self.urls.append(url)
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return FakeResponse(json.dumps(result).encode())


def http_error(code, body=b""):
    return urllib.error.HTTPError("https://example.invalid", code, "err", {}, io.BytesIO(body))


def test_url_pins_one_model_and_sends_only_rounded_location():
    url = OpenMeteoSource(LOC).url(date(2025, 1, 1), date(2025, 1, 2))
    q = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    assert urlsplit(url).netloc == "archive-api.open-meteo.com"
    assert q["models"] == OPEN_METEO_MODEL == "ecmwf_ifs"
    assert q["timeformat"] == "unixtime"
    assert q["timezone"] == "auto"
    assert (q["latitude"], q["longitude"], q["elevation"]) == ("51.5", "-0.0", "20.0")
    assert q["hourly"] == "surface_pressure,dew_point_2m,temperature_2m"
    assert set(q) == {
        "latitude", "longitude", "elevation", "start_date", "end_date",
        "hourly", "models", "timeformat", "timezone",
    }  # fmt: skip


def test_load_parses_to_local_time_and_clamps_dates():
    opener = Recorder(payload())
    frame = OpenMeteoSource(LOC, opener=opener).load_hourly(date(2010, 1, 1), date(2999, 1, 1))
    q = parse_qs(urlsplit(opener.urls[0]).query)
    assert q["start_date"] == ["2017-01-01"]
    assert date.fromisoformat(q["end_date"][0]) <= datetime.now(UTC).date() + timedelta(days=1)
    assert str(frame.index.tz) == "Europe/London"
    assert frame.index[0] == pd.Timestamp("2025-01-01 00:00", tz="Europe/London")
    assert list(frame.columns) == ["pressure", "dew_point", "temperature"]
    assert np.isnan(frame["temperature"].iloc[-1])  # null stays missing
    assert frame.attrs == {"source": "open-meteo", "model": "ecmwf_ifs", "temperature_unit": "C"}


def test_model_suffixed_keys_are_accepted():
    frame = parse_open_meteo(payload(suffix="_ecmwf_ifs"))
    assert frame["pressure"].notna().all()


def test_out_of_range_end_retries_with_the_reported_limit():
    today = datetime.now(UTC).date()
    body = json.dumps({"error": True, "reason": f"out of allowed range from 1940-01-01 to {today}"})
    opener = Recorder(http_error(400, body.encode()), payload())
    OpenMeteoSource(LOC, opener=opener).load_hourly(date(2025, 1, 1), today + timedelta(days=1))
    assert len(opener.urls) == 2
    assert parse_qs(urlsplit(opener.urls[1]).query)["end_date"] == [today.isoformat()]


@pytest.mark.parametrize(
    "failure",
    [http_error(500), urllib.error.URLError("dns"), TimeoutError(), ValueError("bad json")],
)
def test_failures_become_weather_errors_without_location(failure):
    source = OpenMeteoSource(LOC, opener=Recorder(failure))
    with pytest.raises(WeatherError) as info:
        source.load_hourly(date(2025, 1, 1), date(2025, 1, 2))
    text = str(info.value)
    assert "51.5" not in text and "open-meteo.com" not in text
    assert info.value.__cause__ is None and info.value.__suppress_context__


def test_malformed_payload_is_a_weather_error():
    with pytest.raises(WeatherError):
        parse_open_meteo({"hourly": {"time": [START]}})


def test_default_opener_is_urllib_and_blocked_in_tests():
    with pytest.raises(AssertionError, match="network"):
        OpenMeteoSource(LOC).load_hourly(date(2025, 1, 1), date(2025, 1, 2))


def test_synthetic_is_deterministic_and_slice_consistent():
    src = SyntheticWeatherSource(seed=4, timezone="America/Chicago")
    long = src.load_hourly(date(2024, 1, 1), date(2024, 12, 31))
    short = src.load_hourly(date(2024, 6, 1), date(2024, 6, 30))
    pd.testing.assert_frame_equal(short, long.loc[short.index])
    pd.testing.assert_frame_equal(short, src.load_hourly(date(2024, 6, 1), date(2024, 6, 30)))
    other = SyntheticWeatherSource(seed=5).load_hourly(date(2024, 6, 1), date(2024, 6, 30))
    assert not short.equals(other)


def test_synthetic_is_plausible_and_complete():
    frame = SyntheticWeatherSource(seed=1).load_hourly(date(2023, 1, 1), date(2023, 12, 31))
    assert len(frame) == 365 * 24 and frame.notna().all().all()
    assert frame["pressure"].between(960, 1060).all()
    assert (frame["dew_point"] < frame["temperature"]).all()
    assert frame.index[-1] == pd.Timestamp("2023-12-31 23:00", tz="UTC")


def test_combine_refuses_mixed_sources_or_models():
    a = SyntheticWeatherSource(seed=1).load_hourly(date(2024, 1, 1), date(2024, 1, 2))
    b = SyntheticWeatherSource(seed=1).load_hourly(date(2024, 1, 2), date(2024, 1, 3))
    assert len(combine(a, b)) == 3 * 24
    c = SyntheticWeatherSource(seed=2).load_hourly(date(2024, 1, 3), date(2024, 1, 4))
    with pytest.raises(WeatherError, match="different sources or models"):
        combine(a, c)
    real = parse_open_meteo(payload())
    with pytest.raises(WeatherError):
        combine(real, a)


def test_forecast_url_and_labelled_as_a_separate_source():
    from winds_of_change import OpenMeteoForecastSource

    opener = Recorder(payload())
    src = OpenMeteoForecastSource(LOC, opener=opener)
    frame = src.load_recent()
    url = urlsplit(opener.urls[0])
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert url.netloc == "api.open-meteo.com"
    assert (q["models"], q["past_days"], q["forecast_days"]) == ("ecmwf_ifs", "31", "3")
    assert "start_date" not in q and q["latitude"] == "51.5"
    assert frame.attrs["source"] == "open-meteo-forecast"
    with pytest.raises(WeatherError, match="different sources"):
        combine(parse_open_meteo(payload()), frame)  # never splice forecast into the archive
    with pytest.raises(ValueError):
        OpenMeteoForecastSource(LOC, past_days=100)


def test_forecast_failures_are_weather_errors():
    from winds_of_change import OpenMeteoForecastSource

    with pytest.raises(WeatherError, match="could not reach"):
        OpenMeteoForecastSource(LOC, opener=Recorder(urllib.error.URLError("x"))).load_recent()
