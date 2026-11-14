"""Ufuk profili ve boşluk taraması testleri (test_fixture).

Tüm ızgaralar sentetiktir; ağ erişimi veya gerçek DEM dosyası gerekmez.
"""

import math

import numpy as np
import pytest

from luna_sight.terrain.dem import DemGrid
from luna_sight.terrain.gaps import scan_coverage
from luna_sight.terrain.horizon import (
    QUALITY_MISSING,
    QUALITY_PARTIAL,
    QUALITY_VALID,
    HorizonConfig,
    compare_radii,
    compute_horizon,
)

PIXEL_M = 10.0


def make_dem(heights: np.ndarray, *, pixel_m: float = PIXEL_M, valid=None) -> DemGrid:
    rows, cols = heights.shape
    xmin = -cols * pixel_m / 2.0
    ymax = rows * pixel_m / 2.0
    return DemGrid(
        heights_m=heights,
        transform=(pixel_m, 0.0, xmin, 0.0, -pixel_m, ymax),
        valid=valid,
    )


def flat_dem(size: int = 200, value: float = 0.0, *, pixel_m: float = PIXEL_M) -> np.ndarray:
    return np.full((size, size), value, dtype=float)


def column_range(dem_size: int, pixel_m: float, x_center: float, half_width_m: float) -> range:
    xmin = -dem_size * pixel_m / 2.0
    lo = int(math.floor((x_center - half_width_m - xmin) / pixel_m))
    hi = int(math.ceil((x_center + half_width_m - xmin) / pixel_m))
    return range(max(lo, 0), min(hi, dem_size))


def test_flat_surface_horizon_is_slightly_negative():
    dem = make_dem(flat_dem())
    profile = compute_horizon(
        dem,
        x_m=0.0,
        y_m=0.0,
        config=HorizonConfig(max_radius_m=1_000.0, observer_height_m=2.0),
        lon_deg=0.0,
    )
    expected = math.degrees(math.atan2(-2.0, 999.999))
    assert profile.quality_flag == QUALITY_VALID
    assert np.all(np.isfinite(profile.horizon_deg))
    assert np.allclose(profile.horizon_deg, expected, atol=1e-3)


def test_ridge_east_sets_max_horizon_at_azimuth_90():
    heights = flat_dem()
    heights[:, 190:200] = 100.0  # gözlemcinin ~905-995 m doğusunda sırt
    dem = make_dem(heights)

    profile = compute_horizon(
        dem,
        x_m=0.0,
        y_m=0.0,
        config=HorizonConfig(max_radius_m=1_000.0, radial_step_m=10.0),
        lon_deg=0.0,
    )

    azimuths = profile.azimuth_deg
    east = np.argmin(np.abs(azimuths - 90.0))
    # Sırt ilk kez 910 m'de görülür; en büyük açı oradadır.
    expected = math.degrees(math.atan2(100.0 - 2.0, 910.0))

    assert profile.horizon_deg[east] == pytest.approx(expected, rel=0.02)
    assert profile.horizon_deg[east] == pytest.approx(np.nanmax(profile.horizon_deg), abs=1e-9)
    # Batı yönü düz zeminde kalır.
    west = np.argmin(np.abs(azimuths - 270.0))
    assert profile.horizon_deg[west] < 0.0


def test_gap_in_data_marks_profile_partial():
    heights = flat_dem()
    valid = np.ones(heights.shape, dtype=bool)
    valid[:, 195:] = False  # doğu yönünde veri boşluğu
    dem = make_dem(heights, valid=valid)

    profile = compute_horizon(
        dem,
        x_m=0.0,
        y_m=0.0,
        config=HorizonConfig(max_radius_m=1_000.0, gap_tolerance=0.0),
        lon_deg=0.0,
    )

    assert profile.quality_flag == QUALITY_PARTIAL
    assert float(np.max(profile.gap_fraction)) > 0.0
    assert profile.notes


def test_observer_in_gap_returns_missing():
    heights = flat_dem()
    valid = np.ones(heights.shape, dtype=bool)
    valid[95:105, 95:105] = False
    dem = make_dem(heights, valid=valid)

    profile = compute_horizon(
        dem, x_m=0.0, y_m=0.0, config=HorizonConfig(max_radius_m=500.0), lon_deg=0.0
    )

    assert profile.quality_flag == QUALITY_MISSING
    assert np.all(np.isnan(profile.horizon_deg))
    assert profile.summary()["horizon_max_deg"] is None


def test_radius_beyond_dem_coverage_is_flagged():
    dem = make_dem(flat_dem())
    profile = compute_horizon(
        dem,
        x_m=0.0,
        y_m=0.0,
        config=HorizonConfig(max_radius_m=5_000.0),
        lon_deg=0.0,
    )
    assert profile.quality_flag == QUALITY_PARTIAL
    assert any("kapsam" in note for note in profile.notes)


