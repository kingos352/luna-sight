"""
backend/flight_physics/penumbra_power.py
========================================
Güneş Diski Yarı-Gölge (Penumbra) ve Güç Modeli.

Gereksinim:
- Güneş diskinin 0.533° açısal çapı için dağ arkasında batarken görünen alan kesri:
  f_area in [0.0, 1.0]
- Limb darkening (kenar kararması) düzeltmesi ile watt cinsinden fotovoltaik güç çıktısı hesabı.

Ay Güney Kutbu'nda Güneş yüksekliği çok düşüktür (-1.5° ile +1.5°). Güneş diskini noktasal
kabul etmek (0 veya 1), saatler süren yarı-gölge (penumbra) evresini kaçırır ve güç
sistemlerinin (batarya boyutu ve şarj marjı) hatalı tasarlanmasına yol açar.
"""

from __future__ import annotations
import math
from typing import Any, Dict, Union
import numpy as np

from backend.config import SOLAR_CONSTANT_1AU

# Güneş Açısal Çapı ve Yarıçapı (Ay'dan bakıldığında 1 AU)
SOLAR_ANGULAR_DIAMETER_DEG: float = 0.533
SOLAR_ANGULAR_RADIUS_DEG: float = SOLAR_ANGULAR_DIAMETER_DEG / 2.0  # 0.2665°

# Standart Uzay Tipi Üç Eklemli (Triple-Junction GaInP/GaAs/Ge) Güneş Paneli
DEFAULT_PANEL_AREA_M2: float = 8.0       # m^2 (Artemis HLS / Lander sınıfı)
DEFAULT_CELL_EFFICIENCY: float = 0.30     # %30 verim
DEFAULT_LIMB_DARKENING_U: float = 0.60    # Güneş fotosferi doğrusal kenar kararması katsayısı


def compute_solar_disk_fraction(
    sun_elevation_deg: Union[float, np.ndarray],
    horizon_elevation_deg: Union[float, np.ndarray],
    apply_limb_darkening: bool = True,
    u_coeff: float = DEFAULT_LIMB_DARKENING_U,
) -> Union[float, np.ndarray]:
    """
    Güneş diskinin yerel dağ sırtı/ufuk arkasında batarken görünen alan kesrini f_area in [0.0, 1.0] hesaplar.

    Parametreler:
        sun_elevation_deg: Güneş merkezinin ufuk yükselme açısı (derece)
        horizon_elevation_deg: Yerel dağ/krater sırtı engel açısı (derece)
        apply_limb_darkening: Fotosferik kenar kararması düzeltmesi uygulansın mı
        u_coeff: Doğrusal kenar kararması katsayısı (varsayılan: 0.60)

    Dönüş:
        f_area in [0.0, 1.0]
    """
    s_el = np.asarray(sun_elevation_deg, dtype=np.float64)
    h_el = np.asarray(horizon_elevation_deg, dtype=np.float64)

    # Açısal fark (Güneş merkezi - Ufuk engeli)
    delta_deg = s_el - h_el
    r_deg = SOLAR_ANGULAR_RADIUS_DEG

    # Normalleştirilmiş disk konumu: y = delta / R_sun in [-1.0, 1.0]
    # y >= 1.0: Disk tamamen ufkun üstünde (Tam Aydınlık)
    # y <= -1.0: Disk tamamen ufkun altında (Tam Umbra/Gölge)
    y = np.clip(delta_deg / r_deg, -1.0, 1.0)

    # 1. Geometrik Dairesel Dilim Alan Kesri
    # f_geom = (1/pi) * [arccos(-y) + y * sqrt(1 - y^2)]
    sqrt_term = np.sqrt(np.maximum(0.0, 1.0 - y**2))
    f_geom = (np.arccos(-y) + y * sqrt_term) / math.pi
    f_geom = np.clip(f_geom, 0.0, 1.0)

    if not apply_limb_darkening:
        return float(f_geom) if np.isscalar(sun_elevation_deg) and np.isscalar(horizon_elevation_deg) else f_geom

    # 2. Limb Darkening (Kenar Kararması) Düzeltmesi
    # I(mu) = I0 * (1 - u * (1 - mu)), mu = cos(theta) = sqrt(1 - rho^2)
    # Disk merkezi kenarlardan daha parlaktır.
    # Düzeltilmiş analitik 3. derece kuadratik düzeltme:
    # f_limb(y) = f_geom(y) + u * correction(y)
    # y=0'da f=0.5, y=-1'de 0, y=1'de 1.
    limb_correction = (u_coeff / 6.0) * (y - y**3) * (4.0 / math.pi)
    f_limb = np.clip(f_geom + limb_correction, 0.0, 1.0)

    return float(f_limb) if np.isscalar(sun_elevation_deg) and np.isscalar(horizon_elevation_deg) else f_limb


def compute_penumbra_power(
    sun_elevation_deg: float,
    horizon_elevation_deg: float,
    panel_area_m2: float = DEFAULT_PANEL_AREA_M2,
    cell_efficiency: float = DEFAULT_CELL_EFFICIENCY,
    incidence_angle_cos: float = 1.0,
    apply_limb_darkening: bool = True,
    solar_constant: float = SOLAR_CONSTANT_1AU,
) -> Dict[str, Any]:
    """
    Yarı-gölge (penumbra) ve kenar kararması etkilerini içerecek şekilde
    anlık fotovoltaik güç çıktısını (Watt) hesaplar.

    Parametreler:
        sun_elevation_deg: Güneş merkez açısı (derece)
        horizon_elevation_deg: Ufuk sırtı açısı (derece)
        panel_area_m2: Güneş paneli efektif alanı (m^2)
        cell_efficiency: Fotovoltaik hücre verimi (0.0 - 1.0)
        incidence_angle_cos: Güneş ışınının panele geliş açısı kosinüsü cos(i)
        apply_limb_darkening: Kenar kararması uygulansın mı
        solar_constant: 1 AU Güneş akısı (W/m^2, varsayılan: 1361.0)

    Dönüş:
        Dict: Güç çıktısı (W), görünürlük yüzdesi, gölge durumu ve ışınım detayları
    """
    f_area = compute_solar_disk_fraction(
        sun_elevation_deg=sun_elevation_deg,
        horizon_elevation_deg=horizon_elevation_deg,
        apply_limb_darkening=apply_limb_darkening,
    )
    f_area_scalar = float(f_area)

    cos_i = max(0.0, float(incidence_angle_cos))
    effective_flux_wm2 = solar_constant * f_area_scalar * cos_i
    power_watts = panel_area_m2 * cell_efficiency * effective_flux_wm2

    # Durum sınıflandırması
    if f_area_scalar >= 0.999:
        eclipse_state = "FULL_SUNLIGHT"
    elif f_area_scalar <= 0.001:
        eclipse_state = "TOTAL_UMBRA"
    else:
        eclipse_state = "PENUMBRA_GRAZING"

    return {
        "sun_elevation_deg": sun_elevation_deg,
        "horizon_elevation_deg": horizon_elevation_deg,
        "visible_disk_fraction": round(f_area_scalar, 4),
        "visible_disk_percent": round(f_area_scalar * 100.0, 2),
        "eclipse_state": eclipse_state,
        "effective_flux_wm2": round(effective_flux_wm2, 2),
        "power_watts": round(power_watts, 2),
        "panel_area_m2": panel_area_m2,
        "cell_efficiency": cell_efficiency,
        "incidence_cosine": round(cos_i, 4),
        "applied_limb_darkening": apply_limb_darkening,
    }
