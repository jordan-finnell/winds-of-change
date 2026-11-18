"""Weather-change features for relating weather to personal health logs.

Typical use::

    from datetime import date
    import pandas as pd
    import winds_of_change as woc

    place = woc.Location(latitude=51.5, longitude=0.0)
    units = woc.Units("F")
    archive = woc.OpenMeteoSource(place)
    history = woc.convert(archive.load_hourly(date(2025, 1, 1), date.today()), units)
    daily = woc.daily_weather(history)  # pressure_change_24h, dew_point_change_6h, ...

    recent = woc.convert(woc.OpenMeteoForecastSource(place).load_recent(), units)
    now = pd.Timestamp.now(tz=recent.index.tz)
    look = woc.outlook(recent, "pressure", now, 24, history=history)
"""

from importlib.metadata import PackageNotFoundError, version

from . import analysis
from .analysis import (
    BAND_LABELS,
    BIN_LABELS,
    ChangeBands,
    ChangeBins,
    align_lag,
    anomaly,
    change_bands,
    change_bins,
    event_days,
    event_profile,
    response_by_band,
    response_by_change,
)
from .factors import DEW_POINT, FACTORS, PRESSURE, TEMPERATURE, Factor, Units, convert, factor
from .features import (
    DEFAULT_WINDOWS,
    Outlook,
    change_column,
    daily_weather,
    decycle,
    outlook,
    outlooks,
    window_changes,
)
from .location import Location, LocationError
from .sources import (
    OPEN_METEO_MODEL,
    OpenMeteoForecastSource,
    OpenMeteoSource,
    SyntheticWeatherSource,
    WeatherError,
    WeatherSource,
    combine,
    parse_open_meteo,
)

try:
    __version__ = version("winds-of-change")
except PackageNotFoundError:  # running from a source checkout without installing
    __version__ = "0.0.0"

__all__ = [
    "BAND_LABELS",
    "BIN_LABELS",
    "DEFAULT_WINDOWS",
    "DEW_POINT",
    "FACTORS",
    "OPEN_METEO_MODEL",
    "PRESSURE",
    "TEMPERATURE",
    "ChangeBands",
    "ChangeBins",
    "Factor",
    "Location",
    "LocationError",
    "OpenMeteoForecastSource",
    "OpenMeteoSource",
    "Outlook",
    "SyntheticWeatherSource",
    "Units",
    "WeatherError",
    "WeatherSource",
    "__version__",
    "align_lag",
    "analysis",
    "anomaly",
    "change_bands",
    "change_bins",
    "change_column",
    "combine",
    "convert",
    "daily_weather",
    "decycle",
    "event_days",
    "event_profile",
    "factor",
    "outlook",
    "outlooks",
    "parse_open_meteo",
    "response_by_band",
    "response_by_change",
    "window_changes",
]
