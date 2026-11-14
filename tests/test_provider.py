"""K3 efemeris sağlayıcı adaptörü. Ağa çıkmaz.

`site` nesnesi bilinçli olarak K3 tipiyle değil, protokolün beklediği üç
alanı taşıyan sade bir nesneyle verilir: K1 ile K3 arasında derleme zamanı
bağımlılığı olmadığının testi budur.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest
import responses
from conftest import FIXTURE_EARTH, FIXTURE_SUN, SIGNATURE

from luna_sight.ephemeris import API_URL, POSITION_COLUMNS, HorizonsEphemeris, Site

#: `FIXTURE_SUN` ve `FIXTURE_EARTH` bu üç damgayı içeriyor.
GRID = pd.date_range("2026-11-14 00:00", periods=3, freq="30min", tz="UTC")


@dataclass(frozen=True)
class K3Site:
    """K3 tarafından verilen bölge nesnesinin ördek tiplemesi."""

    site_id: str
    latitude_deg: float
    longitude_deg_east: float


SITE = K3Site(site_id="Site01", latitude_deg=-89.463163, longitude_deg_east=-137.489553)


def _register(sun: str = FIXTURE_SUN) -> None:
    for result in (sun, FIXTURE_EARTH):
        responses.add(
            responses.GET,
            API_URL,
            json={"signature": SIGNATURE, "result": result},
            status=200,
        )


@responses.activate
def test_positions_matches_protocol() -> None:
    _register()
    frame = HorizonsEphemeris().positions(SITE, GRID)

    assert list(frame.columns) == ["timestamp_utc", *POSITION_COLUMNS]
    assert len(frame) == len(GRID)
    assert list(frame["timestamp_utc"]) == list(GRID)
    assert frame["sun_alt_deg"].iloc[0] == pytest.approx(1.228504)
    assert frame["earth_alt_deg"].iloc[0] == pytest.approx(-0.413)
    assert frame[list(POSITION_COLUMNS)].notna().all().all()


@responses.activate
def test_step_is_derived_from_requested_grid() -> None:
    _register()
    HorizonsEphemeris().positions(SITE, GRID)
    first_request = responses.calls[0].request
    assert "STEP_SIZE=%2730+m%27" in first_request.url or "30+m" in first_request.url


@responses.activate
def test_site_coordinates_are_passed_through() -> None:
    _register()
    HorizonsEphemeris().positions(SITE, GRID)
    url = responses.calls[0].request.url
    assert "-137.489553" in url
    assert "-89.463163" in url


@responses.activate
def test_raw_responses_are_exposed_for_provenance() -> None:
    _register()
    provider = HorizonsEphemeris()
    provider.positions(SITE, GRID)
    assert set(provider.last_responses) == {"sun", "earth"}
    assert provider.last_responses["sun"].model_id == "DE441"
    assert len(provider.last_responses["sun"].sha256) == 64


@responses.activate
def test_timestamp_outside_horizons_answer_stays_nan() -> None:
    """Eksik damga doldurulmaz; K3 bunu uncertain olarak sınıflar."""
    _register()
    extended = GRID.append(pd.DatetimeIndex(["2026-11-14 01:30:00+00:00"]))
    frame = HorizonsEphemeris().positions(SITE, extended)

    assert len(frame) == 4
    last = frame.iloc[-1]
    assert pd.isna(last["sun_az_deg"])
    assert pd.isna(last["earth_alt_deg"])
    assert frame.iloc[:3][list(POSITION_COLUMNS)].notna().all().all()


def test_naive_grid_is_rejected() -> None:
    naive = pd.date_range("2026-11-14 00:00", periods=3, freq="30min")
    with pytest.raises(ValueError, match="UTC"):
        HorizonsEphemeris().positions(SITE, naive)


def test_empty_grid_is_rejected() -> None:
    with pytest.raises(ValueError, match="boş"):
        HorizonsEphemeris().positions(SITE, pd.DatetimeIndex([], tz="UTC"))


def test_irregular_grid_is_rejected() -> None:
    irregular = pd.DatetimeIndex(
        ["2026-11-14 00:00:00+00:00", "2026-11-14 00:30:00+00:00", "2026-11-14 02:00:00+00:00"]
    )
    with pytest.raises(ValueError, match="düzenli aralıklı"):
        HorizonsEphemeris().positions(SITE, irregular)


def test_sub_minute_step_is_rejected() -> None:
    fine = pd.date_range("2026-11-14 00:00", periods=3, freq="30s", tz="UTC")
    with pytest.raises(ValueError, match="tam dakika"):
        HorizonsEphemeris().positions(SITE, fine)


def test_site_without_required_fields_is_rejected() -> None:
    with pytest.raises(TypeError, match="site_id"):
        HorizonsEphemeris().positions(object(), GRID)


@responses.activate
def test_native_site_object_is_accepted() -> None:
    """K1 kendi `Site` nesnesini de kabul eder; dönüşüm atlanır."""
    _register()
    native = Site(site_id="Site01", latitude_deg=-89.463163, longitude_deg_east=-137.489553)
    frame = HorizonsEphemeris().positions(native, GRID)
    assert len(frame) == len(GRID)


@responses.activate
def test_single_timestamp_uses_contract_default_step() -> None:
    """Tek damgadan adım çıkarılamaz; veri sözleşmesi varsayılanı 5 dakikadır."""
    _register()
    HorizonsEphemeris().positions(SITE, GRID[:1])
    assert "5+m" in responses.calls[0].request.url


@responses.activate
def test_unsorted_grid_is_sorted_before_query() -> None:
    _register()
    shuffled = GRID[[2, 0, 1]]
    frame = HorizonsEphemeris().positions(SITE, shuffled)
    assert list(frame["timestamp_utc"]) == list(GRID)
    assert frame[list(POSITION_COLUMNS)].notna().all().all()
