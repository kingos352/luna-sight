"""
tests/test_multi_region.py
==========================
Çoklu Bölge (Multi-Region) Desteği, NASA LOLA Yerel DEM Kırpma,
Güney Kutbu Alternatif Bilimsel Güvenli İniş Sahaları ve API Entegrasyon Testleri.
"""

from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient
import rasterio

from backend.main import app
from backend.config import DEM_DIR, REGIONS_DIR, ARTEMIS_CANDIDATES_JSON_PATH
from backend.terrain_engine import TerrainEngine
from backend.ai_landing_engine import AILandingEngine


@pytest.fixture
def client():
    return TestClient(app)


def test_candidates_json_categories_and_count():
    """artemis_candidates.json içinde 18 sahanın ve 3 kategorinin eksiksiz olduğunu doğrular."""
    assert ARTEMIS_CANDIDATES_JSON_PATH.exists()
    with open(ARTEMIS_CANDIDATES_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    sites = data.get("candidate_sites", [])
    assert len(sites) == 18

    # Kategorilere göre ayır
    artemis_sites = [s for s in sites if s.get("category") == "ARTEMIS_III_OFFICIAL"]
    shackleton_sites = [s for s in sites if s.get("category") == "SHACKLETON_CRATER_UHD"]
    safe_haven_sites = [s for s in sites if s.get("category") == "SOUTH_POLE_SAFE_HAVEN"]

    assert len(artemis_sites) == 9
    assert len(shackleton_sites) == 4
    assert len(safe_haven_sites) == 5

    # 5 Yeni Sahayı doğrula
    safe_ids = {s["site_id"] for s in safe_haven_sites}
    expected_safe = {"SHOEMAKER_RIM", "FAUSTINI_RIM", "CABEUS_RIDGE", "SLATER_RIM", "SVERDRUP_RIM"}
    assert safe_ids == expected_safe

    # Her sahanın koordinat ve topoğrafya değerlerinin geçerliliği
    for s in safe_haven_sites:
        coords = s["coordinates"]
        topo = s["topography"]
        assert -90.0 <= coords["latitude_deg"] <= -80.0
        assert -180.0 <= coords["longitude_deg"] <= 180.0
        assert topo["slope_deg"] <= 10.0  # Güvenli eğim
        assert topo["roughness_tri_m"] < 1.5


def test_regional_geotiff_files_exist():
    """Tüm 18 aday saha için 256x256 GeoTIFF DEM dosyalarının oluşturulduğunu doğrular."""
    assert REGIONS_DIR.exists()
    
    expected_regions = [
        "MALAPERT_MASSIF", "CONNECTING_RIDGE_EXT", "LEIBNITZ_BETA",
        "DE_GERLACHE_RIM_1", "DE_GERLACHE_RIM_2", "AMUNDSEN_RIM",
        "NOBILE_RIM_2", "DE_GERLACHE_KOCHER", "HAWORTH",
        "SITE_ALPHA", "SITE_BETA", "SITE_GAMMA", "SITE_DELTA",
        "SHOEMAKER_RIM", "FAUSTINI_RIM", "CABEUS_RIDGE", "SLATER_RIM", "SVERDRUP_RIM"
    ]

    for reg_id in expected_regions:
        tif_path = REGIONS_DIR / f"{reg_id}.tif"
        assert tif_path.exists(), f"Eksik bölge DEM dosyası: {tif_path}"
        with rasterio.open(tif_path) as src:
            assert src.width == 256
            assert src.height == 256
            tags = src.tags()
            assert "SITE_ID" in tags
            assert tags["SITE_ID"] == reg_id


def test_terrain_engine_multi_region_loading():
    """TerrainEngine'in farklı bölgeleri önbellekten bağımsız ve doğru yüklediğini doğrular."""
    engine_malapert = TerrainEngine.get_engine_for_region("MALAPERT_MASSIF")
    engine_cabeus = TerrainEngine.get_engine_for_region("CABEUS_RIDGE")
    engine_faustini = TerrainEngine.get_engine_for_region("FAUSTINI_RIM")

    assert engine_malapert.region_id == "MALAPERT_MASSIF"
    assert engine_cabeus.region_id == "CABEUS_RIDGE"
    assert engine_faustini.region_id == "FAUSTINI_RIM"

    # Yükseklik matrisleri birbirinden farklı olmalı
    mesh_m = engine_malapert.get_mesh_data(target_resolution=64)
    mesh_c = engine_cabeus.get_mesh_data(target_resolution=64)
    assert mesh_m["region_id"] == "MALAPERT_MASSIF"
    assert mesh_c["region_id"] == "CABEUS_RIDGE"
    assert mesh_m["elev_max"] != mesh_c["elev_max"]


def test_api_mesh_and_layers_with_region_id(client):
    """GET /api/terrain/mesh ve /layers uç noktalarının region_id parametresini doğru işlediğini doğrular."""
    # 1. Cabeus Ridge Mesh
    res_m = client.get("/api/terrain/mesh?resolution=64&region_id=CABEUS_RIDGE")
    assert res_m.status_code == 200
    data_m = res_m.json()
    assert data_m["region_id"] == "CABEUS_RIDGE"
    assert "elevation_matrix" in data_m

    # 2. Faustini Rim Layers
    res_l = client.get("/api/terrain/layers?resolution=64&region_id=FAUSTINI_RIM")
    assert res_l.status_code == 200
    data_l = res_l.json()
    assert data_l["region_id"] == "FAUSTINI_RIM"
    assert "slope" in data_l
    assert "suitability" in data_l
    assert data_l["stats"]["slope_mean"] < 15.0


def test_api_inspect_with_region_id(client):
    """POST /api/terrain/inspect uç noktasının seçilen bölge DEM'i üzerinden analiz yaptığını doğrular."""
    payload = {
        "norm_x": 0.5,
        "norm_y": 0.5,
        "region_id": "FAUSTINI_RIM",
        "utc_start": "2026-11-15T00:00:00Z",
        "utc_end": "2026-11-15T06:00:00Z",
        "step_hours": 1.0,
    }
    res = client.post("/api/terrain/inspect", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "elevation_m" in data
    assert "slope_deg" in data
    assert data["slope_deg"] <= 8.0  # Faustini düz platosu


def test_ai_landing_on_safe_haven_regions():
    """Yapay zeka otonom iniş motorunun yeni güvenli sahalarda başarıyla indiğini doğrular."""
    ai = AILandingEngine()
    test_sites = ["SHOEMAKER_RIM", "FAUSTINI_RIM", "CABEUS_RIDGE", "SLATER_RIM", "SVERDRUP_RIM"]

    for sid in test_sites:
        res = ai.simulate_landing(site_id=sid, apply_noise=False)
        assert res.status in ["PERFECT_TOUCHDOWN", "SAFE_TOUCHDOWN"]
        assert res.scoring.total_score >= 80.0
        assert len(res.trajectory) > 20
        assert res.fuel_remaining_pct > 15.0
