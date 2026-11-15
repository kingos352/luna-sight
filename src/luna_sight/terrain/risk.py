"""LunarSight — Arazi Riski Analizi.

Bu modül, LOLA DEM verisinden arazi riski metriklerini hesaplar:
- Yerel eğim açısı (derece) ve istatistikleri
- Krater yoğunluğu ve en yakın krater uzaklığı
- Analiz alanları için yan yana metrik karşılaştırması

Gerçek DEM (GeoTIFF) mevcutsa ondan hesaplar; yoksa temsili model
üzerinden "gerçek arazi verisi bekleniyor" uyarısı ile analiz yapmaz.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from luna_sight.terrain.dem import DemGrid, load_lola_dem
from luna_sight.terrain.polar import R_MOON_M
from luna_sight.terrain.sites import CANDIDATE_SITES, CandidateSite
from luna_sight.terrain.surface_3d import IAU_CRATERS

# ─── Sabitler ───

RISK_SOURCE_REAL = "real_dem"
RISK_SOURCE_REPRESENTATIVE = "representative_model"
RISK_SOURCE_MISSING = "missing"

DEFAULT_ANALYSIS_RADIUS_M = 5000.0  # 5 km analiz yarıçapı
DEFAULT_SLOPE_WINDOW_M = 100.0  # Eğim penceresi (100 m)

# ─── Veri Sınıfları ───


@dataclass(frozen=True)
class SlopeStats:
    """Eğim istatistikleri (derece cinsinden)."""

    mean_deg: float
    max_deg: float
    median_deg: float
    std_deg: float
    p95_deg: float
    fraction_above_5deg: float
    fraction_above_10deg: float
    fraction_above_15deg: float
    fraction_above_20deg: float
    valid_fraction: float  # geçerli piksel oranı

    def as_dict(self) -> dict[str, object]:
        return {
            "mean_deg": round(self.mean_deg, 3),
            "max_deg": round(self.max_deg, 3),
            "median_deg": round(self.median_deg, 3),
            "std_deg": round(self.std_deg, 3),
            "p95_deg": round(self.p95_deg, 3),
            "fraction_above_5deg": round(self.fraction_above_5deg, 4),
            "fraction_above_10deg": round(self.fraction_above_10deg, 4),
            "fraction_above_15deg": round(self.fraction_above_15deg, 4),
            "fraction_above_20deg": round(self.fraction_above_20deg, 4),
            "valid_fraction": round(self.valid_fraction, 4),
        }


@dataclass(frozen=True)
class CraterMetrics:
    """Krater metrikleri."""

    density_per_km2: float
    nearest_crater_distance_m: float
    nearest_crater_name: str
    nearest_crater_diameter_km: float
    craters_in_radius_count: int
    crater_catalog_used: str

    def as_dict(self) -> dict[str, object]:
        return {
            "density_per_km2": round(self.density_per_km2, 4),
            "nearest_crater_distance_m": round(self.nearest_crater_distance_m, 1),
            "nearest_crater_name": self.nearest_crater_name,
            "nearest_crater_diameter_km": round(self.nearest_crater_diameter_km, 2),
            "craters_in_radius_count": self.craters_in_radius_count,
            "crater_catalog_used": self.crater_catalog_used,
        }


@dataclass(frozen=True)
class SiteRiskMetrics:
    """Tek bir site için arazi riski metrikleri."""

    site_id: str
    site_name: str
    latitude_deg: float
    longitude_deg_east: float
    analysis_radius_m: float

    slope: SlopeStats
    crater: CraterMetrics

    dem_source: str  # "real_dem" | "representative_model" | "missing"
    dem_metadata: dict[str, object] | None
    dem_available: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "site_id": self.site_id,
            "site_name": self.site_name,
            "latitude_deg": round(self.latitude_deg, 6),
            "longitude_deg_east": round(self.longitude_deg_east, 6),
            "analysis_radius_m": self.analysis_radius_m,
            "slope": self.slope.as_dict(),
            "crater": self.crater.as_dict(),
            "dem_source": self.dem_source,
            "dem_metadata": self.dem_metadata,
            "dem_available": self.dem_available,
        }


# ─── Yardımcı Fonksiyonlar ───


def _find_dem_paths(site_id: str) -> tuple[Path | None, Path | None, Path | None]:
    """Site için DEM, LDEC ve toterr dosya yollarını bulur."""
    repo_cache = Path(__file__).resolve().parents[3] / "data" / "cache" / "lola"
    cwd_cache = Path("data/cache/lola")
    cache_root = repo_cache if repo_cache.exists() else cwd_cache
    surf = cache_root / f"{site_id}_final_adj_5mpp_surf.tif"
    ldec = cache_root / f"{site_id}_final_adj_5mpp_ldec.tif"
    toterr = cache_root / f"{site_id}_final_adj_5mpp_toterr.tif"
    return (
        surf if surf.exists() else None,
        ldec if ldec.exists() else None,
        toterr if toterr.exists() else None,
    )


def _load_site_dem(site: CandidateSite) -> DemGrid | None:
    """Site için DEM yükler; dosya yoksa None döner."""
    surf_path, ldec_path, toterr_path = _find_dem_paths(site.site_id)
    if surf_path is None:
        return None
    try:
        return load_lola_dem(
            surface_path=surf_path,
            ldec_path=ldec_path if ldec_path else None,
            toterr_path=toterr_path if toterr_path else None,
            site_name=site.site_name,
        )
    except Exception:
        return None


def _compute_slope_map(dem: DemGrid) -> tuple[np.ndarray, np.ndarray]:
    """DEM'den eğim haritası (derece) ve geçerlilik maskesi üretir.

    Merkezi farklar (central differences) ile gradyan hesaplanır:
        slope = atan(sqrt((dz/dx)^2 + (dz/dy)^2)) * 180/pi

    Dönen: (slope_deg, valid_mask)
    """
    heights = dem.heights_m
    pixel_size = dem.pixel_size_m

    if pixel_size <= 0:
        raise ValueError("Geçersiz piksel boyutu")

    # Merkezi farklar
    dzdx = np.gradient(heights, axis=1) / pixel_size
    dzdy = np.gradient(heights, axis=0) / pixel_size

    slope_rad = np.arctan(np.hypot(dzdx, dzdy))
    slope_deg = np.degrees(slope_rad)

    # Geçerlilik maskesi: DEM geçerli ve gradyan hesaplanabilir
    valid = dem.valid & np.isfinite(slope_deg)
    return slope_deg, valid


def _sample_circular_region(
    array: np.ndarray,
    valid: np.ndarray,
    dem: DemGrid,
    center_x_m: float,
    center_y_m: float,
    radius_m: float,
) -> tuple[np.ndarray, int]:
    """DEM ızgarasında belirli bir merkez ve yarıçapta dairesel bölgeyi keser.

    Dönen: (valid_values, total_pixels_in_circle)
    """
    # `to_center_indices` 0-tabanlı piksel merkez indekslerini döndürür (-0.5 uygulanmış).
    col_c_raw, row_c_raw = dem.to_center_indices(center_x_m, center_y_m)
    col_c = float(np.asarray(col_c_raw).item())
    row_c = float(np.asarray(row_c_raw).item())

    pixel_size = dem.pixel_size_m
    radius_px = int(np.ceil(radius_m / pixel_size)) + 1

    rows, cols = array.shape
    r_min = max(0, int(np.floor(row_c - radius_px)))
    r_max = min(rows, int(np.ceil(row_c + radius_px)) + 1)
    c_min = max(0, int(np.floor(col_c - radius_px)))
    c_max = min(cols, int(np.ceil(col_c + radius_px)) + 1)

    if r_min >= r_max or c_min >= c_max:
        return np.array([], dtype=float), 0

    sub_arr = array[r_min:r_max, c_min:c_max]
    sub_val = valid[r_min:r_max, c_min:c_max]

    yy, xx = np.ogrid[: sub_arr.shape[0], : sub_arr.shape[1]]
    cy = row_c - r_min
    cx = col_c - c_min
    dist_px = np.hypot(yy - cy, xx - cx)
    circle_mask = dist_px <= (radius_m / pixel_size)

    total_pixels = int(np.count_nonzero(circle_mask))
    if total_pixels == 0:
        return np.array([], dtype=float), 0

    vals = sub_arr[circle_mask & sub_val]
    return vals, total_pixels


def compute_slope_stats(
    dem: DemGrid,
    center_x_m: float,
    center_y_m: float,
    radius_m: float = DEFAULT_ANALYSIS_RADIUS_M,
) -> SlopeStats:
    """Analiz bölgesi içindeki eğim istatistiklerini hesaplar."""
    slope_deg, valid = _compute_slope_map(dem)
    vals, total_pixels = _sample_circular_region(
        slope_deg, valid, dem, center_x_m, center_y_m, radius_m
    )

    if total_pixels == 0 or vals.size == 0:
        return SlopeStats(
            mean_deg=np.nan,
            max_deg=np.nan,
            median_deg=np.nan,
            std_deg=np.nan,
            p95_deg=np.nan,
            fraction_above_5deg=0.0,
            fraction_above_10deg=0.0,
            fraction_above_15deg=0.0,
            fraction_above_20deg=0.0,
            valid_fraction=0.0,
        )

    valid_frac = float(vals.size / total_pixels)

    return SlopeStats(
        mean_deg=float(np.mean(vals)),
        max_deg=float(np.max(vals)),
        median_deg=float(np.median(vals)),
        std_deg=float(np.std(vals)),
        p95_deg=float(np.percentile(vals, 95)),
        fraction_above_5deg=float(np.mean(vals > 5.0)),
        fraction_above_10deg=float(np.mean(vals > 10.0)),
        fraction_above_15deg=float(np.mean(vals > 15.0)),
        fraction_above_20deg=float(np.mean(vals > 20.0)),
        valid_fraction=valid_frac,
    )


def _crater_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki nokta arası büyük çember mesafesi (km)."""
    lat1_r, lon1_r = np.radians(lat1), np.radians(lon1)
    lat2_r, lon2_r = np.radians(lat2), np.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    return float(R_MOON_M * c / 1000.0)


