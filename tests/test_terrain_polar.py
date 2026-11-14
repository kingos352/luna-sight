"""Koordinat dönüşümü ve azimut yönü testleri (test_fixture)."""

import math

import pytest

from luna_sight.terrain.polar import (
    R_MOON_M,
    azimuth_unit_vector,
    east_unit_vector,
    lonlat_to_xy,
    north_unit_vector,
    xy_to_lonlat,
)


@pytest.mark.parametrize(
    "lon_deg,lat_deg",
    [
        (0.0, -90.0),
        (0.0, -89.9),
        (45.0, -89.5),
        (-123.456, -88.0),
        (179.999, -87.5),
        (12.0, -80.0),
    ],
)
def test_roundtrip_lonlat_xy(lon_deg, lat_deg):
    x, y = lonlat_to_xy(lon_deg, lat_deg)
    lon_back, lat_back = xy_to_lonlat(x, y)
    assert lat_back == pytest.approx(lat_deg, abs=1e-9)
    if lat_deg > -90.0:
        assert lon_back == pytest.approx(lon_deg, abs=1e-9)


def test_pole_is_origin():
    assert lonlat_to_xy(123.0, -90.0) == pytest.approx((0.0, 0.0), abs=1e-9)


def test_equator_radius():
    x, y = lonlat_to_xy(0.0, 0.0)
    assert x == pytest.approx(0.0, abs=1e-9)
    assert y == pytest.approx(2.0 * R_MOON_M, abs=1e-6)


def test_scale_is_local_and_distortion_is_small():
    """Kutba yakın 1 km'lik yerdeğiştirme, stereografide ~1 km kalmalı."""
    lon, lat = 0.0, -89.9
    x1, y1 = lonlat_to_xy(lon, lat)
    # 1 km kuzeye git: enlem yaklaşık 1 km / R kadar artar.
    dlat = math.degrees(1_000.0 / R_MOON_M)
    x2, y2 = lonlat_to_xy(lon, lat + dlat)
    measured = math.hypot(x2 - x1, y2 - y1)
    assert measured == pytest.approx(1_000.0, rel=2e-3)


def test_azimuth_basis_at_origin_meridian():
    assert north_unit_vector(0.0) == pytest.approx((0.0, 1.0))
    assert east_unit_vector(0.0) == pytest.approx((1.0, 0.0))

    assert azimuth_unit_vector(0.0, 0.0) == pytest.approx((0.0, 1.0))
    assert azimuth_unit_vector(90.0, 0.0) == pytest.approx((1.0, 0.0))
    assert azimuth_unit_vector(180.0, 0.0) == pytest.approx((0.0, -1.0))


def test_azimuth_is_orthonormal_and_clockwise():
    for lon in (-170.0, -45.0, 0.0, 37.0, 179.0):
        n = north_unit_vector(lon)
        e = east_unit_vector(lon)
        assert math.hypot(*n) == pytest.approx(1.0)
        assert math.hypot(*e) == pytest.approx(1.0)
        assert n[0] * e[0] + n[1] * e[1] == pytest.approx(0.0)
        # Doğu, kuzeyden saat yönünde 90° dönmüş olmalı.
        assert azimuth_unit_vector(90.0, lon) == pytest.approx(e)


def test_northern_latitude_rejected():
    with pytest.raises(ValueError):
        lonlat_to_xy(0.0, -89.0 + 180.0)


def test_longitude_wrapping():
    x, y = lonlat_to_xy(370.0, -89.0)
    x2, y2 = lonlat_to_xy(10.0, -89.0)
    assert (x, y) == pytest.approx((x2, y2), abs=1e-9)
