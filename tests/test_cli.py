import pandas as pd

from winds_of_change.cli import main


def test_synthetic_features_to_csv(tmp_path):
    out = tmp_path / "weather.csv"
    code = main(["features", "--synthetic", "3", "--start", "2024-02-01", "--end",
                 "2024-02-29", "--units", "F", "--windows", "6,24", "-o", str(out)])  # fmt: skip
    assert code == 0
    frame = pd.read_csv(out, index_col="date", parse_dates=True)
    assert len(frame) == 29
    assert "pressure_change_6h" in frame and "temperature_change_24h" in frame
    assert frame["temperature"].mean() < 80  # Fahrenheit, February


def test_lat_without_lon_is_an_error(capsys):
    assert main(["features", "--lat", "51.5", "--start", "2024-01-01", "--end",
                 "2024-01-02", "-o", "-"]) == 2  # fmt: skip
    assert "--lon" in capsys.readouterr().err
