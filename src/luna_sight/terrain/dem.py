"""LOLA DEM okuma, meta veri kaydı ve bilineer örnekleme.

Modül iki katmandan oluşur:

* :class:`DemGrid` — yalnızca NumPy'ye bağlı ızgara; testler sentetik
  ızgaralarla çalışır ve ağ erişimi gerektirmez.
* :func:`load_lola_dem` — GeoTIFF dosyalarını (yüzey yüksekliği, isteğe
  bağlı LDEC dönüş sayısı ve toplam Z belirsizliği) okuyup
  :class:`DemGrid` üretir.

İki ayrı geçerlilik kavramı vardır ve karıştırılmamalıdır:

``valid``
    Yüzey yüksekliği kullanılabilir mi? PGDA ``*_surf.tif`` ürünü boş
    pikselleri enterpolasyonla doldurduğu için 5 m/piksel ızgarada
    piksellerin büyük bölümü bu sınıfa girer ve ufuk hesabında kullanılır;
    Mazarico vd. (2011) ile aynı yaklaşımdır.

``coverage``
    Pikselde gerçek LOLA dönüşü var mı (LDEC ≥ ``min_returns``)? Bu maske
    yüzeyi dışlamak için değil, **yerel kapsamı raporlamak** için tutulur.
    Gerçek dönüş oranı düşükse profil ``partial`` işaretlenir.

Boşluklar asla "görünür" ya da "engelli" sınıfına çevrilmez; yalnızca
kalite bayrağı ve belirsizlik istatistiği üretir (``docs/DATA_CONTRACT.md``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from luna_sight.terrain.polar import R_MOON_M, xy_to_lonlat

LOLA_PRODUCT = "LRO/LOLA bölgesel DEM (LDEM, 5 m/piksel)"
LOLA_SOURCE_ID = "pgda-lola-5mpp"
LOLA_SOURCE_VERSION = "Barker et al. 2021, düzeltilmiş 5 m/piksel (PSS 203:105119)"
LOLA_DATUM = "MOON_ME (JPL DE421)"


@dataclass(frozen=True)
class DemMetadata:
    """Bir DEM ürününün izlenebilirlik bilgileri."""

    site_id: str
    site_name: str
    product: str
    source_id: str
    source_version: str
    datum: str
    pixel_size_m: float
    width: int
    height: int
    bounds_xy_m: tuple[float, float, float, float]
    units: str = "m"
    crs: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "site_id": self.site_id,
            "site_name": self.site_name,
            "product": self.product,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "datum": self.datum,
            "pixel_size_m": self.pixel_size_m,
            "width": self.width,
            "height": self.height,
            "bounds_xy_m": list(self.bounds_xy_m),
            "units": self.units,
            "crs": self.crs,
        }


def _to_center_indices(
    transform: tuple[float, float, float, float, float, float],
    xs: np.ndarray,
    ys: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """X/Y (metre) → piksel merkez indeksleri (sürekli, 0 tabanlı)."""
    a, b, c, d, e, f = transform
    det = a * e - b * d
    if det == 0.0:
        raise ValueError("Tersinemez afin dönüşüm.")
    px = xs - c
    py = ys - f
    col_corner = (e * px - b * py) / det
    row_corner = (-d * px + a * py) / det
    return col_corner - 0.5, row_corner - 0.5


def _bilinear(
    array: np.ndarray,
    mask: np.ndarray,
    transform: tuple[float, float, float, float, float, float],
    xs: np.ndarray,
    ys: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    u, v = _to_center_indices(transform, np.atleast_1d(xs), np.atleast_1d(ys))
    rows, cols = array.shape

    i0 = np.floor(u).astype(np.int64)
    j0 = np.floor(v).astype(np.int64)
    fu = u - i0
    fv = v - j0

    out = np.zeros(u.shape, dtype=float)
    wsum = np.zeros(u.shape, dtype=float)
    for di, dj, weight in (
        (0, 0, (1.0 - fu) * (1.0 - fv)),
        (1, 0, fu * (1.0 - fv)),
        (0, 1, (1.0 - fu) * fv),
        (1, 1, fu * fv),
    ):
        ii = i0 + di
        jj = j0 + dj
        inside = (ii >= 0) & (ii < cols) & (jj >= 0) & (jj < rows)
        weight = np.where(inside, weight, 0.0)
        safe_i = np.clip(ii, 0, cols - 1)
        safe_j = np.clip(jj, 0, rows - 1)
        ok = mask[safe_j, safe_i] & inside & (weight > 0.0)
        values = np.where(ok, array[safe_j, safe_i], 0.0)
        out += np.where(ok, values * weight, 0.0)
        wsum += np.where(ok, weight, 0.0)

    ok = wsum > 1e-9
    return np.where(ok, out / np.where(ok, wsum, 1.0), np.nan), ok


def _nearest(
    array: np.ndarray,
    transform: tuple[float, float, float, float, float, float],
    xs: np.ndarray,
    ys: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    u, v = _to_center_indices(transform, np.atleast_1d(xs), np.atleast_1d(ys))
    rows, cols = array.shape
    ii = np.rint(u).astype(np.int64)
    jj = np.rint(v).astype(np.int64)
    inside = (ii >= 0) & (ii < cols) & (jj >= 0) & (jj < rows)
    values = np.where(inside, array[np.clip(jj, 0, rows - 1), np.clip(ii, 0, cols - 1)], np.nan)
    return values, inside


@dataclass
class DemGrid:
    """Yükseklik ızgarası ve eşleşen kapsam/belirsizlik maskeleri.

    ``transform`` rasterio/Affine altılısıdır: ``(a, b, c, d, e, f)`` ile
    ``x = a*col + b*row + c`` ve ``y = d*col + e*row + f``. ``(col, row)``
    pikselin sol-üst köşesidir.
    """

    heights_m: np.ndarray
    transform: tuple[float, float, float, float, float, float]
    valid: np.ndarray | None = None
    coverage: np.ndarray | None = None
    uncertainty_m: np.ndarray | None = None
    metadata: DemMetadata | None = None
    _extra: dict[str, object] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.heights_m = np.asarray(self.heights_m, dtype=float)
        if self.heights_m.ndim != 2:
            raise ValueError("heights_m iki boyutlu olmalı.")

        if self.valid is None:
            self.valid = np.isfinite(self.heights_m)
        else:
            self.valid = np.asarray(self.valid, dtype=bool)
            self._check_shape(self.valid, "valid")
        if self.coverage is None:
            self.coverage = self.valid.copy()
        else:
            self.coverage = np.asarray(self.coverage, dtype=bool)
            self._check_shape(self.coverage, "coverage")
        if self.uncertainty_m is not None:
            self.uncertainty_m = np.asarray(self.uncertainty_m, dtype=float)
            self._check_shape(self.uncertainty_m, "uncertainty_m")

    def _check_shape(self, array: np.ndarray, name: str) -> None:
        if array.shape != self.heights_m.shape:
            raise ValueError(f"{name} boyutu heights_m ile aynı olmalı.")

    # ------------------------------------------------------------------ ölçek
    @property
    def shape(self) -> tuple[int, int]:
        return self.heights_m.shape

    @property
    def pixel_size_m(self) -> float:
        a, b, _c, d, _e, _f = self.transform
        return float(abs(a)) if b == 0.0 else float(np.hypot(a, d))

    @property
    def bounds_xy_m(self) -> tuple[float, float, float, float]:
        return bounds_of(self.transform, *self.shape[::-1])

    @property
    def center_xy(self) -> tuple[float, float]:
        xmin, ymin, xmax, ymax = self.bounds_xy_m
        return (xmin + xmax) / 2.0, (ymin + ymax) / 2.0

    def center_lonlat(self, *, radius_m: float = R_MOON_M) -> tuple[float, float]:
        """Izgara merkezinin boylam/enlemi (DEM ürünü aday noktaya ortalanır)."""
        return xy_to_lonlat(*self.center_xy, radius_m=radius_m)

    # -------------------------------------------------------------- örnekleme
    def to_center_indices(
        self, xs: np.ndarray | float, ys: np.ndarray | float
    ) -> tuple[np.ndarray, np.ndarray]:
        """X/Y (metre) → piksel merkez indeksleri (sürekli, 0 tabanlı)."""
        return _to_center_indices(
            self.transform, np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
        )

    def sample(
        self, xs: np.ndarray | float, ys: np.ndarray | float
    ) -> tuple[np.ndarray, np.ndarray]:
        """Bilineer yükseklik örneklemesi.

        Dönen ``(values, ok)`` dizilerinde geçersiz (boşluk/kapsam dışı)
        örnekler ``NaN`` ve ``False`` olur. Geçerli komşuların ağırlıkları
        yeniden normalize edilir; boşluk kenarında tam kayıp yerine kısmi
        örnek elde edilir.
        """
        return _bilinear(self.heights_m, self.valid, self.transform, np.asarray(xs), np.asarray(ys))

    def sample_coverage(self, xs: np.ndarray | float, ys: np.ndarray | float) -> np.ndarray:
        """Gerçek LOLA dönüşü var mı (en yakın piksel, mantıksal)."""
        values, inside = _nearest(self.coverage, self.transform, np.asarray(xs), np.asarray(ys))
        return inside & np.nan_to_num(values, nan=0.0).astype(bool)

    def sample_uncertainty(self, xs: np.ndarray | float, ys: np.ndarray | float) -> np.ndarray:
        """Toplam Z belirsizliği (metre); ürün yoksa ``NaN``."""
        if self.uncertainty_m is None:
            return np.full(np.atleast_1d(np.asarray(xs)).shape, np.nan)
        values, _inside = _nearest(
            self.uncertainty_m, self.transform, np.asarray(xs), np.asarray(ys)
        )
        return values

    def covers(self, xs: np.ndarray | float, ys: np.ndarray | float) -> np.ndarray:
        """Noktalar ızgara kapsamı içinde mi (kenar payı olmadan)."""
        u, v = self.to_center_indices(xs, ys)
        rows, cols = self.heights_m.shape
        return (u >= -0.5) & (u <= cols - 0.5) & (v >= -0.5) & (v <= rows - 0.5)


def bounds_of(
    transform: tuple[float, float, float, float, float, float],
    width: int,
    height: int,
) -> tuple[float, float, float, float]:
    """Afin dönüşümden (xmin, ymin, xmax, ymax) sınırları üretir."""
    a, b, c, d, e, f = transform
    corners_x, corners_y = [], []
    for col, row in ((0, 0), (width, 0), (0, height), (width, height)):
        corners_x.append(a * col + b * row + c)
        corners_y.append(d * col + e * row + f)
    return (min(corners_x), min(corners_y), max(corners_x), max(corners_y))


def load_lola_dem(
    surface_path: str | Path,
    *,
    ldec_path: str | Path | None = None,
    toterr_path: str | Path | None = None,
    min_returns: int = 1,
    site_name: str = "",
) -> DemGrid:
    """LOLA ``*_surf.tif`` (+ LDEC ve toplam belirsizlik) ürününü yükler.

    ``ldec_path`` verilmezse kapsam maskesi yüzey geçerliliğine eşitlenir ve
    ``_extra["ldec_used"] = False`` olarak işaretlenir; bilimsel doğrulama
    için LDEC birlikte yüklenmelidir.
    """
    try:
        import rasterio
    except ImportError as exc:  # pragma: no cover - ortam bağımlılığı
        raise RuntimeError("DEM okumak için rasterio gerekir: pip install rasterio") from exc

    surface_path = Path(surface_path)
    with rasterio.open(surface_path) as ds:
        heights = ds.read(1).astype(float)
        gdal_transform = tuple(ds.transform.to_gdal())
        crs = ds.crs.to_wkt() if ds.crs else ""
        nodata = ds.nodata
        width, height = ds.width, ds.height

    # to_gdal sırası (c, a, b, f, d, e) → (a, b, c, d, e, f)
    gc, ga, gb, gf, gd, ge = gdal_transform
    affine = (ga, gb, gc, gd, ge, gf)

    valid = np.isfinite(heights)
    if nodata is not None:
        valid &= ~np.isclose(heights, nodata)

    coverage = None
    if ldec_path is not None:
        with rasterio.open(ldec_path) as lds:
            ldec = lds.read(1)
        coverage = ldec >= min_returns
        if coverage.shape != heights.shape:
            raise ValueError(
                f"LDEC boyutu ({coverage.shape}) yüzey DEM boyutuyla ({heights.shape}) uyuşmuyor."
            )

    uncertainty = None
    if toterr_path is not None:
        with rasterio.open(toterr_path) as tds:
            uncertainty = tds.read(1).astype(float)
        if uncertainty.shape != heights.shape:
            raise ValueError(f"Belirsizlik boyutu ({uncertainty.shape}) DEM boyutuyla uyuşmuyor.")

    site_id = surface_path.name.split("_")[0] if surface_path.stem else surface_path.stem
    metadata = DemMetadata(
        site_id=site_id,
        site_name=site_name,
        product=LOLA_PRODUCT,
        source_id=LOLA_SOURCE_ID,
        source_version=LOLA_SOURCE_VERSION,
        datum=LOLA_DATUM,
        pixel_size_m=float(abs(ga)),
        width=width,
        height=height,
        bounds_xy_m=bounds_of(affine, width, height),
        crs=crs,
    )
    return DemGrid(
        heights_m=heights,
        transform=affine,
        valid=valid,
        coverage=coverage,
        uncertainty_m=uncertainty,
        metadata=metadata,
        _extra={"ldec_used": coverage is not None, "source_path": str(surface_path)},
    )