def compute_crater_metrics(
    site_lat: float,
    site_lon: float,
    radius_m: float = DEFAULT_ANALYSIS_RADIUS_M,
) -> CraterMetrics:
    """Site çevresindeki krater metriklerini hesaplar (IAU kataloğu kullanarak)."""
    radius_km = radius_m / 1000.0
    area_km2 = np.pi * radius_km**2

    nearest_dist = float("inf")
    nearest_name = ""
    nearest_diam = 0.0
    count_in_radius = 0

    for crater in IAU_CRATERS:
        dist = _crater_distance_km(site_lat, site_lon, crater["lat_deg"], crater["lon_deg"])
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_name = crater["name"]
            nearest_diam = crater["diameter_km"]
        if dist <= radius_km:
            count_in_radius += 1

    density = count_in_radius / area_km2 if area_km2 > 0 else 0.0

    return CraterMetrics(
        density_per_km2=density,
        nearest_crater_distance_m=nearest_dist * 1000.0,
        nearest_crater_name=nearest_name,
        nearest_crater_diameter_km=nearest_diam,
        craters_in_radius_count=count_in_radius,
        crater_catalog_used="IAU_approved (surface_3d.py)",
    )


def analyze_site_risk(
    site: CandidateSite,
    analysis_radius_m: float = DEFAULT_ANALYSIS_RADIUS_M,
) -> SiteRiskMetrics:
    """Tek bir site için tam arazi riski analizi."""
    dem = _load_site_dem(site)

    dem_metadata = None
    dem_available = False
    if dem is not None:
        dem_available = True
        dem_source = RISK_SOURCE_REAL
        if dem.metadata:
            dem_metadata = dem.metadata.as_dict()
        slope_stats = compute_slope_stats(dem, site.x_m, site.y_m, analysis_radius_m)
    else:
        dem_source = RISK_SOURCE_REPRESENTATIVE
        slope_stats = SlopeStats(
            mean_deg=np.nan,
            max_deg=np.nan,
            median_deg=np.nan,
            std_deg=np.nan,
            p95_deg=np.nan,
            fraction_above_5deg=np.nan,
            fraction_above_10deg=np.nan,
            fraction_above_15deg=np.nan,
            fraction_above_20deg=np.nan,
            valid_fraction=0.0,
        )

    # Krater metrikleri (IAU kataloğu her zaman kullanılabilir)
    crater_metrics = compute_crater_metrics(
        site.latitude_deg, site.longitude_deg_east, analysis_radius_m
    )

    return SiteRiskMetrics(
        site_id=site.site_id,
        site_name=site.site_name,
        latitude_deg=site.latitude_deg,
        longitude_deg_east=site.longitude_deg_east,
        analysis_radius_m=analysis_radius_m,
        slope=slope_stats,
        crater=crater_metrics,
        dem_source=dem_source,
        dem_metadata=dem_metadata,
        dem_available=dem_available,
    )


