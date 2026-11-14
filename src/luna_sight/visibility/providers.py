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
