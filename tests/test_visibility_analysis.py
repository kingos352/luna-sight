"""Duyarlılık analizi testleri (test_fixture)."""

from datetime import datetime, timedelta, timezone

import pytest

from luna_sight.visibility.analysis import (
    breakdown,
    joint_totals,
    margin_shift,
    sensitivity_rows,
    span_hours,
)
from luna_sight.visibility.engine import BODY_EARTH, BODY_JOINT, BODY_SUN
from luna_sight.visibility.profile import HorizonProfileLookup
from luna_sight.visibility.series import Sample
from luna_sight.visibility.states import (
    BLOCKED,
    UNCERTAIN,
    VISIBLE,
    VisibilityConfig,
)

START = datetime(2026, 11, 15, tzinfo=timezone.utc)
FLAT = HorizonProfileLookup([0.0, 180.0], [0.0, 0.0])
PATCHY = HorizonProfileLookup(
    [0.0, 180.0, 359.0], [float("nan"), 0.0, 0.0]
)


def make_sample(
    minute: float,
    sun_alt: float | None,
    earth_alt: float | None,
    *,
    sun_az: float = 10.0,
    earth_az: float = 20.0,
) -> Sample:
    return Sample(
        timestamp_utc=START + timedelta(minutes=minute),
        sun_az_deg=sun_az,
        sun_alt_deg=sun_alt,
        earth_az_deg=earth_az,
        earth_alt_deg=earth_alt,
        site_id="Site01",
        latitude_deg=-89.9,
        longitude_deg_east=0.0,
        quality_flag="test_fixture",
        source_id="unit-test",
        source_version="v1",
        model_id="analysis-test",
        parameters="",
    )


def hourly(alt: float, count: int = 13) -> list[Sample]:
    """Saatte 5 dakika adımlı, sabit yükseklikte seri."""
    return [make_sample(5.0 * i, alt, alt) for i in range(count)]


def evaluate(samples: list[Sample], config: VisibilityConfig | None = None):
    from luna_sight.visibility.engine import evaluate_series

    return evaluate_series(samples, FLAT, config or VisibilityConfig())


# ------------------------------------------------------------------- süre/oran
def test_span_hours_uses_first_and_last_sample():
    assert span_hours(evaluate(hourly(1.0))) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        span_hours([])


def test_all_visible_breakdown_sums_to_one():
    item = breakdown(evaluate(hourly(1.0)), BODY_JOINT)
    assert item.state_fractions[VISIBLE] == pytest.approx(1.0)
    assert item.state_fractions[BLOCKED] == pytest.approx(0.0)
    assert item.state_fractions[UNCERTAIN] == pytest.approx(0.0)
    assert item.window_count == 1
    assert item.longest_visible_hours == pytest.approx(1.0)
    assert item.refined_boundaries == 0


def test_all_blocked_and_all_uncertain():
    blocked = breakdown(evaluate(hourly(-1.0)), BODY_JOINT)
    assert blocked.state_fractions[BLOCKED] == pytest.approx(1.0)
    assert blocked.longest_visible_hours is None

    missing = breakdown(
        evaluate([make_sample(5.0 * i, None, 1.0) for i in range(13)]),
        BODY_JOINT,
    )
    assert missing.state_fractions[UNCERTAIN] == pytest.approx(1.0)


def test_wider_margin_converts_visible_to_uncertain():
    """Marj, bant içindeki örnekleri belirsiz yapar; sonuç marja duyarlıdır."""
    samples = hourly(0.05)
    narrow = breakdown(
        evaluate(samples, VisibilityConfig(margin_deg=0.01)), BODY_JOINT
    )
    wide = breakdown(
        evaluate(samples, VisibilityConfig(margin_deg=0.10)), BODY_JOINT
    )
    assert narrow.state_fractions[VISIBLE] == pytest.approx(1.0)
    assert wide.state_fractions[UNCERTAIN] == pytest.approx(1.0)


def test_missing_horizon_fraction_is_uncertain():
    samples = [make_sample(5.0 * i, 1.0, 1.0, sun_az=10.0) for i in range(13)]
    from luna_sight.visibility.engine import evaluate_series

    item = breakdown(evaluate_series(samples, PATCHY), BODY_SUN)
    assert item.state_fractions[UNCERTAIN] == pytest.approx(1.0)
    assert item.state_fractions[VISIBLE] == pytest.approx(0.0)


def test_longest_visible_window_without_refinement():
    alts = [1.0, 1.0, -1.0, -1.0, 1.0, 1.0]
    samples = [make_sample(5.0 * i, alt, alt) for i, alt in enumerate(alts)]
    config = VisibilityConfig(refine_boundaries=False)
    item = breakdown(evaluate(samples, config), BODY_JOINT, config)
    assert item.window_count == 3
    assert item.longest_visible_hours == pytest.approx(10.0 / 60.0, abs=1e-4)


def test_breakdown_rejects_unknown_body():
    with pytest.raises(ValueError):
        breakdown(evaluate(hourly(1.0)), "moon")


# ------------------------------------------------------------------- tablo satırı
def test_sensitivity_rows_cover_three_bodies():
    rows = sensitivity_rows(
        evaluate(hourly(1.0)),
        VisibilityConfig(margin_deg=0.05),
        site_id="Site01",
        profile="outputs/k2/Site01_horizon_2000m.csv",
        radius_m=2000,
    )
    assert [row["body"] for row in rows] == [BODY_SUN, BODY_EARTH, BODY_JOINT]
    for row in rows:
        assert row["site_id"] == "Site01"
        assert row["radius_m"] == 2000
        assert row["margin_deg"] == 0.05
        total = (
            row["visible_fraction"]
            + row["blocked_fraction"]
            + row["uncertain_fraction"]
        )
        assert total == pytest.approx(1.0)


def test_sensitivity_rows_match_body_states():
    rows = sensitivity_rows(
        evaluate(hourly(1.0)),
        site_id="Site01",
        profile="profile.csv",
        radius_m=4000,
    )
    joint = joint_totals(rows)
    assert joint["visible_fraction"] == pytest.approx(1.0)
    assert joint["longest_visible_hours"] == pytest.approx(1.0)
    with pytest.raises(ValueError):
        joint_totals([row for row in rows if row["body"] != BODY_JOINT])


def test_margin_shift_reports_delta_in_fraction():
    baseline = {"visible_fraction": 0.40, "longest_visible_hours": 10.0}
    candidate = {"visible_fraction": 0.55, "longest_visible_hours": 12.5}
    delta = margin_shift(baseline, candidate)
    assert delta["visible_fraction_delta"] == pytest.approx(0.15)
    assert delta["longest_visible_hours_delta"] == pytest.approx(2.5)

    unknown = margin_shift(
        {"visible_fraction": None, "longest_visible_hours": None}, candidate
    )
    assert unknown["visible_fraction_delta"] is None
