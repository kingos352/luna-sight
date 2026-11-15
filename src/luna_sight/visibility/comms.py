"""Ay dağ sırtı bıçak-sırtı (knife-edge) radyo kırınımı ve NASA DSN bağlantı bütçesi.

Bu modül iki ileri uzay telekomünikasyon katmanını birleştirir:
    1. **ITU-R P.526-15 Bıçak Sırtı Kırınım Motoru**: Ay atmosferden yoksun olsa
       da krater duvarları ve dağ sırtları RF dalgalarını Huygens-Fresnel ilkesiyle
       gölge bölgesine kırar. S-Band (2.2 GHz) acil durum telemetrisi doğrudan görüş
       hattının ``0.3°–0.5°`` altında dahi kırınımla bağlantı kurabilirken, Ka-Band
       (26 GHz) ve 1550 nm optik lazer hızla sönümlenir.
    2. **NASA Deep Space Network (DSN) Bağlantı Bütçesi**: Goldstone (``-116.89°``),
       Madrid (``-4.25°``) ve Canberra (``+148.98°``) 70 m yer istasyonları için
       S-Band, Ka-Band ve Optik O2O (1550 nm) bantlarında serbest uzay yol kaybı
       (``FSPL``), kırınım zayıflaması, alınan güç (``dBm``), ``Eb/N0``, bağlantı
       marjı (``dB``) ve ulaşılabilir veri hızı (``Mbps``) hesaplar.

Sözleşme:
    - Tüm istasyon boylamları doğu-pozitif ``[-180, 180]`` aralığındadır.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np

C_LIGHT_M_S: float = 299_792_458.0
"""Vakumda ışık hızı (m/s, CODATA)."""

BOLTZMANN_K_DBW_HZ_K: float = -228.6
"""Boltzmann sabiti ``10 * log10(1.380649e-23)`` (dBW/Hz/K)."""

S_BAND_FREQ_HZ: float = 2.2e9
"""S-Band taşıyıcı frekansı (2.2 GHz)."""

KA_BAND_FREQ_HZ: float = 26.0e9
"""Ka-Band taşıyıcı frekansı (26.0 GHz)."""

OPTICAL_WAVELENGTH_M: float = 1550e-9
"""Optik lazer (O2O) dalga boyu (1550 nm)."""

OPTICAL_FREQ_HZ: float = C_LIGHT_M_S / OPTICAL_WAVELENGTH_M
"""1550 nm optik lazer frekansı (~193.4 THz)."""

DEFAULT_LUNAR_EARTH_DIST_M: float = 384_400_000.0
"""Ortalama Ay-Dünya mesafesi (384.400 km)."""

MIN_OPERATIONAL_MARGIN_DB: float = 3.0
"""NASA derin uzay asgari bağlantı güvenlik marjı (dB)."""


class DSNStation(StrEnum):
    """NASA Deep Space Network (DSN) ana yer istasyonları."""

    GOLDSTONE = "GOLDSTONE"
    MADRID = "MADRID"
    CANBERRA = "CANBERRA"


class FrequencyBand(StrEnum):
    """Desteklenen Ay-Dünya telekomünikasyon frekans bantları."""

    S_BAND = "S_BAND"
    KA_BAND = "KA_BAND"
    OPTICAL_O2O = "OPTICAL_O2O"


@dataclass(frozen=True)
class DSNStationInfo:
    """NASA DSN yer istasyonu koordinat ve anten parametreleri."""

    name: str
    station_id: DSNStation
    latitude_deg: float
    longitude_deg_east: float
    altitude_m: float
    dish_diameter_m: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError(f"latitude_deg [-90, 90] aralığında olmalı: {self.latitude_deg}")
        if not -180.0 <= self.longitude_deg_east <= 180.0:
            raise ValueError(
                f"longitude_deg_east [-180, 180] aralığında olmalı: {self.longitude_deg_east}"
            )

    @property
    def longitude_deg(self) -> float:
        """Geriye dönük okunabilir boylam takma adı (doğu-pozitif)."""
        return self.longitude_deg_east


DSN_STATIONS: dict[DSNStation, DSNStationInfo] = {
    DSNStation.GOLDSTONE: DSNStationInfo(
        name="Goldstone Deep Space Communications Complex",
        station_id=DSNStation.GOLDSTONE,
        latitude_deg=35.426,
        longitude_deg_east=-116.890,
        altitude_m=1000.0,
        dish_diameter_m=70.0,
    ),
    DSNStation.MADRID: DSNStationInfo(
        name="Madrid Deep Space Communications Complex",
        station_id=DSNStation.MADRID,
        latitude_deg=40.430,
        longitude_deg_east=-4.250,
        altitude_m=780.0,
        dish_diameter_m=70.0,
    ),
    DSNStation.CANBERRA: DSNStationInfo(
        name="Canberra Deep Space Communication Complex",
        station_id=DSNStation.CANBERRA,
        latitude_deg=-35.400,
        longitude_deg_east=148.980,
        altitude_m=650.0,
        dish_diameter_m=70.0,
    ),
}


@dataclass(frozen=True)
class BandConfig:
    """Frekans bandı verici/alıcı ve kanal kayıp varsayılanları."""

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


BAND_CONFIGS: dict[FrequencyBand, BandConfig] = {
    FrequencyBand.S_BAND: BandConfig(
        frequency_hz=S_BAND_FREQ_HZ,
        wavelength_m=C_LIGHT_M_S / S_BAND_FREQ_HZ,
        default_tx_power_w=15.0,
        default_tx_gain_dbi=12.0,
        default_rx_gain_dbi=61.0,
        atmospheric_loss_db=0.08,
        pointing_loss_db=0.30,
        noise_temp_k=135.0,
        default_data_rate_bps=64_000.0,
        required_eb_n0_db=3.0,
    ),
    FrequencyBand.KA_BAND: BandConfig(
        frequency_hz=KA_BAND_FREQ_HZ,
        wavelength_m=C_LIGHT_M_S / KA_BAND_FREQ_HZ,
        default_tx_power_w=25.0,
        default_tx_gain_dbi=32.0,
        default_rx_gain_dbi=78.5,
        atmospheric_loss_db=0.75,
        pointing_loss_db=0.80,
        noise_temp_k=165.0,
        default_data_rate_bps=20_000_000.0,
        required_eb_n0_db=3.5,
    ),
    FrequencyBand.OPTICAL_O2O: BandConfig(
        frequency_hz=OPTICAL_FREQ_HZ,
        wavelength_m=OPTICAL_WAVELENGTH_M,
        default_tx_power_w=5.0,
        default_tx_gain_dbi=108.0,
        default_rx_gain_dbi=124.0,
        atmospheric_loss_db=2.20,
        pointing_loss_db=1.50,
        noise_temp_k=290.0,
        default_data_rate_bps=200_000_000.0,
        required_eb_n0_db=4.5,
    ),
}

_BAND_ALIASES: dict[str, FrequencyBand] = {
    "s_band": FrequencyBand.S_BAND,
    "s-band": FrequencyBand.S_BAND,
    "sband": FrequencyBand.S_BAND,
    "2.2ghz": FrequencyBand.S_BAND,
    "ka_band": FrequencyBand.KA_BAND,
    "ka-band": FrequencyBand.KA_BAND,
    "kaband": FrequencyBand.KA_BAND,
    "26ghz": FrequencyBand.KA_BAND,
    "optical_o2o": FrequencyBand.OPTICAL_O2O,
    "optical-o2o": FrequencyBand.OPTICAL_O2O,
    "optical": FrequencyBand.OPTICAL_O2O,
    "o2o": FrequencyBand.OPTICAL_O2O,
    "1550nm": FrequencyBand.OPTICAL_O2O,
}


def _resolve_station(station: DSNStation | str) -> DSNStation:
    if isinstance(station, DSNStation):
        return station
    key = str(station).strip().upper()
    try:
        return DSNStation(key)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DSNStation)
        raise ValueError(f"Bilinmeyen DSN istasyonu '{station}'. Seçenekler: {valid}") from exc


def _resolve_band(band: FrequencyBand | str) -> FrequencyBand:
    if isinstance(band, FrequencyBand):
        return band
    text = str(band).strip()
    upper = text.upper()
    try:
        return FrequencyBand(upper)
    except ValueError:
        alias = _BAND_ALIASES.get(text.lower().replace(" ", ""))
        if alias is not None:
            return alias
        valid = ", ".join(item.value for item in FrequencyBand)
        raise ValueError(f"Bilinmeyen frekans bandı '{band}'. Seçenekler: {valid}") from None


def compute_wavelength(frequency_hz: float = S_BAND_FREQ_HZ) -> float:
    """Taşıyıcı frekansına karşılık gelen dalga boyunu (metre) döndürür: ``c / f``."""
    if not math.isfinite(frequency_hz) or frequency_hz <= 0.0:
        raise ValueError(f"Frekans pozitif sonlu olmalı; {frequency_hz} verildi.")
    return C_LIGHT_M_S / float(frequency_hz)


def compute_free_space_path_loss(
    distance_m: float = DEFAULT_LUNAR_EARTH_DIST_M,
    frequency_hz: float = S_BAND_FREQ_HZ,
) -> float:
    """Serbest uzay yol kaybını (FSPL) desibel cinsinden hesaplar."""
    if not math.isfinite(distance_m) or distance_m <= 0.0:
        raise ValueError(f"distance_m pozitif olmalı; {distance_m} verildi.")
    wavelength_m = compute_wavelength(frequency_hz)
    return float(20.0 * math.log10((4.0 * math.pi * float(distance_m)) / wavelength_m))


def compute_fresnel_parameter(
    obstruction_angle_deg: float | np.ndarray,
    distance_to_ridge_m: float = 5_000.0,
    distance_to_rx_m: float = DEFAULT_LUNAR_EARTH_DIST_M,
    frequency_hz: float = S_BAND_FREQ_HZ,
) -> float | np.ndarray:
    """Fresnel-Kirchhoff kırınım parametresi ``v`` değerini hesaplar.

    Parametreler:
        obstruction_angle_deg: Görüş hattının dağ sırtı arkasında kalma açısı
            (derece; pozitif = gölge bölgesi, negatif = engelsiz hat).
        distance_to_ridge_m: İniş aracı ile dağ sırtı arası mesafe (metre, ``d1``).
        distance_to_rx_m: Dağ sırtı ile alıcı arası mesafe (metre, ``d2``).
        frequency_hz: Sinyal taşıyıcı frekansı (Hz).

    Dönüş:
        Skaler girdi için ``float``, dizi girdi için ``np.ndarray`` boyutsuz ``v``.
    """
    if not math.isfinite(distance_to_ridge_m) or distance_to_ridge_m <= 0.0:
        raise ValueError(f"distance_to_ridge_m pozitif olmalı; {distance_to_ridge_m} verildi.")
    if not math.isfinite(distance_to_rx_m) or distance_to_rx_m <= 0.0:
        raise ValueError(f"distance_to_rx_m pozitif olmalı; {distance_to_rx_m} verildi.")

    wavelength_m = compute_wavelength(frequency_hz)
    scalar_input = np.isscalar(obstruction_angle_deg)
    ang_deg = np.asarray(obstruction_angle_deg, dtype=np.float64)
    if np.any(np.abs(ang_deg) >= 90.0):
        raise ValueError("obstruction_angle_deg (-90, 90) açık aralığında olmalı.")

    h_m = float(distance_to_ridge_m) * np.tan(np.radians(ang_deg))
    geom_factor = (1.0 / float(distance_to_ridge_m)) + (1.0 / float(distance_to_rx_m))
    v = h_m * np.sqrt((2.0 / wavelength_m) * geom_factor)

    if scalar_input:
        return float(v.item())
    return v


def compute_diffraction_loss_itu(v: float | np.ndarray) -> float | np.ndarray:
    """ITU-R P.526-15 tek bıçak-sırtı kırınım zayıflaması ``J(v)`` [dB].

    ``v <= -0.78`` için kayıp ``0.0 dB`` kabul edilir (ilk Fresnel bölgesi
    yeterince açıktır); ``v > -0.78`` için ITU-R P.526 analitik yaklaşıklığı
    uygulanır ve sonuç ``>= 0.0 dB`` olarak döndürülür.
    """
    scalar_input = np.isscalar(v)
    v_arr = np.asarray(v, dtype=np.float64)

    u = v_arr - 0.1
    arg = np.maximum(np.sqrt(u**2 + 1.0) + u, 1e-12)
    loss_db = 6.9 + 20.0 * np.log10(arg)
    loss_db = np.where(v_arr <= -0.78, 0.0, loss_db)
    loss_db = np.maximum(0.0, loss_db)

    if scalar_input:
        return float(loss_db.item())
    return loss_db


def classify_diffraction_regime(v: float | None) -> str:
    """Fresnel parametresi ``v`` değerini fiziksel kırınım rejimine eşler."""
    if v is None or v <= -0.78:
        return "clear_los"
    if v <= 0.0:
        return "fresnel_grazing"
    if v <= 1.0:
        return "shallow_shadow"
    return "deep_shadow"


def evaluate_emergency_link_margin(
    obstruction_angle_deg: float,
    distance_to_ridge_m: float = 5_000.0,
    frequency_hz: float = S_BAND_FREQ_HZ,
    tx_power_w: float = 10.0,
    tx_antenna_gain_dbi: float = 3.0,
    rx_antenna_gain_dbi: float = 61.0,
    receiver_sensitivity_dbm: float = -168.0,
    distance_to_rx_m: float = DEFAULT_LUNAR_EARTH_DIST_M,
) -> dict[str, Any]:
    """Dağ sırtı arkasındaki iniş aracı için acil durum kırınım bağlantı marjını değerlendirir."""
    if not math.isfinite(tx_power_w) or tx_power_w <= 0.0:
        raise ValueError(f"tx_power_w pozitif olmalı; {tx_power_w} verildi.")

    v_val = float(
        compute_fresnel_parameter(
            obstruction_angle_deg=obstruction_angle_deg,
            distance_to_ridge_m=distance_to_ridge_m,
            distance_to_rx_m=distance_to_rx_m,
            frequency_hz=frequency_hz,
        )
    )
    diffraction_loss_db = float(compute_diffraction_loss_itu(v_val))
    fspl_db = compute_free_space_path_loss(distance_to_rx_m, frequency_hz=frequency_hz)
    total_path_loss_db = fspl_db + diffraction_loss_db

    tx_power_dbm = 10.0 * math.log10(float(tx_power_w) * 1000.0)
    rx_power_dbm = tx_power_dbm + tx_antenna_gain_dbi - total_path_loss_db + rx_antenna_gain_dbi
    link_margin_db = rx_power_dbm - receiver_sensitivity_dbm
    link_closed = bool(link_margin_db >= MIN_OPERATIONAL_MARGIN_DB)
    regime = classify_diffraction_regime(v_val)

    return {
        "frequency_ghz": round(frequency_hz / 1e9, 3),
        "obstruction_angle_deg": float(obstruction_angle_deg),
        "distance_to_ridge_m": float(distance_to_ridge_m),
        "fresnel_parameter_v": round(v_val, 4),
        "diffraction_loss_db": round(diffraction_loss_db, 2),
        "fspl_db": round(fspl_db, 2),
        "free_space_loss_db": round(fspl_db, 2),
        "total_path_loss_db": round(total_path_loss_db, 2),
        "tx_power_w": float(tx_power_w),
        "tx_power_dbm": round(tx_power_dbm, 2),
        "rx_power_dbm": round(rx_power_dbm, 2),
        "receiver_sensitivity_dbm": float(receiver_sensitivity_dbm),
        "link_margin_db": round(link_margin_db, 2),
        "link_closed": link_closed,
        "diffraction_regime": regime,
        "communication_mode": (
            "DIFFRACTED_EMERGENCY_BEACON" if obstruction_angle_deg > 0.0 else "DIRECT_LINE_OF_SIGHT"
        ),
    }


def compute_link_budget(
    station: DSNStation | str = DSNStation.GOLDSTONE,
    band: FrequencyBand | str = FrequencyBand.S_BAND,
    distance_m: float = DEFAULT_LUNAR_EARTH_DIST_M,
    tx_power_w: float | None = None,
    data_rate_bps: float | None = None,
    additional_obstacle_loss_db: float = 0.0,
    obstruction_angle_deg: float | None = None,
    distance_to_ridge_m: float = 5_000.0,
    required_margin_db: float = MIN_OPERATIONAL_MARGIN_DB,
) -> dict[str, Any]:
    """Seçilen DSN istasyonu ve frekans bandı için Ay-Dünya bağlantı bütçesini hesaplar.

    Parametreler:
        station: DSN yer istasyonu (``GOLDSTONE``, ``MADRID``, ``CANBERRA``).
        band: Frekans bandı (``S_BAND``, ``KA_BAND``, ``OPTICAL_O2O`` veya takma adları).
        distance_m: Ay-Dünya mesafesi (metre).
        tx_power_w: Verici çıkış gücü (W; ``None`` ise bant varsayılanı).
        data_rate_bps: Hedef veri hızı (bps; ``None`` ise bant varsayılanı).
        additional_obstacle_loss_db: Ek engel zayıflaması (dB, negatif olamaz).
        obstruction_angle_deg: İsteğe bağlı dağ sırtı engel açısı (derece).
            Verilirse ITU-R P.526 kırınım kaybı otomatik hesaplanır.
        distance_to_ridge_m: Dağ sırtına yatay mesafe (metre).
        required_margin_db: Bağlantı kapanma eşiği için güvenlik marjı (dB).

    Dönüş:
        ``fspl_db``, ``diffraction_loss_db``, ``total_path_loss_db``, ``rx_power_dbm``,
        ``eb_n0_db``, ``link_margin_db``, ``achievable_data_rate_mbps``, ``link_closed``,
        ``diffraction_regime`` ve istasyon/bant meta alanlarını içeren sözlük.
    """
    if additional_obstacle_loss_db < 0.0:
        raise ValueError(
            f"additional_obstacle_loss_db negatif olamaz; {additional_obstacle_loss_db} verildi."
        )

    station_enum = _resolve_station(station)
    band_enum = _resolve_band(band)
    cfg = BAND_CONFIGS[band_enum]
    stn_info = DSN_STATIONS[station_enum]

    p_tx_w = float(tx_power_w) if tx_power_w is not None else cfg.default_tx_power_w
    if not math.isfinite(p_tx_w) or p_tx_w <= 0.0:
        raise ValueError(f"tx_power_w pozitif olmalı; {p_tx_w} verildi.")

    r_bps = float(data_rate_bps) if data_rate_bps is not None else cfg.default_data_rate_bps
    if not math.isfinite(r_bps) or r_bps <= 0.0:
        raise ValueError(f"data_rate_bps pozitif olmalı; {r_bps} verildi.")

    v_val: float | None = None
    itu_loss_db = 0.0
    if obstruction_angle_deg is not None:
        v_val = float(
            compute_fresnel_parameter(
                obstruction_angle_deg=obstruction_angle_deg,
                distance_to_ridge_m=distance_to_ridge_m,
                distance_to_rx_m=distance_m,
                frequency_hz=cfg.frequency_hz,
            )
        )
        itu_loss_db = float(compute_diffraction_loss_itu(v_val))
        diffraction_regime = classify_diffraction_regime(v_val)
    elif additional_obstacle_loss_db > 0.0:
        diffraction_regime = "obstructed"
    else:
        diffraction_regime = "clear_los"

    diffraction_loss_db = itu_loss_db + float(additional_obstacle_loss_db)
    fspl_db = compute_free_space_path_loss(distance_m=distance_m, frequency_hz=cfg.frequency_hz)
    total_path_loss_db = (
        fspl_db + cfg.atmospheric_loss_db + cfg.pointing_loss_db + diffraction_loss_db
    )

    p_tx_dbw = 10.0 * math.log10(p_tx_w)
    eirp_dbw = p_tx_dbw + cfg.default_tx_gain_dbi
    rx_power_dbw = eirp_dbw - total_path_loss_db + cfg.default_rx_gain_dbi
    rx_power_dbm = rx_power_dbw + 30.0

    n0_dbw_hz = BOLTZMANN_K_DBW_HZ_K + 10.0 * math.log10(cfg.noise_temp_k)
    eb_n0_db = rx_power_dbw - n0_dbw_hz - 10.0 * math.log10(r_bps)
    link_margin_db = eb_n0_db - cfg.required_eb_n0_db
    link_closed = bool(link_margin_db >= float(required_margin_db))

    max_rate_db_hz = rx_power_dbw - n0_dbw_hz - cfg.required_eb_n0_db - float(required_margin_db)
    achievable_bps = 10.0 ** (max_rate_db_hz / 10.0)
    achievable_mbps = achievable_bps / 1e6

    if link_closed:
        status = "OPERATIONAL_MARGIN"
    elif link_margin_db >= 0.0:
        status = "DEGRADED"
    else:
        status = "LINK_LOSS"

    return {
        "station": station_enum.value,
        "station_name": stn_info.name,
        "station_latitude_deg": stn_info.latitude_deg,
        "station_longitude_deg_east": stn_info.longitude_deg_east,
        "frequency_band": band_enum.value,
        "frequency_hz": cfg.frequency_hz,
        "wavelength_m": cfg.wavelength_m,
        "tx_power_w": p_tx_w,
        "tx_power_dbw": round(p_tx_dbw, 2),
        "tx_antenna_gain_dbi": cfg.default_tx_gain_dbi,
        "eirp_dbw": round(eirp_dbw, 2),
        "distance_km": round(float(distance_m) / 1000.0, 1),
        "fspl_db": round(fspl_db, 2),
        "free_space_loss_db": round(fspl_db, 2),
        "atmospheric_loss_db": cfg.atmospheric_loss_db,
        "pointing_loss_db": cfg.pointing_loss_db,
        "diffraction_loss_db": round(diffraction_loss_db, 2),
        "obstacle_diffraction_loss_db": round(diffraction_loss_db, 2),
        "total_path_loss_db": round(total_path_loss_db, 2),
        "fresnel_parameter_v": None if v_val is None else round(v_val, 4),
        "diffraction_regime": diffraction_regime,
        "rx_antenna_gain_dbi": cfg.default_rx_gain_dbi,
        "rx_power_dbw": round(rx_power_dbw, 2),
        "rx_power_dbm": round(rx_power_dbm, 2),
        "noise_temp_k": cfg.noise_temp_k,
        "n0_dbw_hz": round(n0_dbw_hz, 2),
        "data_rate_bps": r_bps,
        "data_rate_display": (
            f"{r_bps / 1e6:.2f} Mbps" if r_bps >= 1e6 else f"{r_bps / 1e3:.1f} kbps"
        ),
        "eb_n0_db": round(eb_n0_db, 2),
        "eb_n0_achieved_db": round(eb_n0_db, 2),
        "eb_n0_required_db": cfg.required_eb_n0_db,
        "link_margin_db": round(link_margin_db, 2),
        "achievable_data_rate_mbps": round(achievable_mbps, 6),
        "link_closed": link_closed,
        "status": status,
    }


def compare_band_link_budgets(
    station: DSNStation | str = DSNStation.GOLDSTONE,
    distance_m: float = DEFAULT_LUNAR_EARTH_DIST_M,
    obstruction_angle_deg: float | None = None,
    distance_to_ridge_m: float = 5_000.0,
) -> dict[str, dict[str, Any]]:
    """Tüm ön ayarlı bantlar (S-Band, Ka-Band, Optical O2O) için bağlantı bütçesini kıyaslar."""
    return {
        band.value: compute_link_budget(
            station=station,
            band=band,
            distance_m=distance_m,
            obstruction_angle_deg=obstruction_angle_deg,
            distance_to_ridge_m=distance_to_ridge_m,
        )
        for band in FrequencyBand
    }


__all__ = [
    "BAND_CONFIGS",
    "BOLTZMANN_K_DBW_HZ_K",
    "C_LIGHT_M_S",
    "DEFAULT_LUNAR_EARTH_DIST_M",
    "DSN_STATIONS",
    "KA_BAND_FREQ_HZ",
    "MIN_OPERATIONAL_MARGIN_DB",
    "OPTICAL_FREQ_HZ",
    "OPTICAL_WAVELENGTH_M",
    "S_BAND_FREQ_HZ",
    "BandConfig",
    "DSNStation",
    "DSNStationInfo",
    "FrequencyBand",
    "classify_diffraction_regime",
    "compare_band_link_budgets",
    "compute_diffraction_loss_itu",
    "compute_free_space_path_loss",
    "compute_fresnel_parameter",
    "compute_link_budget",
    "compute_wavelength",
    "evaluate_emergency_link_margin",
]
