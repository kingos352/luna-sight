"""
tests/test_landing_db.py
========================
SQLite İniş Veritabanı ve Telemetri Saklama Birim Testleri.
"""

import tempfile
from pathlib import Path
import pytest
import numpy as np

from backend.landing_db import (
    init_db,
    insert_trial,
    get_trials,
    get_stats,
    get_dataset_for_ml,
    clear_database,
    seed_initial_trials,
)
from backend.ai_landing_engine import LandingResult, LandingScoreBreakdown, TrajectoryStep


@pytest.fixture
def temp_db():
    """Geçici test veritabanı yolu sağlar."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass


def test_init_db_and_schema(temp_db):
    """Veritabanı tablosu ve indekslerinin hatasız oluşturulması testi."""
    init_db(temp_db)
    assert temp_db.exists()

    stats = get_stats(temp_db)
    assert stats["total_trials"] == 0
    assert stats["success_rate_pct"] == 0.0


def test_insert_trial_from_dict(temp_db):
    """Sözlük formatında deneme kaydetme testi."""
    sample_trial = {
        "trial_id": "TEST-001",
        "timestamp": "2026-11-15T12:00:00Z",
        "site_id": "SITE_ALPHA",
        "target_lat": -89.78,
        "target_lon": 120.4,
        "initial_alt_m": 3100.0,
        "initial_vh_ms": 60.0,
        "initial_vv_ms": -25.0,
        "final_alt_m": 0.0,
        "touchdown_vxy_ms": 0.25,
        "touchdown_vz_ms": 0.85,
        "tilt_deg": 1.8,
        "fuel_remaining_pct": 14.5,
        "fuel_remaining_kg": 406.0,
        "duration_s": 92.4,
        "slope_deg": 3.4,
        "roughness_tri_m": 0.22,
        "solar_illum_pct": 91.0,
        "dte_vis_pct": 94.0,
        "total_score": 93.5,
        "status": "PERFECT_TOUCHDOWN",
        "status_label_tr": "Mükemmel Yumuşak İniş",
    }

    trial_id = insert_trial(sample_trial, db_path=temp_db)
    assert trial_id == "TEST-001"

    trials = get_trials(limit=10, db_path=temp_db)
    assert len(trials) == 1
    assert trials[0]["trial_id"] == "TEST-001"
    assert trials[0]["site_id"] == "SITE_ALPHA"
    assert trials[0]["total_score"] == 93.5
    assert trials[0]["fuel_consumed_kg"] > 0


def test_insert_trial_from_landing_result(temp_db):
    """LandingResult nesnesi üzerinden veritabanına ekleme testi."""
    scoring = LandingScoreBreakdown(
        vertical_speed_score=24.0,
        horizontal_speed_score=19.0,
        tilt_angle_score=14.5,
        terrain_slope_roughness_score=18.0,
        fuel_reserve_score=10.0,
        environmental_score=9.5,
        total_score=95.0,
    )
    result = LandingResult(
        trial_id="LR-999",
        timestamp="2026-11-15T14:30:00Z",
        target_site_id="SITE_BETA",
        target_site_name="Site Beta",
        target_coords={"norm_x": 0.52, "norm_y": 0.48, "lat": -89.72, "lon": 94.1},
        actual_coords={"norm_x": 0.521, "norm_y": 0.481},
        landing_error_m=12.4,
        duration_s=88.5,
        touchdown_vz_ms=0.92,
        touchdown_vxy_ms=0.18,
        tilt_deg=2.1,
        fuel_remaining_kg=350.0,
        fuel_remaining_pct=12.5,
        status="SAFE_TOUCHDOWN",
        status_label_tr="Güvenli Temas",
        scoring=scoring,
        terrain_metrics={
            "slope_deg": 4.1,
            "roughness_tri_m": 0.31,
            "solar_illumination_pct": 84.0,
            "dte_visibility_pct": 88.0,
        },
        trajectory=[],
    )

    tid = insert_trial(result, db_path=temp_db)
    assert tid == "LR-999"

    stats = get_stats(temp_db)
    assert stats["total_trials"] == 1
    assert stats["success_rate_pct"] == 100.0
    assert stats["average_score"] == 95.0


def test_seed_and_pagination_and_filters(temp_db):
    """Tohumlama, sayfalama ve sorgu filtreleme testi."""
    seeded = seed_initial_trials(count=30, db_path=temp_db)
    assert seeded == 30

    stats = get_stats(temp_db)
    assert stats["total_trials"] == 30
    assert stats["max_score"] >= stats["min_score"]

    # Limit ve Offset testi
    page1 = get_trials(limit=10, offset=0, db_path=temp_db)
    page2 = get_trials(limit=10, offset=10, db_path=temp_db)
    assert len(page1) == 10
    assert len(page2) == 10
    assert page1[0]["trial_id"] != page2[0]["trial_id"]

    # Filtreleme testi: site_id
    alpha_trials = get_trials(limit=50, site_id="SITE_ALPHA", db_path=temp_db)
    for t in alpha_trials:
        assert t["site_id"] == "SITE_ALPHA"


def test_get_dataset_for_ml(temp_db):
    """Makine öğrenimi için veri seti matris çıkarımı testi."""
    seed_initial_trials(count=20, db_path=temp_db)
    X, y_reg, y_cls, feat_names = get_dataset_for_ml(temp_db)

    assert X.shape == (20, 8)
    assert y_reg.shape == (20, 2)
    assert y_cls.shape == (20,)
    assert len(feat_names) == 8
    assert "slope_deg" in feat_names
    assert "initial_vv_ms" in feat_names

    # Sınıf etiketleri standartlaştırılmış olmalı
    for label in y_cls:
        assert label in ["SAFE", "HARD", "CRASH"]


def test_clear_database(temp_db):
    """Veritabanını temizleme testi."""
    seed_initial_trials(count=15, db_path=temp_db)
    assert get_stats(temp_db)["total_trials"] == 15

    ok = clear_database(temp_db)
    assert ok is True
    assert get_stats(temp_db)["total_trials"] == 0
