import math

import pytest

from borehole_stick_gui.geo import build_wgs84_utm_crs, transform_points, validate_hemisphere, validate_utm_zone


def test_build_wgs84_utm_crs_resolves_expected_epsg_codes():
    assert build_wgs84_utm_crs(56, "S").to_epsg() == 32756
    assert build_wgs84_utm_crs(56, "N").to_epsg() == 32656


def test_validate_utm_zone_rejects_out_of_range_values():
    with pytest.raises(ValueError):
        validate_utm_zone(0)
    with pytest.raises(ValueError):
        validate_utm_zone(61)


def test_validate_hemisphere_rejects_unknown_values():
    with pytest.raises(ValueError):
        validate_hemisphere("")
    with pytest.raises(ValueError):
        validate_hemisphere("east")


def test_transform_points_to_web_mercator_returns_finite_coordinates():
    transformed = transform_points(
        [(500000.0, 7000000.0)],
        zone=56,
        hemisphere="S",
        target="EPSG:3857",
    )

    assert len(transformed) == 1
    x, y = transformed[0]
    assert math.isfinite(x)
    assert math.isfinite(y)
    assert (x, y) != (500000.0, 7000000.0)
