"""Zaman ızgarası, görünürlük pencereleri ve karşılaştırma metrikleri (K3)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from luna_sight.visibility.classification import BLOCKED, UNCERTAIN, VISIBLE

DEFAULT_STEP_MINUTES = 5.0
DEFAULT_ANALYSIS_HOURS = 168.0

#: Karşılaştırma tablosunun sütun sırası.
SUMMARY_COLUMNS = (
    "total_rows",
    "usable_rows",
    "sun_visible_hours",
    "earth_visible_hours",
    "joint_visible_hours",
    "joint_blocked_hours",
    "joint_uncertain_hours",
    "visible_fraction",
    "visible_window_count",
    "longest_visible_hours",
    "first_visible_utc",
    "last_visible_utc",
)


@dataclass(frozen=True)
class VisibilityWindow:
    """Kesintisiz görünürlük aralığı."""

    state: str
    start_utc: pd.Timestamp
    end_utc: pd.Timestamp
    duration_hours: float
    sample_count: int


def analysis_timestamps(
    start_utc,
    hours: float = DEFAULT_ANALYSIS_HOURS,
    step_minutes: float = DEFAULT_STEP_MINUTES,
) -> pd.DatetimeIndex:
    """UTC analiz ızgarasını üretir (varsayılan 168 saat, 5 dakika).

    Her örnek ``[t, t + step)`` aralığını temsil eder. Bu yüzden ``hours=24``
    ve ``step_minutes=5`` için 288 örnek döner; kapanış sınırı (24:00) ayrı bir
    örnek olarak eklenmez. Böylece örnek sayısı x adım, tam olarak ``hours``
    kadar süre eder.
    """
    step = float(step_minutes)
    if not math.isfinite(step) or step <= 0:
        raise ValueError("step_minutes pozitif olmalı")

    start = pd.Timestamp(start_utc)
    if start is pd.NaT:
        raise ValueError("start_utc geçerli bir zaman damgası olmalı")
    if start.tzinfo is None:
        raise ValueError("start_utc saat dilimi içermeli (UTC)")
    start = start.tz_convert("UTC")

    span = float(hours)
    if not math.isfinite(span) or span < 0:
        raise ValueError("hours negatif olamaz")

    steps = span * 60.0 / step
    if not math.isclose(steps, round(steps), rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("hours, step_minutes'ın tam katı olmalı")

    count = int(round(steps))
    if count == 0:
        raise ValueError("hours en az step_minutes kadar olmalı")

    return pd.date_range(
        start=start,
        periods=count,
        freq=pd.Timedelta(minutes=step),
    )


def _step_hours(timestamps: pd.DatetimeIndex, step_minutes: float | None) -> float:
    if len(timestamps) > 1:
        deltas = pd.Series(timestamps).diff().dropna()
        positive = deltas[deltas > pd.Timedelta(0)]
        if len(positive):
            return float(positive.median() / pd.Timedelta(hours=1))
    fallback = DEFAULT_STEP_MINUTES if step_minutes is None else step_minutes
    return float(fallback) / 60.0


def visibility_windows(
    states,
    timestamps,
    *,
    state: str = VISIBLE,
    step_minutes: float | None = None,
) -> list[VisibilityWindow]:
    """Belirli bir durumun kesintisiz aralıklarını döndürür."""
    ts = pd.DatetimeIndex(timestamps)
    values = pd.Series(states).reset_index(drop=True)
    if len(ts) != len(values):
        raise ValueError("states ve timestamps aynı uzunlukta olmalı")
    if len(ts) == 0:
        return []

    step = _step_hours(ts, step_minutes)
    flags = (values.to_numpy(dtype=object) == state).tolist()

    windows: list[VisibilityWindow] = []
    start_index: int | None = None
    for index, flag in enumerate(flags):
        if flag and start_index is None:
            start_index = index
        elif not flag and start_index is not None:
            windows.append(_make_window(ts, start_index, index - 1, step, state))
            start_index = None
    if start_index is not None:
        windows.append(_make_window(ts, start_index, len(flags) - 1, step, state))
    return windows


def _make_window(
    timestamps: pd.DatetimeIndex,
    start: int,
    end: int,
    step_hours: float,
    state: str,
) -> VisibilityWindow:
    span = float((timestamps[end] - timestamps[start]) / pd.Timedelta(hours=1))
    return VisibilityWindow(
        state=state,
        start_utc=timestamps[start],
        end_utc=timestamps[end],
        duration_hours=span + step_hours,
        sample_count=end - start + 1,
    )


def summarize(frame: pd.DataFrame, *, step_minutes: float | None = None) -> pd.DataFrame:
    """Site başına görünürlük metriklerini üretir.

    ``partial`` ve ``missing`` kalite bayraklı satırlar süre hesabına katılmaz;
    bu satırlar görünürlük pencerelerini de böler.
    """
    required = (
        "site_id",
        "timestamp_utc",
        "sun_visible",
        "earth_visible",
        "joint_visible",
        "quality_flag",
    )
    missing_columns = [name for name in required if name not in frame.columns]
    if missing_columns:
        raise ValueError("eksik sütun(lar): " + ", ".join(missing_columns))
    if frame.empty:
        raise ValueError("girdi çerçevesi boş olamaz")

    records = []
    for site_id, group in frame.groupby("site_id", sort=True):
        ordered = group.sort_values("timestamp_utc")
        timestamps = pd.DatetimeIndex(ordered["timestamp_utc"])
        step = _step_hours(timestamps, step_minutes)

        usable = ~ordered["quality_flag"].isin(("missing", "partial")).to_numpy()
        joint = ordered["joint_visible"].to_numpy(dtype=object)
        sun = ordered["sun_visible"].to_numpy(dtype=object)
        earth = ordered["earth_visible"].to_numpy(dtype=object)

        usable_rows = int(usable.sum())
        counts = {
            state: int(np.count_nonzero(usable & (joint == state)))
            for state in (VISIBLE, BLOCKED, UNCERTAIN)
        }
        effective = pd.Series(
            np.where(usable, joint, "excluded"),
            index=ordered.index,
        )
        windows = visibility_windows(
            effective, timestamps, state=VISIBLE, step_minutes=step_minutes
        )

        visible_hours = counts[VISIBLE] * step
        records.append(
            {
                "site_id": site_id,
                "total_rows": int(len(ordered)),
                "usable_rows": usable_rows,
                "sun_visible_hours": float(np.count_nonzero(usable & (sun == VISIBLE))) * step,
                "earth_visible_hours": float(np.count_nonzero(usable & (earth == VISIBLE))) * step,
                "joint_visible_hours": visible_hours,
                "joint_blocked_hours": counts[BLOCKED] * step,
                "joint_uncertain_hours": counts[UNCERTAIN] * step,
                "visible_fraction": (
                    visible_hours / (usable_rows * step) if usable_rows else float("nan")
                ),
                "visible_window_count": len(windows),
                "longest_visible_hours": max(
                    (window.duration_hours for window in windows), default=0.0
                ),
                "first_visible_utc": windows[0].start_utc if windows else pd.NaT,
                "last_visible_utc": windows[-1].end_utc if windows else pd.NaT,
            }
        )

    return pd.DataFrame.from_records(records).set_index("site_id").loc[:, SUMMARY_COLUMNS]
