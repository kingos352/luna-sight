"""Motor iskeleti (K1/K2 stub'larıyla) testleri."""

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
    EngineConfig,
    MockEphemeris,
    Site,
    VisibilityEngine,
    run_demo,
    summarize,
)

START = pd.Timestamp("2026-11-14T00:00:00Z")
SITE = Site("A", -89.5, 0.0)


def make_engine(horizon=None, **config) -> VisibilityEngine:
    settings = EngineConfig(hours=2, step_minutes=10, **config)
    return VisibilityEngine(
        MockEphemeris(),
        horizon if horizon is not None else ConstantHorizon(0.0),
        settings,
    )


def test_run_returns_contract_table():
    table = make_engine().run(SITE, START)

    assert tuple(table.columns) == CONTRACT_COLUMNS
    assert len(table) == 12
    assert set(table["site_id"]) == {"A"}
    assert str(table["timestamp_utc"].dt.tz) == "UTC"
    assert table["source_id"].eq("unknown").all()


def test_high_horizon_blocks_all():
    table = make_engine(ConstantHorizon(90.0)).run(SITE, START)
    assert set(table["joint_visible"]) == {BLOCKED}


def test_negative_horizon_is_always_visible():
    table = make_engine(ConstantHorizon(-90.0)).run(SITE, START)
    assert set(table["joint_visible"]) == {VISIBLE}


def test_missing_horizon_becomes_uncertain_and_partial():
    class NaNVolume:
        def horizon_deg(self, azimuth_deg):
            return np.full(np.shape(azimuth_deg), np.nan)

    table = make_engine(NaNVolume()).run(SITE, START)
    assert set(table["joint_visible"]) == {UNCERTAIN}
    assert set(table["quality_flag"]) == {"partial"}


def test_horizon_provider_receives_sun_and_earth_azimuths():
    class RecordingHorizon:
        def __init__(self):
            self.calls = []

        def horizon_deg(self, azimuth_deg):
            values = np.array(azimuth_deg, dtype=float)
            self.calls.append(values)
            return np.zeros_like(values)

    recorder = RecordingHorizon()
    engine = make_engine(recorder)
    engine.run(SITE, START)

    positions = MockEphemeris().positions(SITE, engine.timestamps(START))
    assert len(recorder.calls) == 2
    np.testing.assert_allclose(recorder.calls[0], positions["sun_az_deg"])
    np.testing.assert_allclose(recorder.calls[1], positions["earth_az_deg"])


def test_scalar_horizon_is_broadcast():
    class ScalarHorizon:
        def horizon_deg(self, azimuth_deg):
            return 0.0

    table = make_engine(ScalarHorizon()).run(SITE, START)
    assert len(table) == 12


def test_ephemeris_row_count_mismatch_rejected():
    class ShortEphemeris:
        def positions(self, site, timestamps):
            return MockEphemeris().positions(site, timestamps).iloc[:-1]

    engine = VisibilityEngine(
        ShortEphemeris(), ConstantHorizon(0.0), EngineConfig(hours=2, step_minutes=10)
    )
    with pytest.raises(ValueError, match="satır döndürdü"):
        engine.run(SITE, START)


def test_ephemeris_timestamps_must_match_grid():
    class ShiftedEphemeris:
        def positions(self, site, timestamps):
            frame = MockEphemeris().positions(site, timestamps)
            frame["timestamp_utc"] = frame["timestamp_utc"] + pd.Timedelta(minutes=1)
            return frame

    engine = VisibilityEngine(ShiftedEphemeris(), ConstantHorizon(0.0), EngineConfig(hours=2, step_minutes=10))
    with pytest.raises(ValueError, match="eşleşmiyor"):
        engine.run(SITE, START)


def test_ephemeris_missing_column_rejected():
    class IncompleteEphemeris:
        def positions(self, site, timestamps):
            return MockEphemeris().positions(site, timestamps).drop(columns=["sun_alt_deg"])

    engine = VisibilityEngine(IncompleteEphemeris(), ConstantHorizon(0.0), EngineConfig(hours=2, step_minutes=10))
    with pytest.raises(ValueError, match="sun_alt_deg"):
        engine.run(SITE, START)


def test_invalid_site_coordinates_rejected():
    with pytest.raises(ValueError, match="latitude_deg"):
        make_engine().run(Site("X", 120.0, 0.0), START)


def test_run_many_compares_sites():
    engine = VisibilityEngine(
        MockEphemeris(),
        ConstantHorizon(3.0),
        EngineConfig(hours=24, step_minutes=15),
    )
    table = engine.run_many(
        [Site("A", -89.5, 0.0), Site("B", -88.0, 90.0)],
        START,
    )

    assert len(table) == 2 * 96
    summary = summarize(table)
    assert summary.index.tolist() == ["A", "B"]
    assert summary.loc["A", "visible_window_count"] != summary.loc["B", "visible_window_count"]
    assert summary.loc["A", "longest_visible_hours"] > summary.loc["B", "longest_visible_hours"]
    assert summary.loc["A", "first_visible_utc"] != summary.loc["B", "first_visible_utc"]


def test_demo_runs_without_k1_or_k2():
    table = run_demo(hours=24)
    assert tuple(table.columns) == CONTRACT_COLUMNS
    assert len(table) == 2 * 288
    assert set(table["source_id"]) == {"demo"}

    summary = summarize(table)
    assert summary.index.tolist() == ["A", "B"]
    assert summary["joint_visible_hours"].sum() > 0
