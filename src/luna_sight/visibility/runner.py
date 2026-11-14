"""K3 orkestrasyon katmanı: site tanımı, yapılandırma ve uçtan uca koşum.

``VisibilityRunner``, K1 (efemeris) ve K2 (ufuk) sağlayıcılarını birleştirip
``engine`` çekirdeğini çalıştırır, sonucu sözleşme tablosuna çevirir.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Mapping

import pandas as pd

from luna_sight.visibility.engine import (
    BODY_JOINT,
    BODIES,
    SampleResult,
    Window,
    build_windows,
    evaluate_series,
)
from luna_sight.visibility.grid import (
    DEFAULT_ANALYSIS_HOURS,
    DEFAULT_STEP_MINUTES,
    analysis_timestamps,
)
from luna_sight.visibility.providers import (
    POSITION_COLUMNS,
    ConstantHorizon,
    EphemerisProvider,
    HorizonProvider,
    SyntheticEphemeris,
)
from luna_sight.visibility.series import Sample, sample_from_row, validate_series
from luna_sight.visibility.states import VisibilityConfig
from luna_sight.visibility.table import results_to_frame


@dataclass(frozen=True)
class Site:
    """Görünürlük hesabı yapılan gözlem noktası."""

    site_id: str
    latitude_deg: float
    longitude_deg_east: float

    def __post_init__(self) -> None:
        if not str(self.site_id).strip():
            raise ValueError("site_id boş olamaz")
        if not math.isfinite(self.latitude_deg) or not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError("latitude_deg -90..90 aralığında olmalı")
        if (
            not math.isfinite(self.longitude_deg_east)
            or not -180.0 <= self.longitude_deg_east <= 180.0
        ):
            raise ValueError("longitude_deg_east -180..180 aralığında olmalı")

    def as_dict(self) -> dict[str, object]:
        return {
            "site_id": self.site_id,
            "latitude_deg": self.latitude_deg,
            "longitude_deg_east": self.longitude_deg_east,
        }


@dataclass(frozen=True)
class RunnerConfig:
    """Analiz penceresi ve sınıflandırma parametreleri."""

    start_utc: str = "2026-11-14T00:00:00Z"
    hours: float = DEFAULT_ANALYSIS_HOURS
    step_minutes: float = DEFAULT_STEP_MINUTES
    margin_deg: float = 0.10
    refine_boundaries: bool = True
    quality_flag_missing: str = "missing"

    def __post_init__(self) -> None:
        if not math.isfinite(self.hours) or self.hours <= 0.0:
            raise ValueError("hours pozitif olmalı")
        if not math.isfinite(self.step_minutes) or self.step_minutes <= 0.0:
            raise ValueError("step_minutes pozitif olmalı")
        if not math.isfinite(self.margin_deg) or self.margin_deg < 0.0:
            raise ValueError("margin_deg negatif olamaz")

    def visibility_config(self) -> VisibilityConfig:
        return VisibilityConfig(
            margin_deg=self.margin_deg,
            refine_boundaries=self.refine_boundaries,
            quality_flag_missing=self.quality_flag_missing,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "start_utc": self.start_utc,
            "hours": self.hours,
            "step_minutes": self.step_minutes,
            "margin_deg": self.margin_deg,
            "refine_boundaries": self.refine_boundaries,
            "quality_flag_missing": self.quality_flag_missing,
        }


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return default
    return text


@dataclass
class VisibilityRunner:
    """Sağlayıcıları ve çekirdeği birleştiren uçtan uca koşum."""

    ephemeris: EphemerisProvider
    horizon: HorizonProvider
    config: RunnerConfig = field(default_factory=RunnerConfig)

    # ------------------------------------------------------------------ girdi
    def timestamps(self) -> pd.DatetimeIndex:
        return analysis_timestamps(
            self.config.start_utc, self.config.hours, self.config.step_minutes
        )

    def samples(self, site: Site) -> list[Sample]:
        """Efemeris sağlayıcısından site için doğrulanmış örnek serisi üretir."""
        grid = self.timestamps()
        positions = self.ephemeris.positions(site, grid)
        if not isinstance(positions, pd.DataFrame):
            raise TypeError("efemeris sağlayıcısı pandas DataFrame döndürmeli")

        missing = [
            name
            for name in ("timestamp_utc",) + POSITION_COLUMNS
            if name not in positions.columns
        ]
        if missing:
            raise ValueError("efemeris çıktısında eksik sütun(lar): " + ", ".join(missing))

        source_id = _text(getattr(self.ephemeris, "source_id", ""), "unknown")
        source_version = _text(getattr(self.ephemeris, "source_version", ""), "unknown")
        model_id = _text(getattr(self.ephemeris, "model_id", ""), "visibility-v1")

        samples: list[Sample] = []
        for row in positions.to_dict("records"):
            row = dict(row)
            row["site_id"] = _text(row.get("site_id"), site.site_id)
            row["latitude_deg"] = site.latitude_deg
            row["longitude_deg_east"] = site.longitude_deg_east
            row["quality_flag"] = _text(row.get("quality_flag"), "valid")
            row["source_id"] = _text(row.get("source_id"), source_id)
            row["source_version"] = _text(row.get("source_version"), source_version)
            row["model_id"] = _text(row.get("model_id"), model_id)
            if not _text(row.get("parameters")):
                row["parameters"] = json.dumps(
                    {
                        "rule": "altitude_vs_terrain_horizon",
                        "margin_deg": self.config.margin_deg,
                        "refine_boundaries": self.config.refine_boundaries,
                    },
                    sort_keys=True,
                )
            samples.append(sample_from_row(row))

        validate_series(samples)
        return samples

    # ----------------------------------------------------------------- işlem
    def evaluate(
        self, site: Site, horizon: HorizonProvider | None = None
    ) -> list[SampleResult]:
        """Site için örnek bazlı sınıflandırma sonuçları."""
        provider = horizon or self.horizon
        return evaluate_series(
            self.samples(site), provider, self.config.visibility_config()
        )

    def run(
        self, site: Site, horizon: HorizonProvider | None = None
    ) -> pd.DataFrame:
        """Site için sözleşme tablosunu üretir."""
        return results_to_frame(self.evaluate(site, horizon))

    def run_many(
        self,
        sites: list[Site],
        horizons: Mapping[str, HorizonProvider] | None = None,
    ) -> pd.DataFrame:
        """Birden çok siteyi (isteğe bağlı site bazlı ufukla) tek tabloda birleştirir."""
        if not sites:
            raise ValueError("En az bir site verilmeli")
        frames = []
        for site in sites:
            provider = None if horizons is None else horizons.get(site.site_id)
            frames.append(self.run(site, provider))
        return pd.concat(frames, ignore_index=True)

    def windows(
        self,
        site: Site,
        body: str = BODY_JOINT,
        horizon: HorizonProvider | None = None,
    ) -> list[Window]:
        """Site için kesintisiz durum pencereleri."""
        if body not in BODIES:
            raise ValueError(f"Bilinmeyen gövde: {body}")
        return build_windows(
            self.evaluate(site, horizon), body, self.config.visibility_config()
        )


def run_demo(
    *,
    site: Site | None = None,
    horizon_deg: float = 3.0,
    start_utc: str = "2026-11-14T00:00:00Z",
    hours: float = 24.0,
    step_minutes: float = 5.0,
    margin_deg: float = 0.10,
) -> pd.DataFrame:
    """Sentetik efemeris + sabit ufukla hızlı demo tablosu."""
    runner = VisibilityRunner(
        SyntheticEphemeris(),
        ConstantHorizon(horizon_deg),
        RunnerConfig(
            start_utc=start_utc,
            hours=hours,
            step_minutes=step_minutes,
            margin_deg=margin_deg,
        ),
    )
    return runner.run(site or Site("Demo", -89.5, 0.0))


__all__ = [
    "RunnerConfig",
    "Site",
    "VisibilityRunner",
    "run_demo",
]
