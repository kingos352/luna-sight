"""
tests/test_api.py
=================
FastAPI backend uç noktaları (endpoints) entegrasyon testleri.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_status(client):
    """GET /api/status endpoint testi."""
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online_offline_capable"
    assert "frame_used" in data
    assert data["dem_loaded"] is True
    assert len(data["dem_shape"]) == 2


def test_api_terrain_mesh(client):
    """GET /api/terrain/mesh endpoint testi."""
    res = client.get("/api/terrain/mesh?resolution=64")
    assert res.status_code == 200
    data = res.json()
    assert "elevation_matrix" in data
    assert "width" in data
    assert "height" in data
    assert data["elev_max"] > data["elev_min"]


def test_api_terrain_layers(client):
    """GET /api/terrain/layers endpoint testi."""
    res = client.get("/api/terrain/layers?resolution=64")
    assert res.status_code == 200
    data = res.json()
    assert "slope" in data
    assert "roughness" in data
    assert "illumination" in data
    assert "dte" in data
    assert "suitability" in data
    assert "stats" in data


def test_api_simulate(client):
    """POST /api/simulate endpoint testi."""
    payload = {
        "lat": -89.75,
        "lon": 0.0,
        "elevation_m": 0.0,
        "utc_start": "2026-11-15T00:00:00Z",
        "utc_end": "2026-11-15T06:00:00Z",
        "step_hours": 1.0,
    }
    res = client.post("/api/simulate", json=payload)
    if res.status_code != 200:
        print("SIMULATE ERROR DETAIL:", res.json())
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert len(data["orbital"]["timestamps"]) == 7
    assert len(data["orbital"]["sun_azimuth_deg"]) == 7
    assert "summary" in data
    assert "mean_suitability_score" in data["summary"]


def test_api_terrain_inspect(client):
    """POST /api/terrain/inspect endpoint testi."""
    payload = {
        "norm_x": 0.5,
        "norm_y": 0.5,
        "utc_start": "2026-11-15T00:00:00Z",
        "utc_end": "2026-11-15T06:00:00Z",
        "step_hours": 1.0,
    }
    res = client.post("/api/terrain/inspect", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "elevation_m" in data
    assert "slope_deg" in data
    assert "suitability_score" in data
    assert data["status"] in ["EXCELLENT", "ACCEPTABLE", "UNSAFE"]
    assert len(data["time_series"]) == 7


def test_api_candidates(client):
    """GET /api/terrain/candidates endpoint testi."""
    res = client.get("/api/terrain/candidates")
    assert res.status_code == 200
    data = res.json()
    assert "candidate_sites" in data
    assert len(data["candidate_sites"]) >= 9
    site_ids = [s["site_id"] for s in data["candidate_sites"]]
    assert "MALAPERT_MASSIF" in site_ids
    assert "CONNECTING_RIDGE_EXT" in site_ids
    assert "LEIBNITZ_BETA" in site_ids
    assert "DE_GERLACHE_RIM_1" in site_ids
    assert "DE_GERLACHE_RIM_2" in site_ids
    assert "AMUNDSEN_RIM" in site_ids
    assert "NOBILE_RIM_2" in site_ids
    assert "DE_GERLACHE_KOCHER" in site_ids
    assert "HAWORTH" in site_ids
    # Malapert A ve Mons Mouton aktif listede olmamalı, filtrelenmiş bölgelerde belgelenmeli
    assert "MALAPERT_A" not in site_ids
    assert "MONS_MOUTON" not in site_ids
    assert "filtered_regions" in data["metadata"]


def test_api_ai_landing_stats(client):
    """GET /api/ai/landing/stats endpoint testi."""
    res = client.get("/api/ai/landing/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["total_trials"] >= 50
    assert 0.0 <= data["success_rate_pct"] <= 100.0
    assert "status_counts" in data
    assert "site_performance" in data
    assert len(data["recent_trials"]) > 0


def test_api_ai_landing_run(client):
    """POST /api/ai/landing/run endpoint testi."""
    payload = {
        "site_id": "SITE_ALPHA",
        "initial_altitude_m": 3000.0,
        "apply_noise": True,
    }
    res = client.post("/api/ai/landing/run", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "trial_id" in data
    assert data["target_site_id"] == "SITE_ALPHA"
    assert data["status"] in ["PERFECT_TOUCHDOWN", "SAFE_TOUCHDOWN", "HARD_LANDING", "CRASH"]
    assert 0.0 <= data["scoring"]["total_score"] <= 100.0
    assert len(data["trajectory"]) > 10
    # İlk adımın irtifası yüksek, son adımın irtifası 0 civarında olmalı
    assert data["trajectory"][0]["z_m"] > 2000.0
    assert data["trajectory"][-1]["z_m"] <= 5.0


def test_api_ai_landing_run_artemis_regions(client):
    """POST /api/ai/landing/run ile yeni Artemis III bölgelerine iniş testi."""
    for sid in ["MALAPERT_MASSIF", "CONNECTING_RIDGE_EXT", "LEIBNITZ_BETA"]:
        res = client.post("/api/ai/landing/run", json={"site_id": sid, "initial_altitude_m": 3200.0, "apply_noise": False})
        assert res.status_code == 200
        data = res.json()
        assert data["target_site_id"] == sid
        assert data["status"] in ["PERFECT_TOUCHDOWN", "SAFE_TOUCHDOWN"]
        assert len(data["trajectory"]) > 10


def test_api_ai_landing_analysis(client):
    """GET /api/ai/landing/analysis endpoint testi."""
    res = client.get("/api/ai/landing/analysis")
    assert res.status_code == 200
    data = res.json()
    assert "title" in data
    assert "diagnostics" in data
    assert len(data["diagnostics"]) >= 4
    assert "recommendations" in data
    assert len(data["recommendations"]) >= 3
    assert "standards_compliance" in data
    site_ids = [s["site_id"] for s in data["candidate_sites"]]
    assert "SITE_ALPHA" in site_ids
    assert "SITE_BETA" in site_ids
    assert "SITE_GAMMA" in site_ids
    assert "SITE_DELTA" in site_ids


def test_api_database_endpoints(client):
    """GET /api/database/stats ve GET /api/database/trials testleri."""
    res_stats = client.get("/api/database/stats")
    assert res_stats.status_code == 200
    stats_data = res_stats.json()
    assert "total_trials" in stats_data
    assert "status_counts" in stats_data

    res_trials = client.get("/api/database/trials?limit=10&offset=0")
    assert res_trials.status_code == 200
    trials_data = res_trials.json()
    assert "trials" in trials_data
    assert "count" in trials_data
    assert trials_data["limit"] == 10


def test_api_ml_endpoints(client):
    """GET /api/ml/status, POST /api/ml/train ve POST /api/ml/predict testleri."""
    # 1. ML Durumu
    res_status = client.get("/api/ml/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert "is_trained" in status_data
    assert "feature_importance" in status_data

    # 2. ML Eğitimi
    res_train = client.post("/api/ml/train", json={"force_seed": False, "min_samples": 15})
    assert res_train.status_code == 200
    train_data = res_train.json()
    assert train_data["status"] == "success"
    assert "metrics" in train_data

    # 3. ML Risk Tahmini
    payload = {
        "initial_alt_m": 3100.0,
        "initial_vh_ms": 60.0,
        "initial_vv_ms": -25.0,
        "slope_deg": 3.8,
        "roughness_tri_m": 0.25,
        "solar_illum_pct": 92.0,
        "dte_vis_pct": 94.0,
        "total_mass_kg": 5000.0,
    }
    res_pred = client.post("/api/ml/predict", json=payload)
    assert res_pred.status_code == 200
    pred_data = res_pred.json()
    assert "predicted_score" in pred_data
    assert "probabilities" in pred_data
    assert "SAFE" in pred_data["probabilities"]
    assert "risk_level" in pred_data
    assert "guidance_margins" in pred_data
    assert "advisory_text_tr" in pred_data

