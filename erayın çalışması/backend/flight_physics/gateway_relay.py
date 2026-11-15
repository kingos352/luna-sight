"""
backend/flight_physics/gateway_relay.py
=======================================
Artemis Lunar Gateway (NRHO) Yörüngesel Röle Efemerisi ve Görünürlük Analizi.

Artemis programında (Orion ve Human Landing System - HLS), Dünya-Ay L2 Güney Halo
NRHO (Near Rectilinear Halo Orbit - 9:2 rezonans) yörüngesi kullanılmaktadır:
- Yörünge Periyodu: ~7 gün (~168 saat).
- Apolun (Güney Kutbu üzerinde): İrtifa ~70,000 km, hız düşük (~100 m/s).
  Zamanının yaklaşık %85'ini (5.5 - 6.0 gün) Güney Kutbu görüş hattında geçirir.
- Perilun (Kuzey Kutbu üzerinde): İrtifa ~1,500 - 3,200 km, hız yüksek (~1,700 m/s), hızlı geçiş (~12 saat).
- Kalıcı Gölgeli Kraterler (PSR - Shackleton, Cabeus, Faustini vb.) için Dünya ile doğrudan
  görüş (DTE) kesildiğinde hayati telekomünikasyon ve veri aktarım rölesi sağlar.
"""

from __future__ import annotations
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from backend.config import LUNAR_MEAN_RADIUS_M

# NRHO Yörünge Parametreleri (Artemis Gateway Spesifikasyonu)
NRHO_PERIOD_HOURS: float = 168.0  # 7 gün
NRHO_SEMI_MAJOR_AXIS_KM: float = 36_600.0
NRHO_ECCENTRICITY: float = 0.912  # Yüksek basıklık
NRHO_PERILUNE_RADIUS_KM: float = NRHO_SEMI_MAJOR_AXIS_KM * (1.0 - NRHO_ECCENTRICITY)  # ~3,220 km (Moon center)
NRHO_APOLUNE_RADIUS_KM: float = NRHO_SEMI_MAJOR_AXIS_KM * (1.0 + NRHO_ECCENTRICITY)    # ~69,980 km


def _solve_kepler(M: float, e: float, tolerance: float = 1e-9) -> float:
    """Kepler denklemini Newton-Raphson iterasyonu ile çözer: M = E - e*sin(E)."""
    E = M if e < 0.8 else math.pi
    for _ in range(50):
        f = E - e * math.sin(E) - M
        f_prime = 1.0 - e * math.cos(E)
        delta = f / f_prime
        E -= delta
        if abs(delta) < tolerance:
            break
    return E


