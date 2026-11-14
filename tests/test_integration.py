"""K1/K2/K4 entegrasyon yüzeyi testleri."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest

from luna_sight.visibility import (
    TABLE_COLUMNS,
    Site,
    available_radii,
    build_site_series,
    resolve_horizon_profile,
    resolve_site,
)
from luna_sight.visibility.integration import (
    DEFAULT_PROFILE_ROOT,
    find_horizon_profiles,
)

pytestmark = pytest.mark.skipif(
    not find_horizon_profiles("Site01", DEFAULT_PROFILE_ROOT),
    reason="K2 ufuk profilleri yok",
)


@dataclass(frozen=True)
class ValidEphemeris:
    """Kalite bayrağı ``valid`` olan sabit efemeris (profil kalitesi testi)."""

    sun_alt_deg: float = 40.0

    def positions(self, site, timestamps: pd.DatetimeIndex) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "timestamp_utc": timestamps,
                "sun_az_deg": 0.0,
                "sun_alt_deg": self.sun_alt_deg,
                "earth_az_deg": 0.0,
                "earth_alt_deg": self.sun_alt_deg,
                "quality_flag": "valid",
            }
        )


def test_site_accepts_k2_longitude_convention():
    site = Site("Site01", -89.463163, 222.510447)
    assert site.longitude_deg_east == pytest.approx(222.510447)
    assert Site("Site01", -89.463163, 360.0).longitude_deg_east == 360.0
    with pytest.raises(ValueError):
        Site("Site01", -89.463163, 360.1)


def test_resolve_site_uses_k2_catalog():
    site = resolve_site("Site01")
    assert site.site_id == "Site01"
    assert site.latitude_deg == pytest.approx(-89.463163)
    assert site.longitude_deg_east == pytest.approx(222.510447)


def test_profile_discovery_finds_all_k2_radii():
    assert available_radii("Site01") == [2000, 4000, 20000]
    assert available_radii("Site04") == [2000, 4000, 20000]
    assert available_radii("Yok") == []


def test_default_profile_prefers_4km_and_20km_is_partial():
    default = resolve_horizon_profile("Site04")
    assert default.radius_m == 4000
    assert default.quality_flag == "valid"
    assert default.path.name == "Site04_horizon_4000m.csv"

    regional = resolve_horizon_profile("Site04", 20000)
    assert regional.quality_flag == "partial"
    assert regional.lookup.horizons.min() == pytest.approx(0.368674, abs=1e-6)
    assert regional.lookup.horizons.max() == pytest.approx(31.740239, abs=1e-6)


def test_missing_radius_is_reported_with_options():
    with pytest.raises(KeyError, match="2000 m, 4000 m, 20000 m"):
        resolve_horizon_profile("Site04", 5000)


def test_unknown_site_is_rejected():
    with pytest.raises(KeyError):
        resolve_site("Site99")


def test_build_site_series_matches_k4_signature():
    frame = build_site_series(
        "Site04",
        pd.Timestamp("2026-11-15T00:00:00Z"),
        1,
        60,
    )

    assert list(frame.columns) == list(TABLE_COLUMNS)
    assert len(frame) == 24
    assert set(frame["site_id"]) == {"Site04"}
    assert str(frame["timestamp_utc"].dt.tz) == "UTC"
    assert set(frame["quality_flag"]) == {"test_fixture"}
    assert set(frame["source_id"]) == {"synthetic-scenario"}
    assert frame["longitude_deg_east"].iloc[0] == pytest.approx(188.130102)


def test_build_site_series_accepts_naive_start():
    frame = build_site_series("Site01", "2026-11-15T00:00:00", 1, 120)
    assert len(frame) == 12
    assert str(frame["timestamp_utc"].dt.tz) == "UTC"


def test_partial_profile_quality_propagates_to_valid_rows():
    frame = build_site_series(
        "Site04",
        pd.Timestamp("2026-11-15T00:00:00Z"),
        1,
        120,
        radius_m=20000,
        ephemeris=ValidEphemeris(),
    )
    assert set(frame["quality_flag"]) == {"partial"}
    assert set(frame["joint_visible"]) == {"visible"}


def test_build_site_series_rejects_unknown_site():
    with pytest.raises(KeyError):
        build_site_series("Site99", pd.Timestamp("2026-11-15T00:00:00Z"), 1, 60)
