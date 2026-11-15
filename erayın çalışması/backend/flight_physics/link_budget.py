"""
backend/flight_physics/link_budget.py
=====================================
Frekans Bağımlı Bağlantı Bütçesi ve NASA DSN Yer İstasyonu Modeli.

Gereksinim:
- S-Band (2.2 GHz), Ka-Band (26 GHz) ve 1550nm Optik Lazer (O2O) için
  NASA DSN (Madrid, Goldstone, Canberra) sinyal zayıflama ve marj hesabı.

NASA Deep Space Network (DSN) Yer İstasyonları:
1. Goldstone DSCC (Kaliforniya, ABD) - 35.426° K, 116.89° B
2. Madrid DSCC (İspanya)            - 40.430° K, 4.250° B
3. Canberra DSCC (Avustralya)       - 35.400° G, 148.980° D

Bant Karakteristikleri:
- S-Band (2.2 GHz)  : Yüksek güvenilirlik, düşük veri hızı (TT&C, acil durum)
- Ka-Band (26 GHz)  : Yüksek veri hızı (HD telemetri, canlı video downlink)
- O2O Optik Lazer (1550 nm): 100 Mbps - 1.2 Gbps ultra hızlı derin uzay lazer iletişimi
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Dict, List, Optional
import numpy as np

from backend.config import SPEED_OF_LIGHT_KM_S

C_LIGHT_M_S: float = SPEED_OF_LIGHT_KM_S * 1000.0  # 299,792,458 m/s
BOLTZMANN_K_DBW_HZ_K: float = -228.6  # 10*log10(1.380649e-23)
DEFAULT_LUNAR_EARTH_DIST_M: float = 384_400_000.0  # ~384,400 km


class DSNStation(str, Enum):
    GOLDSTONE = "GOLDSTONE"
    MADRID = "MADRID"
    CANBERRA = "CANBERRA"


class FrequencyBand(str, Enum):
    S_BAND = "S_BAND"          # 2.2 GHz
    KA_BAND = "KA_BAND"        # 26.0 GHz
    OPTICAL_O2O = "OPTICAL_O2O"  # 1550 nm Lazer


@dataclass(frozen=True)
class DSNStationInfo:
    name: str
    station_id: DSNStation
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    dish_diameter_m: float  # 34m veya 70m


DSN_STATIONS: Dict[DSNStation, DSNStationInfo] = {
    DSNStation.GOLDSTONE: DSNStationInfo(
        name="Goldstone Deep Space Communications Complex",
        station_id=DSNStation.GOLDSTONE,
        latitude_deg=35.426,
        longitude_deg=-116.890,
        altitude_m=1000.0,
        dish_diameter_m=70.0,
    ),
    DSNStation.MADRID: DSNStationInfo(
        name="Madrid Deep Space Communications Complex",
        station_id=DSNStation.MADRID,
        latitude_deg=40.430,
        longitude_deg=-4.250,
        altitude_m=780.0,
        dish_diameter_m=70.0,
    ),
    DSNStation.CANBERRA: DSNStationInfo(
        name="Canberra Deep Space Communication Complex",
        station_id=DSNStation.CANBERRA,
        latitude_deg=-35.400,
        longitude_deg=148.980,
        altitude_m=650.0,
        dish_diameter_m=70.0,
    ),
}


@dataclass(frozen=True)
class BandConfig:
    frequency_hz: float
    wavelength_m: float
    default_tx_power_w: float
    default_tx_gain_dbi: float
    default_rx_gain_dbi: float
    atmospheric_loss_db: float
    pointing_loss_db: float
    noise_temp_k: float
    default_data_rate_bps: float
    required_eb_n0_db: float


BAND_CONFIGS: Dict[FrequencyBand, BandConfig] = {
    FrequencyBand.S_BAND: BandConfig(
        frequency_hz=2.2e9,
        wavelength_m=C_LIGHT_M_S / 2.2e9,  # ~0.136 m
        default_tx_power_w=15.0,
        default_tx_gain_dbi=12.0,      # Orta kazançlı yönlü anten
        default_rx_gain_dbi=61.0,      # DSN 70m çanak @ 2.2 GHz
        atmospheric_loss_db=0.08,      # Temiz gökyüzü S-bant zayıflama
        pointing_loss_db=0.30,
        noise_temp_k=135.0,            # Sistem gürültü sıcaklığı
        default_data_rate_bps=64_000.0, # 64 kbps telemetri
        required_eb_n0_db=3.0,         # LDPC kodlama ile asgari Eb/N0
    ),
    FrequencyBand.KA_BAND: BandConfig(
        frequency_hz=26.0e9,
        wavelength_m=C_LIGHT_M_S / 26.0e9,  # ~0.0115 m (11.5 mm)
        default_tx_power_w=25.0,
        default_tx_gain_dbi=32.0,      # Yüksek kazançlı gimbal anten (0.5m)
        default_rx_gain_dbi=78.5,      # DSN 34m/70m Ka-Band çanağı
        atmospheric_loss_db=0.75,      # Atmosferik su buharı ve O2 kaybı
        pointing_loss_db=0.80,
        noise_temp_k=165.0,
        default_data_rate_bps=20_000_000.0,  # 20 Mbps HD Video Downlink
        required_eb_n0_db=3.5,
    ),
    FrequencyBand.OPTICAL_O2O: BandConfig(
        frequency_hz=C_LIGHT_M_S / 1550e-9,  # ~193.4 THz (1550 nm IR)
        wavelength_m=1550e-9,
        default_tx_power_w=5.0,        # 5 Watt darbe modülasyonlu fiber lazer
        default_tx_gain_dbi=108.0,     # 20 cm lazer optik teleskop
        default_rx_gain_dbi=124.0,     # 1 metrelik yer istasyonu optik alıcı teleskop
        atmospheric_loss_db=2.20,      # Atmosferik saçılma ve optik türbülans
        pointing_loss_db=1.50,         # Hassas mikro-radyan yönelim kaybı
        noise_temp_k=290.0,
        default_data_rate_bps=200_000_000.0,  # 200 Mbps Lazer Downlink
        required_eb_n0_db=4.5,
    ),
}


def compute_link_budget(
    station: DSNStation = DSNStation.GOLDSTONE,
    band: FrequencyBand = FrequencyBand.S_BAND,
    distance_m: float = DEFAULT_LUNAR_EARTH_DIST_M,
    tx_power_w: Optional[float] = None,
    data_rate_bps: Optional[float] = None,
    additional_obstacle_loss_db: float = 0.0,
) -> Dict[str, Any]:
    """
    Seçilen DSN istasyonu ve frekans bandı için eksiksiz uzay-yer bağlantı bütçesi (Link Budget) hesaplar.

    Parametreler:
        station: DSN İstasyonu (GOLDSTONE, MADRID, CANBERRA)
        band: Frekans Bandı (S_BAND, KA_BAND, OPTICAL_O2O)
        distance_m: Ay-Dünya mesafesi (metre)
        tx_power_w: İletici gücü (W, None ise bant varsayılanı)
        data_rate_bps: İletişim veri hızı (bps, None ise varsayılan)
        additional_obstacle_loss_db: Dağ kırınımı veya yerel engel kaybı (dB)

    Dönüş:
        Dict: EIRP, FSPL, alınan güç, Eb/N0, marj ve bağlantı yeterlilik durumu
    """
    cfg = BAND_CONFIGS[band]
    stn_info = DSN_STATIONS[station]

    p_tx_w = float(tx_power_w) if tx_power_w is not None else cfg.default_tx_power_w
    p_tx_dbw = 10.0 * math.log10(p_tx_w)
    r_bps = float(data_rate_bps) if data_rate_bps is not None else cfg.default_data_rate_bps

    # 1. EIRP (Eşdeğer İzotropik Işınım Gücü)
    eirp_dbw = p_tx_dbw + cfg.default_tx_gain_dbi

    # 2. Serbest Uzay Yol Kaybı (FSPL)
    fspl_db = 20.0 * math.log10((4.0 * math.pi * distance_m) / cfg.wavelength_m)

    # 3. Toplam Yol ve Çevre Kayıpları
    total_losses_db = (
        fspl_db
        + cfg.atmospheric_loss_db
        + cfg.pointing_loss_db
        + float(additional_obstacle_loss_db)
    )

    # 4. Alınan Güç (P_rx)
    rx_power_dbw = eirp_dbw - total_losses_db + cfg.default_rx_gain_dbi
    rx_power_dbm = rx_power_dbw + 30.0

    # 5. Gürültü Spektral Yoğunluğu (N0)
    # N0 = k_B * T_sys (dBW/Hz)
    n0_dbw_hz = BOLTZMANN_K_DBW_HZ_K + 10.0 * math.log10(cfg.noise_temp_k)

    # 6. Alınan Eb / N0
    # Eb/N0 = P_rx - N0 - 10*log10(R_bps)
    rate_db_hz = 10.0 * math.log10(r_bps)
    eb_n0_db = rx_power_dbw - n0_dbw_hz - rate_db_hz

    # 7. Bağlantı Güvenlik Marjı
    link_margin_db = eb_n0_db - cfg.required_eb_n0_db

    # NASA Derin Uzay Uçuş Standartları: >= +3.0 dB marj başarılı sayılır
    is_link_established = bool(link_margin_db >= 3.0)

    return {
        "station": station.value,
        "station_name": stn_info.name,
        "frequency_band": band.value,
        "frequency_hz": cfg.frequency_hz,
        "wavelength_m": cfg.wavelength_m,
        "tx_power_w": p_tx_w,
        "tx_power_dbw": round(p_tx_dbw, 2),
        "tx_antenna_gain_dbi": cfg.default_tx_gain_dbi,
        "eirp_dbw": round(eirp_dbw, 2),
        "distance_km": round(distance_m / 1000.0, 1),
        "free_space_loss_db": round(fspl_db, 2),
        "atmospheric_loss_db": cfg.atmospheric_loss_db,
        "pointing_loss_db": cfg.pointing_loss_db,
        "obstacle_diffraction_loss_db": round(float(additional_obstacle_loss_db), 2),
        "rx_antenna_gain_dbi": cfg.default_rx_gain_dbi,
        "rx_power_dbw": round(rx_power_dbw, 2),
        "rx_power_dbm": round(rx_power_dbm, 2),
        "noise_temp_k": cfg.noise_temp_k,
        "n0_dbw_hz": round(n0_dbw_hz, 2),
        "data_rate_bps": r_bps,
        "data_rate_display": f"{r_bps / 1e6:.2f} Mbps" if r_bps >= 1e6 else f"{r_bps / 1e3:.1f} kbps",
        "eb_n0_achieved_db": round(eb_n0_db, 2),
        "eb_n0_required_db": cfg.required_eb_n0_db,
        "link_margin_db": round(link_margin_db, 2),
        "link_established": is_link_established,
        "status": "OPERATIONAL_MARGIN" if link_margin_db >= 3.0 else ("DEGRADED" if link_margin_db >= 0.0 else "LINK_LOSS"),
    }
