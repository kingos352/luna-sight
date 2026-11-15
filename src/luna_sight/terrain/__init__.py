"""Topografya ve ufuk profili modülleri (K2).

Girdi örnekleri: LRO/LOLA güney kutup stereografik DEM (PGDA, 5 m/piksel).
Çıktılar: koordinat dönüşümleri, veri boşluğu taraması ve azimut bazlı
topografik ufuk yüksekliği açılarından oluşur.
"""

from luna_sight.terrain.dem import DemGrid, DemMetadata, load_lola_dem
from luna_sight.terrain.gaps import GapReport, scan_coverage
from luna_sight.terrain.hazard import (
    LUNAR_RADIUS_M,
    apply_curvature_correction,
    calculate_curvature_drop,
    calculate_effective_horizon_angle,
    calculate_horizon_distance,
    compute_aspect_map,
    compute_boulder_hazard_map,
    compute_boulder_hazard_probability,
    compute_solar_incidence_cosine,
    compute_surface_normals,
    evaluate_landing_footprint,
)
from luna_sight.terrain.horizon import (
    HorizonConfig,
    HorizonProfile,
    compare_radii,
    compute_horizon,
    horizon_from_profile,
    merge_hybrid_profiles,
)
from luna_sight.terrain.pathfinder import (
    DEFAULT_ROVER_SPEED_KMH,
    PSR_TARGETS,
    find_safe_corridor,
)
from luna_sight.terrain.polar import (
    R_MOON_M,
    azimuth_unit_vector,
    lonlat_to_xy,
    xy_to_lonlat,
)
from luna_sight.terrain.risk import (
    DEFAULT_ANALYSIS_RADIUS_M,
    PRECOMPUTED_SLOPE_DIR,
    RISK_SOURCE_MISSING,
    RISK_SOURCE_PRECOMPUTED,
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
    load_precomputed_slope_summary,
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
    "DEFAULT_ROVER_SPEED_KMH",
    "DemGrid",
    "DemMetadata",
    "GapReport",
    "HorizonConfig",
    "HorizonProfile",
    "LUNAR_RADIUS_M",
    "PRECOMPUTED_SLOPE_DIR",
    "PSR_TARGETS",
    "R_MOON_KM",
    "R_MOON_M",
    "RISK_SOURCE_MISSING",
    "RISK_SOURCE_PRECOMPUTED",
    "RISK_SOURCE_REAL",
    "RISK_SOURCE_REPRESENTATIVE",
    "SlopeStats",
    "SiteRiskMetrics",
    "analyze_all_sites_risk",
    "analyze_site_risk",
    "apply_curvature_correction",
    "azimuth_unit_vector",
    "build_lunar_globe_figure",
    "build_polar_relief_figure",
    "calculate_curvature_drop",
    "calculate_effective_horizon_angle",
    "calculate_horizon_distance",
    "compare_radii",
    "compute_aspect_map",
    "compute_boulder_hazard_map",
    "compute_boulder_hazard_probability",
    "compute_crater_metrics",
    "compute_horizon",
    "compute_lunar_elevation",
    "compute_slope_stats",
    "compute_solar_incidence_cosine",
    "compute_surface_normals",
    "evaluate_landing_footprint",
    "find_safe_corridor",
    "format_side_by_side_comparison",
    "get_candidate_site",
    "horizon_from_profile",
    "load_lola_dem",
    "load_precomputed_slope_summary",
    "lonlat_to_xy",
    "merge_hybrid_profiles",
    "scan_coverage",
    "xy_to_lonlat",
]
