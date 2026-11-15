"""Azimut bazlı topoğrafik ufuk profili.

Gözlemci noktasından her azimut yönünde ışın boyunca DEM örneklenir ve
ufuk yükseklik açısı, ışın üzerindeki en büyük yükseklik açısı olarak
hesaplanır:

    h(θ) = max_r atan2( z(r·û(θ)) - (z_gözlemci + h_göz), r )

Bu, Güneş ve Dünya'nın ``terrain_horizon_sun_deg`` / ``terrain_horizon_earth_deg``
alanlarına girdi sağlayan profildir (``docs/DATA_CONTRACT.md``). Profil tek
başına görünürlük kararı vermez; K3 motoru azimut/yükseklik serisiyle
birlikte kullanır.

Yüzey enterpolasyonlu olabilir: 5 m/piksel LOLA ızgarasında piksellerin
yalnızca küçük bir bölümünde gerçek dönüş vardır. Bu nedenle profil,
kullanılan ışınların **yerel kapsam oranını** da raporlar ve kapsam
eşiğin altına düşerse ``partial`` işaretlenir; boşluklar görünürlük
kararına çevrilmez.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from luna_sight.terrain.dem import DemGrid
from luna_sight.terrain.polar import azimuth_unit_vector, xy_to_lonlat

QUALITY_VALID = "valid"
QUALITY_PARTIAL = "partial"
QUALITY_MISSING = "missing"


@dataclass(frozen=True)
class HorizonConfig:
    """Ufuk hesabı parametreleri; çıktıda aynen kaydedilir."""

    azimuth_step_deg: float = 1.0
    radial_step_m: float = 10.0
    max_radius_m: float = 5_000.0
    observer_height_m: float = 2.0
    gap_tolerance: float = 0.02
    coverage_tolerance: float = 0.05

    def __post_init__(self) -> None:
        if not 0.0 < self.azimuth_step_deg <= 90.0:
            raise ValueError("azimuth_step_deg (0, 90] aralığında olmalı.")
        if self.radial_step_m <= 0.0:
            raise ValueError("radial_step_m pozitif olmalı.")
        if self.max_radius_m <= self.radial_step_m:
            raise ValueError("max_radius_m, radial_step_m'den büyük olmalı.")
        if self.observer_height_m < 0.0:
            raise ValueError("observer_height_m negatif olamaz.")
        if not 0.0 <= self.gap_tolerance <= 1.0:
            raise ValueError("gap_tolerance [0, 1] aralığında olmalı.")
        if not 0.0 <= self.coverage_tolerance <= 1.0:
            raise ValueError("coverage_tolerance [0, 1] aralığında olmalı.")

    def as_dict(self) -> dict[str, float]:
        return {
            "azimuth_step_deg": self.azimuth_step_deg,
            "radial_step_m": self.radial_step_m,
            "max_radius_m": self.max_radius_m,
            "observer_height_m": self.observer_height_m,
            "gap_tolerance": self.gap_tolerance,
            "coverage_tolerance": self.coverage_tolerance,
        }


@dataclass
class HorizonProfile:
    """Bir gözlemci noktası için azimut → ufuk profili."""

    x_m: float
    y_m: float
    lon_deg: float
    lat_deg: float
    config: HorizonConfig
    azimuth_deg: np.ndarray
    horizon_deg: np.ndarray
    occluder_distance_m: np.ndarray
    gap_fraction: np.ndarray
    native_coverage: np.ndarray
    quality_flag: str
    site_id: str = ""
    notes: list[str] = field(default_factory=list)

    def rows(self) -> list[dict[str, object]]:
        """Satır bazlı (CSV'ye yazılabilir) profil."""
        return [
            {
                "azimuth_deg": round(float(az), 4),
                "horizon_deg": None if np.isnan(hz) else round(float(hz), 6),
                "occluder_distance_m": None if np.isnan(od) else round(float(od), 2),
                "gap_fraction": round(float(gf), 6),
                "native_coverage_fraction": round(float(nc), 6),
            }
            for az, hz, od, gf, nc in zip(
                self.azimuth_deg,
                self.horizon_deg,
                self.occluder_distance_m,
                self.gap_fraction,
                self.native_coverage,
                strict=True,
            )
        ]

    def summary(self) -> dict[str, object]:
        hz = self.horizon_deg[np.isfinite(self.horizon_deg)]
        return {
            "site_id": self.site_id,
            "x_m": round(self.x_m, 3),
            "y_m": round(self.y_m, 3),
            "lon_deg_east": round(self.lon_deg, 6),
            "lat_deg": round(self.lat_deg, 6),
            "quality_flag": self.quality_flag,
            "azimuth_count": int(self.azimuth_deg.size),
            "horizon_min_deg": None if hz.size == 0 else round(float(hz.min()), 6),
            "horizon_max_deg": None if hz.size == 0 else round(float(hz.max()), 6),
            "horizon_mean_deg": None if hz.size == 0 else round(float(hz.mean()), 6),
            "mean_gap_fraction": round(float(np.mean(self.gap_fraction)), 6),
            "mean_native_coverage": round(float(np.mean(self.native_coverage)), 6),
            "parameters": self.config.as_dict(),
            "notes": list(self.notes),
        }

    def horizon_at(
        self,
        azimuth_deg: float | np.ndarray | list[float],
        *,
        interpolate: bool = True,
        azimuth_tolerance_deg: float | None = None,
    ) -> float | np.ndarray:
        """Verilen azimut(lar) için ufuk açısını döndürür."""
        return horizon_from_profile(
            self,
            azimuth_deg,
            interpolate=interpolate,
            azimuth_tolerance_deg=azimuth_tolerance_deg,
        )


def _ray_grid(
    dem: DemGrid,
    x_m: float,
    y_m: float,
    config: HorizonConfig,
    lon_deg: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    azimuths = np.arange(0.0, 360.0, config.azimuth_step_deg)
    radii = np.arange(config.radial_step_m, config.max_radius_m + 1e-9, config.radial_step_m)
    directions = np.array([azimuth_unit_vector(float(az), lon_deg) for az in azimuths])
    xs = x_m + directions[:, 0:1] * radii[None, :]
    ys = y_m + directions[:, 1:2] * radii[None, :]
    heights, ok = dem.sample(xs, ys)
    coverage = dem.sample_coverage(xs, ys)
    return azimuths, radii, heights, ok, coverage


def compute_horizon(
    dem: DemGrid,
    x_m: float,
    y_m: float,
    config: HorizonConfig | None = None,
    *,
    lon_deg: float | None = None,
) -> HorizonProfile:
    """``(x_m, y_m)`` noktası için ufuk profilini üretir.

    Gözlemci pikseli geçersizse profil ``missing`` olarak işaretlenir ve
    yükseklikler ``NaN`` döner; eksik veri asla "görünür" sayılmaz.
    """
    config = config or HorizonConfig()
    point_lon, lat_deg = xy_to_lonlat(x_m, y_m)
    if lon_deg is None:
        lon_deg = point_lon

    azimuths, radii, heights, ok, coverage = _ray_grid(dem, x_m, y_m, config, lon_deg)
    notes: list[str] = []

    z_observer, observer_ok = dem.sample(np.array([x_m]), np.array([y_m]))
    if not bool(observer_ok[0]):
        notes.append("Gözlemci pikseli geçersiz (boşluk veya kapsam dışı).")
        return HorizonProfile(
            x_m=x_m,
            y_m=y_m,
            lon_deg=lon_deg,
            lat_deg=lat_deg,
            config=config,
            azimuth_deg=azimuths,
            horizon_deg=np.full(azimuths.shape, np.nan),
            occluder_distance_m=np.full(azimuths.shape, np.nan),
            gap_fraction=np.ones(azimuths.shape),
            native_coverage=np.zeros(azimuths.shape),
            quality_flag=QUALITY_MISSING,
            notes=notes,
        )

    eye = float(z_observer[0]) + config.observer_height_m
    elevation = np.arctan2(heights - eye, radii[None, :])
    elevation = np.where(ok, elevation, -np.inf)

    best = np.argmax(elevation, axis=1)
    best_value = elevation[np.arange(elevation.shape[0]), best]
    seen = np.isfinite(best_value)

    horizon = np.where(seen, np.degrees(best_value), np.nan)
    occluder = np.where(seen, radii[best], np.nan)
    gap_fraction = 1.0 - ok.mean(axis=1)
    native_coverage = coverage.mean(axis=1)

    covered_radii = radii[ok.all(axis=0)]
    if covered_radii.size == 0 or covered_radii[-1] < config.max_radius_m:
        reached = 0.0 if covered_radii.size == 0 else float(covered_radii[-1])
        notes.append(
            "İstenen yarıçap DEM kapsamını aşıyor; "
            f"tüm azimutlarda güvenilir yarıçap {reached:.0f} m."
        )

    quality = QUALITY_VALID
    if not seen.all():
        quality = QUALITY_PARTIAL
        notes.append("Bazı azimutlarda geçerli örnek bulunamadı.")
    if float(np.nanmax(gap_fraction)) > config.gap_tolerance:
        quality = QUALITY_PARTIAL
        notes.append(
            "Veri boşluğu toleransı aşıldı "
            f"(en büyük boşluk oranı {float(np.nanmax(gap_fraction)):.3f}, "
            f"tolerans {config.gap_tolerance:.3f})."
        )
    mean_coverage = float(np.mean(native_coverage))
    if mean_coverage < config.coverage_tolerance:
        quality = QUALITY_PARTIAL
        notes.append(
            "Yerel LOLA dönüş kapsamı eşiğin altında "
            f"(ortalama {mean_coverage:.3f}, eşik {config.coverage_tolerance:.3f}); "
            "yüzey enterpolasyonu belirgin."
        )
    if notes and quality == QUALITY_VALID:
        quality = QUALITY_PARTIAL

    return HorizonProfile(
        x_m=x_m,
        y_m=y_m,
        lon_deg=lon_deg,
        lat_deg=lat_deg,
        config=config,
        azimuth_deg=azimuths,
        horizon_deg=horizon,
        occluder_distance_m=occluder,
        gap_fraction=gap_fraction,
        native_coverage=native_coverage,
        quality_flag=quality,
        notes=notes,
    )


def compare_radii(
    dem: DemGrid,
    x_m: float,
    y_m: float,
    radii_m: tuple[float, ...] = (2_000.0, 5_000.0),
    config: HorizonConfig | None = None,
) -> dict[str, object]:
    """Aynı nokta için iki analiz yarıçapını karşılaştırır.

    Dönen sözlük her yarıçapın özetini ve profiller arasındaki en büyük
    ufuk farkını içerir. Bu, "iki analiz yarıçapı karşılaştırıldı" kabul
    ölçütünün kanıtıdır.
    """
    base = config or HorizonConfig()
    profiles: list[HorizonProfile] = []
    for radius in radii_m:
        cfg = HorizonConfig(
            azimuth_step_deg=base.azimuth_step_deg,
            radial_step_m=base.radial_step_m,
            max_radius_m=float(radius),
            observer_height_m=base.observer_height_m,
            gap_tolerance=base.gap_tolerance,
            coverage_tolerance=base.coverage_tolerance,
        )
        profiles.append(compute_horizon(dem, x_m, y_m, cfg))

    reference = profiles[0].horizon_deg
    deltas = []
    for profile in profiles[1:]:
        delta = np.abs(profile.horizon_deg - reference)
        if np.isfinite(delta).any():
            deltas.append(float(np.nanmax(delta)))

    return {
        "radii_m": list(radii_m),
        "profiles": [p.summary() for p in profiles],
        "max_horizon_delta_deg": None if not deltas else round(max(deltas), 6),
    }


def horizon_from_profile(
    profile: HorizonProfile,
    azimuth_deg: float | np.ndarray | list[float],
    *,
    interpolate: bool = True,
    azimuth_tolerance_deg: float | None = None,
) -> float | np.ndarray:
    """Verilen ufuk profilinden istenen azimut(lar) için ufuk açısını döndürür.

    K3 görünürlük motorunun Güneş ve Dünya azimutlarındaki topoğrafik ufuk
    yükseklik açılarını (``terrain_horizon_sun_deg``, ``terrain_horizon_earth_deg``)
    hesaplamasında kullanılır.

    Parametreler:
        profile:
            ``compute_horizon`` ile üretilmiş ``HorizonProfile`` nesnesi.
        azimuth_deg:
            Sorgulanacak azimut veya azimut dizisi (derece cinsinden).
        interpolate:
            True ise dairesel periyodik [0, 360) doğrusal enterpolasyon yapar.
            False ise en yakın azimut değerini seçer.
        azimuth_tolerance_deg:
            En yakın azimut eşleşmesinde (interpolate=False) izin verilen
            en büyük açısal fark (derece). Fark toleransı aşarsa NaN döner.

    Dönüş:
        Skaler azimut için float, dizi için np.ndarray ufuk yükseklik açısı (derece).
    """
    is_scalar = np.isscalar(azimuth_deg)
    query_az = np.asarray(azimuth_deg, dtype=float)
    query_norm = np.mod(query_az, 360.0)

    if profile.quality_flag == QUALITY_MISSING or profile.azimuth_deg.size == 0:
        nan_res = np.full(query_norm.shape, np.nan)
        return float(nan_res.item()) if is_scalar else nan_res

    order = np.argsort(profile.azimuth_deg)
    src_az = profile.azimuth_deg[order]
    src_hz = profile.horizon_deg[order]

    if interpolate:
        ext_az = np.append(src_az, src_az[0] + 360.0)
        ext_hz = np.append(src_hz, src_hz[0])
        result = np.interp(query_norm, ext_az, ext_hz)
    else:
        diff = np.abs(query_norm[..., None] - src_az[None, :])
        angular_dist = np.minimum(diff, 360.0 - diff)
        nearest_idx = np.argmin(angular_dist, axis=-1)
        min_dist = np.take_along_axis(angular_dist, nearest_idx[..., None], axis=-1).squeeze(
            axis=-1
        )

        result = src_hz[nearest_idx]
        if azimuth_tolerance_deg is not None:
            result = np.where(min_dist <= azimuth_tolerance_deg, result, np.nan)

    if is_scalar:
        return float(result.item())
    return result


def _resolve_horizon_columns(df: pd.DataFrame, label: str) -> tuple[str, str | None]:
    if "azimuth_deg" not in df.columns:
        raise ValueError(f"{label} DataFrame içinde 'azimuth_deg' kolonu bulunmalıdır.")
    if "horizon_elevation_deg" in df.columns:
        elev_col = "horizon_elevation_deg"
    elif "horizon_deg" in df.columns:
        elev_col = "horizon_deg"
    else:
        raise ValueError(
            f"{label} DataFrame içinde 'horizon_elevation_deg' veya 'horizon_deg' kolonu olmalıdır."
        )

    if "horizon_distance_m" in df.columns:
        dist_col: str | None = "horizon_distance_m"
    elif "occluder_distance_m" in df.columns:
        dist_col = "occluder_distance_m"
    else:
        dist_col = None
    return elev_col, dist_col


def _prepare_sorted_profile(df: pd.DataFrame, label: str) -> tuple[pd.DataFrame, np.ndarray]:
    if df.empty:
        raise ValueError(f"{label} profili boş olamaz.")
    work = df.copy()
    az = np.mod(pd.to_numeric(work["azimuth_deg"], errors="raise").to_numpy(dtype=float), 360.0)
    work["_az_norm"] = az
    work = work.sort_values("_az_norm", kind="stable").drop_duplicates(
        subset=["_az_norm"], keep="first"
    )
    sorted_az = work["_az_norm"].to_numpy(dtype=float)
    return work.reset_index(drop=True), sorted_az


def _circular_nearest_indices(src_az: np.ndarray, target_az: np.ndarray) -> np.ndarray:
    diff = np.abs(target_az[:, None] - src_az[None, :])
    angular_dist = np.minimum(diff, 360.0 - diff)
    return np.argmin(angular_dist, axis=1)


def _align_circular_elevation(
    src_az: np.ndarray,
    src_el: np.ndarray,
    target_az: np.ndarray,
) -> np.ndarray:
    nearest_idx = _circular_nearest_indices(src_az, target_az)
    nearest_dist = np.minimum(
        np.abs(target_az - src_az[nearest_idx]),
        360.0 - np.abs(target_az - src_az[nearest_idx]),
    )
    exact_mask = nearest_dist <= 1e-9

    finite_mask = np.isfinite(src_el)
    if np.count_nonzero(finite_mask) >= 2:
        fin_az = src_az[finite_mask]
        fin_el = src_el[finite_mask]
        ext_az = np.concatenate([fin_az - 360.0, fin_az, fin_az + 360.0])
        ext_el = np.concatenate([fin_el, fin_el, fin_el])
        interp_vals = np.interp(target_az, ext_az, ext_el)
    elif np.count_nonzero(finite_mask) == 1:
        interp_vals = np.full(target_az.shape, float(src_el[finite_mask][0]), dtype=float)
    else:
        interp_vals = np.full(target_az.shape, np.nan, dtype=float)

    return np.where(exact_mask, src_el[nearest_idx], interp_vals)


def merge_hybrid_profiles(
    near_profile: pd.DataFrame,
    far_profile: pd.DataFrame,
) -> pd.DataFrame:
    """Yakın (yüksek çözünürlük) ve uzak (bölgesel) ufuk profillerini birleştirir.

    Profiller azimut (``azimuth_deg``, 0–360°) ekseninde hizalanır (gerekirse
    dairesel doğrusal enterpolasyon uygulanır), her azimutta
    ``max(horizon_elevation_deg)`` alınır ve daha yüksek engeli veren profilin
    mesafe/meta verisi korunur.
    """
    near_elev_col, near_dist_col = _resolve_horizon_columns(near_profile, "near_profile")
    far_elev_col, far_dist_col = _resolve_horizon_columns(far_profile, "far_profile")

    near_df, near_az = _prepare_sorted_profile(near_profile, "near_profile")
    far_df, far_az = _prepare_sorted_profile(far_profile, "far_profile")

    out_elev_col = (
        "horizon_elevation_deg"
        if "horizon_elevation_deg" in (near_elev_col, far_elev_col)
        else "horizon_deg"
    )
    if "horizon_distance_m" in (near_dist_col, far_dist_col):
        out_dist_col: str | None = "horizon_distance_m"
    elif "occluder_distance_m" in (near_dist_col, far_dist_col):
        out_dist_col = "occluder_distance_m"
    else:
        out_dist_col = None

    target_az = near_az if near_az.size >= far_az.size else far_az

    near_el_src = pd.to_numeric(near_df[near_elev_col], errors="coerce").to_numpy(dtype=float)
    far_el_src = pd.to_numeric(far_df[far_elev_col], errors="coerce").to_numpy(dtype=float)

    near_el_aligned = _align_circular_elevation(near_az, near_el_src, target_az)
    far_el_aligned = _align_circular_elevation(far_az, far_el_src, target_az)

    near_idx = _circular_nearest_indices(near_az, target_az)
    far_idx = _circular_nearest_indices(far_az, target_az)

    merged_el = np.fmax(near_el_aligned, far_el_aligned)
    choose_far = np.where(
        np.isnan(near_el_aligned),
        np.isfinite(far_el_aligned),
        np.isfinite(far_el_aligned) & (far_el_aligned > near_el_aligned),
    )

    result = pd.DataFrame({"azimuth_deg": target_az, out_elev_col: merged_el})

    if out_dist_col is not None:
        near_dist_vals = (
            pd.to_numeric(near_df[near_dist_col], errors="coerce").to_numpy(dtype=float)[near_idx]
            if near_dist_col is not None
            else np.full(target_az.shape, np.nan, dtype=float)
        )
        far_dist_vals = (
            pd.to_numeric(far_df[far_dist_col], errors="coerce").to_numpy(dtype=float)[far_idx]
            if far_dist_col is not None
            else np.full(target_az.shape, np.nan, dtype=float)
        )
        result[out_dist_col] = np.where(choose_far, far_dist_vals, near_dist_vals)

    skip_cols = {
        "azimuth_deg",
        "_az_norm",
        near_elev_col,
        far_elev_col,
        "source_range",
    }
    if near_dist_col is not None:
        skip_cols.add(near_dist_col)
    if far_dist_col is not None:
        skip_cols.add(far_dist_col)

    preserved_cols: list[str] = []
    for col in list(near_df.columns) + list(far_df.columns):
        if col not in skip_cols and col not in preserved_cols:
            preserved_cols.append(col)

    for col in preserved_cols:
        in_near = col in near_df.columns
        in_far = col in far_df.columns
        if in_near and in_far:
            near_vals = near_df[col].to_numpy()[near_idx]
            far_vals = far_df[col].to_numpy()[far_idx]
            result[col] = np.where(choose_far, far_vals, near_vals)
        elif in_near:
            result[col] = near_df[col].to_numpy()[near_idx]
        elif in_far:
            result[col] = far_df[col].to_numpy()[far_idx]

    result["source_range"] = "hybrid"
    return result
