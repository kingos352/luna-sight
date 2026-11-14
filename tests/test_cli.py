"""Çalıştırılabilir giriş noktası: önbellek, manifest ve CSV çıktısı. Ağa çıkmaz."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
import responses
from conftest import FIXTURE_EARTH, FIXTURE_SUN, SIGNATURE

from luna_sight.ephemeris import API_URL
from luna_sight.ephemeris.__main__ import SITES, main


def _register_all_sites() -> None:
    """Her bölge için Güneş ve Dünya sorgusunu sırayla yanıtla."""
    for _ in SITES:
        for result in (FIXTURE_SUN, FIXTURE_EARTH):
            responses.add(
                responses.GET,
                API_URL,
                json={"signature": SIGNATURE, "result": result},
                status=200,
            )


def test_sites_use_east_positive_longitude() -> None:
    assert len(SITES) >= 2, "en az iki aday bölge karşılaştırılmalı"
    assert len({site.site_id for site in SITES}) == len(SITES)
    for site in SITES:
        assert -90.0 <= site.latitude_deg <= 90.0
        assert 0.0 <= site.longitude_deg_east <= 360.0


@responses.activate
def test_cli_writes_cache_manifest_and_csv(tmp_path: Path) -> None:
    _register_all_sites()
    exit_code = main(
        [
            "--start",
            "2026-11-14 00:00",
            "--hours",
            "1",
            "--step",
            "30 m",
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert exit_code == 0

    cache_dir = tmp_path / "data" / "cache"
    series_files = sorted(path.name for path in cache_dir.glob("ephemeris_*.csv"))
    assert len(series_files) == len(SITES)
    assert series_files[0].endswith("_20261114T0000_1h.csv")

    # Ham yanıt başına bir manifest satırı: bölge sayısı x iki gövde.
    rows = list(csv.DictReader((tmp_path / "data" / "manifest.csv").open(encoding="utf-8")))
    assert len(rows) == 2 * len(SITES)
    assert {row["owner"] for row in rows} == {"K1"}
    assert all(row["local_path"].startswith("data/cache/") for row in rows)
    assert all(len(row["sha256"]) == 64 for row in rows)


def test_cli_requires_start() -> None:
    with pytest.raises(SystemExit):
        main([])
