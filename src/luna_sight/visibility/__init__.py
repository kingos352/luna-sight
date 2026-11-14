"""Görünürlük motoru (K3).

Girdi: K1 azimut/yükseklik serisi + K2 ufuk profili.
Çıktı: ``visible`` / ``blocked`` / ``uncertain`` durumları, gerekçe kodları,
kesintisiz pencereler ve özet istatistikler.
"""

from luna_sight.visibility.analysis import (
    BodyBreakdown,
    breakdown,
    joint_totals,
    margin_shift,
    sensitivity_rows,
    span_hours,
)
from luna_sight.visibility.engine import (
    BODY_EARTH,
    BODY_JOINT,
    BODY_SUN,
    BodyState,
    SampleResult,
    Window,
    build_windows,
    classify,
    evaluate,
    evaluate_series,
    refine_crossing_time,
    summarize_windows,
)
from luna_sight.visibility.profile import HorizonProfileLookup
from luna_sight.visibility.series import (
    Sample,
    load_series_csv,
    parse_utc,
    sample_from_row,
    validate_series,
)
from luna_sight.visibility.states import (
    BLOCKED,
    REASON_CLEAR,
    REASON_MISSING_EPHEMERIS,
    REASON_MISSING_HORIZON,
    REASON_OCCLUDED,
    REASON_QUALITY_MISSING,
    REASON_TRANSITION,
    STATES,
    UNCERTAIN,
    VISIBLE,
    VisibilityConfig,
)

__all__ = [
    "BLOCKED",
    "BODY_EARTH",
    "BODY_JOINT",
    "BODY_SUN",
    "BodyBreakdown",
    "BodyState",
    "HorizonProfileLookup",
    "REASON_CLEAR",
    "REASON_MISSING_EPHEMERIS",
    "REASON_MISSING_HORIZON",
    "REASON_OCCLUDED",
    "REASON_QUALITY_MISSING",
    "REASON_TRANSITION",
    "STATES",
    "Sample",
    "SampleResult",
    "UNCERTAIN",
    "VISIBLE",
    "VisibilityConfig",
    "Window",
    "breakdown",
    "build_windows",
    "classify",
    "evaluate",
    "evaluate_series",
    "joint_totals",
    "load_series_csv",
    "margin_shift",
    "parse_utc",
    "refine_crossing_time",
    "sample_from_row",
    "sensitivity_rows",
    "span_hours",
    "summarize_windows",
    "validate_series",
]
