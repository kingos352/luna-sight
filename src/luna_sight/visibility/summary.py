"""Görünürlük tablosundan site bazlı özet metrikler (K3).

Her örnek ``[t, t + step)`` aralığını temsil ettiği için süreler örnek
sayısı × adım süresi olarak hesaplanır; böylece özet ile analiz penceresi
tutarlı kalır.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from luna_sight.visibility.states import BLOCKED, UNCERTAIN, VISIBLE
from luna_sight.visibility.table import validate_table

SUMMARY_COLUMNS = (
    "samples",
    "step_minutes",
    "total_hours",
    "visible_hours",
    "blocked_hours",
    "uncertain_hours",
    "visible_fraction",
    "visible_window_count",
    "longest_visible_hours",
    "margin_deg",
)


def _step_hours(timestamps: pd.Series) -> float:
    if len(timestamps) < 2:
        return 0.0
    deltas = np.diff(np.sort(timestamps.to_numpy(dtype="datetime64[ns]")).astype("int64"))
    positive = deltas[deltas > 0]
    if positive.size == 0:
        return 0.0
    return float(np.median(positive)) / 3_600_000_000_000.0


def _run_stats(mask: pd.Series) -> tuple[int, int]:
    """True bloklarının sayısı ve en uzun blok uzunluğu (örnek sayısı)."""
    count = 0
    longest = 0
    current = 0
    for value in mask.to_numpy(dtype=bool):
        if value:
            current += 1
            longest = max(longest, current)
        elif current:
            count += 1
            current = 0
    if current:
        count += 1
    return count, longest


def _common_margin(frame: pd.DataFrame) -> float | None:
    values = {
        json.loads(text).get("margin_deg")
        for text in frame["parameters"].dropna().astype(str)
        if text.strip().startswith("{")
    }
    if len(values) == 1:
        value = values.pop()
        return None if value is None else float(value)
    return None


def summarize(frame: pd.DataFrame) -> pd.DataFrame:
    """Tabloyu ``site_id`` indeksli tek satırlık özet metriklerine indirger."""
    data = validate_table(frame)
    rows: list[dict[str, object]] = []

    for site_id, group in data.groupby("site_id", sort=True):
        group = group.sort_values("timestamp_utc")
        step_hours = _step_hours(group["timestamp_utc"])
        # Örnekler zaman içinde nokta; N örnek N-1 aralık eder. Motorun
        # pencereleri de ilk–son örnek arasını kapsadığı için aynı tanım
        # kullanılır.
        interval_count = max(len(group) - 1, 0)
        total_hours = step_hours * interval_count
        intervals = group.iloc[:interval_count] if interval_count else group.iloc[0:0]

        totals = {
            state: float((intervals["joint_visible"] == state).sum()) * step_hours
            for state in (VISIBLE, BLOCKED, UNCERTAIN)
        }
        window_count, longest_samples = _run_stats(intervals["joint_visible"] == VISIBLE)

        rows.append(
            {
                "site_id": str(site_id),
                "samples": int(len(group)),
                "step_minutes": round(step_hours * 60.0, 6),
                "total_hours": round(total_hours, 6),
                "visible_hours": round(totals[VISIBLE], 6),
                "blocked_hours": round(totals[BLOCKED], 6),
                "uncertain_hours": round(totals[UNCERTAIN], 6),
                "visible_fraction": (
                    round(totals[VISIBLE] / total_hours, 6) if total_hours > 0 else None
                ),
                "visible_window_count": int(window_count),
                "longest_visible_hours": round(longest_samples * step_hours, 6),
                "margin_deg": _common_margin(group),
            }
        )

    return pd.DataFrame(rows).set_index("site_id").loc[:, list(SUMMARY_COLUMNS)]


__all__ = ["SUMMARY_COLUMNS", "summarize"]
