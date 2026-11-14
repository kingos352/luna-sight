"""Ephemeris serisi okuma ve doğrulama (test_fixture)."""

from datetime import UTC, datetime

import pytest

from luna_sight.visibility.series import (
    Sample,
    load_series_csv,
    parse_utc,
    sample_from_row,
    validate_series,
)

HEADER = "timestamp_utc,site_id,latitude_deg,longitude_deg_east,sun_az_deg,sun_alt_deg,earth_az_deg,earth_alt_deg,quality_flag\n"


def write_csv(tmp_path, body):
    path = tmp_path / "series.csv"
    path.write_text(HEADER + body, encoding="utf-8")
    return path


def test_parse_utc_normalises_to_utc():
    assert parse_utc("2026-11-15T00:00:00Z") == datetime(
        2026, 11, 15, tzinfo=UTC
    )
    # Zaman dilimi belirtilmemiş metin UTC kabul edilir.
    assert parse_utc("2026-11-15 03:00:00") == datetime(
        2026, 11, 15, 3, tzinfo=UTC
    )
    # +03:00 → UTC'ye çevrilir.
    assert parse_utc("2026-11-15T03:00:00+03:00") == datetime(
        2026, 11, 15, tzinfo=UTC
    )


def test_load_series_reads_optional_columns(tmp_path):
    path = write_csv(
        tmp_path,
        "2026-11-15T00:00:00Z,Site04,-89.766811,-171.869898,10,1,20,2,valid\n"
        "2026-11-15T00:05:00Z,Site04,-89.766811,-171.869898,11,1.1,21,2.1,valid\n",
    )
    samples = load_series_csv(path)
    assert len(samples) == 2
    assert samples[0].latitude_deg == pytest.approx(-89.766811)
    assert samples[0].longitude_deg_east == pytest.approx(-171.869898)
    assert samples[1].sun_az_deg == pytest.approx(11.0)


def test_empty_and_invalid_tokens_become_none(tmp_path):
    path = write_csv(
        tmp_path,
        "2026-11-15T00:00:00Z,Site04,,,,,,,valid\n"
        "2026-11-15T00:05:00Z,Site04,,,NaN,1,n/a,2,valid\n",
    )
    samples = load_series_csv(path)
    assert samples[0].sun_alt_deg is None
    assert samples[0].earth_az_deg is None
    assert samples[1].sun_az_deg is None
    assert samples[1].earth_az_deg is None
    assert samples[1].sun_alt_deg == pytest.approx(1.0)


def test_missing_required_column_raises(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("timestamp_utc,sun_az_deg\n2026-11-15T00:00:00Z,10\n", encoding="utf-8")
    with pytest.raises(ValueError, match="zorunlu sütunlar"):
        load_series_csv(path)


def test_non_increasing_timestamps_rejected(tmp_path):
    path = write_csv(
        tmp_path,
        "2026-11-15T00:05:00Z,Site04,,,10,1,20,2,valid\n"
        "2026-11-15T00:05:00Z,Site04,,,11,1,21,2,valid\n",
    )
    with pytest.raises(ValueError, match="kesin artan"):
        load_series_csv(path)

    path2 = write_csv(
        tmp_path,
        "2026-11-15T00:10:00Z,Site04,,,10,1,20,2,valid\n"
        "2026-11-15T00:05:00Z,Site04,,,11,1,21,2,valid\n",
    )
    with pytest.raises(ValueError, match="kesin artan"):
        load_series_csv(path2)


def test_empty_series_rejected():
    with pytest.raises(ValueError):
        validate_series([])


def test_sample_from_row_defaults():
    sample = sample_from_row(
        {
            "timestamp_utc": "2026-11-15T00:00:00Z",
            "sun_az_deg": "0",
            "sun_alt_deg": "1",
            "earth_az_deg": "10",
            "earth_alt_deg": "2",
        }
    )
    assert isinstance(sample, Sample)
    assert sample.site_id == ""
    assert sample.quality_flag == "valid"
    assert sample.latitude_deg is None
