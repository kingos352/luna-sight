"""Topografya ve ufuk profili modülleri (K2).

Girdi örnekleri: LRO/LOLA güney kutup stereografik DEM (PGDA, 5 m/piksel).
Çıktılar: koordinat dönüşümleri, veri boşluğu taraması ve azimut bazlı
topografik ufuk yüksekliği açılarından oluşur.
"""

from luna_sight.terrain.dem import DemGrid, DemMetadata, load_lola_dem
from luna_sight.terrain.gaps import GapReport, scan_coverage
from luna_sight.terrain.horizon import (
    HorizonConfig,
    HorizonProfile,
    compare_radii,
    compute_horizon,
    horizon_from_profile,
)
from luna_sight.terrain.polar import (
    R_MOON_M,
    azimuth_unit_vector,
    lonlat_to_xy,
    xy_to_lonlat,
)
from luna_sight.terrain.risk import (
    DEFAULT_ANALYSIS_RADIUS_M,
    RISK_SOURCE_MISSING,
    RISK_SOURCE_REAL,
    RISK_SOURCE_REPRESENTATIVE,
    CraterMetrics,
    SiteRiskMetrics,
    SlopeStats,
    analyze_all_sites_risk,
    analyze_site_risk,
    compute_crater_metrics,
    compute_slope_stats,
    format_side_by_side_comparison,
)
from luna_sight.terrain.sites import CANDIDATE_SITES, CandidateSite, get_candidate_site
from luna_sight.terrain.surface_3d import (
    R_MOON_KM,
    build_lunar_globe_figure,
    build_polar_relief_figure,
    compute_lunar_elevation,
)

__all__ = [
    "CANDIDATE_SITES",
    "CandidateSite",
    "CraterMetrics",
    "DEFAULT_ANALYSIS_RADIUS_M",
    "DemGrid",
    "DemMetadata",
    "GapReport",
    "HorizonConfig",
    "HorizonProfile",
    "R_MOON_KM",
    "R_MOON_M",
    "RISK_SOURCE_MISSING",
    "RISK_SOURCE_REAL",
    "RISK_SOURCE_REPRESENTATIVE",
    "SlopeStats",
    "SiteRiskMetrics",
    "azimuth_unit_vector",
    "build_lunar_globe_figure",
    "build_polar_relief_figure",
    "compare_radii",
    "compute_crater_metrics",
    "compute_horizon",
    "compute_lunar_elevation",
    "compute_slope_stats",
    "format_side_by_side_comparison",
    "get_candidate_site",
    "horizon_from_profile",
    "load_lola_dem",
    "lonlat_to_xy",
    "scan_coverage",
    "xy_to_lonlat",
    "analyze_all_sites_risk",
    "analyze_site_risk",
    "compute_crater_metrics",
    "compute_slope_stats",
]