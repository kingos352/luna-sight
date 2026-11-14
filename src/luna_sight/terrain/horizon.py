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


def _ray_grid(
    dem: DemGrid,
    x_m: float,
    y_m: float,
    config: HorizonConfig,
    lon_deg: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    azimuths = np.arange(0.0, 360.0, config.azimuth_step_deg)
    radii = np.arange(
        config.radial_step_m, config.max_radius_m + 1e-9, config.radial_step_m
    )
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
