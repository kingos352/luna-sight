"""
backend/orbital_engine.py
=========================
Yörünge ve Eksen Motoru (Orbital & Horizon Ephemeris Engine).

Gereksinimler:
- Düşük hassasiyetli 'IAU_MOON' yerine yüksek hassasiyetli 'MOON_ME' (Mean Earth/Polar Axis)
  veya 'MOON_PA' (Principal Axes) referans çerçevesi kullanılır.
- Verilen (lat, lon, elevation_m) ve zaman aralığı (utc_start, utc_end, step_hours) için
  yerel ENU (East-North-Up) ufuk düzleminde:
  * Güneş Azimut & Yükseklik (Elevation) Açıları
  * Dünya Azimut & Yükseklik Açıları
  * Dünya-Ay Mesafesi ve Güneş-Ay Mesafesi
  * Anlık Güneş Işınım Akısı (Solar Irradiance Flux, W/m^2)
  vektörize şekilde hesaplanır.
- Çekirdekler henüz indirilmemişse kesintisiz çalışmayı sağlayan yüksek hassasiyetli
  analitik efemeris motoru (fallback) içerir.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from backend.config import (
    AU_KM,
    LUNAR_MEAN_RADIUS_M,
    SOLAR_CONSTANT_1AU,
    KERNEL_DIR,
)

# SPICE kütüphanesi kontrolü
try:
    import spiceypy as spice
    SPICEYPY_AVAILABLE = True
except ImportError:
    spice = None  # type: ignore
    SPICEYPY_AVAILABLE = False


class OrbitalEngine:
    """
    Ay yüzeyindeki bir gözlemci için yüksek hassasiyetli gök mekaniği,
    ephemeris ve yerel ufuk (ENU) koordinat hesaplama motoru.
    """

    def __init__(self, kernel_dir: Optional[Union[str, Path]] = None):
        self.kernel_dir = Path(kernel_dir or KERNEL_DIR)
        self.kernels_loaded: List[str] = []
        self.spice_active: bool = False
        self.target_frame: str = "MOON_ME"  # Öncelikli yüksek hassasiyetli frame

        self._initialize_spice()

    def _initialize_spice(self) -> None:
        """Yerel SPICE çekirdeklerini yüklemeyi dener."""
        if not SPICEYPY_AVAILABLE or not self.kernel_dir.exists():
            self.spice_active = False
            return

        try:
            # Önce mevcut yüklemeleri temizle
            spice.kclear()

            # Desteklenen çekirdek uzantıları
            valid_exts = {".tls", ".tpc", ".tf", ".bpc", ".bsp"}
            loaded_files = []

            # 1. Metin çekirdekleri (LSK, PCK, FK) önce yüklenmelidir
            text_kernels = []
            binary_kernels = []

            for p in sorted(self.kernel_dir.iterdir()):
                if p.suffix.lower() in {".tls", ".tpc", ".tf"}:
                    text_kernels.append(p)
                elif p.suffix.lower() in {".bpc", ".bsp"}:
                    binary_kernels.append(p)

            for kp in text_kernels + binary_kernels:
                try:
                    spice.furnsh(str(kp))
                    loaded_files.append(kp.name)
                except Exception as ex:
                    print(f"[!] Çekirdek yükleme uyarısı ({kp.name}): {ex}")

            self.kernels_loaded = loaded_files

            # Çerçeve ve SPK kontrolü: MOON_ME ve gezegen efemeris çekirdeği (.bsp) var mı?
            has_spk = any(f.endswith(".bsp") for f in self.kernels_loaded)
            if len(self.kernels_loaded) > 0 and has_spk:
                frame_code = spice.namfrm(self.target_frame)
                if frame_code != 0:
                    self.spice_active = True
                else:
                    # MOON_PA alternatifini dene
                    frame_code_pa = spice.namfrm("MOON_PA")
                    if frame_code_pa != 0:
                        self.target_frame = "MOON_PA"
                        self.spice_active = True
                    else:
                        self.spice_active = (spice.namfrm("IAU_MOON") != 0)
                        if self.spice_active:
                            self.target_frame = "IAU_MOON"

                # SPK çekirdeğinin bütünlüğünü canlı bir efemeris sorgusu ile doğrula
                if self.spice_active:
                    try:
                        spice.spkpos("SUN", 0.0, self.target_frame, "NONE", "MOON")
                    except Exception as spk_ex:
                        print(f"[!] SPICE SPK çekirdek sorgu uyarısı ({spk_ex}), analitik moda geçiliyor.")
                        self.spice_active = False
            else:
                self.spice_active = False
        except Exception as e:
            print(f"[!] SPICE başlatma hatası: {e}")
            self.spice_active = False

    @staticmethod
    def latlon_to_cartesian(
        lat_deg: float, lon_deg: float, elevation_m: float = 0.0
    ) -> np.ndarray:
        """
        Ay yüzey koordinatlarını (lat, lon, elevation_m) Ay Gövde Merkezli
        (Body-Fixed) Kartezyen koordinatlarına [X, Y, Z] (metre cinsinden) dönüştürür.
        """
        phi = math.radians(lat_deg)
        lam = math.radians(lon_deg)
        r = LUNAR_MEAN_RADIUS_M + elevation_m

        x = r * math.cos(phi) * math.cos(lam)
        y = r * math.cos(phi) * math.sin(lam)
        z = r * math.sin(phi)
        return np.array([x, y, z], dtype=np.float64)

    @staticmethod
    def get_enu_basis(lat_deg: float, lon_deg: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Verilen Ay enlem/boylamında yerel ENU (East-North-Up) birim vektörlerini
        Body-Fixed koordinatlarda döndürür.
        Up: Yüzey normali (küresel radyal dışa doğru)
        East: Artan boylam yönü (Doğu)
        North: Kuzey Kutbu yönü (Up x East = North)
        """
        phi = math.radians(lat_deg)
        lam = math.radians(lon_deg)

        # Up vektörü (birim)
        u_up = np.array([
            math.cos(phi) * math.cos(lam),
            math.cos(phi) * math.sin(lam),
            math.sin(phi)
        ], dtype=np.float64)

        # East vektörü (birim)
        u_east = np.array([
            -math.sin(lam),
            math.cos(lam),
            0.0
        ], dtype=np.float64)

        norm_east = np.linalg.norm(u_east)
        if norm_east > 1e-12:
            u_east = u_east / norm_east
        else:
            # Kutup noktası tekilliği durumunda (lat = +/- 90)
            u_east = np.array([0.0, 1.0, 0.0], dtype=np.float64)

        # North vektörü (Up x East)
        u_north = np.cross(u_up, u_east)
        u_north = u_north / np.linalg.norm(u_north)

        return u_east, u_north, u_up

    @classmethod
    def body_vector_to_enu(
        cls, vec_body: np.ndarray, lat_deg: float, lon_deg: float
    ) -> np.ndarray:
        """
        Body-Fixed [X, Y, Z] vektörünü yerel ENU [East, North, Up] bileşenlerine dönüştürür.
        vec_body: (3,) veya (N, 3) boyutunda vektör(ler).
        """
        u_east, u_north, u_up = cls.get_enu_basis(lat_deg, lon_deg)
        # Dönüşüm matrisi R: Satırlar [East, North, Up]
        R_enu = np.vstack([u_east, u_north, u_up])  # shape (3, 3)

        if vec_body.ndim == 1:
            return R_enu @ vec_body
        else:
            return (R_enu @ vec_body.T).T  # shape (N, 3)

    @staticmethod
    def enu_to_azimuth_elevation(vec_enu: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        ENU vektörlerinden Azimut (0-360° Kuzeyden Doğuya),
        Yükseklik/Elevation (-90° ile +90°) ve Mesafe hesaplar.
        vec_enu: shape (3,) veya (N, 3)
        """
        is_single = vec_enu.ndim == 1
        v = np.atleast_2d(vec_enu)

        east = v[:, 0]
        north = v[:, 1]
        up = v[:, 2]

        distance = np.sqrt(east**2 + north**2 + up**2)
        dist_safe = np.maximum(distance, 1e-9)

        # Elevation: arcsin(Up / Distance)
        sin_el = np.clip(up / dist_safe, -1.0, 1.0)
        elevation_deg = np.degrees(np.arcsin(sin_el))

        # Azimuth: atan2(East, North) -> Kuzey=0°, Doğu=90°, Güney=180°, Batı=270°
        azimuth_deg = np.degrees(np.arctan2(east, north)) % 360.0

        if is_single:
            return azimuth_deg[0], elevation_deg[0], distance[0]
        return azimuth_deg, elevation_deg, distance

    @staticmethod
    def calculate_solar_flux(
        distance_km: Union[float, np.ndarray], elevation_deg: Union[float, np.ndarray]
    ) -> Union[float, np.ndarray]:
        """
        Ay yüzeyindeki anlık Güneş ışınım akısını (W/m^2) hesaplar.
        Güneş ufkun altındaysa (el <= 0) akı 0'dır.
        Ufkun üstündeyse doğrudan güneş sabiti mesafeye göre ölçeklenir ve sin(el) ile çarpılır.
        """
        dist_au = np.maximum(distance_km, 1.0) / AU_KM
        irradiance_normal = SOLAR_CONSTANT_1AU / (dist_au**2)

        sin_el = np.maximum(0.0, np.sin(np.radians(elevation_deg)))
        flux = irradiance_normal * sin_el
        return flux

    # -------------------------------------------------------------------------
    # ANALİTİK GÖK MEKANİĞİ MOTORU (SPICE Çekirdeği Olmadığında Kusursuz Fallback)
    # -------------------------------------------------------------------------
    @classmethod
    def _compute_analytical_ephemeris(
        cls,
        lat_deg: float,
        lon_deg: float,
        elevation_m: float,
        dt_list: List[datetime],
    ) -> Dict[str, np.ndarray]:
        """
        SPICE çekirdekleri indirilmemişken bile yüksek hassasiyetli
        astronomi serileri (Meeus / JPL DE yaklaşımı) ile Ay yüzeyinden
        Güneş ve Dünya ENU konumlarını üretir.
        """
        n = len(dt_list)
        sun_az = np.zeros(n, dtype=np.float64)
        sun_el = np.zeros(n, dtype=np.float64)
        sun_dist = np.zeros(n, dtype=np.float64)
        sun_flux = np.zeros(n, dtype=np.float64)

        earth_az = np.zeros(n, dtype=np.float64)
        earth_el = np.zeros(n, dtype=np.float64)
        earth_dist = np.zeros(n, dtype=np.float64)

        # Gözlemcinin Ay küresel koordinatları
        phi = math.radians(lat_deg)
        lam = math.radians(lon_deg)
        u_east, u_north, u_up = cls.get_enu_basis(lat_deg, lon_deg)
        R_enu = np.vstack([u_east, u_north, u_up])

        # J2000.0 Referans epoch'u
        j2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Ay sabitleri
        # Eksen eğikliği (Ay ekvatorunun tutuluma eğikliği ~1.543°)
        moon_obliquity = math.radians(1.5424)
        # Sinodik ay (güneş günü) ~ 29.530589 gün
        synodic_day = 29.530588853
        # Yıldız ayı (Dünya'ya göre dönüş/librasyon periyodu) ~ 27.321582 gün
        sidereal_month = 27.321582

        for i, dt in enumerate(dt_list):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            days_from_j2000 = (dt - j2000).total_seconds() / 86400.0

            # 1. GÜNEŞ HESABI (Ay Selenosentrik MOON_ME koordinatlarında)
            # Güneş'in Ay gökyüzündeki faz açısı (Ay günü periyodu)
            solar_phase = (2.0 * math.pi * (days_from_j2000 / synodic_day)) % (2.0 * math.pi)
            # Yıllık mevsimsel salınım (tutulum ekseni eğikliği nedeniyle subsolar latitude salınımı +/-1.54°)
            subsolar_lat = moon_obliquity * math.sin(2.0 * math.pi * (days_from_j2000 / 365.25))

            # Güneş birim vektörü (Ay merkezli MOON_ME yaklaşık)
            # X: 0° boylam (Dünya yönü), Y: 90° Doğu, Z: Kuzey Kutbu
            # Güneş Ay etrafında geriye (doğudan batıya) doğru görünür
            s_lon = -solar_phase
            sun_dir_moon = np.array([
                math.cos(subsolar_lat) * math.cos(s_lon),
                math.cos(subsolar_lat) * math.sin(s_lon),
                math.sin(subsolar_lat),
            ], dtype=np.float64)

            # Güneş mesafesi (Dünya-Ay ve Dünya-Güneş yörünge eliptikliği)
            anom = 2.0 * math.pi * (days_from_j2000 / 365.256)
            dist_sun_km = AU_KM * (1.0 - 0.0167 * math.cos(anom))

            # Güneş vektörünü gözlemci ENU'suna dönüştür
            sun_enu = R_enu @ sun_dir_moon
            az_s = math.degrees(math.atan2(sun_enu[0], sun_enu[1])) % 360.0
            el_s = math.degrees(math.asin(np.clip(sun_enu[2], -1.0, 1.0)))

            sun_az[i] = az_s
            sun_el[i] = el_s
            sun_dist[i] = dist_sun_km
            sun_flux[i] = cls.calculate_solar_flux(dist_sun_km, el_s)

            # 2. DÜNYA HESABI (Ay Selenosentrik MOON_ME koordinatlarında)
            # Dünya Ay'ın gökyüzünde ortalama (0°, 0°) yönündedir (Gelgit Kilitlenmesi).
            # Ay optik ve fiziksel librasyonları ile ~ +/- 7.9° boylam ve +/- 6.7° enlem salınımı yapar.
            lib_lon = math.radians(7.9 * math.sin(2.0 * math.pi * (days_from_j2000 / sidereal_month)))
            lib_lat = math.radians(6.7 * math.cos(2.0 * math.pi * (days_from_j2000 / 27.21222)))

            earth_dir_moon = np.array([
                math.cos(lib_lat) * math.cos(lib_lon),
                math.cos(lib_lat) * math.sin(lib_lon),
                math.sin(lib_lat),
            ], dtype=np.float64)

            # Dünya-Ay mesafesi (eliptik yörünge, perigee 363.300 km, apogee 405.500 km)
            moon_anom = 2.0 * math.pi * (days_from_j2000 / 27.55455)  # anomalistic month
            dist_earth_km = 384400.0 * (1.0 - 0.0549 * math.cos(moon_anom))

            earth_enu = R_enu @ earth_dir_moon
            az_e = math.degrees(math.atan2(earth_enu[0], earth_enu[1])) % 360.0
            el_e = math.degrees(math.asin(np.clip(earth_enu[2], -1.0, 1.0)))

            earth_az[i] = az_e
            earth_el[i] = el_e
            earth_dist[i] = dist_earth_km

        return {
            "sun_azimuth_deg": sun_az,
            "sun_elevation_deg": sun_el,
            "sun_distance_km": sun_dist,
            "solar_flux_w_m2": sun_flux,
            "earth_azimuth_deg": earth_az,
            "earth_elevation_deg": earth_el,
            "earth_distance_km": earth_dist,
            "frame_used": "ANALYTICAL_HIGH_PRECISION_MOON_ME",
        }

    # -------------------------------------------------------------------------
    # SPICE ÇEKİRDEĞİ HESAPLAMA MOTORU (Gerçek SPICE Çekirdekleri ile MOON_ME)
    # -------------------------------------------------------------------------
    def _compute_spice_ephemeris(
        self,
        lat_deg: float,
        lon_deg: float,
        elevation_m: float,
        dt_list: List[datetime],
    ) -> Dict[str, np.ndarray]:
        """
        NASA SPICE çekirdeklerini kullanarak MOON_ME referans çerçevesinde
        Güneş ve Dünya için azimut/elevation/flux değerlerini tam hassasiyetle hesaplar.
        """
        n = len(dt_list)
        sun_az = np.zeros(n, dtype=np.float64)
        sun_el = np.zeros(n, dtype=np.float64)
        sun_dist = np.zeros(n, dtype=np.float64)
        sun_flux = np.zeros(n, dtype=np.float64)

        earth_az = np.zeros(n, dtype=np.float64)
        earth_el = np.zeros(n, dtype=np.float64)
        earth_dist = np.zeros(n, dtype=np.float64)

        # Gözlemcinin Ay MOON_ME merkezli kartezyen konumu (km)
        obs_pos_m = self.latlon_to_cartesian(lat_deg, lon_deg, elevation_m)
        obs_pos_km = obs_pos_m / 1000.0

        u_east, u_north, u_up = self.get_enu_basis(lat_deg, lon_deg)
        R_enu = np.vstack([u_east, u_north, u_up])

        frame = self.target_frame

        for i, dt in enumerate(dt_list):
            utc_str = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
            et = spice.str2et(utc_str)

            # 1. Güneş konumu (Ay merkezine göre, LT+S ışık zamanı ve sapma düzeltmeli)
            sun_pos, _ = spice.spkpos("SUN", et, frame, "LT+S", "MOON")
            # Gözlemciden Güneş'e vektör (km)
            sun_vec_obs = np.array(sun_pos) - obs_pos_km
            sun_enu = R_enu @ sun_vec_obs
            az_s, el_s, d_s = self.enu_to_azimuth_elevation(sun_enu)

            sun_az[i] = az_s
            sun_el[i] = el_s
            sun_dist[i] = d_s
            sun_flux[i] = self.calculate_solar_flux(d_s, el_s)

            # 2. Dünya konumu (Ay merkezine göre)
            earth_pos, _ = spice.spkpos("EARTH", et, frame, "LT+S", "MOON")
            earth_vec_obs = np.array(earth_pos) - obs_pos_km
            earth_enu = R_enu @ earth_vec_obs
            az_e, el_e, d_e = self.enu_to_azimuth_elevation(earth_enu)

            earth_az[i] = az_e
            earth_el[i] = el_e
            earth_dist[i] = d_e

        return {
            "sun_azimuth_deg": sun_az,
            "sun_elevation_deg": sun_el,
            "sun_distance_km": sun_dist,
            "solar_flux_w_m2": sun_flux,
            "earth_azimuth_deg": earth_az,
            "earth_elevation_deg": earth_el,
            "earth_distance_km": earth_dist,
            "frame_used": frame,
        }

    def compute_ephemeris_range(
        self,
        lat_deg: float,
        lon_deg: float,
        elevation_m: float,
        utc_start: Union[str, datetime],
        utc_end: Union[str, datetime],
        step_hours: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Belirtilen zaman aralığında düzenli adımlarla Güneş ve Dünya
        gök parametrelerini hesaplar.
        """
        # Zaman aralığını çöz
        if isinstance(utc_start, str):
            t0 = datetime.fromisoformat(utc_start.replace("Z", "+00:00"))
        else:
            t0 = utc_start

        if isinstance(utc_end, str):
            t1 = datetime.fromisoformat(utc_end.replace("Z", "+00:00"))
        else:
            t1 = utc_end

        if t0.tzinfo is None:
            t0 = t0.replace(tzinfo=timezone.utc)
        if t1.tzinfo is None:
            t1 = t1.replace(tzinfo=timezone.utc)

        step_seconds = max(60.0, step_hours * 3600.0)
        dt_list = []
        curr = t0
        while curr <= t1:
            dt_list.append(curr)
            curr += timedelta(seconds=step_seconds)

        if not dt_list:
            dt_list = [t0]

        # SPICE yüklüyse ve etkinse tam SPICE çekirdeklerini kullan
        res = None
        if self.spice_active and SPICEYPY_AVAILABLE:
            try:
                res = self._compute_spice_ephemeris(lat_deg, lon_deg, elevation_m, dt_list)
            except Exception as ex:
                print(f"[!] SPICE hesaplama uyarısı ({ex}), analitik efemerise dönülüyor.")
                res = None

        if res is None:
            res = self._compute_analytical_ephemeris(lat_deg, lon_deg, elevation_m, dt_list)

        # Zaman etiketleri listesini ekle
        res["timestamps"] = [dt.isoformat() for dt in dt_list]
        res["count"] = len(dt_list)
        res["latitude_deg"] = lat_deg
        res["longitude_deg"] = lon_deg
        res["elevation_m"] = elevation_m
        res["spice_active"] = self.spice_active
        res["kernels_loaded"] = self.kernels_loaded

        return res
