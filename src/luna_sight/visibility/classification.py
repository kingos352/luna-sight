"""Görünürlük sınıflandırma kuralları (K3).

`docs/DATA_CONTRACT.md` üç durum tanımlar: ``visible``, ``blocked`` ve
``uncertain``. Bir gök cismi, yerel topoğrafik ufkun üzerindeyse görünür
sayılır. Ufuk ile yükseklik arasındaki fark model belirsizliği kadar bir bant
içinde kalıyorsa sonuç ``uncertain`` olur; eksik veri hiçbir zaman görünür
veya engelli sınıfına çevrilmez.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

VISIBLE = "visible"
BLOCKED = "blocked"
UNCERTAIN = "uncertain"
STATES = (VISIBLE, BLOCKED, UNCERTAIN)

#: Derece cinsinden varsayılan model belirsizliği.
DEFAULT_UNCERTAINTY_DEG = 0.5


def _validate_uncertainty(uncertainty_deg: float) -> float:
    value = float(uncertainty_deg)
    if not math.isfinite(value) or value < 0:
        raise ValueError("uncertainty_deg negatif veya sonlu olmayan bir değer olamaz")
    return value


def _is_missing(value) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def classify_visibility(
    altitude_deg,
    horizon_deg,
    uncertainty_deg: float = DEFAULT_UNCERTAINTY_DEG,
) -> str:
    """Tek bir yükseklik/ufuk çiftini sınıflandırır.

    ``visible``: yükseklik, ufkun belirsizlik bandından yüksek.
    ``blocked``: yükseklik, ufkun belirsizlik bandından düşük.
    ``uncertain``: bant içinde ya da girdilerden biri eksik.
    """
    band = _validate_uncertainty(uncertainty_deg)
    if _is_missing(altitude_deg) or _is_missing(horizon_deg):
        return UNCERTAIN

    margin = float(altitude_deg) - float(horizon_deg)
    if margin > band:
        return VISIBLE
    if margin < -band:
        return BLOCKED
    return UNCERTAIN


def classify_states(
    altitude_deg,
    horizon_deg,
    uncertainty_deg: float = DEFAULT_UNCERTAINTY_DEG,
) -> pd.Series:
    """``classify_visibility`` kuralının vektörel sürümü."""
    band = _validate_uncertainty(uncertainty_deg)
    altitude = pd.to_numeric(pd.Series(altitude_deg), errors="coerce")
    horizon = pd.to_numeric(pd.Series(horizon_deg), errors="coerce")
    if len(altitude) != len(horizon):
        raise ValueError("altitude_deg ve horizon_deg aynı uzunlukta olmalı")

    margin = altitude.to_numpy(dtype="float64") - horizon.to_numpy(dtype="float64")
    result = np.full(len(margin), UNCERTAIN, dtype=object)
    known = ~np.isnan(margin)
    result[known & (margin > band)] = VISIBLE
    result[known & (margin < -band)] = BLOCKED
    return pd.Series(result, index=altitude.index, dtype="object", name="state")


def combine_states(first, second) -> pd.Series:
    """Güneş ve Dünya durumlarını ortak görünürlüğe indirger.

    Ortak görünürlük yalnızca iki cisim de görünürse ``visible`` olur. Herhangi
    biri kesin olarak engelliyse sonuç ``blocked``, aksi halde ``uncertain``.
    """
    left = pd.Series(first, dtype="object")
    right = pd.Series(second, dtype="object")
    if len(left) != len(right):
        raise ValueError("first ve second aynı uzunlukta olmalı")

    for series in (left, right):
        unknown = set(series.dropna().unique()) - set(STATES)
        if unknown:
            raise ValueError(f"geçersiz durum değeri: {sorted(unknown)}")

    left_values = left.to_numpy(dtype=object)
    right_values = right.to_numpy(dtype=object)
    both_visible = (left_values == VISIBLE) & (right_values == VISIBLE)
    any_blocked = (left_values == BLOCKED) | (right_values == BLOCKED)

    result = np.full(len(left_values), UNCERTAIN, dtype=object)
    result[both_visible] = VISIBLE
    result[~both_visible & any_blocked] = BLOCKED
    return pd.Series(result, index=left.index, dtype="object", name="joint_state")
