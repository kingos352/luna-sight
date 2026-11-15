"""Ay yüzeyi tehlike, küresel eğrilik, yüzey normali ve iniş elipsi analizi (Extra 5).

Bu modül:
1. Ay küresel eğrilik düşüşü ve geometrik ufuk mesafesi hesaplarını,
2. Horn algoritması tabanlı yüzey normali, yönsel eğim (aspect) ve Güneş
   geliş açısı kosinüsü hesaplarını,
3. Alt-piksel fraktal kayaç çarpma olasılığı (BHI — Golombek & Rapp)
   modelini ve aday iniş bölgesi ayak izi değerlendirmesini sağlar.
"""

from __future__ import annotations

import math

import numpy as np

from luna_sight.terrain.polar import R_MOON_M
from luna_sight.terrain.sites import get_candidate_site

# ─── Sabitler ───

LUNAR_RADIUS_M: float = R_MOON_M  # 1_737_400.0 m

DEFAULT_FOOTPRINT_AREA_M2: float = 12.0  # Artemis HLS iniş takımı ayak izi (m^2)
DEFAULT_CRITICAL_DIAMETER_M: float = 0.35  # Kritik engel kayaç çapı (m)
DEFAULT_FRACTAL_GAMMA: float = 2.70  # Fraktal güç yasası üssü
BASE_K_COEFF: float = 0.0008  # Düz Ay regoliti taban kayaç yoğunluk katsayısı


# ─── Küresel Eğrilik Düzeltmesi ───


def calculate_curvature_drop(
    distance_m: float | np.ndarray,
    radius_m: float = LUNAR_RADIUS_M,
) -> float | np.ndarray:
    """Belirtilen mesafe için Ay küresel yüzey düşüşünü (m) hesaplar.

    Formül: ``z_drop = r^2 / (2 * R_Moon)``.
    """
    if radius_m <= 0.0:
        raise ValueError("Ay yarıçapı pozitif bir değer olmalıdır.")
    drop = (np.asarray(distance_m, dtype=np.float64) ** 2) / (2.0 * radius_m)
    if np.isscalar(distance_m):
        return float(drop.item())
    return drop


def apply_curvature_correction(
    z_elevation: float | np.ndarray,
    distance_m: float | np.ndarray,
    radius_m: float = LUNAR_RADIUS_M,
) -> float | np.ndarray:
    """Topografik kota küresel düşüş düzeltmesini uygular.

    Formül: ``z_eff(r) = z(r) - r^2 / (2 * R_Moon)``.
    """
    drop = calculate_curvature_drop(distance_m, radius_m=radius_m)
    corrected = np.asarray(z_elevation, dtype=np.float64) - drop
    if np.isscalar(z_elevation) and np.isscalar(distance_m):
        return float(corrected.item())
    return corrected


def calculate_horizon_distance(
    observer_height_m: float,
    radius_m: float = LUNAR_RADIUS_M,
) -> float:
    """Ay küresinde verilen gözlemci yüksekliği için geometrik ufuk mesafesini (m) hesaplar.

    Formül: ``d = sqrt(2 * R * h + h^2)``.
    """
    if radius_m <= 0.0:
        raise ValueError("Ay yarıçapı pozitif bir değer olmalıdır.")
    if observer_height_m < 0.0:
        return 0.0
    return math.sqrt(2.0 * radius_m * observer_height_m + observer_height_m**2)


def calculate_effective_horizon_angle(
    z_observer: float,
    z_target: float,
    distance_m: float,
    apply_curvature: bool = True,
    radius_m: float = LUNAR_RADIUS_M,
) -> float:
    """Gözlemci ile hedef nokta arasındaki ufuk yükselme açısını (derece) hesaplar."""
    if distance_m <= 0.0:
        return 0.0
    z_eff = (
        float(apply_curvature_correction(z_target, distance_m, radius_m=radius_m))
        if apply_curvature
        else float(z_target)
    )
    tan_alpha = (z_eff - float(z_observer)) / distance_m
    return math.degrees(math.atan(max(0.0, tan_alpha)))


# ─── Yüzey Normalleri ve Yönsel Eğim (Aspect) ───


