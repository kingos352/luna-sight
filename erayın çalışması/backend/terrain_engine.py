"""
backend/terrain_engine.py
=========================
Haritalandırma ve Arazi Analiz Motoru (Lunar Terrain Analysis Engine).

Özellikler:
1. data/dem/ altındaki LRO LOLA GeoTIFF yükseklik verisini okur (dosya yoksa
   sentetik Güney Kutbu krater modelini otomatik oluşturur).
2. Ham yükseklik matrisinden tamamen bağımsız olarak hesaplar:
   - Eğim (Slope, Horn algoritması ile derece cinsinden)
   - Yüzey Pürüzlülüğü / TRI (Terrain Ruggedness Index, metre cinsinden)
   - 360° Ufuk Yükselme Maskesi (Horizon Ray-Casting & azimut bazlı tepe engel açıları)
3. Orbital motor çıktılarıyla ufuk maskesini birleştirerek:
   - Güneşlenme Yüzdesi (Solar Illumination %)
   - Doğrudan Dünya Görüş Hattı (DTE Line-of-Sight %)
   - Çok Kriterli İniş Uygunluk Skoru (Landing Suitability Index, 0-100)
   katmanlarını piksel bazında üretir ve önbelleğe alır.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from backend.config import (
    DEFAULT_DEM_PATH,
    DEM_DIR,
    MAX_LANDING_SLOPE_DEG,
    ACCEPTABLE_SLOPE_DEG,
    LUNAR_MEAN_RADIUS_M,
)
from backend.orbital_engine import OrbitalEngine

# Rasterio kontrolü
try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    rasterio = None  # type: ignore
    RASTERIO_AVAILABLE = False


class TerrainEngine:
    """
    Yerel Ay Sayısal Yükseklik Modeli (DEM) işleme,
    morfoloji türetme ve iniş kriteri değerlendirme motoru.
    """

    _region_cache: Dict[str, "TerrainEngine"] = {}

    def __init__(
        self,
        dem_path: Optional[Union[str, Path]] = None,
        pixel_size_m: float = 40.0,
        center_lat: float = -89.75,
        center_lon: float = 0.0,
        region_id: Optional[str] = None,
    ):
        self.dem_path = Path(dem_path or DEFAULT_DEM_PATH)
        self.pixel_size_m = pixel_size_m
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.region_id = region_id

        # Yükseklik ve katman önbellekleri
        self.elevation: Optional[np.ndarray] = None
        self.slope: Optional[np.ndarray] = None
        self.roughness: Optional[np.ndarray] = None
        self.horizon_mask: Optional[np.ndarray] = None  # shape (n_azimuth, H, W)
        self.azimuth_angles_deg: np.ndarray = np.linspace(0, 360, 36, endpoint=False)  # Her 10°

        # Dinamik analiz katmanları (zaman aralığına bağlı)
        self.illumination_pct: Optional[np.ndarray] = None
        self.dte_pct: Optional[np.ndarray] = None
        self.suitability_score: Optional[np.ndarray] = None
        self.last_sim_params: Optional[Dict[str, Any]] = None

        # DEM'i yükle veya oluştur
        self.load_or_generate_dem()

    @classmethod
    def get_engine_for_region(cls, region_id: Optional[str] = None) -> "TerrainEngine":
        """Belirtilen bölge ID'si için önbellekten veya diskten TerrainEngine örneğini döner."""
        if not region_id or region_id.upper() in ("DEFAULT", "SHACKLETON"):
            key = "DEFAULT"
            if key not in cls._region_cache:
                cls._region_cache[key] = TerrainEngine(dem_path=DEFAULT_DEM_PATH, region_id="DEFAULT")
            return cls._region_cache[key]

        reg_key = region_id.upper().strip()
        if reg_key in cls._region_cache:
            return cls._region_cache[reg_key]

        from backend.config import REGIONS_DIR, SHACKLETON_DEM_PATH

        # Shackleton Ultra-HD sahaları
        if reg_key in ("SITE_ALPHA", "SITE_BETA", "SITE_GAMMA", "SITE_DELTA") and SHACKLETON_DEM_PATH.exists():
            engine = TerrainEngine(dem_path=SHACKLETON_DEM_PATH, region_id=reg_key)
            cls._region_cache[reg_key] = engine
            return engine

        # Bölgesel NASA LOLA DEM GeoTIFF
        tif_candidate = REGIONS_DIR / f"{reg_key}.tif"
        if tif_candidate.exists():
            engine = TerrainEngine(dem_path=tif_candidate, region_id=reg_key)
            cls._region_cache[reg_key] = engine
            return engine

        # Dosya bulunamazsa varsayılan DEM
        engine = TerrainEngine(dem_path=DEFAULT_DEM_PATH, region_id=reg_key)
        cls._region_cache[reg_key] = engine
        return engine

    def load_or_generate_dem(self) -> None:
        """DEM dosyasını yükler, yoksa sentetik kraterli DEM üretir."""
        if self.dem_path.exists() and self.dem_path.stat().st_size > 0:
            try:
                if RASTERIO_AVAILABLE and self.dem_path.suffix.lower() in {".tif", ".tiff"}:
                    with rasterio.open(self.dem_path) as src:
                        self.elevation = src.read(1).astype(np.float32)
                        # Metadata oku
                        tags = src.tags()
                        if "PIXEL_SIZE_M" in tags:
                            self.pixel_size_m = float(tags["PIXEL_SIZE_M"])
                        if "CENTER_LAT" in tags:
                            self.center_lat = float(tags["CENTER_LAT"])
                        if "CENTER_LON" in tags:
                            self.center_lon = float(tags["CENTER_LON"])
                        print(f"[+] DEM yüklendi (Rasterio): {self.elevation.shape}")
                        self._compute_base_layers()
                        return
                elif self.dem_path.suffix.lower() == ".npy":
                    self.elevation = np.load(self.dem_path).astype(np.float32)
                    self._compute_base_layers()
                    return
            except Exception as e:
                print(f"[!] DEM yüklenirken hata oluştu ({e}), sentetik veri oluşturuluyor.")

        # Dosya yoksa veya yüklenemediyse sentetik veri üret
        self._generate_synthetic_internal()
        self._compute_base_layers()

    def _generate_synthetic_internal(self, width: int = 256, height: int = 256) -> None:
        """LRO LOLA standardında sentetik Ay Güney Kutbu topografyası üretir."""
        from scripts.generate_synthetic_dem import generate_lunar_dem_array, save_dem_geotiff

        elev, meta = generate_lunar_dem_array(
            width=width, height=height, pixel_size_m=self.pixel_size_m
        )
        self.elevation = elev
        self.center_lat = meta["center_lat"]
        self.center_lon = meta["center_lon"]
        self.pixel_size_m = meta["pixel_size_m"]

        # Diske kaydet
        save_dem_geotiff(
            self.elevation,
            self.dem_path,
            pixel_size_m=self.pixel_size_m,
            center_lat=self.center_lat,
            center_lon=self.center_lon,
        )

    def _compute_base_layers(self) -> None:
        """Eğim (Slope) ve Pürüzlülük (Roughness / TRI) katmanlarını hesaplar."""
        if self.elevation is None:
            return

        self.slope = self.compute_slope_horn(self.elevation, self.pixel_size_m)
        self.roughness = self.compute_roughness_tri(self.elevation)
        # Horizon ray-casting maskesini hesapla (200 piksel = 12 km menzil)
        self.compute_horizon_mask(num_azimuths=36, max_radius_pixels=200)

    @staticmethod
    def compute_slope_horn(dem: np.ndarray, cell_size_m: float) -> np.ndarray:
        """
        Horn (1981) 3x3 komşuluk algoritmasıyla her pikselin eğimini
        (derece cinsinden) hesaplar.
        """
        h, w = dem.shape
        # Pad ile kenar etkilerini güvenli yönet
        padded = np.pad(dem, 1, mode="edge")

        # 8-yollu komşular:
        # z1(NW) z2(N) z3(NE)
        # z4(W)  z0    z5(E)
        # z6(SW) z7(S) z8(SE)
        z1 = padded[0:h, 0:w]
        z2 = padded[0:h, 1:w+1]
        z3 = padded[0:h, 2:w+2]

        z4 = padded[1:h+1, 0:w]
        z5 = padded[1:h+1, 2:w+2]

        z6 = padded[2:h+2, 0:w]
        z7 = padded[2:h+2, 1:w+1]
        z8 = padded[2:h+2, 2:w+2]

        # Gradyanlar (Horn ağırlıklı türevler)
        dz_dx = ((z3 + 2.0 * z5 + z8) - (z1 + 2.0 * z4 + z6)) / (8.0 * cell_size_m)
        dz_dy = ((z6 + 2.0 * z7 + z8) - (z1 + 2.0 * z2 + z3)) / (8.0 * cell_size_m)

        slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
        slope_deg = np.degrees(slope_rad).astype(np.float32)
        return slope_deg

    @staticmethod
    def compute_roughness_tri(dem: np.ndarray) -> np.ndarray:
        """
        Terrain Ruggedness Index (TRI - Riley et al. 1999).
        Her pikselin 8 komşusuyla kot farklarının karekök ortalamasını hesaplar.
        """
        h, w = dem.shape
        padded = np.pad(dem, 1, mode="edge")

        center = dem
        diff_sq_sum = np.zeros((h, w), dtype=np.float32)

        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                neighbor = padded[1 + dy : h + 1 + dy, 1 + dx : w + 1 + dx]
                diff_sq_sum += (neighbor - center) ** 2

        tri = np.sqrt(diff_sq_sum / 8.0).astype(np.float32)
        return tri

    def compute_horizon_mask(
        self,
        num_azimuths: int = 36,
        max_radius_pixels: int = 64,
        apply_curvature: bool = True,
    ) -> np.ndarray:
        """
        360° Ufuk Yükselme Maskesi (Horizon Ray-Casting Algoritması).
        Her pikselden num_azimuths farklı yönde çevre sırtların oluşturduğu
        maksimum ufuk yükselme açısını (alfa, derece cinsinden) hesaplar.
        apply_curvature=True olduğunda Ay küresel eğrilik düzeltmesi
        z_eff = z - r^2 / (2 * R_Moon) uygulanır.
        Çıktı shape: (num_azimuths, H, W)
        """
        if self.elevation is None:
            raise ValueError("DEM henüz yüklenmedi.")

        dem = self.elevation
        h, w = dem.shape
        self.azimuth_angles_deg = np.linspace(0, 360, num_azimuths, endpoint=False)
        horizon_mask = np.zeros((num_azimuths, h, w), dtype=np.float32)

        cell_m = self.pixel_size_m
        r_moon_m = LUNAR_MEAN_RADIUS_M

        if max_radius_pixels <= 50:
            steps = np.arange(1, max_radius_pixels + 1, dtype=np.float32)
        else:
            steps = np.concatenate([
                np.arange(1, 40, 1, dtype=np.float32),
                np.arange(40, max_radius_pixels + 1, 3, dtype=np.float32)
            ])

        # Matris koordinatları: Y (Satır, Kuzeyden Güneye azalır), X (Sütun, Batıdan Doğuya artar)
        # Azimut: 0° Kuzey (-Y yönü), 90° Doğu (+X), 180° Güney (+Y), 270° Batı (-X)
        for az_idx, az_deg in enumerate(self.azimuth_angles_deg):
            az_rad = math.radians(az_deg)
            # İlerleme birim adımları (piksel)
            step_x = math.sin(az_rad)
            step_y = -math.cos(az_rad)

            max_tan_alpha = np.zeros((h, w), dtype=np.float32)

            for step in steps:
                dx = int(round(step * step_x))
                dy = int(round(step * step_y))
                if dx == 0 and dy == 0:
                    continue

                dist_m = math.sqrt(dx**2 + dy**2) * cell_m
                if dist_m < 1e-3:
                    continue

                # Kaydırılmış komşu kotları (sınır dışı pikseller kenar değerini korur)
                # dy satır kaydırma, dx sütun kaydırma
                shifted = np.roll(dem, shift=(-dy, -dx), axis=(0, 1))

                # Kenar taşmalarını sıfır/kenar yap
                if dy > 0:
                    shifted[-dy:, :] = dem[-1:, :]
                elif dy < 0:
                    shifted[:-dy, :] = dem[:1, :]

                if dx > 0:
                    shifted[:, -dx:] = dem[:, -1:]
                elif dx < 0:
                    shifted[:, :-dx] = dem[:, :1]

                # Ay küresel eğrilik düzeltmesi: z_eff = z - r^2 / (2 * R_Moon)
                if apply_curvature:
                    curv_drop = (dist_m ** 2) / (2.0 * r_moon_m)
                    eff_shifted = shifted - curv_drop
                else:
                    eff_shifted = shifted

                tan_alpha = (eff_shifted - dem) / dist_m
                max_tan_alpha = np.maximum(max_tan_alpha, tan_alpha)

            # Açıya dönüştür (derece)
            horizon_mask[az_idx] = np.degrees(np.arctan(np.maximum(0.0, max_tan_alpha)))

        self.horizon_mask = horizon_mask
        return horizon_mask

    def compute_horizon_elevation(
        self,
        y: int,
        x: int,
        azimuth_deg: float,
        apply_curvature: bool = True,
        max_radius_pixels: int = 64,
    ) -> float:
        """
        Belirtilen (y, x) pikselinde ve azimut açısında Ay küresel eğrilik düzeltmeli
        doğrudan ray-casting ufuk yükselme açısını (derece) hesaplar.
        """
        if self.elevation is None:
            raise ValueError("DEM henüz yüklenmedi.")

        dem = self.elevation
        h, w = dem.shape
        if not (0 <= y < h and 0 <= x < w):
            return 0.0

        z0 = float(dem[y, x])
        az_rad = math.radians(azimuth_deg)
        step_x = math.sin(az_rad)
        step_y = -math.cos(az_rad)

        cell_m = self.pixel_size_m
        r_moon_m = LUNAR_MEAN_RADIUS_M
        max_tan_alpha = 0.0

        for r_step in range(1, max_radius_pixels + 1):
            px = int(round(x + r_step * step_x))
            py = int(round(y + r_step * step_y))
            if not (0 <= py < h and 0 <= px < w):
                break

            dist_m = math.sqrt((px - x)**2 + (py - y)**2) * cell_m
            if dist_m < 1e-3:
                continue

            z_target = float(dem[py, px])
            if apply_curvature:
                z_eff = z_target - (dist_m ** 2) / (2.0 * r_moon_m)
            else:
                z_eff = z_target

            tan_alpha = (z_eff - z0) / dist_m
            if tan_alpha > max_tan_alpha:
                max_tan_alpha = tan_alpha

        return float(math.degrees(math.atan(max(0.0, max_tan_alpha))))

    def get_horizon_elevation_at(self, y: int, x: int, azimuth_deg: float) -> float:
        """Belirtilen piksel ve azimut yönündeki ufuk engel açısını döndürür."""
        if self.horizon_mask is None:
            self.compute_horizon_mask(apply_curvature=True)
            assert self.horizon_mask is not None

        norm_az = azimuth_deg % 360.0
        step_az = 360.0 / len(self.azimuth_angles_deg)
        idx0 = int(norm_az // step_az) % len(self.azimuth_angles_deg)
        idx1 = (idx0 + 1) % len(self.azimuth_angles_deg)
        frac = (norm_az - (idx0 * step_az)) / step_az

        val0 = self.horizon_mask[idx0, y, x]
        val1 = self.horizon_mask[idx1, y, x]
        return float((1.0 - frac) * val0 + frac * val1)

    def simulate_temporal_layers(
        self,
        orbital_results: Dict[str, Any],
    ) -> Dict[str, np.ndarray]:
        """
        Orbital motorun zaman serisi açıları (Güneş & Dünya azimut/elevation) ile
        360° ufuk maskesini birleştirerek piksel bazında:
        - Solar Illumination % (Güneşlenme Süresi Yüzdesi)
        - DTE Line-of-Sight % (Dünya ile Doğrudan Görüş Hattı Yüzdesi)
        - Çok Kriterli İniş Uygunluk Skoru (0-100)
        hesaplar.
        """
        if self.elevation is None or self.horizon_mask is None or self.slope is None or self.roughness is None:
            self._compute_base_layers()
            assert self.elevation is not None and self.horizon_mask is not None and self.slope is not None and self.roughness is not None

        h, w = self.elevation.shape
        num_az = len(self.azimuth_angles_deg)
        step_az = 360.0 / num_az

        sun_az_arr = np.asarray(orbital_results["sun_azimuth_deg"])
        sun_el_arr = np.asarray(orbital_results["sun_elevation_deg"])
        earth_az_arr = np.asarray(orbital_results["earth_azimuth_deg"])
        earth_el_arr = np.asarray(orbital_results["earth_elevation_deg"])

        num_steps = len(sun_az_arr)
        if num_steps == 0:
            raise ValueError("Zaman serisi adımı boş.")

        solar_lit_count = np.zeros((h, w), dtype=np.float32)
        dte_visible_count = np.zeros((h, w), dtype=np.float32)

        for t in range(num_steps):
            s_az = sun_az_arr[t] % 360.0
            s_el = sun_el_arr[t]
            e_az = earth_az_arr[t] % 360.0
            e_el = earth_el_arr[t]

            # 1. Güneşlenme kontrolü
            if s_el > 0.0:
                s_idx = int(round(s_az / step_az)) % num_az
                horizon_s = self.horizon_mask[s_idx]
                lit = s_el > horizon_s
                solar_lit_count += lit.astype(np.float32)

            # 2. Dünya görüş hattı kontrolü
            if e_el > 0.0:
                e_idx = int(round(e_az / step_az)) % num_az
                horizon_e = self.horizon_mask[e_idx]
                dte = e_el > horizon_e
                dte_visible_count += dte.astype(np.float32)

        illumination_pct = (solar_lit_count / num_steps) * 100.0
        dte_pct = (dte_visible_count / num_steps) * 100.0

        # 3. İniş Uygunluk Skoru (Suitability Score, 0 - 100)
        # Eğim skoru: slope <= 5° -> 1.0; 5° < slope <= 12° -> lineer düşüş; > 12° -> 0 (güvenlik kısıtı)
        slope_score = np.zeros_like(self.slope)
        mask_safe = self.slope <= MAX_LANDING_SLOPE_DEG
        mask_accept = (self.slope > MAX_LANDING_SLOPE_DEG) & (self.slope <= ACCEPTABLE_SLOPE_DEG)

        slope_score[mask_safe] = 1.0
        slope_score[mask_accept] = 1.0 - (
            (self.slope[mask_accept] - MAX_LANDING_SLOPE_DEG)
            / (ACCEPTABLE_SLOPE_DEG - MAX_LANDING_SLOPE_DEG)
        )

        # Pürüzlülük skoru: TRI arttıkça skor üssel azalır
        rough_score = np.exp(-self.roughness / 1.5).astype(np.float32)

        # Aydınlanma ve DTE skorları (0 - 1)
        illum_score = (illumination_pct / 100.0).astype(np.float32)
        dte_score = (dte_pct / 100.0).astype(np.float32)

        # Ağırlıklı birleşim: %35 Eğim, %25 Pürüzlülük, %20 Güneşlenme, %20 DTE
        combined = (
            0.35 * slope_score
            + 0.25 * rough_score
            + 0.20 * illum_score
            + 0.20 * dte_score
        )

        # Eğim kritik sınırı aşarsa skor 0 olur
        combined[self.slope > ACCEPTABLE_SLOPE_DEG] = 0.0
        suitability_score = (np.clip(combined, 0.0, 1.0) * 100.0).astype(np.float32)

        self.illumination_pct = illumination_pct
        self.dte_pct = dte_pct
        self.suitability_score = suitability_score

        return {
            "illumination_pct": illumination_pct,
            "dte_pct": dte_pct,
            "suitability_score": suitability_score,
        }

    def get_mesh_data(self, target_resolution: int = 128) -> Dict[str, Any]:
        """
        Frontend 3B Three.js sahnesi için optimize edilmiş indirgenmiş yükseklik
        matrisi, sınır ve ölçek parametrelerini döndürür.
        """
        if self.elevation is None:
            self.load_or_generate_dem()
            assert self.elevation is not None

        h, w = self.elevation.shape
        step_y = max(1, h // target_resolution)
        step_x = max(1, w // target_resolution)

        sub_elevation = self.elevation[::step_y, ::step_x]
        sub_h, sub_w = sub_elevation.shape

        real_width_m = w * self.pixel_size_m
        real_height_m = h * self.pixel_size_m

        return {
            "region_id": self.region_id or "DEFAULT",
            "width": sub_w,
            "height": sub_h,
            "original_width": w,
            "original_height": h,
            "pixel_size_m": self.pixel_size_m,
            "real_size_x_m": real_width_m,
            "real_size_y_m": real_height_m,
            "center_lat": self.center_lat,
            "center_lon": self.center_lon,
            "elev_min": float(np.min(self.elevation)),
            "elev_max": float(np.max(self.elevation)),
            "elevation_matrix": sub_elevation.tolist(),
        }

    def get_layers_dict(self, target_resolution: int = 128) -> Dict[str, Any]:
        """Tüm katmanları indirgenmiş çözünürlükte sözlük olarak sunar."""
        if self.elevation is None or self.slope is None:
            self._compute_base_layers()

        # Eğer dinamik katmanlar henüz hesaplanmadıysa varsayılan 24 saatlik döngü ile hesapla
        if self.suitability_score is None:
            engine = OrbitalEngine()
            now = "2026-11-15T00:00:00Z"
            end = "2026-11-16T00:00:00Z"
            res = engine.compute_ephemeris_range(
                self.center_lat, self.center_lon, 0.0, now, end, step_hours=1.0
            )
            self.simulate_temporal_layers(res)

        h, w = self.elevation.shape
        step_y = max(1, h // target_resolution)
        step_x = max(1, w // target_resolution)

        return {
            "region_id": self.region_id or "DEFAULT",
            "width": w // step_x,
            "height": h // step_y,
            "elevation": self.elevation[::step_y, ::step_x].tolist(),
            "slope": self.slope[::step_y, ::step_x].tolist(),
            "roughness": self.roughness[::step_y, ::step_x].tolist(),
            "illumination": self.illumination_pct[::step_y, ::step_x].tolist(),
            "dte": self.dte_pct[::step_y, ::step_x].tolist(),
            "suitability": self.suitability_score[::step_y, ::step_x].tolist(),
            "stats": {
                "elev_min": float(np.min(self.elevation)),
                "elev_max": float(np.max(self.elevation)),
                "slope_mean": float(np.mean(self.slope)),
                "slope_max": float(np.max(self.slope)),
                "roughness_mean": float(np.mean(self.roughness)),
                "illumination_mean": float(np.mean(self.illumination_pct)),
                "dte_mean": float(np.mean(self.dte_pct)),
                "suitability_mean": float(np.mean(self.suitability_score)),
            },
        }

    def inspect_point(
        self, norm_x: float, norm_y: float, orbital_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Kullanıcının 3B sahnede tıkladığı normalize edilmiş (0-1) koordinat için
        detaylı topografik ve zaman serisi iniş metriklerini döndürür.
        norm_x: 0 (Batı) ile 1 (Doğu) arası
        norm_y: 0 (Kuzey) ile 1 (Güney) arası
        """
        if self.elevation is None or self.slope is None or self.roughness is None:
            self._compute_base_layers()

        h, w = self.elevation.shape
        px = int(np.clip(round(norm_x * (w - 1)), 0, w - 1))
        py = int(np.clip(round(norm_y * (h - 1)), 0, h - 1))

        elev = float(self.elevation[py, px])
        slope_val = float(self.slope[py, px])
        rough_val = float(self.roughness[py, px])

        # Zaman serisi gölge ve görüş hattı analizi
        sun_az_arr = np.asarray(orbital_results["sun_azimuth_deg"])
        sun_el_arr = np.asarray(orbital_results["sun_elevation_deg"])
        earth_az_arr = np.asarray(orbital_results["earth_azimuth_deg"])
        earth_el_arr = np.asarray(orbital_results["earth_elevation_deg"])
        timestamps = orbital_results["timestamps"]

        time_series = []
        lit_steps = 0
        dte_steps = 0

        for t in range(len(timestamps)):
            s_az = float(sun_az_arr[t])
            s_el = float(sun_el_arr[t])
            e_az = float(earth_az_arr[t])
            e_el = float(earth_el_arr[t])

            horiz_s = self.get_horizon_elevation_at(py, px, s_az)
            horiz_e = self.get_horizon_elevation_at(py, px, e_az)

            is_lit = (s_el > 0.0) and (s_el > horiz_s)
            is_dte = (e_el > 0.0) and (e_el > horiz_e)

            if is_lit:
                lit_steps += 1
            if is_dte:
                dte_steps += 1

            flux = OrbitalEngine.calculate_solar_flux(
                orbital_results["sun_distance_km"][t], s_el if is_lit else 0.0
            )

            time_series.append({
                "time": timestamps[t],
                "sun_azimuth": round(s_az, 2),
                "sun_elevation": round(s_el, 2),
                "horizon_elevation_sun": round(horiz_s, 2),
                "is_lit": is_lit,
                "solar_flux": round(float(flux), 1),
                "earth_azimuth": round(e_az, 2),
                "earth_elevation": round(e_el, 2),
                "horizon_elevation_earth": round(horiz_e, 2),
                "is_dte": is_dte,
            })

        n_steps = max(1, len(timestamps))
        illum_pct = (lit_steps / n_steps) * 100.0
        dte_pct = (dte_steps / n_steps) * 100.0

        # Uygunluk skoru
        s_slope = 1.0 if slope_val <= MAX_LANDING_SLOPE_DEG else max(0.0, 1.0 - (slope_val - 5.0) / 7.0)
        s_rough = math.exp(-rough_val / 1.5)
        s_score = 0.0 if slope_val > ACCEPTABLE_SLOPE_DEG else (
            (0.35 * s_slope + 0.25 * s_rough + 0.20 * (illum_pct / 100.0) + 0.20 * (dte_pct / 100.0)) * 100.0
        )

        return {
            "pixel_x": px,
            "pixel_y": py,
            "norm_x": norm_x,
            "norm_y": norm_y,
            "elevation_m": round(elev, 1),
            "slope_deg": round(slope_val, 2),
            "roughness_m": round(rough_val, 3),
            "illumination_pct": round(illum_pct, 1),
            "dte_pct": round(dte_pct, 1),
            "suitability_score": round(s_score, 1),
            "status": "EXCELLENT" if s_score >= 80 else ("ACCEPTABLE" if s_score >= 50 else "UNSAFE"),
            "time_series": time_series,
        }
