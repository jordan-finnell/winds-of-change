"""The weather factors this package tracks, and display units.

Data is canonical (hPa, °C) from the source onwards. Convert once, on the hourly frame,
before computing features: changes then come out in the display unit automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

TemperatureUnit = Literal["C", "F"]


@dataclass(frozen=True)
class Factor:
    key: str
    api_var: str  # Open-Meteo hourly variable name
    label: str
    kind: Literal["pressure", "temperature"]  # decides the unit
    description: str


PRESSURE = Factor(
    key="pressure",
    api_var="surface_pressure",
    label="Pressure",
    kind="pressure",
    description="Surface (station-level) air pressure: what the body actually feels.",
)
DEW_POINT = Factor(
    key="dew_point",
    api_var="dew_point_2m",
    label="Humidity (dew point)",
    kind="temperature",
    description=(
        "Dew point measures the moisture in the air. Unlike relative humidity it does not "
        "swing with the day's temperature, so its changes track humid or dry air arriving."
    ),
)
TEMPERATURE = Factor(
    key="temperature",
    api_var="temperature_2m",
    label="Temperature",
    kind="temperature",
    description="Air temperature 2 m above ground.",
)

FACTORS: tuple[Factor, ...] = (PRESSURE, DEW_POINT, TEMPERATURE)


def factor(key: str) -> Factor:
    for f in FACTORS:
        if f.key == key:
            return f
    raise KeyError(key)


@dataclass(frozen=True)
class Units:
    temperature: TemperatureUnit = "C"

    def __post_init__(self) -> None:
        if self.temperature not in ("C", "F"):
            raise ValueError("temperature unit must be 'C' or 'F'")

    def unit_for(self, f: Factor) -> str:
        return "hPa" if f.kind == "pressure" else f"°{self.temperature}"


def convert(hourly: pd.DataFrame, units: Units) -> pd.DataFrame:
    """Canonical (hPa, °C) hourly frame -> display units. Records the result in ``attrs``."""
    current = hourly.attrs.get("temperature_unit", "C")
    out = hourly.copy()
    out.attrs = dict(hourly.attrs)
    if current != units.temperature:
        for f in FACTORS:
            if f.kind == "temperature" and f.key in out:
                if units.temperature == "F":
                    out[f.key] = out[f.key] * 9 / 5 + 32
                else:
                    out[f.key] = (out[f.key] - 32) * 5 / 9
    out.attrs["temperature_unit"] = units.temperature
    return out
