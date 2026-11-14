"""Ayrıştırıcı, parametre üretimi ve hata yolları. Ağa çıkmaz."""

from __future__ import annotations

import json

import pandas as pd
import pytest
import requests
import responses
from conftest import (
    FIXTURE_SUN,
    FIXTURE_SUN_WITH_GAP,
    FIXTURE_TRUNCATED,
    SIGNATURE,
    SUN_SECOND_ROW,
)

from luna_sight.ephemeris import (
    API_URL,
    HorizonsError,
    HorizonsFormatError,
    Site,
    build_params,
    fetch,
    parse_observer_table,
)


def test_site_longitude_is_east_positive(site: Site) -> None:
    assert site.site_coord == "0.0,-89.45,0.0"
    assert build_params("sun", site, "2026-11-14 00:00", "2026-11-14 01:00")["SITE_COORD"] == (
        "'0.0,-89.45,0.0'"
    )


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(-120.0, 0.0), (0.0, 400.0)],
)
def test_site_rejects_out_of_range_coordinates(latitude: float, longitude: float) -> None:
    with pytest.raises(ValueError):
        Site(site_id="bad", latitude_deg=latitude, longitude_deg_east=longitude)


def test_site_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="site_id"):
        Site(site_id="", latitude_deg=-89.45, longitude_deg_east=0.0)


def test_build_params_is_airless_and_utc_calendar(site: Site) -> None:
    params = build_params("earth", site, "2026-11-14 00:00", "2026-11-21 00:00", step="5 m")
    assert params["COMMAND"] == "'399'"
    assert params["CENTER"] == "'coord@301'"
    assert params["APPARENT"] == "AIRLESS"  # Ay yüzeyinde kırılma yok
    assert params["QUANTITIES"] == "'4'"  # azimut ve yükseklik
    assert params["STEP_SIZE"] == "'5 m'"


def test_build_params_rejects_unknown_body(site: Site) -> None:
    with pytest.raises(ValueError, match="bilinmeyen gövde"):
        build_params("mars", site, "2026-11-14 00:00", "2026-11-14 01:00")


def test_parse_normal_case() -> None:
    frame = parse_observer_table(FIXTURE_SUN)
    assert list(frame.columns) == ["timestamp_utc", "az_deg", "alt_deg"]
    assert len(frame) == 3
    # pandas 3 varsayılan çözünürlüğü mikrosaniyedir; sözleşme için önemli
    # olan damganın UTC bilgisini taşımasıdır, birim çözünürlüğü değil.
    dtype = frame["timestamp_utc"].dtype
    assert isinstance(dtype, pd.DatetimeTZDtype)
    assert str(dtype.tz) == "UTC"
    assert frame["timestamp_utc"].is_monotonic_increasing
    assert frame.loc[0, "az_deg"] == pytest.approx(126.628204)
    assert frame.loc[0, "alt_deg"] == pytest.approx(1.228504)
    assert frame["az_deg"].between(0, 360).all()
    assert frame["alt_deg"].between(-90, 90).all()


def test_parse_keeps_missing_values_as_nan() -> None:
    """`n.a.` görünür ya da engelli sayılmaz, NaN olarak taşınır."""
    frame = parse_observer_table(FIXTURE_SUN_WITH_GAP)
    assert len(frame) == 3
    assert frame["az_deg"].isna().sum() == 1
    assert pd.isna(frame.loc[1, "alt_deg"])


def test_parse_rejects_truncated_response() -> None:
    with pytest.raises(HorizonsFormatError, match=r"\$\$SOE/\$\$EOE"):
        parse_observer_table(FIXTURE_TRUNCATED)


def test_parse_rejects_empty_block() -> None:
    with pytest.raises(HorizonsFormatError, match="boş"):
        parse_observer_table("head\n$$SOE\n$$EOE\ntail")


def test_parse_rejects_unparseable_timestamp() -> None:
    """Beklenmeyen takvim biçimi sessizce NaT'a düşmez."""
    broken = FIXTURE_SUN.replace(SUN_SECOND_ROW, " 14/11/2026 00:30,*, , 1.0, 2.0,")
    with pytest.raises(HorizonsFormatError, match="zaman damgası"):
        parse_observer_table(broken)


def test_parse_skips_blank_lines_inside_block() -> None:
    padded = FIXTURE_SUN.replace(SUN_SECOND_ROW, f"\n   \n{SUN_SECOND_ROW}")
    assert len(parse_observer_table(padded)) == 3


def test_parse_rejects_short_row() -> None:
    broken = FIXTURE_SUN.replace(SUN_SECOND_ROW, " 2026-Nov-14 00:30,*")
    with pytest.raises(HorizonsFormatError, match="eksik kolonlu"):
        parse_observer_table(broken)


@responses.activate
def test_fetch_raises_on_server_error(site: Site) -> None:
    """Hizmet hatası veri gibi işlenmez."""
    responses.add(responses.GET, API_URL, body="service unavailable", status=503)
    with pytest.raises(HorizonsError, match="HTTP 503"):
        fetch("sun", site, "2026-11-14 00:00", "2026-11-14 01:00", session=requests.Session())


@responses.activate
def test_fetch_raises_on_unexpected_payload(site: Site) -> None:
    responses.add(responses.GET, API_URL, json={"signature": {"version": "1.2"}}, status=200)
    with pytest.raises(HorizonsFormatError):
        fetch("sun", site, "2026-11-14 00:00", "2026-11-14 01:00", session=requests.Session())


@responses.activate
def test_fetch_records_provenance(site: Site) -> None:
    responses.add(
        responses.GET,
        API_URL,
        json={"signature": SIGNATURE, "result": FIXTURE_SUN},
        status=200,
    )
    response = fetch(
        "sun", site, "2026-11-14 00:00", "2026-11-14 01:00", session=requests.Session()
    )
    assert response.source_version == "1.2"
    assert response.model_id == "DE441"
    assert len(response.sha256) == 64
    assert response.retrieved_utc.endswith("Z")
    assert json.loads(response.parameters_json)["APPARENT"] == "AIRLESS"
