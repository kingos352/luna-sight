"""
backend/flight_physics/curvature.py
===================================
Ay Küresel Eğrilik Düzeltmesi Modülü.

Ay yüzeyinde ufuk ray-casting ve görüş hattı (LoS / DTE / Solar) taramalarında
küresel eğrilik etkisi ihmal edilirse, ufuk açıları hatalı yüksek hesaplanır.

Ay yarıçapı R_Moon = 1,737,400.0 m.
r mesafesindeki arazinin küresel düşüş formülü:
    z_eff(r) = z(r) - (r^2) / (2 * R_Moon)

Örnekler:
    r = 10 km  -> z_drop ~ 28.78 m
    r = 30 km  -> z_drop ~ 258.98 m
    r = 50 km  -> z_drop ~ 719.46 m
"""

from __future__ import annotations
import math
from typing import Union
import numpy as np

from backend.config import LUNAR_MEAN_RADIUS_M

LUNAR_RADIUS_M: float = LUNAR_MEAN_RADIUS_M  # 1_737_400.0 m


def calculate_curvature_drop(
    distance_m: Union[float, np.ndarray],
    radius_m: float = LUNAR_RADIUS_M,
) -> Union[float, np.ndarray]:
    """
    Belirtilen mesafe için Ay küresel yüzey düşüşünü (m) hesaplar:
    z_drop = r^2 / (2 * R_Moon)
    """
    if radius_m <= 0:
        raise ValueError("Ay yarıçapı pozitif bir değer olmalıdır.")
    return (np.asarray(distance_m, dtype=np.float64) ** 2) / (2.0 * radius_m)


def apply_curvature_correction(
    z_elevation: Union[float, np.ndarray],
    distance_m: Union[float, np.ndarray],
    radius_m: float = LUNAR_RADIUS_M,
) -> Union[float, np.ndarray]:
    """
    Topografik kota küresellik düşüş düzeltmesini uygular:
    z_eff(r) = z(r) - (r^2) / (2 * R_Moon)
    """
    drop = calculate_curvature_drop(distance_m, radius_m=radius_m)
    return np.asarray(z_elevation, dtype=np.float64) - drop


def calculate_horizon_distance(
    observer_height_m: float,
    radius_m: float = LUNAR_RADIUS_M,
) -> float:
    """
    Ay küresinde verilen gözlemci yüksekliği (h) için geometrik ufuk mesafesini (m) hesaplar:
    d = sqrt(2 * R * h + h^2)
    """
    if observer_height_m < 0:
        return 0.0
    return math.sqrt(2.0 * radius_m * observer_height_m + observer_height_m**2)


def calculate_effective_horizon_angle(
    z_observer: float,
    z_target: float,
    distance_m: float,
    apply_curvature: bool = True,
    radius_m: float = LUNAR_RADIUS_M,
) -> float:
    """
    Gözlemci ile hedef nokta arasındaki ufuk yükselme açısını (derece)
    küresel eğrilik düzeltmesi ile veya düzlem varsayımıyla hesaplar.
    """
    if distance_m <= 0:
        return 0.0

    if apply_curvature:
        z_eff = apply_curvature_correction(z_target, distance_m, radius_m=radius_m)
    else:
        z_eff = z_target

    tan_alpha = (z_eff - z_observer) / distance_m
    angle_rad = math.atan(max(0.0, float(tan_alpha)))
    return math.degrees(angle_rad)
