"""Veri sözleşmesi tablosu, kalite bayrakları ve köken kaydı. Ağa çıkmaz."""

from __future__ import annotations

import csv
import hashlib

import pandas as pd
import pytest
import responses
from conftest import FIXTURE_EARTH, FIXTURE_SUN, FIXTURE_SUN_WITH_GAP, SIGNATURE

from luna_sight.ephemeris import (
    API_URL,
    EPHEMERIS_COLUMNS,
    Site,
    append_manifest_row,
    build_site_timeseries,
    fetch,
    write_cache,
)


def _register(sun_body: str = FIXTURE_SUN) -> None:
    """Güneş ve Dünya sorgularını sırayla yanıtla."""
    for result in (sun_body, FIXTURE_EARTH):
        responses.add(
            responses.GET,
            API_URL,
            json={"signature": SIGNATURE, "result": result},
            status=200,
        )


@responses.activate
def test_timeseries_matches_data_contract(site: Site) -> None:
    _register()
    frame, raw = build_site_timeseries(site, "2026-11-14 00:00", "2026-11-14 01:00", step="30 m")

    assert list(frame.columns) == EPHEMERIS_COLUMNS
    assert len(frame) == 3
    # pandas 3 varsayılan çözünürlüğü mikrosaniyedir; sözleşme için önemli
    # olan damganın UTC bilgisini taşımasıdır, birim çözünürlüğü değil.
    dtype = frame["timestamp_utc"].dtype
    assert isinstance(dtype, pd.DatetimeTZDtype)
    assert str(dtype.tz) == "UTC"
    assert (frame["site_id"] == "shackleton_rim_a").all()
    assert (frame["longitude_deg_east"] == 0.0).all()
    assert (frame["quality_flag"] == "valid").all()
    assert (frame["source_id"] == "jpl_horizons").all()
    assert (frame["model_id"] == "DE441").all()
    assert (frame["source_version"] == "1.2").all()
    assert set(raw) == {"sun", "earth"}

    assert frame["sun_az_deg"].between(0, 360).all()
    assert frame["sun_alt_deg"].between(-90, 90).all()
    assert frame.loc[0, "earth_alt_deg"] == pytest.approx(-0.413)


@responses.activate
def test_missing_angle_becomes_partial_not_visible(site: Site) -> None:
    """Eksik veri `partial` olur; görünür ya da engelli sınıfına çevrilmez."""
    _register(FIXTURE_SUN_WITH_GAP)
    frame, _ = build_site_timeseries(site, "2026-11-14 00:00", "2026-11-14 01:00", step="30 m")

    gap = frame.loc[frame["sun_az_deg"].isna()]
    assert len(gap) == 1
    assert gap["quality_flag"].tolist() == ["partial"]
    assert (frame["quality_flag"] == "valid").sum() == 2
    assert set(frame["quality_flag"]) <= {"valid", "partial", "missing"}


@responses.activate
def test_forced_quality_flag_marks_fixture_data(site: Site) -> None:
    _register()
    frame, _ = build_site_timeseries(
        site, "2026-11-14 00:00", "2026-11-14 01:00", step="30 m", quality_flag="test_fixture"
    )
    assert (frame["quality_flag"] == "test_fixture").all()


@responses.activate
def test_cache_and_manifest_record_provenance(site: Site, tmp_path) -> None:
    responses.add(
        responses.GET,
        API_URL,
        json={"signature": SIGNATURE, "result": FIXTURE_SUN},
        status=200,
    )
    response = fetch("sun", site, "2026-11-14 00:00", "2026-11-14 01:00")

    cached = write_cache(response, tmp_path / "cache")
    assert cached.exists()
    digest = hashlib.sha256(cached.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    assert digest == response.sha256

    manifest = tmp_path / "manifest.csv"
    append_manifest_row(manifest, response, cached)
    rows = list(csv.DictReader(manifest.open(encoding="utf-8")))
    assert len(rows) == 1
    row = rows[0]
    assert row["provider"] == "NASA/JPL"
    assert row["source_url"] == API_URL
    assert row["sha256"] == response.sha256
    assert row["owner"] == "K1"
    assert "AIRLESS" in row["parameters"]

    # Aynı yanıt iki kez yazılmaz, manifest satırı eklenir.
    assert write_cache(response, tmp_path / "cache") == cached
    append_manifest_row(manifest, response, cached, status="partial")
    assert len(list(csv.DictReader(manifest.open(encoding="utf-8")))) == 2
