"""K1/K2/K4 ile K3 arasındaki entegrasyon yüzeyi.

Bu modül, K3 motorunu diğer modüllerin somut çıktılarına bağlar:

- **K2**: resmi aday bölge kataloğu (`luna_sight.terrain.sites`) ve
  `outputs/k2/<Site>_horizon_<r>m.csv` profilleri.
- **K1**: sözleşme sütunlu efemeris serisi (`--series` yolu; CSV şeması
  :mod:`luna_sight.visibility.series` ile doğrulanır).
- **K4**: `build_site_series(site_id, start_utc, days, step_minutes)`
  imzası; Streamlit arayüzü bu fonksiyonu arar.

K2 veya K1 henüz kurulu değilse K3 tek başına çalışmaya devam eder:
site bilgisi özet JSON'undan, efemeris ise senaryodan gelebilir.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from luna_sight.visibility.grid import DEFAULT_STEP_MINUTES
from luna_sight.visibility.profile import HorizonProfileLookup
from luna_sight.visibility.providers import SyntheticEphemeris
from luna_sight.visibility.runner import RunnerConfig, Site, VisibilityRunner

DEFAULT_PROFILE_ROOT = Path("outputs/k2")
"""K2 ufuk profillerinin varsayılan dizini."""

DEFAULT_RADIUS_PREFERENCE = (4000, 2000, 20000)
"""K4 gibi yarıçap seçmeyen çağıranlar için tercih sırası."""

_PROFILE_RE = re.compile(r"^(?P<site>.+)_horizon_(?P<radius>\d+)m\.csv$")


@dataclass(frozen=True)
class ResolvedProfile:
    """Bir site için seçilen K2 ufuk profili ve köken bilgisi."""

    site_id: str
    radius_m: int
    path: Path
    lookup: HorizonProfileLookup
    quality_flag: str
    summary: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "site_id": self.site_id,
            "radius_m": self.radius_m,
            "path": str(self.path),
            "quality_flag": self.quality_flag,
            "points": int(self.lookup.azimuths.size),
            "horizon_min_deg": round(float(self.lookup.horizons.min()), 4),
            "horizon_max_deg": round(float(self.lookup.horizons.max()), 4),
        }


def find_horizon_profiles(
    site_id: str, root: str | Path = DEFAULT_PROFILE_ROOT
) -> dict[int, Path]:
    """``<Site>_horizon_<r>m.csv`` dosyalarını yarıçapa göre bulur."""
    directory = Path(root)
    found: dict[int, Path] = {}
    if not directory.is_dir():
        return found
    for path in sorted(directory.glob(f"{site_id}_horizon_*m.csv")):
        match = _PROFILE_RE.match(path.name)
        if match and match.group("site") == site_id:
            found[int(match.group("radius"))] = path
    return found


def _summary_path(site_id: str, radius_m: int, root: Path) -> Path | None:
    candidates = [
        root / f"{site_id}_summary_{radius_m}m.json",
        root / f"{site_id}_summary.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _read_summary(site_id: str, radius_m: int, root: Path) -> dict[str, object]:
    path = _summary_path(site_id, radius_m, root)
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_horizon_profile(
    site_id: str,
    radius_m: int | None = None,
    *,
    root: str | Path = DEFAULT_PROFILE_ROOT,
) -> ResolvedProfile:
    """Site için K2 profilini seçer, okur ve kalite bayrağını taşır.

    ``radius_m`` verilmezse 4 km → 2 km → 20 km sırasıyla ilk bulunan
    kullanılır. K2'nin 20 km profilleri DEM kapsamını aştığı için
    ``quality_flag="partial"`` taşır; bu bilgi çağırana korunur.
    """
    directory = Path(root)
    available = find_horizon_profiles(site_id, directory)
    if not available:
        raise KeyError(f"{site_id} için {directory} altında ufuk profili bulunamadı")

    if radius_m is None:
        selected = next(
            (radius for radius in DEFAULT_RADIUS_PREFERENCE if radius in available),
            max(available),
        )
    elif radius_m in available:
        selected = int(radius_m)
    else:
        options = ", ".join(f"{radius} m" for radius in sorted(available))
        raise KeyError(f"{site_id} için {radius_m} m profil yok. Mevcut: {options}")

    summary = _read_summary(site_id, selected, directory)
    quality = str(summary.get("quality_flag", "valid"))
    return ResolvedProfile(
        site_id=site_id,
        radius_m=selected,
        path=available[selected],
        lookup=HorizonProfileLookup.from_csv(available[selected]),
        quality_flag=quality,
        summary=summary,
    )


def resolve_site(
    site_id: str, *, root: str | Path = DEFAULT_PROFILE_ROOT
) -> Site:
    """Site bilgisini K2 kataloğundan, yoksa K2 özet JSON'undan çözer."""
    site = _from_k2_catalog(site_id)
    if site is not None:
        return site

    directory = Path(root)
    available = find_horizon_profiles(site_id, directory)
    radius = next(
        (item for item in DEFAULT_RADIUS_PREFERENCE if item in available),
        max(available) if available else 0,
    )
    summary = _read_summary(site_id, radius, directory)
    latitude = summary.get("lat_deg")
    longitude = summary.get("lon_deg_east")
    if latitude is None or longitude is None:
        raise KeyError(f"Bilinmeyen site: {site_id}")
    return Site(site_id, float(latitude), float(longitude))


