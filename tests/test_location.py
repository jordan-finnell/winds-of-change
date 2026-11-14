import pytest

from winds_of_change import Location, LocationError


def test_rounds_to_one_decimal_and_ten_metres():
    loc = Location(12.3456, -45.6789, elevation=1234.0)
    assert (loc.latitude, loc.longitude, loc.elevation) == (12.3, -45.7, 1230.0)


def test_repr_hides_coordinates():
    text = repr(Location(12.3456, -45.6789, elevation=1234.0))
    for fragment in ("12.3", "45.7", "1230"):
        assert fragment not in text


@pytest.mark.parametrize(
    "kwargs, field",
    [
        ({"latitude": 91.0, "longitude": 0.0}, "latitude"),
        ({"latitude": 0.0, "longitude": -181.0}, "longitude"),
        ({"latitude": True, "longitude": 0.0}, "latitude"),
        ({"latitude": "51.5", "longitude": 0.0}, "latitude"),
        ({"latitude": float("nan"), "longitude": 0.0}, "latitude"),
        ({"latitude": 0.0, "longitude": 0.0, "elevation": 99999.0}, "elevation"),
        ({"latitude": 0.0, "longitude": 0.0, "timezone": "Mars/Olympus"}, "timezone"),
    ],
)
def test_invalid_values_name_the_field_not_the_value(kwargs, field):
    with pytest.raises(LocationError) as info:
        Location(**kwargs)
    message = str(info.value)
    assert field in message
    bad = kwargs[field]
    if not isinstance(bad, bool):
        assert str(bad) not in message


def test_from_mapping():
    settings = {"latitude": 51.48, "longitude": -0.01, "timezone": "Europe/London"}
    loc = Location.from_mapping(settings)
    assert (loc.latitude, loc.longitude, loc.timezone) == (51.5, -0.0, "Europe/London")


def test_from_mapping_rejects_unknown_and_missing_keys():
    with pytest.raises(LocationError, match="unknown weather setting"):
        Location.from_mapping({"latitude": 1.0, "longitude": 1.0, "lat": 1.0})
    with pytest.raises(LocationError, match="missing: longitude"):
        Location.from_mapping({"latitude": 1.0})
    with pytest.raises(LocationError, match="table"):
        Location.from_mapping("51.5,0.0")  # type: ignore[arg-type]
