"""Sınıflandırma durumları ve gerekçe kodları (test_fixture).

`docs/DATA_CONTRACT.md` üç durum tanımlar: visible, blocked, uncertain.
Eksik veri hiçbir koşulda visible/blocked sınıfına çevrilmez.
"""

import pytest

from luna_sight.visibility.engine import classify
from luna_sight.visibility.states import (
    BLOCKED,
    REASON_CLEAR,
    REASON_MISSING_EPHEMERIS,
    REASON_MISSING_HORIZON,
    REASON_OCCLUDED,
    REASON_QUALITY_MISSING,
    REASON_TRANSITION,
    UNCERTAIN,
    VISIBLE,
    VisibilityConfig,
)


@pytest.mark.parametrize(
    "alt_deg,horizon_deg,expected",
    [
        (10.0, 0.0, VISIBLE),
        (0.5, 0.0, VISIBLE),
        (-10.0, 0.0, BLOCKED),
        (-0.5, 0.0, BLOCKED),
        (5.0, 5.5, BLOCKED),
        (5.5, 5.0, VISIBLE),
    ],
)
def test_normal_cases(alt_deg, horizon_deg, expected):
    state, _reason = classify(alt_deg, horizon_deg)
    assert state == expected


def test_clear_and_occluded_reasons():
    assert classify(10.0, 0.0)[1] == REASON_CLEAR
    assert classify(-10.0, 0.0)[1] == REASON_OCCLUDED


@pytest.mark.parametrize("margin", [0.0, 0.05, -0.05, 0.099, -0.099])
def test_transition_band_is_uncertain(margin):
    state, reason = classify(margin, 0.0)
    assert state == UNCERTAIN
    assert reason == REASON_TRANSITION


def test_transition_band_edges_and_custom_margin():
    # Tam sınır (0.10°) hâlâ geçiş bandında sayılır.
    assert classify(0.10, 0.0)[0] == UNCERTAIN
    assert classify(0.101, 0.0)[0] == VISIBLE
    assert classify(-0.101, 0.0)[0] == BLOCKED

    strict = VisibilityConfig(margin_deg=0.0)
    assert classify(0.0, 0.0, config=strict)[0] == UNCERTAIN
    assert classify(0.01, 0.0, config=strict)[0] == VISIBLE


def test_missing_altitude_is_uncertain():
    state, reason = classify(None, 0.0)
    assert state == UNCERTAIN
    assert reason == REASON_MISSING_EPHEMERIS


def test_missing_horizon_is_uncertain():
    state, reason = classify(10.0, None)
    assert state == UNCERTAIN
    assert reason == REASON_MISSING_HORIZON


def test_quality_missing_overrides_geometry():
    """Kalite bayrağı `missing` ise yükseklik ufkun üzerinde olsa da karar yok."""
    state, reason = classify(10.0, 0.0, quality_flag="missing")
    assert state == UNCERTAIN
    assert reason == REASON_QUALITY_MISSING

    # Diğer kalite bayrakları geometrik sınıflandırmayı değiştirmez.
    assert classify(10.0, 0.0, quality_flag="partial")[0] == VISIBLE
    assert classify(10.0, 0.0, quality_flag="test_fixture")[0] == VISIBLE


def test_config_validation_and_serialisation():
    with pytest.raises(ValueError):
        VisibilityConfig(margin_deg=-0.1)

    payload = VisibilityConfig(margin_deg=0.25).as_dict()
    assert payload == {
        "margin_deg": 0.25,
        "refine_boundaries": True,
        "quality_flag_missing": "missing",
    }
