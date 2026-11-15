"""Aday iniş bölgeleri kataloğu testleri (K2)."""

import pytest

from luna_sight.terrain import CANDIDATE_SITES, CandidateSite, get_candidate_site
from luna_sight.terrain.polar import lonlat_to_xy


def test_candidate_sites_structure():
    assert "Site01" in CANDIDATE_SITES
    assert "Site02" in CANDIDATE_SITES
    assert "Site03" in CANDIDATE_SITES
    assert "Site04" in CANDIDATE_SITES
    assert "Site05" in CANDIDATE_SITES
    assert "Site06" in CANDIDATE_SITES
    assert "Site07" in CANDIDATE_SITES
    assert "Site08" in CANDIDATE_SITES
    assert "Site09" in CANDIDATE_SITES
    assert "Site11" in CANDIDATE_SITES
    assert "Site12" in CANDIDATE_SITES
    assert "Site13" in CANDIDATE_SITES

    for site_id, site in CANDIDATE_SITES.items():
        assert isinstance(site, CandidateSite)
        assert site.site_id == site_id
        assert -90.0 <= site.latitude_deg <= 0.0
        assert -180.0 <= site.longitude_deg_east <= 180.0

        # X, Y koordinatlarının lon/lat ile tutarlılığı (±50 m tolerans)
        calc_x, calc_y = lonlat_to_xy(site.longitude_deg_east, site.latitude_deg)
        assert abs(calc_x - site.x_m) < 50.0, f"{site_id} X koordinatı uyumsuz"
        assert abs(calc_y - site.y_m) < 50.0, f"{site_id} Y koordinatı uyumsuz"


def test_candidate_site_not_found():
    with pytest.raises(KeyError):
        get_candidate_site("Site99_bilinmeyen")
    with pytest.raises(KeyError):
        get_candidate_site("Malapert_A")  # Artemis III adayı olmadığı için katalogda olmamalı