def analyze_all_sites_risk(
    analysis_radius_m: float = DEFAULT_ANALYSIS_RADIUS_M,
) -> dict[str, SiteRiskMetrics]:
    """Tüm aday siteler için arazi riski analizi."""
    return {
        site_id: analyze_site_risk(site, analysis_radius_m)
        for site_id, site in CANDIDATE_SITES.items()
    }


def _fmt_deg(val: float) -> str:
    return "— (DEM bekleniyor)" if np.isnan(val) else f"{val:.2f}°"


def _fmt_pct(val: float) -> str:
    return "— (DEM bekleniyor)" if np.isnan(val) else f"{val:.1%}"


def format_side_by_side_comparison(metrics: dict[str, SiteRiskMetrics]) -> str:
    """İki site için yan yana metrik karşılaştırma metni."""
    if len(metrics) != 2:
        return "Karşılaştırma için tam 2 site gerekli."

    items = list(metrics.values())
    a, b = items[0], items[1]

    a_coord = f"{a.latitude_deg:.4f}°/{a.longitude_deg_east:+.4f}°"
    b_coord = f"{b.latitude_deg:.4f}°/{b.longitude_deg_east:+.4f}°"
    a_rad = f"{a.analysis_radius_m / 1000:.1f} km"
    b_rad = f"{b.analysis_radius_m / 1000:.1f} km"
    a_dem = "Evet" if a.dem_available else "Hayır"
    b_dem = "Evet" if b.dem_available else "Hayır"
    a_dist = f"{a.crater.nearest_crater_distance_m / 1000:.1f} km"
    b_dist = f"{b.crater.nearest_crater_distance_m / 1000:.1f} km"
    a_diam = f"{a.crater.nearest_crater_diameter_km:.1f} km"
    b_diam = f"{b.crater.nearest_crater_diameter_km:.1f} km"

    lines = [
        "=" * 80,
        "LUNAR SIGHT — ARAZİ RİSKİ KARŞILAŞTIRMASI",
        "=" * 80,
        "",
        f"{'Metrik':<35} {a.site_id:<22} {b.site_id:<22}",
        "-" * 80,
        f"{'Site Adı':<35} {a.site_name:<22} {b.site_name:<22}",
        f"{'Koordinatlar':<35} {a_coord:<22} {b_coord:<22}",
        f"{'Analiz Yarıçapı':<35} {a_rad:<22} {b_rad:<22}",
        f"{'DEM Kaynağı':<35} {a.dem_source:<22} {b.dem_source:<22}",
        f"{'DEM Mevcut':<35} {a_dem:<22} {b_dem:<22}",
        "",
        "EĞİM (derece)",
        f"{'  Ortalama':<33} {_fmt_deg(a.slope.mean_deg):<22} {_fmt_deg(b.slope.mean_deg):<22}",
        f"{'  Maksimum':<33} {_fmt_deg(a.slope.max_deg):<22} {_fmt_deg(b.slope.max_deg):<22}",
        f"{'  Medyan':<33} {_fmt_deg(a.slope.median_deg):<22} {_fmt_deg(b.slope.median_deg):<22}",
        f"{'  Std Sapma':<33} {_fmt_deg(a.slope.std_deg):<22} {_fmt_deg(b.slope.std_deg):<22}",
        f"{'  P95':<33} {_fmt_deg(a.slope.p95_deg):<22} {_fmt_deg(b.slope.p95_deg):<22}",
        (
            f"{'  >5° oranı':<33} "
            f"{_fmt_pct(a.slope.fraction_above_5deg):<22} "
            f"{_fmt_pct(b.slope.fraction_above_5deg):<22}"
        ),
        (
            f"{'  >10° oranı':<33} "
            f"{_fmt_pct(a.slope.fraction_above_10deg):<22} "
            f"{_fmt_pct(b.slope.fraction_above_10deg):<22}"
        ),
        (
            f"{'  >15° oranı':<33} "
            f"{_fmt_pct(a.slope.fraction_above_15deg):<22} "
            f"{_fmt_pct(b.slope.fraction_above_15deg):<22}"
        ),
        (
            f"{'  >20° oranı':<33} "
            f"{_fmt_pct(a.slope.fraction_above_20deg):<22} "
            f"{_fmt_pct(b.slope.fraction_above_20deg):<22}"
        ),
        (
            f"{'  Geçerli piksel %':<33} "
            f"{_fmt_pct(a.slope.valid_fraction):<22} "
            f"{_fmt_pct(b.slope.valid_fraction):<22}"
        ),
        "",
        "KRATER METRİKLERİ",
        (
            f"{'  Yoğunluk (adet/km²)':<33} "
            f"{a.crater.density_per_km2:<22.3f} "
            f"{b.crater.density_per_km2:<22.3f}"
        ),
        (
            f"{'  En yakın krater':<33} "
            f"{a.crater.nearest_crater_name:<22} "
            f"{b.crater.nearest_crater_name:<22}"
        ),
        f"{'  En yakın mesafe':<33} {a_dist:<22} {b_dist:<22}",
        f"{'  En yakın çap':<33} {a_diam:<22} {b_diam:<22}",
        (
            f"{'  Analiz alanındaki adet':<33} "
            f"{a.crater.craters_in_radius_count:<22} "
            f"{b.crater.craters_in_radius_count:<22}"
        ),
        (
            f"{'  Kataloğu':<33} "
            f"{a.crater.crater_catalog_used:<22} "
            f"{b.crater.crater_catalog_used:<22}"
        ),
        "",
        "NOTLAR:",
        "- Eğim: 5 m/piksel LOLA DEM'den merkezi farklar ile (central differences)",
        "- Eğim eşikleri: 5°/10°/15°/20° sadece ham ölçüm; güvenli/güvensiz kararı verilmez",
        "- Krater yoğunluğu: IAU onaylı kataloğu (14 krater) kullanılarak",
        "- DEM yoksa eğim hesaplanmaz; gerçek DEM indirilene kadar krater metrikleri sunulur",
        "",
    ]
    return "\n".join(lines)


__all__ = [
    "DEFAULT_ANALYSIS_RADIUS_M",
    "RISK_SOURCE_MISSING",
    "RISK_SOURCE_REAL",
    "RISK_SOURCE_REPRESENTATIVE",
    "CraterMetrics",
    "SiteRiskMetrics",
    "SlopeStats",
    "analyze_all_sites_risk",
    "analyze_site_risk",
    "compute_crater_metrics",
    "compute_slope_stats",
    "format_side_by_side_comparison",
]
