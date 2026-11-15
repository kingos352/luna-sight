"""
backend/flight_physics/knife_edge_diffraction.py
================================================
Lunar Knife-Edge Diffraction Engine (Ay Dağ Sırtı Radyo Kırınım Motoru).

Gereksinim:
- Fresnel kırınım parametresi v ve Lee/ITU-R P.526 bıçak sırtı zayıflama fonksiyonu J(v) dB.
- S-Band (2.2 GHz) için doğrudan görüş hattı (LoS) 0.3° - 0.5° dağ arkasında kalsa dahi
  kırınımlı acil durum telsiz sinyal marjı hesabı.

Fiziksel İlke:
Ay atmosferden ve troposferik saçılmadan yoksundur; ancak krater sırtları ve dağ tepeleri
keskin dielektrik "bıçak sırtı" (knife-edge) engeller gibi davranarak RF dalgalarını
Huygens-Fresnel ilkesi uyarınca gölge bölgesine kırar.
NASA DSN yer istasyonları (70m çanak) veya Gateway ile ultra-düşük veri hızlı (10-100 bps)
acil durum telemetrisi, doğrudan hat kapalıyken bile kırınım sayesinde iletişim kurabilir.
"""

from __future__ import annotations
import math
from typing import Any, Dict, Union
import numpy as np

from backend.config import SPEED_OF_LIGHT_KM_S

C_LIGHT_M_S: float = SPEED_OF_LIGHT_KM_S * 1000.0  # 299,792,458 m/s
S_BAND_FREQ_HZ: float = 2.2e9  # 2.2 GHz S-Band Acil Durum / TT&C
DEFAULT_LUNAR_EARTH_DIST_M: float = 384_400_000.0  # ~384,400 km


def compute_wavelength(frequency_hz: float = S_BAND_FREQ_HZ) -> float:
    """Frekansa bağlı dalga boyunu (metre) hesaplar: lambda = c / f."""
    if frequency_hz <= 0:
        raise ValueError("Frekans pozitif olmalıdır.")
    return C_LIGHT_M_S / frequency_hz


def compute_fresnel_parameter(
    obstruction_angle_deg: Union[float, np.ndarray],
    distance_to_ridge_m: float = 5_000.0,
    distance_to_rx_m: float = DEFAULT_LUNAR_EARTH_DIST_M,
    frequency_hz: float = S_BAND_FREQ_HZ,
) -> Union[float, np.ndarray]:
    """
    Fresnel-Kirchhoff kırınım parametresi v'yi hesaplar.

    Parametreler:
        obstruction_angle_deg: Görüş hattının dağ sırtı arkasında kaldığı açı (derece)
                               Pozitif değer = Gölge bölgesi (engel hattı kesiyor).
                               Negatif değer = Açık hat (görüş hattı engelin üzerinde).
        distance_to_ridge_m: İniş aracı ile dağ sırtı arasındaki mesafe (metre, d1)
        distance_to_rx_m: Dağ sırtı ile alıcı (Dünya DSN / Gateway) arasındaki mesafe (d2)
        frequency_hz: Sinyal taşıyıcı frekansı (Hz)

    Dönüş:
        Boyutsuz Fresnel parametresi v
    """
    wavelength_m = compute_wavelength(frequency_hz)
    ang_rad = np.radians(np.asarray(obstruction_angle_deg, dtype=np.float64))

    # Engel penetrasyon yüksekliği: h = d1 * tan(theta)
    h_m = distance_to_ridge_m * np.tan(ang_rad)

    # v = h * sqrt((2 / lambda) * (1/d1 + 1/d2))
    geom_factor = (1.0 / distance_to_ridge_m) + (1.0 / distance_to_rx_m)
    v = h_m * np.sqrt((2.0 / wavelength_m) * geom_factor)

    return float(v) if np.isscalar(obstruction_angle_deg) else v


