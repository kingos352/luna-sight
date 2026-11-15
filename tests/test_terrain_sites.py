"""Aday iniş bölgeleri kataloğu testleri (K2)."""

import pytest

from luna_sight.terrain import CANDIDATE_SITES, CandidateSite, get_candidate_site
from luna_sight.terrain.polar import lonlat_to_xy


def test_candidate_sites_structure():
    assert "Site01" in CANDIDATE_SITES
    assert "Site04" in CANDIDATE_SITES

    site1 = get_candidate_site("Site01")
    assert isinstance(site1, CandidateSite)
    assert site1.site_name == "Connecting ridge"
    assert -90.0 <= site1.latitude_deg <= 0.0
    assert -180.0 <= site1.longitude_deg_east <= 180.0

    # X, Y koordinatlarının lon/lat ile tutarlılığı (±50 m tolerans)
    calc_x, calc_y = lonlat_to_xy(site1.longitude_deg_east, site1.latitude_deg)
    assert abs(calc_x - site1.x_m) < 50.0
    assert abs(calc_y - site1.y_m) < 50.0


def test_candidate_site_not_found():
    with pytest.raises(KeyError):
        get_candidate_site("Site99_bilinmeyen")


def test_all_sites_xy_matches_lonlat():
    """Her bölgenin x_m/y_m değeri kendi enlem/boylamından türemiş olmalı.

    Katalog bir dönem 14 bölgenin 11'inde çelişkili değer taşıyordu; sapma
    `CABEUS_RIDGE` için 202 km'ye çıkıyordu. `x_m`/`y_m` bölgesel DEM'i
    örneklemekte kullanıldığı için (`scripts/k2_regional_horizon.py`),
    çelişki yanlış konumdan üretilmiş bir ufuk profilinin doğru bölge adıyla
    kaydedilmesine yol açar.
    """
    inconsistent = []
    for site_id, site in CANDIDATE_SITES.items():
        calc_x, calc_y = lonlat_to_xy(site.longitude_deg_east, site.latitude_deg)
        if abs(calc_x - site.x_m) >= 50.0 or abs(calc_y - site.y_m) >= 50.0:
            inconsistent.append((site_id, site.x_m, site.y_m, calc_x, calc_y))
    assert not inconsistent, f"x_m/y_m enlem/boylamla çelişiyor: {inconsistent}"


def test_catalog_carries_no_measurements():
    """Katalog ölçüm taşımaz; sayılar yalnızca outputs/ altındaki ürünlerden gelir.

    `0.0` varsayılanı da ölçülmüş bir değermiş gibi görünür; bu yüzden
    alanların `None` kalması denetlenir.
    """
    with_values = [site_id for site_id, site in CANDIDATE_SITES.items() if site.has_measurements]
    assert not with_values, f"katalogda bağlanmamış ölçüm değeri var: {with_values}"


def test_catalog_has_no_fabricated_identities():
    """Uydurma bölge kimlikleri katalogda bulunmaz."""
    for fabricated in ("SITE_ALPHA", "SITE_BETA", "SITE_GAMMA", "SITE_DELTA"):
        assert fabricated not in CANDIDATE_SITES


def test_site_descriptions_carry_no_numeric_claims():
    """Açıklama metni ölçüm iddiası taşımaz.

    `SVERDRUP_RIM` açıklaması bir dönem "1.45 derece" eğim iddia ediyordu;
    o sayının depoda bir kaynağı yoktu.
    """
    import re

    pattern = re.compile(r"\d+[.,]?\d*\s*(°|derece|km|%)", re.IGNORECASE)
    offenders = [
        (site_id, text)
        for site_id, site in CANDIDATE_SITES.items()
        for text in (site.description, site.operational_role)
        if pattern.search(text)
    ]
    assert not offenders, f"açıklamada sayısal iddia: {offenders}"
