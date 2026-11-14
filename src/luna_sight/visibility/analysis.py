"""Duyarlılık analizi yardımcıları (K3).

``margin_deg`` ve ufuk profili yarıçapı birer **seçim**dir; görünürlük
sonucu bu seçimlere ne kadar duyarlıysa kullanıcıya o kadar belirsizlik
olarak yansıtılmalıdır. Bu modül, motor çıktısını durum bazlı süre/oran ve
pencere istatistikleriyle tek bir tablo satırına indirger.

Modül bilimsel bir model eklemez; yalnızca ``engine`` çıktısını özetler.
"""

from __future__ import annotations

from dataclasses import dataclass

from luna_sight.visibility.engine import (
    BODIES,
    SampleResult,
    build_windows,
    summarize_windows,
)
from luna_sight.visibility.states import STATES, VisibilityConfig


def span_hours(results: list[SampleResult]) -> float:
    """İlk ve son örnek arasındaki süre (saat)."""
    if not results:
        raise ValueError("Sonuç listesi boş.")
    delta = results[-1].sample.timestamp_utc - results[0].sample.timestamp_utc
    return delta.total_seconds() / 3600.0


@dataclass(frozen=True)
class BodyBreakdown:
    """Tek bir gövdenin durum dağılımı ve pencere özeti."""

    body: str
    total_hours: float
    state_hours: dict[str, float]
    state_fractions: dict[str, float | None]
    window_count: int
    longest_visible_hours: float | None
    refined_boundaries: int

    def as_dict(self) -> dict[str, object]:
        row: dict[str, object] = {"body": self.body, "total_hours": self.total_hours}
        for state in STATES:
            row[f"{state}_hours"] = self.state_hours[state]
            fraction = self.state_fractions[state]
            row[f"{state}_fraction"] = (
                None if fraction is None else round(fraction, 6)
            )
        row["window_count"] = self.window_count
        row["longest_visible_hours"] = self.longest_visible_hours
        row["refined_boundaries"] = self.refined_boundaries
        return row


def breakdown(
    results: list[SampleResult],
    body: str,
    config: VisibilityConfig | None = None,
    span_hours_value: float | None = None,
) -> BodyBreakdown:
    """Bir gövde için durum oranlarını ve pencere istatistiklerini üretir."""
    if body not in BODIES:
        raise ValueError(f"Bilinmeyen gövde: {body}. Seçenekler: {', '.join(BODIES)}")
    config = config or VisibilityConfig()
    total = span_hours(results) if span_hours_value is None else span_hours_value
    stats = summarize_windows(build_windows(results, body, config), span_hours=total)

    state_hours = {state: float(stats["state_hours"][state]) for state in STATES}
    state_fractions: dict[str, float | None] = {}
    for state in STATES:
        if total > 0.0:
            state_fractions[state] = state_hours[state] / total
        else:
            state_fractions[state] = None

    return BodyBreakdown(
        body=body,
        total_hours=round(total, 4),
        state_hours={state: round(value, 4) for state, value in state_hours.items()},
        state_fractions=state_fractions,
        window_count=int(stats["window_count"]),
        longest_visible_hours=stats["longest_visible_hours"],
        refined_boundaries=int(stats["refined_boundaries"]),
    )


def sensitivity_rows(
    results: list[SampleResult],
    config: VisibilityConfig | None = None,
    *,
    site_id: str = "",
    profile: str = "",
    radius_m: int | None = None,
    span_hours_value: float | None = None,
) -> list[dict[str, object]]:
    """Bir profil/marj çifti için üç gövdenin özet satırlarını üretir.

    Satırlar CSV'ye doğrudan yazılabilecek biçimdedir; ``body`` sütunu
    ``sun`` / ``earth`` / ``joint`` değerlerini alır.
    """
    config = config or VisibilityConfig()
    total = span_hours(results) if span_hours_value is None else span_hours_value
    rows: list[dict[str, object]] = []
    for body in BODIES:
        item = breakdown(results, body, config, span_hours_value=total)
        row: dict[str, object] = {
            "site_id": site_id,
            "profile": profile,
            "radius_m": radius_m,
            "margin_deg": config.margin_deg,
        }
        row.update(item.as_dict())
        rows.append(row)
    return rows


def joint_totals(rows: list[dict[str, object]]) -> dict[str, object]:
    """``sensitivity_rows`` çıktısından ortak (``joint``) satırı seçer."""
    for row in rows:
        if row.get("body") == "joint":
            return row
    raise ValueError("Satırlarda 'joint' gövdesi yok.")


def margin_shift(
    baseline: dict[str, object], candidate: dict[str, object]
) -> dict[str, float | None]:
    """İki ortak satır arasındaki görünürlük farkını (yüzde puan) verir."""
    base = baseline.get("visible_fraction")
    cand = candidate.get("visible_fraction")
    if base is None or cand is None:
        return {"visible_fraction_delta": None, "longest_visible_hours_delta": None}
    base_longest = baseline.get("longest_visible_hours")
    cand_longest = candidate.get("longest_visible_hours")
    return {
        "visible_fraction_delta": round(float(cand) - float(base), 6),
        "longest_visible_hours_delta": (
            None
            if base_longest is None or cand_longest is None
            else round(float(cand_longest) - float(base_longest), 4)
        ),
    }


__all__ = [
    "BodyBreakdown",
    "breakdown",
    "joint_totals",
    "margin_shift",
    "sensitivity_rows",
    "span_hours",
]
