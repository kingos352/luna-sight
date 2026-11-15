"""Güneş diski (0.533°) yarı-gölge (penumbra) aydınlanma ve fotovoltaik güç modeli.

Ay Güney Kutbu'nda Güneş ufuk çizgisi boyunca çok düşük eğimle sıyırarak
hareket ettiğinden, Güneş'i noktasal kaynak (0 veya 1) saymak saatlerce
sürebilen kısmi gölgeleme (penumbra) evresini gizler ve üretilen enerji
(Wh) hesabını saptırır.

Bu modül:
    1. Güneş'in ``0.533°`` açısal çapı (``0.2665°`` yarıçap) için dağ/krater
       ufku üzerinde kalan disk alan kesrini hesaplar.
    2. Güneş fotosferinin kenar kararması (linear limb darkening:
       ``I(mu) = I_0 * [1 - u * (1 - mu)]``) için kapalı-form analitik akı
       integralini uygular.
    3. Noktasal vs. yarı-gölge güç profilleri ve kümülatif Watt-saat (Wh)
       enerji farkını döndürür.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

SOLAR_CONSTANT_1AU: float = 1361.0
"""1 AU mesafesinde Güneş sabiti (W/m^2)."""

SOLAR_ANGULAR_DIAMETER_DEG: float = 0.533
"""1 AU'dan görülen ortalama Güneş açısal çapı (derece)."""

SOLAR_ANGULAR_RADIUS_DEG: float = SOLAR_ANGULAR_DIAMETER_DEG / 2.0
"""1 AU'dan görülen ortalama Güneş açısal yarıçapı (0.2665°)."""

DEFAULT_LIMB_DARKENING_U: float = 0.60
"""Güneş fotosferi için standart doğrusal kenar kararması katsayısı."""


def compute_solar_disk_fraction(
    sun_center_el_deg: float | np.ndarray,
    horizon_el_deg: float | np.ndarray,
    limb_darkening: bool = True,
    u_coeff: float = DEFAULT_LIMB_DARKENING_U,
) -> float | np.ndarray:
    """Güneş diskinin yerel ufuk üzerinde kalan görünür akı/alan kesrini ``[0, 1]`` hesaplar.

    Parametreler:
        sun_center_el_deg: Güneş merkezinin yükseklik açısı (derece).
        horizon_el_deg: Aynı azimuttaki yerel topoğrafik ufuk açısı (derece).
        limb_darkening: Doğrusal fotosfer kenar kararması uygulansın mı.
        u_coeff: Kenar kararması katsayısı ``u in [0, 1]`` (varsayılan ``0.60``).

    Dönüş:
        Skaler girdiler için ``float``, dizi girdiler için ``np.ndarray``
        (tam gölge ``0.0``, tam güneş ``1.0``, eksik/``NaN`` girdi için ``NaN``).
    """
    if not 0.0 <= float(u_coeff) <= 1.0:
        raise ValueError(f"u_coeff [0, 1] aralığında olmalı; {u_coeff} verildi.")

    scalar_input = np.isscalar(sun_center_el_deg) and np.isscalar(horizon_el_deg)
    s_arr, h_arr = np.broadcast_arrays(
        np.asarray(sun_center_el_deg, dtype=np.float64),
        np.asarray(horizon_el_deg, dtype=np.float64),
    )

    valid = np.isfinite(s_arr) & np.isfinite(h_arr)
    delta_deg = np.where(valid, s_arr - h_arr, 0.0)
    y = np.clip(delta_deg / SOLAR_ANGULAR_RADIUS_DEG, -1.0, 1.0)

    sqrt_term = np.sqrt(np.maximum(0.0, 1.0 - y**2))
    f_geom = np.clip((np.arccos(-y) + y * sqrt_term) / math.pi, 0.0, 1.0)

    if limb_darkening and u_coeff > 0.0:
        # Doğrusal kenar kararması I(mu) = 1 - u * (1 - mu) için kesin kapalı-form integral:
        # f_limb(y) = [(1 - u) * f_geom(y) + (u / 2) * (2/3 + y - y^3 / 3)] / (1 - u / 3)
        u = float(u_coeff)
        limb_poly = (2.0 / 3.0) + y - (y**3) / 3.0
        frac = ((1.0 - u) * f_geom + (u / 2.0) * limb_poly) / (1.0 - u / 3.0)
        frac = np.clip(frac, 0.0, 1.0)
    else:
        frac = f_geom

    result = np.where(valid, frac, np.nan)
    if scalar_input:
        return float(result.item())
    return result


