"""Görünürlük motoru: sınıflandırma, birleşik durum ve kesintisiz pencereler.

Motor üç durum üretir (``visible`` / ``blocked`` / ``uncertain``) ve her
örnek için gerekçe kodu tutar. Eksik ephemeris, eksik ufuk veya ``missing``
kalite bayrağı **her zaman** ``uncertain`` üretir; eksik veri görünür ya da
engelli sayılmaz.

Geçiş sınırları: komşu iki örnek farklı durumdaysa sınır, ilgili seviyeye
göre zaman ekseninde doğrusal enterpolasyonla inceltilir. Kesin durumlar
arasındaki geçişte seviye ``0`` (ufuk çizgisi), geçiş bandının kenarında ise
``±margin_deg`` kullanılır. 5 dakikalık örneklemede bu, ±2.5 dakikalık
kuantalamayı örnekleme gürültüsü mertebesine indirir.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from luna_sight.visibility.profile import HorizonProfileLookup
from luna_sight.visibility.series import Sample
from luna_sight.visibility.states import (
    BLOCKED,
    DEFINITE_STATES,
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

BODY_SUN = "sun"
BODY_EARTH = "earth"
BODY_JOINT = "joint"
BODIES = (BODY_SUN, BODY_EARTH, BODY_JOINT)


# --------------------------------------------------------------------- kayıtlar
@dataclass(frozen=True)
class BodyState:
    """Bir gök cismi için tek örneğin sınıflandırması."""

    state: str
    reason: str
    horizon_deg: float | None
    margin_deg: float | None
    """``alt − ufuk``; pozitifse ufkun üzerinde."""


@dataclass(frozen=True)
class SampleResult:
    """Bir zaman damgasının Güneş, Dünya ve ortak görünürlük sonucu."""

    sample: Sample
    sun: BodyState
    earth: BodyState
    joint_state: str
    joint_reason: str
    joint_margin_deg: float | None

    def as_row(self) -> dict[str, object]:
        """Veri sözleşmesine uygun çıktı satırı."""
        return {
            "site_id": self.sample.site_id,
            "latitude_deg": _fmt(self.sample.latitude_deg),
            "longitude_deg_east": _fmt(self.sample.longitude_deg_east),
            "timestamp_utc": self.sample.timestamp_utc.isoformat(),
            "sun_az_deg": _fmt(self.sample.sun_az_deg),
            "sun_alt_deg": _fmt(self.sample.sun_alt_deg),
            "earth_az_deg": _fmt(self.sample.earth_az_deg),
            "earth_alt_deg": _fmt(self.sample.earth_alt_deg),
            "terrain_horizon_sun_deg": _fmt(self.sun.horizon_deg),
            "terrain_horizon_earth_deg": _fmt(self.earth.horizon_deg),
            "sun_visible": self.sun.state,
            "earth_visible": self.earth.state,
            "joint_visible": self.joint_state,
            "sun_margin_deg": _fmt(self.sun.margin_deg),
            "earth_margin_deg": _fmt(self.earth.margin_deg),
            "joint_margin_deg": _fmt(self.joint_margin_deg),
            "sun_reason": self.sun.reason,
            "earth_reason": self.earth.reason,
            "joint_reason": self.joint_reason,
            "quality_flag": self.sample.quality_flag,
            "source_id": self.sample.source_id,
            "source_version": self.sample.source_version,
            "model_id": self.sample.model_id,
            "parameters": self.sample.parameters,
        }


def _fmt(value: float | None, digits: int = 6) -> str:
    return "" if value is None else f"{value:.{digits}f}"


# ------------------------------------------------------------------ sınıflandırma
def classify(
    alt_deg: float | None,
    horizon_deg: float | None,
    *,
    quality_flag: str = "valid",
    config: VisibilityConfig | None = None,
) -> tuple[str, str]:
    """Yükseklik ve ufku üç durumdan birine eşler.

    Dönüş: ``(durum, gerekçe)``.
    """
    config = config or VisibilityConfig()
    if alt_deg is None:
        return UNCERTAIN, REASON_MISSING_EPHEMERIS
    if horizon_deg is None:
        return UNCERTAIN, REASON_MISSING_HORIZON
    if quality_flag == config.quality_flag_missing:
        return UNCERTAIN, REASON_QUALITY_MISSING

    margin = alt_deg - horizon_deg
    if abs(margin) <= config.margin_deg:
        return UNCERTAIN, REASON_TRANSITION
    if margin > 0.0:
        return VISIBLE, REASON_CLEAR
    return BLOCKED, REASON_OCCLUDED


def _evaluate_body(
    azimuth_deg: float | None,
    altitude_deg: float | None,
    profile: HorizonProfileLookup,
    quality_flag: str,
    config: VisibilityConfig,
) -> BodyState:
    if azimuth_deg is None or altitude_deg is None:
        return BodyState(UNCERTAIN, REASON_MISSING_EPHEMERIS, None, None)
    horizon = profile.elevation_at(azimuth_deg)
    state, reason = classify(
        altitude_deg, horizon, quality_flag=quality_flag, config=config
    )
    margin = None if horizon is None else altitude_deg - horizon
    return BodyState(state, reason, horizon, margin)


def _joint(sun: BodyState, earth: BodyState) -> tuple[str, str, float | None]:
    """Güneş ve Dünya durumlarından ortak görünürlük üretir."""
    if sun.state == BLOCKED or earth.state == BLOCKED:
        return BLOCKED, REASON_OCCLUDED, _min_margin(sun, earth)
    if sun.state == VISIBLE and earth.state == VISIBLE:
        return VISIBLE, REASON_CLEAR, _min_margin(sun, earth)

    # En az bir cisim belirsiz: gerekçeyi belirsizlikten seç.
    for body in (sun, earth):
        if body.state == UNCERTAIN and body.reason == REASON_TRANSITION:
            return UNCERTAIN, REASON_TRANSITION, _min_margin(sun, earth)
    reason = REASON_MISSING_EPHEMERIS
    for body in (sun, earth):
        if body.state == UNCERTAIN:
            reason = body.reason
            break
    return UNCERTAIN, reason, _min_margin(sun, earth)


def _min_margin(sun: BodyState, earth: BodyState) -> float | None:
    """Ortak marj; iki cisimden biri bilinmiyorsa ortak marj da bilinmiyor."""
    if sun.margin_deg is None or earth.margin_deg is None:
        return None
    return min(sun.margin_deg, earth.margin_deg)


def evaluate(
    sample: Sample,
    profile: HorizonProfileLookup,
    config: VisibilityConfig | None = None,
) -> SampleResult:
    """Tek bir örneği sınıflandırır."""
    config = config or VisibilityConfig()
    sun = _evaluate_body(
        sample.sun_az_deg, sample.sun_alt_deg, profile, sample.quality_flag, config
    )
    earth = _evaluate_body(
        sample.earth_az_deg, sample.earth_alt_deg, profile, sample.quality_flag, config
    )
    joint_state, joint_reason, joint_margin = _joint(sun, earth)
    return SampleResult(
        sample=sample,
        sun=sun,
        earth=earth,
        joint_state=joint_state,
        joint_reason=joint_reason,
        joint_margin_deg=joint_margin,
    )


def evaluate_series(
    samples: list[Sample],
    profile: HorizonProfileLookup,
    config: VisibilityConfig | None = None,
) -> list[SampleResult]:
    """Seriyi sırayla sınıflandırır (zaman sırası doğrulanmış olmalı)."""
    config = config or VisibilityConfig()
    return [evaluate(sample, profile, config) for sample in samples]


# --------------------------------------------------------------------- pencereler
@dataclass(frozen=True)
class Window:
    """Kesintisiz bir durum aralığı."""

    body: str
    state: str
    start_utc: datetime
    end_utc: datetime
    start_refined: bool = False
    end_refined: bool = False
    reason: str = ""

    @property
    def duration_hours(self) -> float:
        return (self.end_utc - self.start_utc).total_seconds() / 3600.0

    def as_dict(self) -> dict[str, object]:
        return {
            "body": self.body,
            "state": self.state,
            "start_utc": self.start_utc.isoformat(),
            "end_utc": self.end_utc.isoformat(),
            "duration_hours": round(self.duration_hours, 4),
            "start_refined": self.start_refined,
            "end_refined": self.end_refined,
            "reason": self.reason,
        }


def refine_crossing_time(
    t0: datetime,
    t1: datetime,
    margin0: float,
    margin1: float,
    level: float = 0.0,
) -> datetime | None:
    """``alt − ufuk`` verilen seviyeyi geçiyorsa geçiş zamanını enterpolasyonla bulur.

    ``level = 0`` ufuk çizgisini, ``level = ±margin_deg`` geçiş bandının
    kenarını verir. Marjlar seviyeyi kesmiyorsa ``None`` döner.
    """
    above0 = margin0 - level
    above1 = margin1 - level
    if above0 == 0.0 and above1 == 0.0:
        return None
    if (above0 > 0.0) == (above1 > 0.0):
        return None
    fraction = -above0 / (above1 - above0)
    seconds = (t1 - t0).total_seconds() * fraction
    return t0 + timedelta(seconds=seconds)


def _boundary_level(state_a: str, state_b: str, margin_deg: float) -> float:
    """İki komşu durum arasındaki sınırın hangi marj seviyesinde olduğunu seçer."""
    if state_a in DEFINITE_STATES and state_b in DEFINITE_STATES:
        return 0.0
    definite = state_a if state_a in DEFINITE_STATES else state_b
    return margin_deg if definite == VISIBLE else -margin_deg


def _body_series(
    results: list[SampleResult], body: str
) -> tuple[list[str], list[float | None], list[str]]:
    if body == BODY_SUN:
        return (
            [r.sun.state for r in results],
            [r.sun.margin_deg for r in results],
            [r.sun.reason for r in results],
        )
    if body == BODY_EARTH:
        return (
            [r.earth.state for r in results],
            [r.earth.margin_deg for r in results],
            [r.earth.reason for r in results],
        )
    if body == BODY_JOINT:
        return (
            [r.joint_state for r in results],
            [r.joint_margin_deg for r in results],
            [r.joint_reason for r in results],
        )
    raise ValueError(f"Bilinmeyen gövde: {body}. Seçenekler: {', '.join(BODIES)}")


def build_windows(
    results: list[SampleResult],
    body: str = BODY_JOINT,
    config: VisibilityConfig | None = None,
) -> list[Window]:
    """Durum serisini kesintisiz pencerelere böler ve sınırları inceltir."""
    if not results:
        raise ValueError("Sonuç listesi boş.")
    config = config or VisibilityConfig()
    states, margins, reasons = _body_series(results, body)
    times = [r.sample.timestamp_utc for r in results]

    runs: list[tuple[str, int, int]] = []
    start = 0
    for index in range(1, len(states)):
        if states[index] != states[start]:
            runs.append((states[start], start, index - 1))
            start = index
    runs.append((states[start], start, len(states) - 1))

    boundaries: list[tuple[datetime, bool]] = []
    for run_index in range(len(runs) - 1):
        _state, _s, end_index = runs[run_index]
        next_index = end_index + 1
        refined_time: datetime | None = None
        refined = False
        if config.refine_boundaries:
            m0, m1 = margins[end_index], margins[next_index]
            if m0 is not None and m1 is not None:
                level = _boundary_level(
                    states[end_index], states[next_index], config.margin_deg
                )
                refined_time = refine_crossing_time(
                    times[end_index], times[next_index], m0, m1, level
                )
                refined = refined_time is not None
        boundaries.append((refined_time or times[next_index], refined))

    windows: list[Window] = []
    for run_index, (state, first_index, _last_index) in enumerate(runs):
        start_time = times[0] if run_index == 0 else boundaries[run_index - 1][0]
        start_refined = False if run_index == 0 else boundaries[run_index - 1][1]
        if run_index == len(runs) - 1:
            end_time, end_refined = times[-1], False
        else:
            end_time, end_refined = boundaries[run_index]
        windows.append(
            Window(
                body=body,
                state=state,
                start_utc=start_time,
                end_utc=end_time,
                start_refined=start_refined,
                end_refined=end_refined,
                reason=reasons[first_index],
            )
        )
    return windows


def summarize_windows(
    windows: list[Window], span_hours: float | None = None
) -> dict[str, object]:
    """Durum bazlı toplam süre ve görünürlük istatistikleri."""
    totals = {state: 0.0 for state in (VISIBLE, BLOCKED, UNCERTAIN)}
    for window in windows:
        totals[window.state] = totals.get(window.state, 0.0) + window.duration_hours

    visible_windows = [w for w in windows if w.state == VISIBLE]
    longest = max(visible_windows, key=lambda w: w.duration_hours, default=None)
    total_hours = span_hours if span_hours is not None else sum(totals.values())

    return {
        "window_count": len(windows),
        "total_hours": round(total_hours, 4),
        "state_hours": {state: round(value, 4) for state, value in totals.items()},
        "visible_fraction": (
            round(totals[VISIBLE] / total_hours, 6) if total_hours > 0 else None
        ),
        "longest_visible_hours": (
            None if longest is None else round(longest.duration_hours, 4)
        ),
        "longest_visible_start_utc": (
            None if longest is None else longest.start_utc.isoformat()
        ),
        "refined_boundaries": sum(
            1 for w in windows if w.start_refined or w.end_refined
        ),
    }