def test_compare_radii_detects_far_ridge():
    size = 500
    pixel = 20.0
    heights = np.zeros((size, size), dtype=float)
    cols = column_range(size, pixel, 3_000.0, 50.0)
    heights[:, list(cols)] = 200.0
    dem = make_dem(heights, pixel_m=pixel)

    result = compare_radii(
        dem,
        x_m=0.0,
        y_m=0.0,
        radii_m=(2_000.0, 5_000.0),
        config=HorizonConfig(radial_step_m=20.0, azimuth_step_deg=2.0),
    )

    near, far = result["profiles"]
    assert near["horizon_max_deg"] < 0.0  # 2 km içinde sırt yok
    assert far["horizon_max_deg"] > 3.0  # 3 km'deki 200 m sırt görünür
    assert result["max_horizon_delta_deg"] > 3.0


def test_config_validation():
    with pytest.raises(ValueError):
        HorizonConfig(azimuth_step_deg=0.0)
    with pytest.raises(ValueError):
        HorizonConfig(max_radius_m=5.0, radial_step_m=10.0)
    with pytest.raises(ValueError):
        HorizonConfig(observer_height_m=-1.0)


def test_gap_scan_reports_fractions():
    heights = flat_dem()
    valid = np.ones(heights.shape, dtype=bool)
    valid[:, 150:] = False  # x >= 500 m'nin doğusu boş
    dem = make_dem(heights, valid=valid)

    report = scan_coverage(dem, 0.0, 0.0, radii_m=(200.0, 900.0), gap_tolerance=0.0)

    assert report.quality_flag == QUALITY_PARTIAL
    assert report.surface_gap_fraction[0] == pytest.approx(0.0, abs=1e-9)
    assert 0.1 < report.surface_gap_fraction[1] < 0.3
    assert report.native_coverage_fraction[0] == pytest.approx(1.0, abs=1e-9)
    assert 0.7 < report.native_coverage_fraction[1] < 0.9
    assert report.pixel_count[0] < report.pixel_count[1]


def test_horizon_from_profile_interpolation_and_tolerance():
    from luna_sight.terrain.horizon import HorizonProfile, horizon_from_profile

    # Sentetik 4 yönlü profil: 0: 10°, 90: 20°, 180: 30°, 270: 40°
    az = np.array([0.0, 90.0, 180.0, 270.0])
    hz = np.array([10.0, 20.0, 30.0, 40.0])
    cfg = HorizonConfig()
    profile = HorizonProfile(
        x_m=0.0,
        y_m=0.0,
        lon_deg=0.0,
        lat_deg=-89.0,
        config=cfg,
        azimuth_deg=az,
        horizon_deg=hz,
        occluder_distance_m=np.full(4, 1000.0),
        gap_fraction=np.zeros(4),
        native_coverage=np.ones(4),
        quality_flag=QUALITY_VALID,
    )

    # 1. Tam azimut eşleşmesi
    assert horizon_from_profile(profile, 0.0) == pytest.approx(10.0)
    assert horizon_from_profile(profile, 90.0) == pytest.approx(20.0)
    assert horizon_from_profile(profile, 360.0) == pytest.approx(10.0)  # Modulo 360

    # 2. Ara açı doğrusal enterpolasyonu (45° -> 10 ve 20 arası -> 15°)
    assert horizon_from_profile(profile, 45.0, interpolate=True) == pytest.approx(15.0)

    # 3. 360/0 dairesel döngü enterpolasyonu (315° -> 270: 40° ile 360: 10° arası -> 25°)
    assert horizon_from_profile(profile, 315.0, interpolate=True) == pytest.approx(25.0)

    # 4. profile.horizon_at metodu
    arr_res = profile.horizon_at(np.array([0.0, 45.0, 90.0]))
    assert np.allclose(arr_res, [10.0, 15.0, 20.0])

    # 5. interpolate=False ve tolerance kontrolü
    # 44° -> en yakın 0 veya 90 mı? 44° -> 0° farkı 44°, 90° farkı 46° -> en yakın 0° (10.0)
    assert horizon_from_profile(
        profile, 2.0, interpolate=False, azimuth_tolerance_deg=5.0
    ) == pytest.approx(10.0)
    # Tolerans 1° iken 2° sorgulanırsa tolerans aşımı -> NaN
    assert np.isnan(
        horizon_from_profile(profile, 2.0, interpolate=False, azimuth_tolerance_deg=1.0)
    )

    # 6. QUALITY_MISSING durumunda daima NaN
    profile_missing = HorizonProfile(
        x_m=0.0,
        y_m=0.0,
        lon_deg=0.0,
        lat_deg=-89.0,
        config=cfg,
        azimuth_deg=az,
        horizon_deg=hz,
        occluder_distance_m=np.full(4, 1000.0),
        gap_fraction=np.ones(4),
        native_coverage=np.zeros(4),
        quality_flag=QUALITY_MISSING,
    )
    assert np.isnan(horizon_from_profile(profile_missing, 45.0))