def compute_diffraction_loss_itu(v: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """
    ITU-R P.526-15 ve Lee knife-edge kırınım zayıflama fonksiyonu J(v) [dB].

    Formül:
        v <= -1.0 : J(v) = 0 dB (tam görüş hattı)
        v > -1.0  : J(v) = 6.9 + 20 * log10( sqrt((v - 0.1)^2 + 1) + v - 0.1 )
    """
    v_arr = np.asarray(v, dtype=np.float64)

    # Vektörel hesaplama
    # v <= -1.0 için kayıp 0.0 dB
    u = v_arr - 0.1
    arg = np.sqrt(u**2 + 1.0) + u
    arg = np.maximum(arg, 1e-12)

    loss_db = 6.9 + 20.0 * np.log10(arg)
    loss_db = np.where(v_arr <= -1.0, 0.0, loss_db)
    loss_db = np.maximum(0.0, loss_db)

    return float(loss_db) if np.isscalar(v) else loss_db


def compute_free_space_path_loss(
    distance_m: float,
    frequency_hz: float = S_BAND_FREQ_HZ,
) -> float:
    """Serbest uzay yol kaybı FSPL = 20*log10(4*pi*d / lambda) dB."""
    wavelength_m = compute_wavelength(frequency_hz)
    fspl = 20.0 * math.log10((4.0 * math.pi * distance_m) / wavelength_m)
    return float(fspl)


def evaluate_emergency_link_margin(
    obstruction_angle_deg: float,
    distance_to_ridge_m: float = 5_000.0,
    frequency_hz: float = S_BAND_FREQ_HZ,
    tx_power_w: float = 10.0,
    tx_antenna_gain_dbi: float = 3.0,
    rx_antenna_gain_dbi: float = 61.0,  # NASA DSN 70m çanak @ 2.2 GHz
    receiver_sensitivity_dbm: float = -168.0,  # 10 bps ultra-dar bant acil telemetri
    distance_to_rx_m: float = DEFAULT_LUNAR_EARTH_DIST_M,
) -> Dict[str, Any]:
    """
    Dağ sırtı arkasında kalan iniş aracı için bıçak sırtı kırınımlı
    acil durum bağlantı bütçesi ve bağlantı marjını (Link Margin dB) değerlendirir.

    Parametreler:
        obstruction_angle_deg: Görüş hattının dağ arkasında kalma açısı (örn: 0.3° - 0.5°)
        distance_to_ridge_m: Dağ sırtına mesafe (m)
        frequency_hz: Frekans (varsayılan: 2.2 GHz S-Band)
        tx_power_w: İletici gücü (W, varsayılan: 10 W)
        tx_antenna_gain_dbi: İletici anten kazancı (dBi)
        rx_antenna_gain_dbi: Alıcı DSN anten kazancı (dBi)
        receiver_sensitivity_dbm: Alıcı hassasiyeti (dBm)
        distance_to_rx_m: Dünya mesafesi (m)

    Dönüş:
        Dict: Fresnel parametresi, kırınım kaybı, alınan güç, marj ve bağlantı durumu
    """
    v = compute_fresnel_parameter(
        obstruction_angle_deg=obstruction_angle_deg,
        distance_to_ridge_m=distance_to_ridge_m,
        distance_to_rx_m=distance_to_rx_m,
        frequency_hz=frequency_hz,
    )
    v_scalar = float(v)

    diffraction_loss_db = float(compute_diffraction_loss_itu(v_scalar))
    fspl_db = compute_free_space_path_loss(distance_to_rx_m, frequency_hz=frequency_hz)

    # İletici gücü dBm cinsinden: P_dBm = 10 * log10(P_W * 1000)
    tx_power_dbm = 10.0 * math.log10(tx_power_w * 1000.0)

    # Alınan Güç (EIRP - FSPL - J(v) + G_rx)
    rx_power_dbm = tx_power_dbm + tx_antenna_gain_dbi - fspl_db - diffraction_loss_db + rx_antenna_gain_dbi

    # Bağlantı Marjı: Alınan Güç - Hassasiyet
    link_margin_db = rx_power_dbm - receiver_sensitivity_dbm

    link_closed = bool(link_margin_db >= 3.0)  # +3 dB asgari uzay iletişim güvenlik marjı

    return {
        "frequency_ghz": round(frequency_hz / 1e9, 3),
        "obstruction_angle_deg": obstruction_angle_deg,
        "distance_to_ridge_m": distance_to_ridge_m,
        "fresnel_parameter_v": round(v_scalar, 3),
        "diffraction_loss_db": round(diffraction_loss_db, 2),
        "free_space_loss_db": round(fspl_db, 2),
        "total_path_loss_db": round(fspl_db + diffraction_loss_db, 2),
        "tx_power_w": tx_power_w,
        "tx_power_dbm": round(tx_power_dbm, 2),
        "rx_power_dbm": round(rx_power_dbm, 2),
        "receiver_sensitivity_dbm": receiver_sensitivity_dbm,
        "link_margin_db": round(link_margin_db, 2),
        "link_closed": link_closed,
        "communication_mode": "DIFFRACTED_EMERGENCY_BEACON" if obstruction_angle_deg > 0 else "DIRECT_LINE_OF_SIGHT",
    }
