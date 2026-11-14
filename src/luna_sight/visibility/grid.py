"""UTC analiz ızgarası (K3).

Her örnek ``[t, t + step)`` aralığını temsil eder. Böylece örnek sayısı × adım
tam olarak ``hours`` kadar süre eder ve süre toplamları analiz penceresiyle
tutarlı kalır.
"""

from __future__ import annotations

import math

import pandas as pd

DEFAULT_STEP_MINUTES = 5.0
DEFAULT_ANALYSIS_HOURS = 168.0


def analysis_timestamps(
    start_utc,
    hours: float = DEFAULT_ANALYSIS_HOURS,
    step_minutes: float = DEFAULT_STEP_MINUTES,
) -> pd.DatetimeIndex:
    """UTC analiz ızgarasını üretir (varsayılan 168 saat, 5 dakika)."""
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

    return pd.date_range(start=start, periods=count, freq=pd.Timedelta(minutes=step))
