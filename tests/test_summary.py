"""Özet metrik ve sözleşme doğrulama testleri."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from luna_sight.visibility import (
    BLOCKED,
    VISIBLE,
    ConstantHorizon,
    Sample,
    evaluate_series,
    summarize,
)
from luna_sight.visibility.summary import SUMMARY_COLUMNS
from luna_sight.visibility.table import results_to_frame, validate_table

START = datetime(2026, 11, 14, tzinfo=timezone.utc)


def sample(index: int, sun_alt: float, earth_alt: float = 5.0) -> Sample:
    return Sample(
        timestamp_utc=START + timedelta(hours=index),
        sun_az_deg=180.0,
        sun_alt_deg=sun_alt,
        earth_az_deg=180.0,
        earth_alt_deg=earth_alt,
        site_id="T",
        latitude_deg=-89.5,
        longitude_deg_east=0.0,
        quality_flag="valid",
        source_id="test",
        source_version="v1",
        model_id="visibility-v1",
        parameters='{"rule": "test", "margin_deg": 0.2}',
    )


def frame_for(alts: list[float]) -> "object":
    results = evaluate_series(
        [sample(index, alt) for index, alt in enumerate(alts)],
        ConstantHorizon(0.0),
    )
    return results_to_frame(results)


def test_mixed_states_produce_expected_totals():
    frame = frame_for([5.0, -5.0, 5.0, 5.0])
    summary = summarize(frame)

    row = summary.loc["T"]
    assert list(summary.columns) == list(SUMMARY_COLUMNS)
    assert row["samples"] == 4
    assert row["step_minutes"] == pytest.approx(60.0)
    assert row["total_hours"] == pytest.approx(3.0)
    assert row["visible_hours"] == pytest.approx(2.0)
    assert row["blocked_hours"] == pytest.approx(1.0)
    assert row["uncertain_hours"] == pytest.approx(0.0)
    assert row["visible_fraction"] == pytest.approx(2.0 / 3.0)
    assert row["visible_window_count"] == 2
    assert row["longest_visible_hours"] == pytest.approx(1.0)
    assert row["margin_deg"] == pytest.approx(0.2)


def test_all_visible_and_all_blocked():
    all_visible = summarize(frame_for([5.0, 5.0, 5.0]))
    assert all_visible.loc["T", "visible_fraction"] == pytest.approx(1.0)
    assert all_visible.loc["T", "visible_window_count"] == 1

    all_blocked = summarize(frame_for([-5.0, -5.0]))
    assert all_blocked.loc["T", "visible_fraction"] == pytest.approx(0.0)
    assert all_blocked.loc["T", "visible_window_count"] == 0
    assert all_blocked.loc["T", "longest_visible_hours"] == pytest.approx(0.0)


def test_single_sample_has_no_fraction():
    summary = summarize(frame_for([5.0]))
    row = summary.loc["T"]
    assert row["samples"] == 1
    assert row["total_hours"] == pytest.approx(0.0)
    assert row["visible_fraction"] is None


def test_joint_state_is_blocked_when_either_body_is_blocked():
    results = evaluate_series(
        [sample(0, 5.0, earth_alt=-5.0)],
        ConstantHorizon(0.0),
    )
    frame = results_to_frame(results)
    assert frame.loc[0, "sun_visible"] == VISIBLE
    assert frame.loc[0, "earth_visible"] == BLOCKED
    assert frame.loc[0, "joint_visible"] == BLOCKED


def test_validate_table_rejects_unknown_state():
    frame = frame_for([5.0, 5.0])
    frame.loc[0, "joint_visible"] = "maybe"
    with pytest.raises(ValueError, match="joint_visible"):
        validate_table(frame)


def test_validate_table_requires_contract_columns():
    frame = frame_for([5.0])
    with pytest.raises(ValueError, match="timestamp_utc"):
        validate_table(frame.drop(columns=["timestamp_utc"]))