def generate_gateway_ephemeris(
    start_utc: Union[str, datetime] = "2026-11-15T00:00:00Z",
    duration_days: float = 7.0,
    step_hours: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    7 günlük analitik L2 Güney Halo NRHO yörünge izi (ephemeris) üretir.

    Parametreler:
        start_utc: Başlangıç ISO UTC zamanı
        duration_days: Simülasyon süresi (varsayılan: 7.0 gün)
        step_hours: Efemeris adımı (varsayılan: 1.0 saat)

    Dönüş:
        List[Dict]: Her zaman adımı için selenomerkezî koordinatlar, mesafe ve alt-uydu noktası
    """
    if isinstance(start_utc, str):
        t0 = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
    else:
        t0 = start_utc
        if t0.tzinfo is None:
            t0 = t0.replace(tzinfo=timezone.utc)

    total_hours = duration_days * 24.0
    num_steps = max(1, int(round(total_hours / step_hours)))

    ephemeris: List[Dict[str, Any]] = []
    n = 2.0 * math.pi / NRHO_PERIOD_HOURS  # Ortalama hareket (rad/saat)

    # Başlangıçta apolunda (Güney Kutbu üzerinde maksimum görüşte) başlasın (M0 = pi)
    M0 = math.pi

    for step in range(num_steps + 1):
        t_hour = step * step_hours
        current_time = t0 + timedelta(hours=t_hour)

        M = (M0 + n * t_hour) % (2.0 * math.pi)
        E = _solve_kepler(M, NRHO_ECCENTRICITY)

        # Yörünge düzleminde koordinatlar
        # Gerçek anomali nu
        cos_nu = (math.cos(E) - NRHO_ECCENTRICITY) / (1.0 - NRHO_ECCENTRICITY * math.cos(E))
        sin_nu = (math.sqrt(1.0 - NRHO_ECCENTRICITY**2) * math.sin(E)) / (1.0 - NRHO_ECCENTRICITY * math.cos(E))
        nu = math.atan2(sin_nu, cos_nu)

        r_km = NRHO_SEMI_MAJOR_AXIS_KM * (1.0 - NRHO_ECCENTRICITY * math.cos(E))

        # NRHO Selenomerkezî Koordinat Dönüşümü:
        # Apolun Z < 0 (Güney Kutbu altı/dışı), Perilun Z > 0 (Kuzey)
        # Yörünge düzlemi ~90° eğimli, X-Z düzleminde ana hareket
        # nu = 0 perilun (Kuzey, Z > 0), nu = pi apolun (Derin Güney, Z < 0)
        x_km = 0.35 * r_km * math.sin(nu)  # X-ekseni salınımı (halo komponenti)
        y_km = 0.20 * r_km * math.sin(2.0 * nu)  # Y-ekseni out-of-plane küçük salınım
        z_km = r_km * math.cos(nu)  # nu = pi -> cos(pi) = -1 -> z = -r_km (Derin Güney ~ -70,000 km)

        distance_km = math.sqrt(x_km**2 + y_km**2 + z_km**2)
        altitude_km = distance_km - (LUNAR_MEAN_RADIUS_M / 1000.0)

        # Alt-uydu selenografik koordinatları (enlem, boylam)
        sub_lat_deg = math.degrees(math.asin(np.clip(z_km / distance_km, -1.0, 1.0)))
        sub_lon_deg = math.degrees(math.atan2(y_km, x_km))

        ephemeris.append({
            "utc": current_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "step_hour": round(t_hour, 2),
            "x_km": round(x_km, 2),
            "y_km": round(y_km, 2),
            "z_km": round(z_km, 2),
            "distance_km": round(distance_km, 2),
            "altitude_km": round(altitude_km, 2),
            "sub_lat_deg": round(sub_lat_deg, 3),
            "sub_lon_deg": round(sub_lon_deg, 3),
            "in_southern_sweet_spot": bool(z_km < -15_000.0),
        })

    return ephemeris


def compute_gateway_visibility(
    site_lat: float,
    site_lon: float,
    site_elev_m: float = 0.0,
    ephemeris: Optional[List[Dict[str, Any]]] = None,
    min_elevation_deg: float = 5.0,
    terrain_engine: Any = None,
) -> Dict[str, Any]:
    """
    Herhangi bir iniş sahası (özellikle krater tabanı / PSR) için Gateway görünürlük pencerelerini
    (AOS / LOS) ve yerel ufuk engellerini tespit eder.

    Parametreler:
        site_lat: İniş sahası enlemi (derece, örn: -89.75 Shackleton)
        site_lon: İniş sahası boylamı (derece)
        site_elev_m: Yüzey kotu (metre)
        ephemeris: Önceden üretilmiş ephemeris (None ise 7 günlük üretilir)
        min_elevation_deg: Asgari anten yükseklik açısı (derece, varsayılan: 5.0°)
        terrain_engine: Opsiyonel TerrainEngine örneği (gerçek ufuk engeli için)

    Dönüş:
        Dict: AOS/LOS pencereleri, toplam iletişim saati, erişilebilirlik yüzdesi ve adım adım telemetri
    """
    if ephemeris is None:
        ephemeris = generate_gateway_ephemeris(duration_days=7.0, step_hours=1.0)

    # İniş sahasının selenomerkezî Kartezyen vektörü (km)
    r_site_m = LUNAR_MEAN_RADIUS_M + site_elev_m
    lat_rad = math.radians(site_lat)
    lon_rad = math.radians(site_lon)

    # Selenomerkezî birim vektörler (Up, East, North)
    up_vec = np.array([
        math.cos(lat_rad) * math.cos(lon_rad),
        math.cos(lat_rad) * math.sin(lon_rad),
        math.sin(lat_rad),
    ], dtype=np.float64)

    east_vec = np.array([
        -math.sin(lon_rad),
        math.cos(lon_rad),
        0.0,
    ], dtype=np.float64)

    north_vec = np.cross(up_vec, east_vec)
    north_vec = north_vec / np.linalg.norm(north_vec)

    site_pos_km = (r_site_m / 1000.0) * up_vec

    time_steps: List[Dict[str, Any]] = []
    visible_count = 0
    total_steps = len(ephemeris)

    # Pencere takibi
    windows: List[Dict[str, Any]] = []
    current_window_start: Optional[str] = None
    current_window_steps: int = 0

    for item in ephemeris:
        gw_pos_km = np.array([item["x_km"], item["y_km"], item["z_km"]], dtype=np.float64)
        rho_vec = gw_pos_km - site_pos_km
        rho_dist_km = float(np.linalg.norm(rho_vec))

        rho_hat = rho_vec / rho_dist_km

        # Yerel gök kubbe açıları
        up_comp = float(np.dot(rho_hat, up_vec))
        east_comp = float(np.dot(rho_hat, east_vec))
        north_comp = float(np.dot(rho_hat, north_vec))

        # Yükseklik açısı (elevation)
        elev_rad = math.asin(np.clip(up_comp, -1.0, 1.0))
        elev_deg = math.degrees(elev_rad)

        # Azimut açısı (0° Kuzey, 90° Doğu)
        az_deg = (math.degrees(math.atan2(east_comp, north_comp))) % 360.0

        # Arazi engeli kontrolü
        horizon_obstruction_deg = 0.0
        if terrain_engine is not None and hasattr(terrain_engine, "get_horizon_elevation_at"):
            try:
                # Merkez piksel üzerinden veya piksel koordinatından
                h, w = terrain_engine.elevation.shape
                py, px = h // 2, w // 2
                horizon_obstruction_deg = terrain_engine.get_horizon_elevation_at(py, px, az_deg)
            except Exception:
                horizon_obstruction_deg = 0.0

        effective_threshold = max(min_elevation_deg, horizon_obstruction_deg)
        is_visible = bool(elev_deg >= effective_threshold)

        if is_visible:
            visible_count += 1
            if current_window_start is None:
                current_window_start = item["utc"]
                current_window_steps = 1
            else:
                current_window_steps += 1
        else:
            if current_window_start is not None:
                # Pencere kapandı (LOS)
                windows.append({
                    "aos_utc": current_window_start,
                    "los_utc": item["utc"],
                    "duration_hours": current_window_steps * (ephemeris[1]["step_hour"] - ephemeris[0]["step_hour"] if len(ephemeris) > 1 else 1.0),
                })
                current_window_start = None
                current_window_steps = 0

        time_steps.append({
            "utc": item["utc"],
            "elevation_deg": round(elev_deg, 2),
            "azimuth_deg": round(az_deg, 2),
            "range_km": round(rho_dist_km, 1),
            "horizon_elevation_deg": round(horizon_obstruction_deg, 2),
            "visible": is_visible,
        })

    # Son pencere açık kaldıysa ekle
    if current_window_start is not None:
        step_dt = (ephemeris[1]["step_hour"] - ephemeris[0]["step_hour"]) if len(ephemeris) > 1 else 1.0
        windows.append({
            "aos_utc": current_window_start,
            "los_utc": ephemeris[-1]["utc"],
            "duration_hours": current_window_steps * step_dt,
        })

    coverage_pct = (visible_count / max(1, total_steps)) * 100.0
    total_contact_hours = sum(w["duration_hours"] for w in windows)

    return {
        "site_lat": site_lat,
        "site_lon": site_lon,
        "site_elev_m": site_elev_m,
        "total_steps": total_steps,
        "visible_steps": visible_count,
        "coverage_percentage": round(coverage_pct, 2),
        "total_contact_hours": round(total_contact_hours, 2),
        "windows_count": len(windows),
        "windows": windows,
        "time_series": time_steps,
    }