def _from_k2_catalog(site_id: str) -> Site | None:
    try:
        from luna_sight.terrain.sites import CANDIDATE_SITES
    except ImportError:
        return None
    candidate = CANDIDATE_SITES.get(site_id)
    if candidate is None:
        return None
    return Site(
        candidate.site_id, candidate.latitude_deg, candidate.longitude_deg_east
    )


def build_site_series(
    site_id: str,
    start_utc,
    days: float,
    step_minutes: float = DEFAULT_STEP_MINUTES,
    *,
    radius_m: int | None = None,
    margin_deg: float = 0.10,
    ephemeris=None,
    horizon=None,
    profile_root: str | Path = DEFAULT_PROFILE_ROOT,
) -> pd.DataFrame:
    """Tek çağrıda sözleşme tablosu üretir (K4 arayüzü).

    İmza Streamlit arayüzünün aradığı biçimdedir::

        build_site_series(site_id, start_utc, days, step_minutes)

    ``ephemeris`` verilmezse senaryo serisi kullanılır ve satırlar
    ``test_fixture`` olarak işaretlenir; gerçek K1 serisi için sözleşme
    sütunlu bir sağlayıcı geçilmelidir. ``horizon`` verilmezse K2 profili
    otomatik seçilir.
    """
    if days <= 0:
        raise ValueError("days pozitif olmalı")
    site = resolve_site(site_id, root=profile_root)

    resolved: ResolvedProfile | None = None
    if horizon is None:
        resolved = resolve_horizon_profile(site_id, radius_m, root=profile_root)
        horizon = resolved.lookup

    start = pd.Timestamp(start_utc)
    if start is pd.NaT:
        raise ValueError("start_utc geçerli bir zaman damgası olmalı")
    if start.tzinfo is None:
        start = start.tz_localize("UTC")

    config = RunnerConfig(
        start_utc=start.isoformat(),
        hours=float(days) * 24.0,
        step_minutes=float(step_minutes),
        margin_deg=float(margin_deg),
    )
    runner = VisibilityRunner(ephemeris or SyntheticEphemeris(), horizon, config)
    frame = runner.run(site)

    if resolved is not None and resolved.quality_flag == "partial":
        frame.loc[frame["quality_flag"] == "valid", "quality_flag"] = "partial"
    return frame


def available_radii(
    site_id: str, root: str | Path = DEFAULT_PROFILE_ROOT
) -> list[int]:
    """Site için mevcut K2 profil yarıçaplarını döndürür."""
    return sorted(find_horizon_profiles(site_id, root))


__all__ = [
    "DEFAULT_PROFILE_ROOT",
    "DEFAULT_RADIUS_PREFERENCE",
    "ResolvedProfile",
    "available_radii",
    "build_site_series",
    "find_horizon_profiles",
    "resolve_horizon_profile",
    "resolve_site",
]
