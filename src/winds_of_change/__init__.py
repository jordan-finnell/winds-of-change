"""Weather-change features for relating weather to personal health logs.

Typical use::

    from datetime import date
    from winds_of_change import Location, OpenMeteoSource, Units, convert, daily_weather

    source = OpenMeteoSource(Location(latitude=51.5, longitude=0.0))
    hourly = convert(source.load_hourly(date(2025, 1, 1), date(2025, 6, 30)), Units("F"))
    daily = daily_weather(hourly)          # pressure_change_24h, dew_point_change_6h, ...
"""

from importlib.metadata import PackageNotFoundError, version

from . import analysis
from .analysis import (
    BIN_LABELS,
    ChangeBins,
    align_lag,
    anomaly,
    change_bins,
    event_days,
    event_profile,
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
    "BIN_LABELS",
    "DEFAULT_WINDOWS",
    "DEW_POINT",
    "FACTORS",
    "OPEN_METEO_MODEL",
    "PRESSURE",
    "TEMPERATURE",
    "ChangeBins",
    "Factor",
    "Location",
    "LocationError",
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
    "response_by_change",
    "window_changes",
]
