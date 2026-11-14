"""Gerçek Horizons yanıtıyla uçtan uca kontrol, kasetten oynatılır.

Kaset `tests/cassettes/test_horizons_api/` altında saklanır ve depoya
girer. `pytest-recording` varsayılan kayıt kipi `none` olduğu için bu
test ağa çıkmaz; yanıtı yenilemek için açıkça
`--record-mode=rewrite` verilmesi gerekir.
"""

from __future__ import annotations

import pytest

from luna_sight.ephemeris import Site, build_site_timeseries

START = "2026-11-14 00:00"
STOP = "2026-11-14 06:00"
STEP = "30 m"


@pytest.mark.vcr
def test_real_horizons_timeseries(site: Site) -> None:
    frame, raw = build_site_timeseries(site, START, STOP, step=STEP)

    # 6 saat / 30 dakika = 13 damga (iki uç dahil)
    assert len(frame) == 13
    assert frame["timestamp_utc"].is_monotonic_increasing
    assert frame["timestamp_utc"].dt.tz is not None
    assert (frame["quality_flag"] == "valid").all()

    # Güney kutbunda Güneş ufku sıyırır: yükseklik küçük ve pozitif kalır.
    assert frame["sun_alt_deg"].between(-5.0, 5.0).all()
    # Ay dönüşü yavaştır: 6 saatte azimut birkaç dereceden fazla kaymaz.
    assert abs(frame["sun_az_deg"].iloc[-1] - frame["sun_az_deg"].iloc[0]) < 5.0
    # Yakın tarafta Dünya neredeyse sabittir; bu bölgede ufka çok yakın.
    assert frame["earth_az_deg"].std() < 1.0

    assert raw["sun"].model_id == raw["earth"].model_id == "DE441"
    assert raw["sun"].source_version == "1.2"


@pytest.mark.vcr
def test_real_horizons_longitude_sign_is_east_positive() -> None:
    """Doğu-pozitif boylam Horizons tarafından aynı yönde yorumlanıyor mu.

    Aynı enlemde doğu-pozitif 90 derece ile 270 derece sorgulanır.
    Yönler karışıksa iki noktanın Güneş azimutları ayırt edilemezdi.
    """
    east = Site(site_id="probe_e090", latitude_deg=-85.0, longitude_deg_east=90.0)
    west = Site(site_id="probe_e270", latitude_deg=-85.0, longitude_deg_east=270.0)

    east_frame, _ = build_site_timeseries(east, START, "2026-11-14 00:30", step=STEP)
    west_frame, _ = build_site_timeseries(west, START, "2026-11-14 00:30", step=STEP)

    difference = abs(east_frame.loc[0, "sun_az_deg"] - west_frame.loc[0, "sun_az_deg"])
    assert difference > 10.0
