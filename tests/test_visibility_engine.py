"""Motor testleri: birleşik durum, pencereler ve sınır inceltme (test_fixture)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from luna_sight.visibility.engine import (
    BODY_EARTH,
    BODY_JOINT,
    BODY_SUN,
    build_windows,
    evaluate,
    evaluate_series,
    refine_crossing_time,
    summarize_windows,
)
from luna_sight.visibility.profile import HorizonProfileLookup
from luna_sight.visibility.series import Sample
from luna_sight.visibility.states import (
    BLOCKED,
    REASON_CLEAR,
    REASON_MISSING_EPHEMERIS,
    REASON_OCCLUDED,
    REASON_TRANSITION,
    UNCERTAIN,
    VISIBLE,
    VisibilityConfig,
)
from luna_sight.visibility.synthetic import synthetic_series

START = datetime(2026, 11, 15, tzinfo=UTC)
FLAT = HorizonProfileLookup([0.0, 180.0], [0.0, 0.0])
K2_PROFILE = (
    Path(__file__).resolve().parents[1] / "outputs" / "k2" / "Site04_horizon_4000m.csv"
)
CONTRACT_FIELDS = {
    "site_id",
    "latitude_deg",
    "longitude_deg_east",
    "timestamp_utc",
    "sun_az_deg",
    "sun_alt_deg",
    "earth_az_deg",
    "earth_alt_deg",
    "terrain_horizon_sun_deg",
    "terrain_horizon_earth_deg",
    "sun_visible",
    "earth_visible",
    "joint_visible",
    "quality_flag",
    "source_id",
    "source_version",
    "model_id",
    "parameters",
}


def make_sample(
    minute: float,
    sun_alt: float | None,
    earth_alt: float | None,
    *,
    sun_az: float = 10.0,
    earth_az: float = 20.0,
    quality_flag: str = "valid",
) -> Sample:
    return Sample(
        timestamp_utc=START + timedelta(minutes=minute),
        sun_az_deg=sun_az,
        sun_alt_deg=sun_alt,
        earth_az_deg=earth_az,
        earth_alt_deg=earth_alt,
        site_id="Site04",
        latitude_deg=-89.766811,
        longitude_deg_east=-171.869898,
        quality_flag=quality_flag,
        source_id="test-fixture",
        source_version="v1",
        model_id="unit-test",
        parameters="margin=0.1",
    )


# ------------------------------------------------------------------ birleşik durum
def test_both_visible_gives_visible_joint():
    result = evaluate(make_sample(0, 1.0, 1.0), FLAT)
    assert (result.sun.state, result.earth.state) == (VISIBLE, VISIBLE)
    assert result.joint_state == VISIBLE
    assert result.joint_reason == REASON_CLEAR
    assert result.joint_margin_deg == pytest.approx(1.0)


def test_blocked_body_blocks_joint():
    result = evaluate(make_sample(0, 1.0, -1.0), FLAT)
    assert result.earth.state == BLOCKED
    assert result.joint_state == BLOCKED
    assert result.joint_reason == REASON_OCCLUDED
    # Ortak marj, en kısıtlayıcı cisminkidir.
    assert result.joint_margin_deg == pytest.approx(-1.0)


def test_uncertain_body_makes_joint_uncertain():
    result = evaluate(make_sample(0, 0.05, 1.0), FLAT)
    assert result.sun.state == UNCERTAIN
    assert result.joint_state == UNCERTAIN
    assert result.joint_reason == REASON_TRANSITION


def test_blocked_wins_over_uncertain():
    """Kesin engel, diğer cisim belirsiz olsa da ortak kararı belirler."""
    result = evaluate(make_sample(0, None, -1.0), FLAT)
    assert result.sun.reason == REASON_MISSING_EPHEMERIS
    assert result.joint_state == BLOCKED


def test_missing_ephemeris_is_explicit():
    result = evaluate(make_sample(0, None, 1.0), FLAT)
    assert result.sun.state == UNCERTAIN
    assert result.sun.reason == REASON_MISSING_EPHEMERIS
    assert result.sun.horizon_deg is None
    assert result.sun.margin_deg is None
    assert result.joint_reason == REASON_MISSING_EPHEMERIS


def test_missing_horizon_segment_is_uncertain():
    profile = HorizonProfileLookup(
        [0.0, 90.0, 180.0, 270.0], [0.0, float("nan"), 2.0, 3.0]
    )
    # 90° civarı NaN segmentin içinde kalır.
    result = evaluate(make_sample(0, 10.0, 10.0, sun_az=90.0, earth_az=90.0), profile)
    assert result.sun.state == UNCERTAIN
    assert result.sun.horizon_deg is None


def test_quality_missing_forces_uncertain():
    result = evaluate(make_sample(0, 10.0, 10.0, quality_flag="missing"), FLAT)
    assert result.sun.state == UNCERTAIN


def test_row_contains_all_contract_fields():
    row = evaluate(make_sample(0, 1.0, 1.0), FLAT).as_row()
    assert CONTRACT_FIELDS <= set(row)
    assert row["sun_visible"] == VISIBLE
    assert row["joint_visible"] == VISIBLE
    assert row["latitude_deg"] == "-89.766811"
    assert row["parameters"] == "margin=0.1"
    assert row["timestamp_utc"].endswith("+00:00")


# ------------------------------------------------------------------ sınır inceltme
def test_refine_crossing_time_interpolates_linearly():
    t0 = START
    t1 = START + timedelta(minutes=10)
    # −1 → +1: sıfır geçişi tam ortada.
    assert refine_crossing_time(t0, t1, -1.0, 1.0) == START + timedelta(minutes=5)
    # −2 → +1: geçiş 2/3 noktada.
    refined = refine_crossing_time(t0, t1, -2.0, 1.0)
    assert refined is not None
    assert (refined - START).total_seconds() == pytest.approx(10 * 60 * 2 / 3, abs=1e-6)


def test_refine_crossing_time_rejects_non_crossings():
    t0 = START
    t1 = START + timedelta(minutes=10)
    assert refine_crossing_time(t0, t1, 1.0, 2.0) is None
    assert refine_crossing_time(t0, t1, -2.0, -1.0) is None
    assert refine_crossing_time(t0, t1, 1.0, 1.0) is None


def test_refine_crossing_time_with_band_level():
    t0 = START
    t1 = START + timedelta(minutes=10)
    refined = refine_crossing_time(t0, t1, 1.0, 0.05, level=0.1)
    assert refined is not None
    assert (refined - START).total_seconds() == pytest.approx(600.0 * 0.9 / 0.95)
    # Seviye iki marjın arasında değilse inceltme yapılmaz.
    assert refine_crossing_time(t0, t1, 1.0, 0.5, level=0.1) is None


# ------------------------------------------------------------------ pencereler
def test_windows_split_and_refine_boundary():
    results = evaluate_series(
        [
            make_sample(0, 1.0, 1.0),
            make_sample(10, 1.0, 1.0),
            make_sample(20, -1.0, -1.0),
            make_sample(30, -1.0, -1.0),
        ],
        FLAT,
    )
    windows = build_windows(results, BODY_JOINT)

    assert [w.state for w in windows] == [VISIBLE, BLOCKED]
    first, second = windows
    # +1 → −1 geçişi 10. ve 20. dakikaların tam ortasında inceltilmeli.
    assert first.start_utc == START
    assert first.end_utc == START + timedelta(minutes=15)
    assert first.end_refined is True
    assert second.start_utc == START + timedelta(minutes=15)
    assert second.start_refined is True
    assert second.end_utc == START + timedelta(minutes=30)
    assert second.end_refined is False
    assert first.reason == REASON_CLEAR
    assert second.reason == REASON_OCCLUDED
    assert first.duration_hours == pytest.approx(15.0 / 60.0)


def test_uncertain_band_edges_are_refined():
    """Geçiş bandının kenarları ±margin_deg seviyesine göre inceltilir."""
    results = evaluate_series(
        [
            make_sample(0, 1.0, 1.0),
            make_sample(10, 1.0, 1.0),
            make_sample(20, 0.05, 1.0),
            make_sample(30, -1.0, -1.0),
            make_sample(40, -1.0, -1.0),
        ],
        FLAT,
    )
    windows = build_windows(results, BODY_JOINT)

    assert [w.state for w in windows] == [VISIBLE, UNCERTAIN, BLOCKED]
    visible, uncertain, blocked = windows
    # +1.0 → +0.05, seviye +0.1: geçiş 10. ve 20. dakikalar arasında %94.7'de.
    assert (visible.end_utc - START).total_seconds() == pytest.approx(
        600.0 + 600.0 * 0.9 / 0.95, abs=1e-6
    )
    assert visible.end_refined is True
    # +0.05 → −1.0, seviye −0.1: 20. ve 30. dakikalar arasında %14.3'te.
    assert uncertain.start_utc == visible.end_utc
    assert (uncertain.end_utc - START).total_seconds() == pytest.approx(
        1200.0 + 600.0 * 0.15 / 1.05, abs=1e-6
    )
    assert uncertain.end_refined is True
    assert uncertain.reason == REASON_TRANSITION
    assert blocked.start_utc == uncertain.end_utc
    assert blocked.start_refined is True


def test_missing_ephemeris_boundary_is_not_refined():
    """Marjı olmayan belirsizlik (eksik veri) inceltilemez."""
    results = evaluate_series(
        [
            make_sample(0, 1.0, 1.0),
            make_sample(10, None, 1.0),
            make_sample(20, -1.0, -1.0),
        ],
        FLAT,
    )
    windows = build_windows(results, BODY_JOINT)

    assert [w.state for w in windows] == [VISIBLE, UNCERTAIN, BLOCKED]
    assert windows[0].end_utc == START + timedelta(minutes=10)
    assert windows[0].end_refined is False
    assert windows[1].reason == REASON_MISSING_EPHEMERIS
    assert windows[2].start_utc == START + timedelta(minutes=20)
    assert windows[2].start_refined is False


def test_windows_without_refinement_use_sample_times():
    results = evaluate_series(
        [make_sample(0, 1.0, 1.0), make_sample(10, -1.0, -1.0)],
        FLAT,
    )
    windows = build_windows(results, BODY_JOINT, VisibilityConfig(refine_boundaries=False))
    assert windows[0].end_utc == START + timedelta(minutes=10)
    assert windows[0].end_refined is False
    assert windows[1].start_refined is False


def test_body_specific_windows_differ():
    """Güneş görünürken Dünya engelli olabilir; pencereler gövdeye özeldir."""
    results = evaluate_series(
        [make_sample(0, 1.0, -1.0), make_sample(10, 1.0, 1.0)],
        FLAT,
    )
    sun_windows = build_windows(results, BODY_SUN)
    earth_windows = build_windows(results, BODY_EARTH)
    joint_windows = build_windows(results, BODY_JOINT)

    assert [w.state for w in sun_windows] == [VISIBLE]
    assert [w.state for w in earth_windows] == [BLOCKED, VISIBLE]
    assert [w.state for w in joint_windows] == [BLOCKED, VISIBLE]
    assert sun_windows[0].body == BODY_SUN


def test_window_input_validation():
    with pytest.raises(ValueError):
        build_windows([], BODY_JOINT)
    results = evaluate_series([make_sample(0, 1.0, 1.0)], FLAT)
    with pytest.raises(ValueError):
        build_windows(results, "mars")


# ------------------------------------------------------------------ özet
def test_summarize_windows_totals():
    results = evaluate_series(
        [
            make_sample(0, 1.0, 1.0),
            make_sample(10, 1.0, 1.0),
            make_sample(20, -1.0, -1.0),
            make_sample(30, -1.0, -1.0),
        ],
        FLAT,
    )
    windows = build_windows(results, BODY_JOINT)
    summary = summarize_windows(windows, span_hours=0.5)

    assert summary["window_count"] == 2
    assert summary["total_hours"] == pytest.approx(0.5)
    assert summary["state_hours"][VISIBLE] == pytest.approx(15.0 / 60.0)
    assert summary["state_hours"][BLOCKED] == pytest.approx(15.0 / 60.0)
    assert summary["visible_fraction"] == pytest.approx(0.5)
    assert summary["longest_visible_hours"] == pytest.approx(15.0 / 60.0)
    assert summary["longest_visible_start_utc"] == START.isoformat()
    assert summary["refined_boundaries"] == 2  # ilk pencerenin bitişi + ikincinin başlangıcı


def test_summarize_windows_without_visible_period():
    results = evaluate_series(
        [make_sample(0, -1.0, -1.0), make_sample(10, -1.0, -1.0)], FLAT
    )
    summary = summarize_windows(build_windows(results, BODY_JOINT))
    assert summary["visible_fraction"] == pytest.approx(0.0)
    assert summary["longest_visible_hours"] is None
    assert summary["longest_visible_start_utc"] is None


# ------------------------------------------------------------------ uçtan uca
@pytest.mark.skipif(not K2_PROFILE.exists(), reason="K2 profil çıktısı yok")
def test_synthetic_series_end_to_end():
    profile = HorizonProfileLookup.from_csv(K2_PROFILE)
    samples = synthetic_series(hours=24.0, step_minutes=10.0, site_id="Site04")
    results = evaluate_series(samples, profile)

    assert len(results) == 145
    # Senaryo serisi test_fixture olarak kalmalı; bilimsel sonuç sayılmaz.
    assert {r.sample.quality_flag for r in results} == {"test_fixture"}
    states = {r.joint_state for r in results}
    assert states <= {VISIBLE, BLOCKED, UNCERTAIN}

    # Geniş geçiş bandı uçtan uca uncertain üretmeli.
    wide = evaluate_series(samples, profile, VisibilityConfig(margin_deg=2.0))
    assert UNCERTAIN in {r.joint_state for r in wide}

    summary = summarize_windows(build_windows(results, BODY_JOINT), span_hours=24.0)
    assert summary["window_count"] >= 1
    assert 0.0 <= summary["visible_fraction"] <= 1.0
