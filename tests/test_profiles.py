"""K2 ufuk profili sağlayıcısı ve CLI testleri."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from luna_sight.visibility import (
    BLOCKED,
    UNCERTAIN,
    VISIBLE,
    EngineConfig,
    MockEphemeris,
    ProfileHorizon,
    Site,
    VisibilityEngine,
    load_horizon_profile,
)
from luna_sight.visibility.__main__ import main

START = pd.Timestamp("2026-11-14T00:00:00Z")
AZIMUTHS = np.array([0.0, 90.0, 180.0, 270.0])
HORIZONS = np.array([0.0, 10.0, 0.0, -10.0])


def at(provider: ProfileHorizon, azimuth: float) -> float:
    return float(provider.horizon_deg(azimuth))


def test_profile_interpolates_linearly():
    profile = ProfileHorizon(AZIMUTHS, HORIZONS)
    assert at(profile, 0.0) == pytest.approx(0.0)
    assert at(profile, 45.0) == pytest.approx(5.0)
    assert at(profile, 90.0) == pytest.approx(10.0)
    assert at(profile, 135.0) == pytest.approx(5.0)


def test_profile_wraps_around_north():
    profile = ProfileHorizon(AZIMUTHS, HORIZONS)
    expected = -10.0 + (359.0 - 270.0) / 90.0 * 10.0
    assert at(profile, 359.0) == pytest.approx(expected)


def test_profile_normalises_out_of_range_azimuths():
    profile = ProfileHorizon(AZIMUTHS, HORIZONS)
    assert at(profile, 405.0) == pytest.approx(at(profile, 45.0))
    assert at(profile, -45.0) == pytest.approx(at(profile, 315.0))


def test_nearest_mode_and_tolerance():
    nearest = ProfileHorizon(AZIMUTHS, HORIZONS, interpolate=False)
    assert float(nearest.horizon_deg(44.0)) == pytest.approx(0.0)
    assert float(nearest.horizon_deg(46.0)) == pytest.approx(10.0)

    limited = ProfileHorizon(
        AZIMUTHS, HORIZONS, interpolate=False, azimuth_tolerance_deg=10.0
    )
    values = limited.horizon_deg(np.array([5.0, 88.0, 50.0]))
    assert values[0] == pytest.approx(0.0)
    assert values[1] == pytest.approx(10.0)
    assert np.isnan(values[2])


def test_missing_horizon_values_stay_missing():
    profile = ProfileHorizon(
        AZIMUTHS, np.array([0.0, np.nan, 0.0, 0.0])
    )
    values = profile.horizon_deg(np.array([0.0, 45.0, 90.0, 135.0, 180.0]))
    assert np.isfinite(values[[0, 4]]).all()
    assert np.isnan(values[[1, 2, 3]]).all()


def test_profile_sorts_and_validates():
    profile = ProfileHorizon(np.array([90.0, 0.0]), np.array([10.0, 0.0]))
    assert profile.azimuth_deg.tolist() == [0.0, 90.0]
    assert at(profile, 45.0) == pytest.approx(5.0)

    with pytest.raises(ValueError):
        ProfileHorizon(np.array([0.0, 90.0]), np.array([0.0]))
    with pytest.raises(ValueError):
        ProfileHorizon(np.array([]), np.array([]))
    with pytest.raises(ValueError):
        ProfileHorizon(np.array([np.nan]), np.array([0.0]))
    with pytest.raises(ValueError):
        ProfileHorizon(AZIMUTHS, HORIZONS, azimuth_tolerance_deg=-1.0)


def test_load_horizon_profile_reads_k2_csv(tmp_path):
    path = tmp_path / "profile.csv"
    path.write_text(
        "\ufeffazimuth_deg,horizon_deg,gap_fraction\n"
        "90,10,0\n0,0,0\n180,0,0\n270,-10,0\n",
        encoding="utf-8",
    )
    profile = load_horizon_profile(path)

    assert profile.azimuth_deg.tolist() == [0.0, 90.0, 180.0, 270.0]
    assert at(profile, 45.0) == pytest.approx(5.0)


def test_load_horizon_profile_rejects_missing_columns(tmp_path):
    path = tmp_path / "broken.csv"
    path.write_text("angle,value\n0,0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="azimuth_deg"):
        load_horizon_profile(path)


def test_engine_with_real_profile_separates_states():
    profile = ProfileHorizon(np.arange(0.0, 360.0), np.full(360, 5.0))
    engine = VisibilityEngine(
        MockEphemeris(),
        profile,
        EngineConfig(hours=24, step_minutes=60),
    )
    table = engine.run(Site("T", -89.0, 0.0), START)

    high = table.loc[table["sun_alt_deg"] > 6.0, "sun_visible"]
    low = table.loc[table["sun_alt_deg"] < 4.0, "sun_visible"]
    assert len(high) > 0 and (high == VISIBLE).all()
    assert len(low) > 0 and (low == BLOCKED).all()
    assert set(table["joint_visible"]) <= {VISIBLE, BLOCKED, UNCERTAIN}


def test_cli_runs_with_horizon_csv(tmp_path, capsys):
    profile_path = tmp_path / "profile.csv"
    pd.DataFrame({"azimuth_deg": [0, 90, 180, 270], "horizon_deg": [0, 0, 0, 0]}).to_csv(
        profile_path, index=False
    )
    output = tmp_path / "visibility.csv"

    exit_code = main(
        [
            "--horizon-csv",
            str(profile_path),
            "--site-id",
            "T",
            "--latitude",
            "-89.5",
            "--longitude",
            "0",
            "--hours",
            "2",
            "--step-minutes",
            "30",
            "--csv",
            str(output),
        ]
    )

    assert exit_code == 0
    assert output.exists()
    assert "mock" in capsys.readouterr().out


def test_cli_requires_site_arguments_with_profile(tmp_path):
    profile_path = tmp_path / "profile.csv"
    pd.DataFrame({"azimuth_deg": [0, 90], "horizon_deg": [0, 0]}).to_csv(
        profile_path, index=False
    )
    with pytest.raises(SystemExit):
        main(["--horizon-csv", str(profile_path)])
