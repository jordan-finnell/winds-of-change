"""``woc``: export daily weather-change features to CSV (e.g. for notebooks).

    woc features --lat 51.5 --lon 0.0 --start 2024-01-01 --end 2024-12-31 -o weather.csv
    woc features --synthetic 7 --start 2024-01-01 --end 2024-03-31 -o demo.csv

Coordinates are taken from the command line, rounded to 0.1 degrees before any request,
and never written anywhere. The output file contains weather for that place, so keep it
private if the place is.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date

from .factors import Units, convert
from .features import DEFAULT_WINDOWS, daily_weather
from .location import Location, LocationError
from .sources import OpenMeteoSource, SyntheticWeatherSource, WeatherError, WeatherSource


def _windows(text: str) -> tuple[int, ...]:
    try:
        values = tuple(int(part) for part in text.split(",") if part.strip())
    except ValueError:
        raise argparse.ArgumentTypeError("windows must be comma-separated hours") from None
    if not values or min(values) < 1:
        raise argparse.ArgumentTypeError("windows must be positive hours")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="woc", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    feat = sub.add_parser("features", help="write daily change features to CSV")
    where = feat.add_mutually_exclusive_group(required=True)
    where.add_argument("--lat", type=float, help="latitude (rounded to 0.1)")
    where.add_argument("--synthetic", type=int, metavar="SEED", help="invented weather, offline")
    feat.add_argument("--lon", type=float, help="longitude (rounded to 0.1)")
    feat.add_argument("--elevation", type=float, help="metres, for downscaling (optional)")
    feat.add_argument("--timezone", help="IANA zone (default: looked up from the coordinates)")
    feat.add_argument("--start", type=date.fromisoformat, required=True)
    feat.add_argument("--end", type=date.fromisoformat, required=True)
    feat.add_argument("--units", choices=("C", "F"), default="C", help="temperature unit")
    feat.add_argument(
        "--windows", type=_windows, default=DEFAULT_WINDOWS, help="hours, e.g. 3,6,24"
    )
    feat.add_argument("-o", "--output", required=True, help="CSV path ('-' for stdout)")
    return parser


def _source(args: argparse.Namespace) -> WeatherSource:
    if args.synthetic is not None:
        return SyntheticWeatherSource(seed=args.synthetic, timezone=args.timezone or "UTC")
    if args.lon is None:
        raise LocationError("--lon is required with --lat")
    return OpenMeteoSource(
        Location(args.lat, args.lon, elevation=args.elevation, timezone=args.timezone)
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source = _source(args)
        hourly = convert(source.load_hourly(args.start, args.end), Units(args.units))
    except (LocationError, WeatherError) as exc:
        print(f"woc: {exc}", file=sys.stderr)
        return 2
    daily = daily_weather(hourly, args.windows)
    daily = daily.loc[str(args.start) : str(args.end)]
    target = sys.stdout if args.output == "-" else args.output
    daily.to_csv(target, float_format="%.2f")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
