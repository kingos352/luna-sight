"""
backend/flight_physics/boulder_hazard.py
========================================
Alt-Piksel Fraktal Kayaç Tehlike Dağılımı (BHI - Boulder Hazard Index).

Gereksinim:
- 12 m^2 iniş takımı bacak açıklığı (footprint) için N(D) = k * D^(-gamma)
  güç yasasıyla alt-piksel kayaç çarpma riski hesabı:
  compute_boulder_hazard_probability(slope, crater_dist)

Gezegen Bilimi Modeli (Golombek & Rapp, NASA Artemis / Surveyor Standartları):
- Yüzeydeki kayaç kümülatif boyut-frekans dağılımı (CSFD):
    N(D) = k * D^(-gamma)  [m^-2 başına çapı >= D olan kayaç sayısı]
- Tipik gamma üssü: 2.70 (2.4 - 3.2 aralığında)
- k katsayısı (kayaç yoğunluğu):
  * Eğim arttıkça regolit kayması ana kayayı açığa çıkarır (k artar).
  * Krater kenarlarına yaklaştıkça çarpışma fırlatığı (ejecta) kayaç yoğunluğu katlanarak artar.
- 12 m^2 bacak açıklığı alanında kritik yükseklik D_crit >= 0.35 m (35 cm gövde/motor altı açıklığı)
- Poisson Çarpışma Olasılığı:
    lambda = A_footprint * N(D_crit)
    P(carpisma >= 1) = 1 - exp(-lambda)
"""

from __future__ import annotations
import math
from typing import Any, Dict, Union
import numpy as np

DEFAULT_FOOTPRINT_AREA_M2: float = 12.0  # Artemis HLS / İniş aracı bacak açıklığı
DEFAULT_CRITICAL_DIAMETER_M: float = 0.35  # Kritik engel kayaç boyutu (35 cm)
DEFAULT_FRACTAL_GAMMA: float = 2.70  # Fraktal güç yasası katsayısı
BASE_K_COEFF: float = 0.0008  # Düz Ay regoliti için taban yoğunluk katsayısı (Golombek 1997)


def calculate_k_coefficient(
    slope_deg: Union[float, np.ndarray],
    crater_dist_m: Union[float, np.ndarray],
    base_k: float = BASE_K_COEFF,
) -> Union[float, np.ndarray]:
    """
    Yerel eğim (derece) ve krater kenarına olan mesafeye (metre) bağlı olarak
    kayaç yoğunluk faktörü k'yı hesaplar.
    """
    slope = np.asarray(slope_deg, dtype=np.float64)
    dist = np.asarray(crater_dist_m, dtype=np.float64)

    # 1. Eğim faktörü: Eğim arttıkça dik yamaçlarda kayaç oranı üstel artar
    # 0° -> 1.0, 15° -> ~2.7, 30° -> ~7.4
    slope_factor = np.exp(np.clip(slope / 15.0, 0.0, 3.0))

    # 2. Krater yakınlığı faktörü: Krater kenarına (<500 m) yaklaştıkça ejecta blanket yoğunluğu artar
    # dist = 0 m -> 4.0x, dist = 500 m -> 2.1x, dist > 2000 m -> 1.0x
    crater_factor = 1.0 + 3.0 * np.exp(-np.clip(dist / 600.0, 0.0, 10.0))

    k = base_k * slope_factor * crater_factor
    return k if not np.isscalar(slope_deg) and not np.isscalar(crater_dist_m) else (float(k) if np.ndim(k) == 0 else k)


def compute_boulder_hazard_probability(
    slope: Union[float, np.ndarray],
    crater_dist: Union[float, np.ndarray],
    footprint_area_m2: float = DEFAULT_FOOTPRINT_AREA_M2,
    d_crit_m: float = DEFAULT_CRITICAL_DIAMETER_M,
    gamma: float = DEFAULT_FRACTAL_GAMMA,
) -> Union[Dict[str, Any], np.ndarray]:
    """
    12 m^2 iniş takımı bacak açıklığı için güç yasasıyla alt-piksel kayaç çarpma riski hesabı.

    Parametreler:
        slope: Yüzey eğimi (derece)
        crater_dist: En yakın krater kenarı/merkezine mesafe (metre)
        footprint_area_m2: İniş takımı kapsama alanı (varsayılan: 12.0 m^2)
        d_crit_m: Kritik kayaç çapı (varsayılan: 0.35 m)
        gamma: Güç yasası üssü (varsayılan: 2.70)

    Dönüş:
        Skalar girişler için Dict (olasılık, beklenen kayaç sayısı, BHI skoru, tehlike sınıfı).
        Dizi (array) girişler için np.ndarray olasılık matrisi.
    """
    is_scalar = np.isscalar(slope) and np.isscalar(crater_dist)

    slope_arr = np.asarray(slope, dtype=np.float64)
    dist_arr = np.asarray(crater_dist, dtype=np.float64)

    k_arr = calculate_k_coefficient(slope_arr, dist_arr)

    # N(D_crit) = k * D_crit^(-gamma)
    n_crit = k_arr * (d_crit_m ** (-gamma))

    # Beklenen tehlikeli kayaç sayısı (Poisson lambda)
    lam = footprint_area_m2 * n_crit

    # P(çarpışma >= 1) = 1 - exp(-lambda)
    prob = 1.0 - np.exp(-lam)
    prob = np.clip(prob, 0.0, 1.0)

    if not is_scalar:
        return prob

    p_val = float(prob)
    lam_val = float(lam)
    bhi_score = min(100.0, p_val * 100.0)

    if bhi_score < 15.0:
        hazard_class = "NOMINAL_SAFE"
        risk_level = "DÜŞÜK"
    elif bhi_score < 40.0:
        hazard_class = "MODERATE_CAUTION"
        risk_level = "ORTA"
    elif bhi_score < 70.0:
        hazard_class = "HIGH_HAZARD"
        risk_level = "YÜKSEK"
    else:
        hazard_class = "CRITICAL_ABORT_ZONE"
        risk_level = "KRİTİK_TEHLİKE"

    return {
        "slope_deg": float(slope),
        "crater_dist_m": float(crater_dist),
        "footprint_area_m2": footprint_area_m2,
        "critical_diameter_m": d_crit_m,
        "gamma": gamma,
        "expected_hazardous_boulders": round(lam_val, 4),
        "collision_probability": round(p_val, 4),
        "bhi_score": round(bhi_score, 2),
        "hazard_class": hazard_class,
        "risk_level": risk_level,
    }


def compute_boulder_hazard_map(
    slope_map: np.ndarray,
    crater_dist_map: np.ndarray,
    footprint_area_m2: float = DEFAULT_FOOTPRINT_AREA_M2,
    d_crit_m: float = DEFAULT_CRITICAL_DIAMETER_M,
    gamma: float = DEFAULT_FRACTAL_GAMMA,
) -> np.ndarray:
    """Tüm iniş bölgesi DEM haritası için BHI (0-100) matrisi üretir."""
    prob_map = compute_boulder_hazard_probability(
        slope=slope_map,
        crater_dist=crater_dist_map,
        footprint_area_m2=footprint_area_m2,
        d_crit_m=d_crit_m,
        gamma=gamma,
    )
    bhi_map = np.clip(prob_map * 100.0, 0.0, 100.0)
    return bhi_map.astype(np.float32)
