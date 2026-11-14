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
)
from luna_sight.terrain.polar import (
    R_MOON_M,
    azimuth_unit_vector,
    lonlat_to_xy,
    xy_to_lonlat,
)

__all__ = [
    "R_MOON_M",
    "DemGrid",
    "DemMetadata",
    "GapReport",
    "HorizonConfig",
    "HorizonProfile",
    "azimuth_unit_vector",
    "compare_radii",
    "compute_horizon",
    "load_lola_dem",
    "lonlat_to_xy",
    "scan_coverage",
    "xy_to_lonlat",
]
