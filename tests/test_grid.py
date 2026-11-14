"""UTC analiz ızgarası testleri."""

from __future__ import annotations

import pandas as pd
import pytest

from luna_sight.visibility.grid import (
    DEFAULT_ANALYSIS_HOURS,
    DEFAULT_STEP_MINUTES,
    analysis_timestamps,
)

START = "2026-11-14T00:00:00Z"


def test_default_grid_is_interval_exact():
    grid = analysis_timestamps(START)
    assert len(grid) == int(DEFAULT_ANALYSIS_HOURS * 60 / DEFAULT_STEP_MINUTES)
    assert len(grid) == 2016
    assert grid[0] == pd.Timestamp(START)
    assert grid[-1] - grid[0] == pd.Timedelta(hours=167, minutes=55)
    assert (grid[1] - grid[0]) == pd.Timedelta(minutes=5)


def test_custom_grid_counts_and_timezone():
    grid = analysis_timestamps(START, hours=12, step_minutes=30)
    assert len(grid) == 24
    assert str(grid.tz) == "UTC"
    assert grid.freq == pd.Timedelta(minutes=30)


def test_naive_start_is_rejected():
    with pytest.raises(ValueError, match="saat dilimi"):
        analysis_timestamps("2026-11-14T00:00:00", hours=1)


def test_non_multiple_hours_are_rejected():
    with pytest.raises(ValueError, match="tam katı"):
        analysis_timestamps(START, hours=1, step_minutes=7)


def test_invalid_steps_and_spans_are_rejected():
    with pytest.raises(ValueError):
        analysis_timestamps(START, hours=1, step_minutes=0)
    with pytest.raises(ValueError):
        analysis_timestamps(START, hours=-1)
    with pytest.raises(ValueError):
        analysis_timestamps(START, hours=0, step_minutes=5)


def test_result_is_utc_even_for_other_offsets():
    grid = analysis_timestamps("2026-11-14T03:00:00+03:00", hours=1, step_minutes=30)
    assert grid[0] == pd.Timestamp("2026-11-14T00:00:00Z")