def compute_penumbra_power(
    sun_center_el_deg: float | np.ndarray,
    horizon_el_deg: float | np.ndarray,
    step_minutes: float = 5.0,
    max_power_w: float = 1000.0,
    *,
    limb_darkening: bool = True,
    u_coeff: float = DEFAULT_LIMB_DARKENING_U,
) -> dict[str, Any]:
    """Zaman serisi boyunca noktasal ve yarı-gölge (penumbra) güç/enerji çıktısını hesaplar.

    Parametreler:
        sun_center_el_deg: Güneş merkezi yükseklik açısı serisi (derece).
        horizon_el_deg: Yerel ufuk yüksekliği serisi veya skaler değer (derece).
        step_minutes: Örnekleme adımı (dakika, pozitif).
        max_power_w: Tam aydınlıkta nominal panel gücü (Watt, negatif olamaz).
        limb_darkening: Fotosfer kenar kararması düzeltmesi uygulansın mı.
        u_coeff: Doğrusal kenar kararması katsayısı.

    Dönüş:
        ``point_source_hours``, ``effective_penumbra_hours``,
        ``penumbra_transition_hours``, ``point_energy_wh``,
        ``penumbra_energy_wh``, ``energy_delta_wh`` özet metrikleri ile
        ``point_power_w``, ``penumbra_power_w`` ve ``disk_fraction`` dizileri.
    """
    if not math.isfinite(step_minutes) or step_minutes <= 0.0:
        raise ValueError(f"step_minutes pozitif olmalı; {step_minutes} verildi.")
    if not math.isfinite(max_power_w) or max_power_w < 0.0:
        raise ValueError(f"max_power_w negatif olamaz; {max_power_w} verildi.")

    s_raw = np.atleast_1d(np.asarray(sun_center_el_deg, dtype=np.float64)).ravel()
    h_raw = np.atleast_1d(np.asarray(horizon_el_deg, dtype=np.float64)).ravel()
    s_arr, h_arr = np.broadcast_arrays(s_raw, h_raw)
    if s_arr.size == 0:
        raise ValueError("Girdi serisi boş olamaz.")

    disk_fraction = np.asarray(
        compute_solar_disk_fraction(
            s_arr,
            h_arr,
            limb_darkening=limb_darkening,
            u_coeff=u_coeff,
        ),
        dtype=np.float64,
    )

    valid = np.isfinite(disk_fraction)
    point_mask = valid & (s_arr > h_arr)
    transition_mask = valid & (disk_fraction > 0.0) & (disk_fraction < 1.0)

    peak_w = float(max_power_w)
    point_power_w = np.where(point_mask, peak_w, 0.0)
    penumbra_power_w = np.where(valid, disk_fraction * peak_w, 0.0)

    dt_hours = float(step_minutes) / 60.0
    point_source_hours = float(np.sum(point_mask) * dt_hours)
    effective_penumbra_hours = float(np.sum(np.where(valid, disk_fraction, 0.0)) * dt_hours)
    penumbra_transition_hours = float(np.sum(transition_mask) * dt_hours)

    point_energy_wh = float(np.sum(point_power_w) * dt_hours)
    penumbra_energy_wh = float(np.sum(penumbra_power_w) * dt_hours)
    energy_delta_wh = penumbra_energy_wh - point_energy_wh

    return {
        "point_source_hours": round(point_source_hours, 4),
        "effective_penumbra_hours": round(effective_penumbra_hours, 4),
        "penumbra_transition_hours": round(penumbra_transition_hours, 4),
        "point_energy_wh": round(point_energy_wh, 4),
        "penumbra_energy_wh": round(penumbra_energy_wh, 4),
        "energy_delta_wh": round(energy_delta_wh, 4),
        "point_power_w": point_power_w,
        "penumbra_power_w": penumbra_power_w,
        "disk_fraction": disk_fraction,
    }


__all__ = [
    "DEFAULT_LIMB_DARKENING_U",
    "SOLAR_ANGULAR_DIAMETER_DEG",
    "SOLAR_ANGULAR_RADIUS_DEG",
    "SOLAR_CONSTANT_1AU",
    "compute_penumbra_power",
    "compute_solar_disk_fraction",
]
