"""Motorun dış veri kaynakları: K1 (efemeris) ve K2 (ufuk) arayüzleri.

K3, K1 ve K2'nin kodunu beklemeden bu iki protokolü uygulayan herhangi bir
sağlayıcıyla çalışabilir. Dosyadaki ``ConstantHorizon`` ve ``MockEphemeris``
sınıfları yalnızca geliştirme, demo ve test içindir; gerçek veri K1/K2
modüllerinden gelir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd

POSITION_COLUMNS = ("sun_az_deg", "sun_alt_deg", "earth_az_deg", "earth_alt_deg")


class HorizonProvider(Protocol):
    """K2 arayüzü: verilen azimutlar için topoğrafik ufuk yüksekliği (derece)."""

    def horizon_deg(self, azimuth_deg: np.ndarray) -> np.ndarray:
        """Her azimut için ufuk yüksekliği döndürür; bilinmeyen için ``nan``."""
        ...


class EphemerisProvider(Protocol):
    """K1 arayüzü: site ve zaman ızgarası için Güneş/Dünya konumları."""

    def positions(self, site, timestamps: pd.DatetimeIndex) -> pd.DataFrame:
        """``timestamp_utc`` + ``POSITION_COLUMNS`` sütunlarını döndürür."""
        ...


@dataclass(frozen=True)
class ConstantHorizon:
    """Her azimutta aynı ufku döndüren geliştirme sağlayıcısı."""

    horizon_deg_value: float = 0.0

    def horizon_deg(self, azimuth_deg: np.ndarray) -> np.ndarray:
        azimuths = np.asarray(azimuth_deg, dtype=float)
        return np.full(azimuths.shape, float(self.horizon_deg_value), dtype=float)


@dataclass(frozen=True, eq=False)
class ProfileHorizon:
    """K2 ufuk profili (azimut → ufuk açısı) sağlayıcısı.

    ``outputs/k2/<Site>_horizon_<r>m.csv`` dosyalarındaki profili motora bağlar.
    Varsayılan olarak dairesel (0–360) doğrusal enterpolasyon yapar; eksik
    azimutlardaki ``nan`` değerleri komşu aralıklara yayılarak görünürlük
    kararını ``uncertain`` yapar.
    """

    azimuth_deg: np.ndarray
    values_deg: np.ndarray
    interpolate: bool = True
    azimuth_tolerance_deg: float | None = None

    def __post_init__(self) -> None:
        azimuths = np.asarray(self.azimuth_deg, dtype=float)
        values = np.asarray(self.values_deg, dtype=float)
        if azimuths.ndim != 1 or values.shape != azimuths.shape:
            raise ValueError("azimut ve ufuk dizileri aynı 1B uzunlukta olmalı")
        if azimuths.size == 0:
            raise ValueError("ufuk profili boş olamaz")
        if not np.isfinite(azimuths).all():
            raise ValueError("azimut değerleri sonlu olmalı")
        if self.azimuth_tolerance_deg is not None and self.azimuth_tolerance_deg < 0:
            raise ValueError("azimuth_tolerance_deg negatif olamaz")

        order = np.argsort(azimuths, kind="stable")
        object.__setattr__(self, "azimuth_deg", azimuths[order])
        object.__setattr__(self, "values_deg", values[order])

    def horizon_deg(self, azimuth_deg) -> np.ndarray:
        query = np.mod(np.asarray(azimuth_deg, dtype=float), 360.0)
        source_az = self.azimuth_deg
        source_hz = self.values_deg

        if self.interpolate:
            extended_az = np.append(source_az, source_az[0] + 360.0)
            extended_hz = np.append(source_hz, source_hz[0])
            return np.interp(query, extended_az, extended_hz)

        diff = np.abs(np.atleast_1d(query)[..., None] - source_az[None, :])
        distance = np.minimum(diff, 360.0 - diff)
        nearest = np.argmin(distance, axis=-1)
        result = np.asarray(source_hz[nearest], dtype=float)
        if self.azimuth_tolerance_deg is not None:
            closest = np.take_along_axis(distance, nearest[..., None], axis=-1)
            result = np.where(
                closest.squeeze(axis=-1) <= self.azimuth_tolerance_deg,
                result,
                np.nan,
            )
        return result.reshape(np.shape(query))


def load_horizon_profile(
    path,
    *,
    azimuth_column: str = "azimuth_deg",
    horizon_column: str = "horizon_deg",
    interpolate: bool = True,
    azimuth_tolerance_deg: float | None = None,
) -> ProfileHorizon:
    """K2 ufuk CSV'sini okur ve motor sağlayıcısına dönüştürür."""
    frame = pd.read_csv(path, encoding="utf-8-sig")
    missing = [
        name for name in (azimuth_column, horizon_column) if name not in frame.columns
    ]
    if missing:
        raise ValueError("ufuk profilinde eksik sütun(lar): " + ", ".join(missing))
    return ProfileHorizon(
        azimuth_deg=frame[azimuth_column].to_numpy(dtype=float),
        values_deg=frame[horizon_column].to_numpy(dtype=float),
        interpolate=interpolate,
        azimuth_tolerance_deg=azimuth_tolerance_deg,
    )



@dataclass(frozen=True)
class MockEphemeris:
    """K1 yerine kullanılan deterministik, sinüzoidal geliştirme sağlayıcısı.

    Boylam, faz kaydırması ile siteler arasında fark üretir. Gerçek gökyüzü
    modeli değildir; yalnızca motoru ve arayüzü K1 olmadan denemek içindir.
    """

    sun_max_alt_deg: float = 10.0
    earth_alt_deg: float = 8.0
    period_hours: float = 24.0

    def positions(self, site, timestamps: pd.DatetimeIndex) -> pd.DataFrame:
        grid = pd.DatetimeIndex(timestamps)
        if len(grid) == 0:
            raise ValueError("zaman ızgarası boş olamaz")

        elapsed = np.asarray(
            (grid - grid[0]) / pd.Timedelta(hours=1), dtype=float
        )
        phase_hours = elapsed + float(site.longitude_deg_east) / 15.0
        angle = 2.0 * np.pi * phase_hours / float(self.period_hours)

        return pd.DataFrame(
            {
                "timestamp_utc": grid,
                "sun_az_deg": np.mod(90.0 + 360.0 * phase_hours / self.period_hours, 360.0),
                "sun_alt_deg": self.sun_max_alt_deg * np.sin(angle),
                "earth_az_deg": np.mod(270.0 + 360.0 * phase_hours / self.period_hours, 360.0),
                "earth_alt_deg": np.full(len(grid), float(self.earth_alt_deg)),
            }
        )
