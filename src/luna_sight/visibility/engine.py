"""Görünürlük motoru iskeleti (K3).

Motor; K1 (efemeris) ve K2 (ufuk) sağlayıcılarını protokol üzerinden alır.
Sağlayıcılar hazır olmasa da ``MockEphemeris`` ve ``ConstantHorizon`` ile
uçtan uca çalıştırılabilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from luna_sight.visibility.classification import DEFAULT_UNCERTAINTY_DEG
from luna_sight.visibility.providers import (
    POSITION_COLUMNS,
    ConstantHorizon,
    EphemerisProvider,
    HorizonProvider,
    MockEphemeris,
)
from luna_sight.visibility.table import DEFAULT_MODEL_ID, build_visibility_table
from luna_sight.visibility.timeline import (
    DEFAULT_ANALYSIS_HOURS,
    DEFAULT_STEP_MINUTES,
    analysis_timestamps,
)


@dataclass(frozen=True)
class Site:
    """Aday iniş bölgesi."""

    site_id: str
    latitude_deg: float
    longitude_deg_east: float


@dataclass
class EngineConfig:
    """Motor çalışma parametreleri."""

    hours: float = DEFAULT_ANALYSIS_HOURS
    step_minutes: float = DEFAULT_STEP_MINUTES
    uncertainty_deg: float = DEFAULT_UNCERTAINTY_DEG
    source_id: str = "unknown"
    source_version: str = "unknown"
    model_id: str = DEFAULT_MODEL_ID
    parameters: dict = field(default_factory=dict)


class VisibilityEngine:
    """Site + zaman ızgarası → veri sözleşmesine uygun görünürlük tablosu."""

    def __init__(
        self,
        ephemeris: EphemerisProvider,
        horizon: HorizonProvider,
        config: EngineConfig | None = None,
    ) -> None:
        self.ephemeris = ephemeris
        self.horizon = horizon
        self.config = config or EngineConfig()

    def timestamps(self, start_utc) -> pd.DatetimeIndex:
        return analysis_timestamps(
            start_utc,
            hours=self.config.hours,
            step_minutes=self.config.step_minutes,
        )

    def run(self, site: Site, start_utc) -> pd.DataFrame:
        """Tek bir site için görünürlük tablosunu üretir."""
        timestamps = self.timestamps(start_utc)
        positions = self._positions(site, timestamps)

        frame = pd.DataFrame(
            {
                "site_id": [site.site_id] * len(timestamps),
                "latitude_deg": np.full(len(timestamps), float(site.latitude_deg)),
                "longitude_deg_east": np.full(len(timestamps), float(site.longitude_deg_east)),
                "timestamp_utc": timestamps,
                "sun_az_deg": positions["sun_az_deg"],
                "sun_alt_deg": positions["sun_alt_deg"],
                "earth_az_deg": positions["earth_az_deg"],
                "earth_alt_deg": positions["earth_alt_deg"],
                "terrain_horizon_sun_deg": self._horizon(
                    positions["sun_az_deg"], "Güneş"
                ),
                "terrain_horizon_earth_deg": self._horizon(
                    positions["earth_az_deg"], "Dünya"
                ),
            }
        )

        return build_visibility_table(
            frame,
            uncertainty_deg=self.config.uncertainty_deg,
            source_id=self.config.source_id,
            source_version=self.config.source_version,
            model_id=self.config.model_id,
            parameters=self.config.parameters,
        )

    def run_many(self, sites, start_utc) -> pd.DataFrame:
        """Birden çok siteyi aynı zaman ızgarasında hesaplar."""
        site_list = list(sites)
        if not site_list:
            raise ValueError("en az bir site gerekli")
        tables = [self.run(site, start_utc) for site in site_list]
        return pd.concat(tables, ignore_index=True)

    def _positions(self, site: Site, timestamps: pd.DatetimeIndex) -> pd.DataFrame:
        frame = self.ephemeris.positions(site, timestamps)

        missing = [name for name in POSITION_COLUMNS if name not in frame.columns]
        if missing:
            raise ValueError("efemeris çıktısında eksik sütun(lar): " + ", ".join(missing))
        if len(frame) != len(timestamps):
            raise ValueError(
                f"efemeris {len(frame)} satır döndürdü, {len(timestamps)} bekleniyordu"
            )
        if "timestamp_utc" in frame.columns:
            returned = pd.DatetimeIndex(
                pd.to_datetime(frame["timestamp_utc"], utc=True, errors="raise")
            )
            if not returned.equals(timestamps):
                raise ValueError("efemeris zaman damgaları analiz ızgarasıyla eşleşmiyor")

        return frame

    def _horizon(self, azimuths: pd.Series, label: str) -> np.ndarray:
        values = np.asarray(
            self.horizon.horizon_deg(np.asarray(azimuths, dtype=float)), dtype=float
        )
        if values.ndim == 0:
            values = np.full(len(azimuths), float(values))
        if values.shape != (len(azimuths),):
            raise ValueError(
                f"{label} ufuk sağlayıcısı {len(azimuths)} değer döndürmeli"
            )
        return values


def run_demo(
    *,
    start_utc="2026-11-14T00:00:00Z",
    hours: float = 24.0,
    step_minutes: float = DEFAULT_STEP_MINUTES,
    uncertainty_deg: float = DEFAULT_UNCERTAINTY_DEG,
    horizon_deg: float = 3.0,
    sites=None,
) -> pd.DataFrame:
    """K1/K2 olmadan çalışan örnek: stub sağlayıcılarla görünürlük tablosu."""
    selected = (
        tuple(sites)
        if sites is not None
        else (
            Site("A", -89.5, 0.0),
            Site("B", -88.0, 45.0),
        )
    )
    config = EngineConfig(
        hours=hours,
        step_minutes=step_minutes,
        uncertainty_deg=uncertainty_deg,
        source_id="demo",
        source_version="0",
    )
    engine = VisibilityEngine(MockEphemeris(), ConstantHorizon(horizon_deg), config)
    return engine.run_many(selected, start_utc)
