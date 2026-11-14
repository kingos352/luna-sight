"""Motorun dış veri kaynakları: K1 (efemeris) ve K2 (ufuk) arayüzleri.

K3, K1 ve K2'nin kodunu beklemeden bu protokolleri uygulayan sağlayıcılarla
çalışır. ``SyntheticEphemeris`` ve ``ConstantHorizon`` yalnızca geliştirme,
demo ve test içindir.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

from luna_sight.visibility.profile import HorizonProfileLookup
from luna_sight.visibility.synthetic import (
    SYNTHETIC_MODEL_ID,
    SYNTHETIC_SOURCE_ID,
    SYNTHETIC_SOURCE_VERSION,
    TEST_FIXTURE,
)

POSITION_COLUMNS = ("sun_az_deg", "sun_alt_deg", "earth_az_deg", "earth_alt_deg")


class EphemerisProvider(Protocol):
    """K1 arayüzü: site ve zaman ızgarası için Güneş/Dünya konumları."""

    def positions(self, site, timestamps: pd.DatetimeIndex) -> pd.DataFrame:
        """``timestamp_utc`` + ``POSITION_COLUMNS`` sütunlarını döndürür."""
        ...


class HorizonProvider(Protocol):
    """K2 arayüzü: tek bir azimut için topoğrafik ufuk yüksekliği (derece)."""

    def elevation_at(self, azimuth_deg: float) -> float | None:
        """Bilinmeyen azimutlar için ``None`` döndürür."""
        ...


@dataclass(frozen=True)
class ConstantHorizon:
    """Her azimutta aynı ufku döndüren geliştirme sağlayıcısı."""

    value_deg: float = 0.0

    def elevation_at(self, azimuth_deg: float) -> float:
        return float(self.value_deg)


def load_horizon_profile(
    path: str | Path,
    azimuth_column: str = "azimuth_deg",
    horizon_column: str = "horizon_deg",
) -> HorizonProfileLookup:
    """K2 ufuk CSV'sini (``azimuth_deg``, ``horizon_deg``) motora bağlar.

    BOM'lu (``utf-8-sig``) dosyalar da okunur; eksik bölgeler ``NaN`` olarak
    korunur ve motor bunları ``uncertain`` üretir.
    """
    return HorizonProfileLookup.from_csv(
        path, azimuth_column=azimuth_column, horizon_column=horizon_column
    )


@dataclass(frozen=True)
class SyntheticEphemeris:
    """K1 yerine kullanılan senaryo serisi.

    ``synthetic.py`` ile aynı senaryoyu üretir: azimut analiz penceresi
    boyunca bir tur atar, yükseklikler dar bir bantta salınır. **Astronomik
    model değildir**; tüm satırlar ``test_fixture`` olarak işaretlenir.
    """

    sun_base_alt_deg: float = -0.8
    sun_swing_alt_deg: float = 0.9
    earth_base_alt_deg: float = -0.2
    earth_swing_alt_deg: float = 0.5
    earth_azimuth_offset_deg: float = 55.0

    def positions(self, site, timestamps: pd.DatetimeIndex) -> pd.DataFrame:
        grid = pd.DatetimeIndex(timestamps)
        if len(grid) == 0:
            raise ValueError("zaman ızgarası boş olamaz")
        if len(grid) == 1:
            raise ValueError("senaryo serisi en az iki örnek gerektirir")

        elapsed = np.asarray((grid - grid[0]) / pd.Timedelta(hours=1), dtype=float)
        span = float(elapsed[-1])
        if span <= 0.0:
            raise ValueError("zaman ızgarası ilerlemeli (artan olmalı)")
        phase = 2.0 * np.pi * elapsed / span
        azimuth = np.mod(elapsed / span * 360.0, 360.0)

        return pd.DataFrame(
            {
                "timestamp_utc": grid,
                "sun_az_deg": azimuth,
                "sun_alt_deg": self.sun_base_alt_deg
                + self.sun_swing_alt_deg * np.sin(phase),
                "earth_az_deg": np.mod(azimuth + self.earth_azimuth_offset_deg, 360.0),
                "earth_alt_deg": self.earth_base_alt_deg
                + self.earth_swing_alt_deg * np.sin(2.0 * phase + 1.0),
                "quality_flag": TEST_FIXTURE,
            }
        )

    @property
    def source_id(self) -> str:
        return SYNTHETIC_SOURCE_ID

    @property
    def source_version(self) -> str:
        return SYNTHETIC_SOURCE_VERSION

    @property
    def model_id(self) -> str:
        return SYNTHETIC_MODEL_ID


__all__ = [
    "POSITION_COLUMNS",
    "ConstantHorizon",
    "EphemerisProvider",
    "HorizonProvider",
    "SyntheticEphemeris",
    "load_horizon_profile",
]
