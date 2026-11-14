"""Runner, sağlayıcılar ve sözleşme tablosu testleri."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from luna_sight.visibility import (
    BLOCKED,
    CONTRACT_COLUMNS,
    UNCERTAIN,
    VISIBLE,
    ConstantHorizon,
    HorizonProfileLookup,
    RunnerConfig,
    Site,
    SyntheticEphemeris,
    VisibilityRunner,
    load_horizon_profile,
    run_demo,
    span_hours,
)
from luna_sight.visibility.providers import POSITION_COLUMNS
from luna_sight.visibility.synthetic import (
    SYNTHETIC_MODEL_ID,
    SYNTHETIC_SOURCE_ID,
    TEST_FIXTURE,
)
from luna_sight.visibility.table import STATE_COLUMNS, TABLE_COLUMNS


def make_runner(hours: float = 24.0, horizon: float = 0.0) -> VisibilityRunner:
    return VisibilityRunner(
        SyntheticEphemeris(),
        ConstantHorizon(horizon),
        RunnerConfig(start_utc="2026-11-14T00:00:00Z", hours=hours, step_minutes=5),
    )


def test_site_validates_coordinates():
    assert Site("A", -89.5, 0.0).site_id == "A"
    with pytest.raises(ValueError):
        Site("", -89.5, 0.0)
    with pytest.raises(ValueError):
        Site("A", -91.0, 0.0)
    with pytest.raises(ValueError):
        Site("A", -89.5, 181.0)
    with pytest.raises(ValueError):
        Site("A", float("nan"), 0.0)


def test_runner_config_validates_window():
    RunnerConfig(hours=24, step_minutes=5)
    with pytest.raises(ValueError):
        RunnerConfig(hours=0)
    with pytest.raises(ValueError):
        RunnerConfig(step_minutes=-5)
    with pytest.raises(ValueError):
        RunnerConfig(margin_deg=-0.1)


def test_synthetic_positions_cover_grid_and_are_fixtures():
    runner = make_runner()
    grid = runner.timestamps()
    positions = SyntheticEphemeris().positions(Site("T", -89.5, 0.0), grid)

    assert len(positions) == len(grid)
    for column in ("timestamp_utc",) + POSITION_COLUMNS:
        assert column in positions.columns
    assert set(positions["quality_flag"]) == {TEST_FIXTURE}
    assert positions["sun_az_deg"].min() >= 0.0
    assert positions["sun_az_deg"].max() < 360.0


def test_runner_builds_contract_table_with_diagnostics():
    runner = make_runner()
    frame = runner.run(Site("T", -89.5, 0.0))

    assert list(frame.columns) == list(TABLE_COLUMNS)
    for column in CONTRACT_COLUMNS:
        assert column in frame.columns
    assert len(frame) == 288
    assert str(frame["timestamp_utc"].dt.tz) == "UTC"
    assert set(frame["joint_visible"]) <= {VISIBLE, BLOCKED, UNCERTAIN}
    assert set(frame["quality_flag"]) == {TEST_FIXTURE}
    assert set(frame["source_id"]) == {SYNTHETIC_SOURCE_ID}
    assert set(frame["model_id"]) == {SYNTHETIC_MODEL_ID}


def test_horizon_choice_changes_visibility():
    site = Site("T", -89.5, 0.0)
    low = make_runner(horizon=-2.0).run(site)
    high = make_runner(horizon=0.0).run(site)

    low_visible = int((low["joint_visible"] == VISIBLE).sum())
    high_visible = int((high["joint_visible"] == VISIBLE).sum())
    assert low_visible == len(low)
    assert high_visible < low_visible


def test_run_many_supports_per_site_horizons():
    runner = make_runner()
    sites = [Site("A", -89.5, 0.0), Site("B", -89.7, 120.0)]
    frame = runner.run_many(sites, {"B": ConstantHorizon(30.0)})

    assert set(frame["site_id"]) == {"A", "B"}
    assert len(frame) == 576
    assert (frame.loc[frame["site_id"] == "B", "joint_visible"] == BLOCKED).all()


def test_run_many_rejects_empty_site_list():
    with pytest.raises(ValueError):
        make_runner().run_many([])


def test_load_horizon_profile_handles_bom_and_nan_gap(tmp_path):
    path = tmp_path / "profile.csv"
    path.write_text(
        "\ufeffazimuth_deg,horizon_deg,gap_fraction\n"
        "0,0,0\n90,nan,1\n180,0,0\n270,-10,0\n",
        encoding="utf-8",
    )
    profile = load_horizon_profile(path)

    assert profile.horizon_deg(0.0) == pytest.approx(0.0)
    assert profile.horizon_deg(45.0) is None
    assert profile.horizon_deg(90.0) is None
    assert profile.horizon_deg(225.0) == pytest.approx(-5.0)
    assert profile.valid_fraction == pytest.approx(0.75)


def test_missing_horizon_gap_becomes_uncertain(tmp_path):
    path = tmp_path / "profile.csv"
    path.write_text(
        "azimuth_deg,horizon_deg\n"
        "0,0\n90,nan\n180,0\n270,0\n",
        encoding="utf-8",
    )
    runner = VisibilityRunner(
        SyntheticEphemeris(),
        load_horizon_profile(path),
        RunnerConfig(hours=24, step_minutes=5),
    )
    frame = runner.run(Site("T", -89.5, 0.0))

    gap = frame.loc[frame["terrain_horizon_sun_deg"].isna()]
    assert len(gap) > 0
    assert (gap["sun_visible"] == UNCERTAIN).all()
    assert set(gap["sun_reason"]) == {"missing_horizon"}
    assert (gap["joint_visible"] != VISIBLE).all()


def test_profile_lookup_is_used_for_both_bodies():
    profile = HorizonProfileLookup(np.arange(0, 360), np.full(360, 10.0))
    runner = VisibilityRunner(
        SyntheticEphemeris(),
        profile,
        RunnerConfig(hours=6, step_minutes=30),
    )
    frame = runner.run(Site("T", -89.5, 0.0))

    assert frame["terrain_horizon_sun_deg"].round(6).eq(10.0).all()
    assert frame["terrain_horizon_earth_deg"].round(6).eq(10.0).all()


def test_evaluate_and_windows_return_core_objects():
    runner = make_runner(hours=6)
    site = Site("T", -89.5, 0.0)

    results = runner.evaluate(site)
    assert len(results) == 72
    assert results[0].sample.site_id == "T"

    windows = runner.windows(site)
    assert windows
    assert abs(sum(window.duration_hours for window in windows) - span_hours(results)) < 1e-9
    with pytest.raises(ValueError):
        runner.windows(site, body="moon")


def test_run_demo_returns_small_table():
    frame = run_demo(hours=2, step_minutes=30)
    assert len(frame) == 4
    assert set(frame["site_id"]) == {"Demo"}
    assert list(frame.columns) == list(TABLE_COLUMNS)
    assert set(STATE_COLUMNS) <= set(frame.columns)


def test_table_rejects_duplicate_site_timestamps():
    frame = make_runner(hours=1).run(Site("T", -89.5, 0.0))
    duplicated = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    from luna_sight.visibility.table import validate_table

    with pytest.raises(ValueError, match="birden fazla"):
        validate_table(duplicated)


K1_HEADER = (
    "site_id,latitude_deg,longitude_deg_east,timestamp_utc,"
    "sun_az_deg,sun_alt_deg,earth_az_deg,earth_alt_deg,"
    "quality_flag,source_id,source_version,model_id,parameters"
)


def write_k1_series(path, *, site_id="Site04", latitude=-89.766811, longitude=-171.869898):
    """K1 `EPHEMERIS_COLUMNS` sırasıyla küçük bir sözleşme CSV'si yazar."""
    import csv

    rows = [
        ["2026-11-15T00:00:00Z", 10.0, -1.2, 65.0, -0.4, "valid"],
        ["2026-11-15T01:00:00Z", 12.0, -0.8, 67.0, -0.2, "valid"],
        ["2026-11-15T02:00:00Z", 14.0, -0.4, 69.0, 0.0, "partial"],
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        handle.write(K1_HEADER + "\n")
        writer = csv.writer(handle)
        for timestamp, sun_az, sun_alt, earth_az, earth_alt, quality in rows:
            writer.writerow(
                [
                    site_id,
                    latitude,
                    longitude,
                    timestamp,
                    sun_az,
                    sun_alt,
                    earth_az,
                    earth_alt,
                    quality,
                    "jpl-horizons",
                    "v1",
                    "horizons-observer-table",
                    '{"step": "1 h"}',
                ]
            )


def test_k1_series_columns_run_through_cli(tmp_path, capsys):
    from luna_sight.visibility.__main__ import main

    series = tmp_path / "k1_series.csv"
    profile = tmp_path / "profile.csv"
    write_k1_series(series)
    pd.DataFrame({"azimuth_deg": [0, 90, 180, 270], "horizon_deg": [0, 0, 0, 0]}).to_csv(
        profile, index=False
    )
    output = tmp_path / "visibility.csv"

    exit_code = main(
        [
            "--series",
            str(series),
            "--profile",
            str(profile),
            "--csv",
            str(output),
        ]
    )

    assert exit_code == 0
    assert output.exists()
    frame = pd.read_csv(output)
    assert len(frame) == 3
    assert set(frame["site_id"]) == {"Site04"}
    assert set(frame["source_id"]) == {"jpl-horizons"}
    assert frame["joint_visible"].isin({VISIBLE, BLOCKED, UNCERTAIN}).all()
    assert "Seri: 3 örnek" in capsys.readouterr().out


def test_series_without_coordinates_requires_cli_site(tmp_path):
    from luna_sight.visibility.__main__ import main

    series = tmp_path / "no_site.csv"
    write_k1_series(series, site_id="", latitude="", longitude="")

    with pytest.raises(SystemExit, match="latitude"):
        main(["--series", str(series)])
