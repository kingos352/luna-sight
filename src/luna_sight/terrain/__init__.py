"""Topoğrafya ve ufuk profili modülü (K2).

Girdi ürünü: LRO/LOLA güney kutup stereografik DEM (PGDA, 5 m/piksel).
Çıktı: koordinat dönüşümleri, veri boşluğu taraması ve azimut bazlı
topoğrafik ufuk yükseklik açıları.
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
from luna_sight.terrain.sites import CANDIDATE_SITES, CandidateSite, get_candidate_site

__all__ = [
    "CANDIDATE_SITES",
    "CandidateSite",
    "DemGrid",
    "DemMetadata",
    "GapReport",
    "HorizonConfig",
    "HorizonProfile",
    "R_MOON_M",
    "azimuth_unit_vector",
    "compare_radii",
    "compute_horizon",
    "get_candidate_site",
    "horizon_from_profile",
    "load_lola_dem",
    "lonlat_to_xy",
    "scan_coverage",
    "xy_to_lonlat",
]
