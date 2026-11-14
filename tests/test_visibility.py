"""K3 görünürlük motoru testleri.

Tüm sentetik veriler `test_fixture` kalite bayrağıyla üretilir
(`docs/DATA_CONTRACT.md`).
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from luna_sight.visibility import (
    BLOCKED,
    CONTRACT_COLUMNS,
    SUMMARY_COLUMNS,
    UNCERTAIN,
    VISIBLE,
    analysis_timestamps,
    build_visibility_table,
    classify_states,
    classify_visibility,
    combine_states,
    summarize,
    visibility_windows,
)

START = pd.Timestamp("2026-11-14T00:00:00Z")


def make_times(periods: int) -> pd.DatetimeIndex:
    return pd.date_range(START, periods=periods, freq="5min")


def make_observations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "site_id": ["A"] * 3,
            "latitude_deg": [-89.5] * 3,
            "longitude_deg_east": [0.0, 10.0, -10.0],
            "timestamp_utc": make_times(3),
            "sun_az_deg": [90.0] * 3,
            "sun_alt_deg": [20.0, -5.0, 0.5],
            "earth_az_deg": [270.0] * 3,
            "earth_alt_deg": [15.0, 15.0, -15.0],
            "terrain_horizon_sun_deg": [10.0, 10.0, 0.0],
            "terrain_horizon_earth_deg": [5.0, 5.0, 5.0],
        }
    )


def make_states_frame(joint_states, *, site_id="A", quality="test_fixture") -> pd.DataFrame:
    quality_flags = quality if isinstance(quality, list) else [quality] * len(joint_states)
    return pd.DataFrame(
        {
            "site_id": [site_id] * len(joint_states),
            "timestamp_utc": make_times(len(joint_states)),
            "sun_visible": joint_states,
            "earth_visible": joint_states,
            "joint_visible": joint_states,
            "quality_flag": quality_flags,
        }
    )


@pytest.mark.parametrize(
    ("altitude", "horizon", "expected"),
    [
        (10.0, 5.0, VISIBLE),
        (5.0, 10.0, BLOCKED),
        (5.2, 5.0, UNCERTAIN),
        (4.8, 5.0, UNCERTAIN),
        (5.5, 5.0, UNCERTAIN),
        (6.0, 5.0, VISIBLE),
        (None, 5.0, UNCERTAIN),
        (5.0, None, UNCERTAIN),
        (float("nan"), 5.0, UNCERTAIN),
    ],
)
def test_classify_visibility_thresholds(altitude, horizon, expected):
    assert classify_visibility(altitude, horizon) == expected


def test_zero_band_makes_any_positive_margin_visible():
    assert classify_visibility(0.1, 0.0, uncertainty_deg=0.0) == VISIBLE
    assert classify_visibility(-0.1, 0.0, uncertainty_deg=0.0) == BLOCKED


def test_invalid_uncertainty_rejected():
    with pytest.raises(ValueError):
        classify_visibility(1.0, 0.0, uncertainty_deg=-0.1)
    with pytest.raises(ValueError):
        classify_states([1.0], [0.0], uncertainty_deg=float("nan"))


def test_classify_states_matches_scalar_rule():
    altitudes = [10.0, 5.0, 5.2, None]
    horizons = [5.0, 10.0, 5.0, 5.0]
    result = classify_states(altitudes, horizons).tolist()
    assert result == [classify_visibility(a, h) for a, h in zip(altitudes, horizons)]


@pytest.mark.parametrize(
    ("sun", "earth", "joint"),
    [
        (VISIBLE, VISIBLE, VISIBLE),
        (VISIBLE, BLOCKED, BLOCKED),
        (BLOCKED, VISIBLE, BLOCKED),
        (BLOCKED, BLOCKED, BLOCKED),
        (VISIBLE, UNCERTAIN, UNCERTAIN),
        (UNCERTAIN, BLOCKED, BLOCKED),
        (UNCERTAIN, UNCERTAIN, UNCERTAIN),
    ],
)
def test_combine_states_truth_table(sun, earth, joint):
    assert combine_states([sun], [earth]).tolist() == [joint]


def test_combine_states_rejects_unknown_state():
    with pytest.raises(ValueError):
        combine_states(["visible"], ["unknown"])


def test_build_visibility_table_uses_contract_shape():
    table = build_visibility_table(
        make_observations(),
        source_id="internal-test",
        source_version="0",
        quality_flag="test_fixture",
    )

    assert tuple(table.columns) == CONTRACT_COLUMNS
    assert table["sun_visible"].tolist() == [VISIBLE, BLOCKED, UNCERTAIN]
    assert table["earth_visible"].tolist() == [VISIBLE, VISIBLE, BLOCKED]
    assert table["joint_visible"].tolist() == [VISIBLE, BLOCKED, BLOCKED]
    assert set(table["quality_flag"]) == {"test_fixture"}

    parameters = json.loads(table["parameters"].iloc[0])
    assert parameters["uncertainty_deg"] == 0.5
    assert parameters["rule"] == "altitude_vs_terrain_horizon"


def test_naive_timestamps_rejected():
    frame = make_observations().assign(
        timestamp_utc=pd.date_range(START.tz_localize(None), periods=3, freq="5min")
    )
    with pytest.raises(ValueError, match="saat dilimi"):
        build_visibility_table(frame)


def test_missing_input_column_rejected():
    frame = make_observations().drop(columns=["terrain_horizon_sun_deg"])
    with pytest.raises(ValueError, match="terrain_horizon_sun_deg"):
        build_visibility_table(frame)


def test_duplicate_site_timestamp_rejected():
    frame = make_observations()
    frame.loc[1, ["site_id", "timestamp_utc"]] = frame.loc[0, ["site_id", "timestamp_utc"]]
    with pytest.raises(ValueError, match="birden fazla"):
        build_visibility_table(frame)


@pytest.mark.parametrize(
    ("column", "value"),
    [("latitude_deg", 120.0), ("longitude_deg_east", -400.0)],
)
def test_out_of_range_coordinates_rejected(column, value):
    frame = make_observations().copy()
    frame.loc[0, column] = value
    with pytest.raises(ValueError, match=column):
        build_visibility_table(frame)


def test_quality_flags_are_derived_from_measurements():
    make = make_observations()
    frame = pd.concat([make.iloc[[0]], make.iloc[[0]]], ignore_index=True)
    frame.loc[1, "sun_alt_deg"] = float("nan")
    frame.loc[1, "timestamp_utc"] = make_times(2)[1]

    incomplete = frame.copy()
    incomplete.loc[1, ["sun_az_deg", "sun_alt_deg", "earth_az_deg", "earth_alt_deg"]] = float("nan")
    incomplete.loc[
        1, ["terrain_horizon_sun_deg", "terrain_horizon_earth_deg"]
    ] = float("nan")
    incomplete.loc[1, "timestamp_utc"] = make_times(2)[1]

    table = build_visibility_table(incomplete)
    assert table["quality_flag"].tolist() == ["valid", "missing"]
    assert table["joint_visible"].tolist() == [VISIBLE, UNCERTAIN]


def test_analysis_timestamps_default_grid():
    grid = analysis_timestamps(START)
    assert len(grid) == 2016
    assert str(grid[0]) == "2026-11-14 00:00:00+00:00"
    assert grid[-1] == START + pd.Timedelta(hours=168) - pd.Timedelta(minutes=5)
    assert grid[1] - grid[0] == pd.Timedelta(minutes=5)
    assert len(grid) * pd.Timedelta(minutes=5) == pd.Timedelta(hours=168)


def test_analysis_timestamps_rejects_bad_input():
    with pytest.raises(ValueError):
        analysis_timestamps(START, hours=1, step_minutes=7)
    with pytest.raises(ValueError):
        analysis_timestamps(START.tz_localize(None))
    with pytest.raises(ValueError):
        analysis_timestamps(START, step_minutes=0)
    with pytest.raises(ValueError):
        analysis_timestamps(START, hours=0)


def test_visibility_windows_duration():
    states = [VISIBLE, VISIBLE, VISIBLE, BLOCKED, BLOCKED, VISIBLE]
    windows = visibility_windows(states, make_times(6))

    assert [window.sample_count for window in windows] == [3, 1]
    assert windows[0].duration_hours == pytest.approx(0.25)
    assert windows[1].duration_hours == pytest.approx(5 / 60)
    assert windows[0].start_utc == START


def test_visibility_windows_empty_when_blocked():
    assert visibility_windows([BLOCKED] * 4, make_times(4)) == []


def test_summarize_compares_sites():
    first = make_states_frame([VISIBLE] * 6 + [BLOCKED] * 6, site_id="A")
    second = make_states_frame([VISIBLE] * 12, site_id="B")
    summary = summarize(pd.concat([first, second], ignore_index=True))

    assert tuple(summary.columns) == SUMMARY_COLUMNS
    assert summary.index.tolist() == ["A", "B"]
    assert summary.loc["A", "joint_visible_hours"] == pytest.approx(0.5)
    assert summary.loc["A", "joint_blocked_hours"] == pytest.approx(0.5)
    assert summary.loc["A", "visible_fraction"] == pytest.approx(0.5)
    assert summary.loc["A", "visible_window_count"] == 1
    assert summary.loc["A", "longest_visible_hours"] == pytest.approx(0.5)
    assert summary.loc["B", "joint_visible_hours"] == pytest.approx(1.0)
    assert summary.loc["B", "visible_fraction"] == pytest.approx(1.0)


def test_summarize_excludes_incomplete_rows_and_splits_windows():
    frame = make_states_frame(
        [VISIBLE] * 12,
        quality=["test_fixture"] * 3 + ["partial"] + ["test_fixture"] * 8,
    )
    summary = summarize(frame)

    assert summary.loc["A", "usable_rows"] == 11
    assert summary.loc["A", "joint_visible_hours"] == pytest.approx(11 * 5 / 60)
    assert summary.loc["A", "visible_window_count"] == 2
    assert summary.loc["A", "longest_visible_hours"] == pytest.approx(40 / 60)
    assert summary.loc["A", "visible_fraction"] == pytest.approx(1.0)


def test_summarize_requires_contract_columns():
    with pytest.raises(ValueError, match="joint_visible"):
        summarize(pd.DataFrame({"site_id": ["A"], "timestamp_utc": [START]}))