def compute_gradients(
    dem: np.ndarray,
    cell_size_m: float = 40.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Horn algoritması ile ``dz/dx`` (Doğu) ve ``dz/dy_north`` (Kuzey) gradyanlarını hesaplar."""
    if cell_size_m <= 0.0:
        raise ValueError("cell_size_m pozitif olmalıdır.")
    dem_arr = np.asarray(dem, dtype=np.float64)
    if dem_arr.ndim != 2:
        raise ValueError("dem iki boyutlu bir dizi olmalıdır.")

    h, w = dem_arr.shape
    padded = np.pad(dem_arr, 1, mode="edge")

    z1 = padded[0:h, 0:w]
    z2 = padded[0:h, 1 : w + 1]
    z3 = padded[0:h, 2 : w + 2]
    z4 = padded[1 : h + 1, 0:w]
    z5 = padded[1 : h + 1, 2 : w + 2]
    z6 = padded[2 : h + 2, 0:w]
    z7 = padded[2 : h + 2, 1 : w + 1]
    z8 = padded[2 : h + 2, 2 : w + 2]

    dz_dx = ((z3 + 2.0 * z5 + z8) - (z1 + 2.0 * z4 + z6)) / (8.0 * cell_size_m)
    dz_dy_matrix = ((z6 + 2.0 * z7 + z8) - (z1 + 2.0 * z2 + z3)) / (8.0 * cell_size_m)
    dz_dy_north = -dz_dy_matrix
    return dz_dx, dz_dy_north


def compute_surface_normals(
    dem: np.ndarray,
    cell_size_m: float = 40.0,
) -> np.ndarray:
    """Her DEM pikseli için gökyüzüne yönelmiş ``(H, W, 3)`` birim yüzey normali üretir.

    Koordinat düzeni: ``+X`` Doğu, ``+Y`` Kuzey, ``+Z`` Yerel Zenit.
    """
    dz_dx, dz_dy_north = compute_gradients(dem, cell_size_m=cell_size_m)
    nx = -dz_dx
    ny = -dz_dy_north
    nz = np.ones_like(nx, dtype=np.float64)

    norm = np.maximum(np.sqrt(nx**2 + ny**2 + nz**2), 1e-8)
    return np.stack([nx / norm, ny / norm, nz / norm], axis=-1)


def compute_aspect_map(
    dem: np.ndarray,
    cell_size_m: float = 40.0,
) -> np.ndarray:
    """Her piksel için yönsel eğim açısını (0–360° saat yönünde kuzeyden azimut) döndürür."""
    dz_dx, dz_dy_north = compute_gradients(dem, cell_size_m=cell_size_m)
    aspect_deg = np.mod(np.degrees(np.arctan2(-dz_dx, -dz_dy_north)) + 360.0, 360.0)
    slope_mag = np.hypot(dz_dx, dz_dy_north)
    aspect_deg[slope_mag < 1e-5] = 0.0
    return aspect_deg


def compute_solar_incidence_cosine(
    surface_normals: np.ndarray,
    sun_azimuth_deg: float,
    sun_elevation_deg: float,
    clamp_negative: bool = True,
) -> np.ndarray:
    """Yüzey normalleri ile Güneş yön vektörü arasındaki ``cos(i) = n_hat . s_hat``
    değerini hesaplar.
    """
    az_rad = math.radians(sun_azimuth_deg)
    el_rad = math.radians(sun_elevation_deg)
    s_hat = np.array(
        [
            math.cos(el_rad) * math.sin(az_rad),
            math.cos(el_rad) * math.cos(az_rad),
            math.sin(el_rad),
        ],
        dtype=np.float64,
    )
    cos_i = np.sum(np.asarray(surface_normals, dtype=np.float64) * s_hat, axis=-1)
    if clamp_negative:
        cos_i = np.maximum(0.0, cos_i)
    return cos_i


# ─── Alt-Piksel Fraktal Kayaç Tehlikesi (BHI) ───


def calculate_k_coefficient(
    slope_deg: float | np.ndarray,
    crater_dist_m: float | np.ndarray,
    base_k: float = BASE_K_COEFF,
) -> float | np.ndarray:
    """Yerel eğim ve krater kenarı mesafesine bağlı kayaç yoğunluk faktörü ``k`` değerini döner."""
    slope = np.asarray(slope_deg, dtype=np.float64)
    dist = np.asarray(crater_dist_m, dtype=np.float64)
    slope_factor = np.exp(np.clip(slope / 15.0, 0.0, 3.0))
    crater_factor = 1.0 + 3.0 * np.exp(-np.clip(dist / 600.0, 0.0, 10.0))
    k = base_k * slope_factor * crater_factor
    if np.ndim(k) == 0:
        return float(k.item())
    return k


def compute_boulder_hazard_probability(
    slope: float | np.ndarray,
    crater_dist: float | np.ndarray,
    footprint_area_m2: float = DEFAULT_FOOTPRINT_AREA_M2,
    d_crit_m: float = DEFAULT_CRITICAL_DIAMETER_M,
    gamma: float = DEFAULT_FRACTAL_GAMMA,
) -> dict[str, object] | np.ndarray:
    """12 m² iniş takımı bacak açıklığı için güç yasasıyla alt-piksel kayaç çarpma riski hesabı."""
    is_scalar = np.isscalar(slope) and np.isscalar(crater_dist)

    slope_arr = np.asarray(slope, dtype=np.float64)
    dist_arr = np.asarray(crater_dist, dtype=np.float64)

    k_arr = calculate_k_coefficient(slope_arr, dist_arr)
    n_crit = k_arr * (d_crit_m ** (-gamma))
    lam = footprint_area_m2 * n_crit
    prob = np.clip(1.0 - np.exp(-lam), 0.0, 1.0)

    if not is_scalar:
        return prob

    p_val = float(prob)
    lam_val = float(lam)
    bhi_score = min(100.0, p_val * 100.0)

    if bhi_score < 15.0:
        hazard_class = "NOMINAL_SAFE"
        risk_level = "DÜŞÜK"
    elif bhi_score < 40.0:
        hazard_class = "MODERATE_CAUTION"
        risk_level = "ORTA"
    elif bhi_score < 70.0:
        hazard_class = "HIGH_HAZARD"
        risk_level = "YÜKSEK"
    else:
        hazard_class = "CRITICAL_ABORT_ZONE"
        risk_level = "KRİTİK_TEHLİKE"

    return {
        "slope_deg": float(slope),
        "crater_dist_m": float(crater_dist),
        "footprint_area_m2": footprint_area_m2,
        "critical_diameter_m": d_crit_m,
        "gamma": gamma,
        "expected_hazardous_boulders": round(lam_val, 4),
        "collision_probability": round(p_val, 4),
        "bhi_score": round(bhi_score, 2),
        "hazard_class": hazard_class,
        "risk_level": risk_level,
    }


def compute_boulder_hazard_map(
    slope_map: np.ndarray,
    crater_dist_map: np.ndarray,
    footprint_area_m2: float = DEFAULT_FOOTPRINT_AREA_M2,
    d_crit_m: float = DEFAULT_CRITICAL_DIAMETER_M,
    gamma: float = DEFAULT_FRACTAL_GAMMA,
) -> np.ndarray:
    """DEM eğim haritası için 0–100 aralığında BHI tehlike matrisi üretir."""
    prob_map = compute_boulder_hazard_probability(
        slope=np.asarray(slope_map, dtype=np.float64),
        crater_dist=np.asarray(crater_dist_map, dtype=np.float64),
        footprint_area_m2=footprint_area_m2,
        d_crit_m=d_crit_m,
        gamma=gamma,
    )
    return np.clip(np.asarray(prob_map, dtype=np.float64) * 100.0, 0.0, 100.0)


# ─── İniş Ayak İzi ve Güvenlik Değerlendirmesi ───


def nearest_crater_rim_distance_m(
    nearest_crater_distance_m: float,
    nearest_crater_diameter_km: float,
) -> float:
    """En yakın krater merkez uzaklığından krater kenarına (rim) olan mesafeyi (m) hesaplar."""
    radius_m = 0.5 * float(nearest_crater_diameter_km) * 1000.0
    return abs(float(nearest_crater_distance_m) - radius_m)


def compute_landing_safety_score(safe_pct: float, boulder_hazard_prob: float) -> float:
    """Güvenli eğim yüzdesi ve kayaç tehlike olasılığından 0–100 güvenlik skoru hesaplar."""
    score = 0.6 * float(safe_pct) + 0.4 * (1.0 - float(boulder_hazard_prob)) * 100.0
    return round(max(0.0, min(100.0, score)), 2)


def _safe_fraction_at_threshold(slope_stats: object, threshold_deg: float) -> float:
    """SlopeStats dağılımından verilen eğim eşiği altındaki güvenli alan oranını [0, 1] döner."""
    exact_map = {
        5.0: 1.0 - float(slope_stats.fraction_above_5deg),
        10.0: 1.0 - float(slope_stats.fraction_above_10deg),
        15.0: 1.0 - float(slope_stats.fraction_above_15deg),
        20.0: 1.0 - float(slope_stats.fraction_above_20deg),
    }
    for key, frac in exact_map.items():
        if math.isclose(threshold_deg, key, abs_tol=1e-9):
            return max(0.0, min(1.0, frac))

    max_deg = float(slope_stats.max_deg)
    upper_x = max(25.0, max_deg if math.isfinite(max_deg) else 25.0)
    xs = np.array([0.0, 5.0, 10.0, 15.0, 20.0, upper_x], dtype=float)
    ys = np.array(
        [
            1.0,
            exact_map[5.0],
            exact_map[10.0],
            exact_map[15.0],
            exact_map[20.0],
            0.0,
        ],
        dtype=float,
    )
    interp = float(np.interp(threshold_deg, xs, ys))
    return max(0.0, min(1.0, interp))


def evaluate_landing_footprint(
    site_id: str,
    semi_major_m: float = 100.0,
    semi_minor_m: float = 100.0,
    max_safe_slope_deg: float = 10.0,
) -> dict[str, object]:
    """Aday iniş bölgesinin 3-sigma ayak izi ve kayaç tehlikesi uyumluluğunu değerlendirir."""
    if semi_major_m <= 0.0 or semi_minor_m <= 0.0:
        raise ValueError("semi_major_m ve semi_minor_m pozitif olmalıdır.")
    if max_safe_slope_deg <= 0.0:
        raise ValueError("max_safe_slope_deg pozitif olmalıdır.")

    from luna_sight.terrain.risk import analyze_site_risk

    site = get_candidate_site(site_id)
    risk = analyze_site_risk(site)
    slope = risk.slope

    if not risk.dem_available or math.isnan(slope.mean_deg):
        return {
            "site_id": site.site_id,
            "site_name": site.site_name,
            "semi_major_m": float(semi_major_m),
            "semi_minor_m": float(semi_minor_m),
            "max_safe_slope_deg": float(max_safe_slope_deg),
            "mean_slope_deg": None,
            "p95_slope_deg": None,
            "max_slope_deg": None,
            "footprint_safe_pct": 0.0,
            "boulder_hazard_prob": 1.0,
            "landing_safety_score": 0.0,
            "hls_10deg_compliant": False,
            "hls_15deg_compliant": False,
            "verdict": "INSUFFICIENT_DEM_DATA",
        }

    mean_slope = float(slope.mean_deg)
    p95_slope = float(slope.p95_deg)
    max_slope = float(slope.max_deg)

    safe_frac = _safe_fraction_at_threshold(slope, max_safe_slope_deg)
    footprint_safe_pct = round(safe_frac * 100.0, 2)

    rim_dist_m = nearest_crater_rim_distance_m(
        risk.crater.nearest_crater_distance_m,
        risk.crater.nearest_crater_diameter_km,
    )
    boulder_result = compute_boulder_hazard_probability(mean_slope, rim_dist_m)
    assert isinstance(boulder_result, dict)
    boulder_prob = float(boulder_result["collision_probability"])

    safety_score = compute_landing_safety_score(footprint_safe_pct, boulder_prob)
    hls_10deg_compliant = bool(mean_slope <= 10.0)
    hls_15deg_compliant = bool(mean_slope <= 15.0)

    if safety_score >= 75.0 and hls_10deg_compliant:
        verdict = "SAFE_NOMINAL"
    elif safety_score >= 50.0 and hls_15deg_compliant:
        verdict = "CONDITIONAL_HAZARD_AVOIDANCE"
    elif safety_score >= 30.0:
        verdict = "HIGH_SLOPE_CAUTION"
    else:
        verdict = "UNSAFE_STEEP_TERRAIN"

    return {
        "site_id": site.site_id,
        "site_name": site.site_name,
        "semi_major_m": float(semi_major_m),
        "semi_minor_m": float(semi_minor_m),
        "max_safe_slope_deg": float(max_safe_slope_deg),
        "mean_slope_deg": round(mean_slope, 3),
        "p95_slope_deg": round(p95_slope, 3),
        "max_slope_deg": round(max_slope, 3),
        "footprint_safe_pct": footprint_safe_pct,
        "boulder_hazard_prob": round(boulder_prob, 4),
        "landing_safety_score": safety_score,
        "hls_10deg_compliant": hls_10deg_compliant,
        "hls_15deg_compliant": hls_15deg_compliant,
        "verdict": verdict,
    }


__all__ = [
    "BASE_K_COEFF",
    "DEFAULT_CRITICAL_DIAMETER_M",
    "DEFAULT_FOOTPRINT_AREA_M2",
    "DEFAULT_FRACTAL_GAMMA",
    "LUNAR_RADIUS_M",
    "apply_curvature_correction",
    "calculate_curvature_drop",
    "calculate_effective_horizon_angle",
    "calculate_horizon_distance",
    "calculate_k_coefficient",
    "compute_aspect_map",
    "compute_boulder_hazard_map",
    "compute_boulder_hazard_probability",
    "compute_gradients",
    "compute_landing_safety_score",
    "compute_solar_incidence_cosine",
    "compute_surface_normals",
    "evaluate_landing_footprint",
    "nearest_crater_rim_distance_m",
]
