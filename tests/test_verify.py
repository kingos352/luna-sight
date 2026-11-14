"""Bağımsız doğrulama geometrisi. Ağa çıkmaz, analitik vakalarla sınanır."""

from __future__ import annotations

import math

import pytest

from luna_sight.ephemeris.verify import (
    MOON_RADIUS_KM,
    angular_difference,
    subpoint_azalt,
)

FAR = 1.0e8  # km; Güneş mertebesinde uzaklık
#: FAR için paralaks artığı: asin(R/d) ~ 0.001 derece. Testler bunu dikkate alır.
PARALLAX_AT_FAR = math.degrees(math.atan2(MOON_RADIUS_KM, FAR))


def test_subpoint_over_site_is_zenith() -> None:
    az, alt = subpoint_azalt(-45.0, 30.0, 30.0, -45.0, FAR)
    assert alt == pytest.approx(90.0)
    assert 0.0 <= az < 360.0


def test_target_due_north_has_zero_azimuth() -> None:
    az, alt = subpoint_azalt(0.0, 0.0, 0.0, 10.0, FAR)
    assert az == pytest.approx(0.0, abs=1e-9)
    assert alt == pytest.approx(80.0, abs=2.0 * PARALLAX_AT_FAR)


def test_target_due_east_has_ninety_azimuth() -> None:
    az, alt = subpoint_azalt(0.0, 0.0, 10.0, 0.0, FAR)
    assert az == pytest.approx(90.0, abs=1e-9)
    assert alt == pytest.approx(80.0, abs=2.0 * PARALLAX_AT_FAR)


def test_target_due_west_has_two_seventy_azimuth() -> None:
    az, _ = subpoint_azalt(0.0, 0.0, -10.0, 0.0, FAR)
    assert az == pytest.approx(270.0, abs=1e-9)


def test_azimuth_is_measured_clockwise_from_north() -> None:
    """Kuzeydoğudaki hedef 0 ile 90 derece arasında olmalı."""
    az, _ = subpoint_azalt(0.0, 0.0, 10.0, 10.0, FAR)
    assert 0.0 < az < 90.0


def test_quarter_turn_away_is_horizon_for_distant_target() -> None:
    """Çeyrek tur uzaktaki hedef ufukta; artık değer tam olarak paralakstır."""
    _, alt = subpoint_azalt(0.0, 0.0, 90.0, 0.0, FAR)
    assert alt == pytest.approx(-PARALLAX_AT_FAR, abs=1e-9)
    assert abs(alt) < 0.002


def test_parallax_lowers_a_nearby_target_at_the_horizon() -> None:
    """Dünya uzaklığında paralaks ufuk açısını ölçülebilir biçimde düşürür.

    Hedef gövde merkezinden 90 derece uzaktayken gözlemci yüzeyde olduğu
    için hedef ufkun altına iner. Beklenen açı asin(R/d) mertebesindedir.
    """
    earth_distance = 405_600.0
    _, alt = subpoint_azalt(0.0, 0.0, 90.0, 0.0, earth_distance)
    expected = -math.degrees(math.atan2(MOON_RADIUS_KM, earth_distance))
    assert alt == pytest.approx(expected, abs=1e-6)
    assert alt < -0.2  # ihmal edilemez


def test_parallax_is_negligible_for_solar_distance() -> None:
    _, alt = subpoint_azalt(0.0, 0.0, 90.0, 0.0, 1.496e8)
    assert abs(alt) < 0.001


def test_south_pole_azimuth_tracks_subpoint_longitude() -> None:
    """Güney kutbuna yakın noktada azimut, alt-nokta boylamını izler.

    Site01 boylamı -137.489553; alt-güneş boylamı 126.617658 iken fark
    yaklaşık 264 derece olmalı. Bu, güney kutbunda meridyen geometrisinin
    beklenen davranışı ve kutupta azimut tanımının testi.
    """
    az, _ = subpoint_azalt(-89.463163, -137.489553, 126.617658, -1.557279, 1.496e8)
    assert az == pytest.approx(264.1, abs=0.5)


def test_rejects_non_positive_distance() -> None:
    with pytest.raises(ValueError, match="distance_km"):
        subpoint_azalt(0.0, 0.0, 0.0, 0.0, 0.0)


def test_rejects_out_of_range_latitude() -> None:
    with pytest.raises(ValueError, match="site_lat_deg"):
        subpoint_azalt(-95.0, 0.0, 0.0, 0.0, FAR)


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [(359.9, 0.1, 0.2), (0.1, 359.9, 0.2), (10.0, 10.0, 0.0), (180.0, 0.0, 180.0)],
)
def test_angular_difference_wraps(first: float, second: float, expected: float) -> None:
    assert angular_difference(first, second) == pytest.approx(expected, abs=1e-9)
