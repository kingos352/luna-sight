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
