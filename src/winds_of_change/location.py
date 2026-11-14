"""Where to fetch weather for, coarsened before it can leave the machine.

A location is personal information. ``Location`` rounds coordinates to one decimal place
(about 11 km, comparable to the 9 km weather-model grid, so nothing is lost) and never shows
them in its ``repr`` or in error messages.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

COORD_DECIMALS = 1
ELEVATION_STEP_M = 10
KEYS = frozenset({"latitude", "longitude", "elevation", "timezone"})


class LocationError(ValueError):
    """Invalid location settings. Messages name the field, never its value."""


@dataclass(frozen=True)
class Location:
    """Rounded coordinates, optional elevation (metres) and optional IANA time zone.

    ``elevation`` is passed to the weather service for its downscaling, which matters in
    mountain terrain where a rounded point can land on a slope. Without it the service uses
    its terrain model's height at the (rounded) point. ``timezone`` overrides the zone the
    service looks up from the coordinates.
    """

    latitude: float = field(repr=False)
    longitude: float = field(repr=False)
    elevation: float | None = field(default=None, repr=False)
    timezone: str | None = None

    def __post_init__(self) -> None:
        lat = _number("latitude", self.latitude, -90.0, 90.0)
        lon = _number("longitude", self.longitude, -180.0, 180.0)
        object.__setattr__(self, "latitude", round(lat, COORD_DECIMALS))
        object.__setattr__(self, "longitude", round(lon, COORD_DECIMALS))
        if self.elevation is not None:
            elev = _number("elevation", self.elevation, -500.0, 9000.0)
            rounded = float(round(elev / ELEVATION_STEP_M) * ELEVATION_STEP_M)
            object.__setattr__(self, "elevation", rounded)
        if self.timezone is not None:
            if not isinstance(self.timezone, str) or not self.timezone.strip():
                raise LocationError("timezone must be a non-empty IANA zone name")
            try:
                ZoneInfo(self.timezone)
            except (ZoneInfoNotFoundError, ValueError):
                raise LocationError("timezone is not a known IANA zone name") from None

    @classmethod
    def from_mapping(cls, settings: Mapping[str, object]) -> Location:
        """Build from a settings table such as ``[weather]`` in a TOML file."""
        if not isinstance(settings, Mapping):
            raise LocationError("weather settings must be a table")
        unknown = set(settings) - KEYS
        if unknown:
            raise LocationError(f"unknown weather setting(s): {', '.join(sorted(unknown))}")
        missing = [k for k in ("latitude", "longitude") if k not in settings]
        if missing:
            raise LocationError(f"weather settings are missing: {', '.join(missing)}")
        return cls(
            latitude=settings["latitude"],  # type: ignore[arg-type]
            longitude=settings["longitude"],  # type: ignore[arg-type]
            elevation=settings.get("elevation"),  # type: ignore[arg-type]
            timezone=settings.get("timezone"),  # type: ignore[arg-type]
        )


def _number(name: str, value: object, lo: float, hi: float) -> float:
    # bool is an int subclass: reject it explicitly so `latitude = true` isn't 1.0.
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise LocationError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number) or not lo <= number <= hi:
        raise LocationError(f"{name} is out of range ({lo:g} to {hi:g})")
    return number
