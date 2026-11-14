"""Ufuk profili araması: dairesel enterpolasyon ve eksik veri (test_fixture)."""

from pathlib import Path

import numpy as np
import pytest

from luna_sight.visibility.profile import HorizonProfileLookup

K2_PROFILE = Path(__file__).resolve().parents[1] / "outputs" / "k2" / "Site04_horizon_4000m.csv"


@pytest.fixture()
def coarse_profile():
    return HorizonProfileLookup([0.0, 90.0, 180.0, 270.0], [0.0, 1.0, 2.0, 3.0])


def test_exact_points_and_midpoint(coarse_profile):
    assert coarse_profile.elevation_at(90.0) == pytest.approx(1.0)
    assert coarse_profile.elevation_at(45.0) == pytest.approx(0.5)
    assert coarse_profile.elevation_at(200.0) == pytest.approx(2.0 + 20.0 / 90.0)


def test_circular_wrap_between_last_and_first(coarse_profile):
    # 270° (3.0) ile 360°/0° (0.0) arasında 315° → 1.5 olmalı.
    assert coarse_profile.elevation_at(315.0) == pytest.approx(1.5)
    # 0°'nin hemen öncesi de dairesel olarak aynı segmenttedir.
    assert coarse_profile.elevation_at(359.0) == pytest.approx(3.0 - 3.0 * 89.0 / 90.0)


def test_longitudes_are_normalised(coarse_profile):
    assert coarse_profile.elevation_at(-45.0) == pytest.approx(coarse_profile.elevation_at(315.0))
    assert coarse_profile.elevation_at(405.0) == pytest.approx(coarse_profile.elevation_at(45.0))


def test_vector_query_matches_scalar(coarse_profile):
    azimuths = np.array([0.0, 45.0, 315.0, 359.0])
    vector = coarse_profile.elevations_at(azimuths)
    scalar = np.array([coarse_profile.elevation_at(az) for az in azimuths])
    assert vector == pytest.approx(scalar)


def test_nan_segment_returns_none():
    profile = HorizonProfileLookup(
        [0.0, 90.0, 180.0, 270.0],
        [0.0, float("nan"), 2.0, 3.0],
    )
    # Eksik noktanın komşu aralıkları bilinmiyor.
    assert profile.elevation_at(90.0) is None
    assert profile.elevation_at(45.0) is None
    assert profile.elevation_at(135.0) is None
    # Eksik bölgenin dışındaki aralıklar sağlam.
    assert profile.elevation_at(200.0) == pytest.approx(2.0 + 20.0 / 90.0)
    assert profile.elevation_at(315.0) == pytest.approx(1.5)
    assert profile.valid_fraction == pytest.approx(0.75)


def test_vector_query_propagates_nan():
    profile = HorizonProfileLookup([0.0, 90.0, 180.0, 270.0], [1.0, float("nan"), 2.0, 3.0])
    values = profile.elevations_at([0.0, 90.0, 180.0])
    assert np.isfinite(values[0])
    assert np.isnan(values[1])
    assert np.isfinite(values[2])


def test_input_validation():
    with pytest.raises(ValueError):
        HorizonProfileLookup([0.0, 90.0], [1.0])
    with pytest.raises(ValueError):
        HorizonProfileLookup([0.0], [1.0])
    with pytest.raises(ValueError):
        HorizonProfileLookup([0.0, 0.0], [1.0, 2.0])
    with pytest.raises(ValueError):
        HorizonProfileLookup([-10.0, 90.0], [1.0, 2.0])
    with pytest.raises(ValueError):
        HorizonProfileLookup([0.0, 361.0], [1.0, 2.0])
    with pytest.raises(ValueError):
        HorizonProfileLookup([0.0, 90.0], [float("nan"), float("nan")])


def test_unsorted_input_is_sorted():
    profile = HorizonProfileLookup([270.0, 0.0, 180.0, 90.0], [3.0, 0.0, 2.0, 1.0])
    assert list(profile.azimuths) == [0.0, 90.0, 180.0, 270.0]
    assert profile.elevation_at(45.0) == pytest.approx(0.5)


@pytest.mark.skipif(not K2_PROFILE.exists(), reason="K2 profil çıktısı yok")
def test_real_k2_profile_loads_and_is_finite():
    profile = HorizonProfileLookup.from_csv(K2_PROFILE)
    summary = profile.summary()
    assert summary["points"] == 360
    assert summary["valid_fraction"] == 1.0
    assert summary["horizon_min_deg"] < summary["horizon_max_deg"]
    # K2'de Site04 için ufuk yaklaşık −31°…+32°.
    assert -40.0 < summary["horizon_min_deg"] < -20.0
    assert 20.0 < summary["horizon_max_deg"] < 40.0
    assert profile.elevation_at(0.0) is not None


def test_csv_missing_columns_raises(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("azimuth_deg,horizon_deg\n0,1\n90,2\n", encoding="utf-8")
    HorizonProfileLookup.from_csv(path)  # bu hâlâ geçerli

    with pytest.raises(ValueError):
        HorizonProfileLookup.from_csv(path, horizon_column="yok")
    with pytest.raises(ValueError):
        HorizonProfileLookup.from_csv(path, azimuth_column="yok")


def test_csv_empty_horizon_becomes_nan(tmp_path):
    path = tmp_path / "partial.csv"
    path.write_text("azimuth_deg,horizon_deg\n0,0.5\n90,\n180,1.5\n", encoding="utf-8")
    profile = HorizonProfileLookup.from_csv(path)
    assert profile.elevation_at(90.0) is None
    assert profile.elevation_at(0.0) == pytest.approx(0.5)
    assert profile.valid_fraction == pytest.approx(2.0 / 3.0)
