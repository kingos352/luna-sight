"""
backend/flight_physics/__init__.py
==================================
Ay İniş Görevi Uçuş Fiziği, Aviyonik ve İleri Telekomünikasyon Modülleri.
"""

from .chebyshev_compression import fit_chebyshev_series, evaluate_chebyshev
from .gateway_relay import generate_gateway_ephemeris, compute_gateway_visibility
from .curvature import (
    LUNAR_RADIUS_M,
    calculate_curvature_drop,
    apply_curvature_correction,
    calculate_horizon_distance,
)
from .surface_normals import (
    compute_surface_normals,
    compute_aspect_map,
    compute_solar_incidence_cosine,
)
from .boulder_hazard import (
    compute_boulder_hazard_probability,
    compute_boulder_hazard_map,
)
from .penumbra_power import (
    compute_solar_disk_fraction,
    compute_penumbra_power,
    SOLAR_ANGULAR_DIAMETER_DEG,
)
from .knife_edge_diffraction import (
    compute_fresnel_parameter,
    compute_diffraction_loss_itu,
    evaluate_emergency_link_margin,
)
from .link_budget import (
    compute_link_budget,
    DSNStation,
    FrequencyBand,
    DSN_STATIONS,
)
from .seu_tmr_shield import (
    TMRVariable,
    SEUInjector,
    SEUProtectedState,
)

__all__ = [
    "fit_chebyshev_series",
    "evaluate_chebyshev",
    "generate_gateway_ephemeris",
    "compute_gateway_visibility",
    "LUNAR_RADIUS_M",
    "calculate_curvature_drop",
    "apply_curvature_correction",
    "calculate_horizon_distance",
    "compute_surface_normals",
    "compute_aspect_map",
    "compute_solar_incidence_cosine",
    "compute_boulder_hazard_probability",
    "compute_boulder_hazard_map",
    "compute_solar_disk_fraction",
    "compute_penumbra_power",
    "SOLAR_ANGULAR_DIAMETER_DEG",
    "compute_fresnel_parameter",
    "compute_diffraction_loss_itu",
    "evaluate_emergency_link_margin",
    "compute_link_budget",
    "DSNStation",
    "FrequencyBand",
    "DSN_STATIONS",
    "TMRVariable",
    "SEUInjector",
    "SEUProtectedState",
]
