"""Veri boşluğu ve yerel kapsam taraması.

LOLA 5 m/piksel ızgarasında piksellerin büyük bölümünde gerçek lazer
dönüşü yoktur; ``*_surf.tif`` bu pikselleri enterpolasyonla doldurur.
Bu yüzden tarama iki oranı ayrı raporlar:

* ``surface_gap_fraction`` — yüzey yüksekliği hiç yok (gerçek boşluk).
* ``native_coverage_fraction`` — LDEC ≥ 1 olan piksel oranı (yerel kapsam).

Ayrıca toplam Z belirsizliği haritası (``*_toterr.tif``) varsa yarıçap
içindeki medyan belirsizlik metre cinsinden raporlanır. Hiçbir oran
görünürlük sınıfına dönüştürülmez; yalnızca kalite bayrağını besler.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from luna_sight.terrain.dem import DemGrid
from luna_sight.terrain.horizon import QUALITY_PARTIAL, QUALITY_VALID

MAX_SCAN_SAMPLES = 1_000_000
"""Bellek sınırı için tarama pikseli üst sınırı; aşılırsa örnekleme seyreltilir."""


@dataclass(frozen=True)
class GapReport:
    """Yarıçap bazlı boşluk, kapsam ve belirsizlik özeti."""

    x_m: float
    y_m: float
    radii_m: tuple[float, ...]
    surface_gap_fraction: tuple[float, ...]
    native_coverage_fraction: tuple[float, ...]
    pixel_count: tuple[int, ...]
    uncertainty_median_m: tuple[float | None, ...]
    quality_flag: str
    sample_stride: int = 1

    def as_dict(self) -> dict[str, object]:
        return {
            "x_m": round(self.x_m, 3),
            "y_m": round(self.y_m, 3),
            "radii_m": list(self.radii_m),
            "surface_gap_fraction": [round(v, 6) for v in self.surface_gap_fraction],
            "native_coverage_fraction": [round(v, 6) for v in self.native_coverage_fraction],
            "pixel_count": list(self.pixel_count),
            "uncertainty_median_m": [
                None if v is None else round(v, 4) for v in self.uncertainty_median_m
            ],
            "quality_flag": self.quality_flag,
            "sample_stride": self.sample_stride,
        }


def _pixel_centers(
    dem: DemGrid, stride: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rows, cols = dem.heights_m.shape
    a, b, c, d, e, f = dem.transform
    r_idx = np.arange(0, rows, stride)
    c_idx = np.arange(0, cols, stride)
    col_grid, row_grid = np.meshgrid(c_idx + 0.5, r_idx + 0.5)
    x = a * col_grid + b * row_grid + c
    y = d * col_grid + e * row_grid + f
    valid = dem.valid[np.ix_(r_idx, c_idx)]
    coverage = dem.coverage[np.ix_(r_idx, c_idx)]
    return x, y, valid, coverage


def scan_coverage(
    dem: DemGrid,
    x_m: float,
    y_m: float,
    radii_m: tuple[float, ...] = (2_000.0, 5_000.0),
    *,
    gap_tolerance: float = 0.02,
    coverage_tolerance: float = 0.05,
) -> GapReport:
    """Gözlemci çevresindeki disklerde boşluk ve yerel kapsamı hesaplar."""
    total = dem.heights_m.size
    stride = max(1, int(np.sqrt(total / MAX_SCAN_SAMPLES)))
    x, y, valid, coverage = _pixel_centers(dem, stride)
    distance = np.hypot(x - x_m, y - y_m)
    uncertainty = dem.uncertainty_m

    surface_gaps: list[float] = []
    native: list[float] = []
    counts: list[int] = []
    uncertainties: list[float | None] = []

    for radius in radii_m:
        inside = distance <= radius
        count = int(inside.sum())
        counts.append(count)
        if count == 0:
            surface_gaps.append(1.0)
            native.append(0.0)
            uncertainties.append(None)
            continue
        surface_gaps.append(float(1.0 - valid[inside].mean()))
        native.append(float(coverage[inside].mean()))
        if uncertainty is not None:
            values = uncertainty[
                np.ix_(
                    np.arange(0, dem.heights_m.shape[0], stride),
                    np.arange(0, dem.heights_m.shape[1], stride),
                )
            ][inside]
            values = values[np.isfinite(values)]
            uncertainties.append(None if values.size == 0 else float(np.median(values)))
        else:
            uncertainties.append(None)

    quality = QUALITY_VALID
    if counts[0] == 0 or max(surface_gaps) > gap_tolerance or min(native) < coverage_tolerance:
        quality = QUALITY_PARTIAL

    return GapReport(
        x_m=x_m,
        y_m=y_m,
        radii_m=tuple(float(r) for r in radii_m),
        surface_gap_fraction=tuple(surface_gaps),
        native_coverage_fraction=tuple(native),
        pixel_count=tuple(counts),
        uncertainty_median_m=tuple(uncertainties),
        quality_flag=quality,
        sample_stride=stride,
    )
