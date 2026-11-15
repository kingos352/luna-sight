"""
tests/test_ai_landing_engine.py
===============================
Ay ve Uzay Fiziği ile Yapay Zeka İniş Simülasyon Motoru Birim ve Yörünge Testleri.
"""

import math
import pytest
from backend.ai_landing_engine import (
    AILandingEngine,
    G_MOON,
    G0,
    M_DRY_KG,
    M_PROP_INITIAL_KG,
    M_TOTAL_INITIAL_KG,
    T_MAX_NEWTON,
    ISP_SECONDS,
)


@pytest.fixture
def landing_engine():
    return AILandingEngine()


def test_physical_constants():
    """Fiziksel sabitlerin NASA ve görev şartnamesine uygunluğu testi."""
    assert G_MOON == 1.62
    assert G0 == 9.80665
    assert M_DRY_KG == 2200.0
    assert M_PROP_INITIAL_KG == 2800.0
    assert M_TOTAL_INITIAL_KG == 5000.0
    assert T_MAX_NEWTON == 18000.0
    assert ISP_SECONDS == 315.0


def test_simulation_nominal_site_alpha(landing_engine):
    """Site Alpha için iniş yörüngesi ve güdüm testi."""
    res = landing_engine.simulate_landing(
        site_id="SITE_ALPHA",
        initial_altitude_m=3200.0,
        apply_noise=False,
    )

    assert res.target_site_id == "SITE_ALPHA"
    assert res.status in ["PERFECT_TOUCHDOWN", "SAFE_TOUCHDOWN"]
    # Düşey iniş hızı Artemis sınırı (<= 1.5 m/s) içinde olmalı
    assert res.touchdown_vz_ms <= 1.5
    # Yatay sürüklenme hızı (<= 0.4 m/s) içinde olmalı
    assert res.touchdown_vxy_ms <= 0.4
    # Gövde eğimi (<= 5.0°) içinde olmalı
    assert res.tilt_deg <= 5.0
    # Kalan yakıt marjı (> %5) güvenli olmalı
    assert res.fuel_remaining_pct > 5.0
    # Toplam puan 80'in üzerinde olmalı
    assert res.scoring.total_score >= 80.0
    # Yörünge adımları geçerli olmalı
    assert len(res.trajectory) > 20
    assert res.trajectory[0].z_m > 3000.0
    assert res.trajectory[-1].z_m <= 1.0


def test_landing_health_scoring_extremes(landing_engine):
    """Puantaj sisteminin uç değerler (mükemmel vs kaza) için testi."""
    # 1. Mükemmel iniş kriterleri
    bd_perf, status_perf, _ = landing_engine.evaluate_landing_health(
        vz_ms=-0.8,
        vxy_ms=0.1,
        tilt_deg=1.5,
        slope_deg=1.0,
        roughness_m=0.2,
        fuel_pct=15.0,
        solar_pct=90.0,
        dte_pct=85.0,
    )
    assert bd_perf.total_score >= 90.0
    assert status_perf == "PERFECT_TOUCHDOWN"

    # 2. Sert iniş (Hard Landing) kriterleri
    bd_hard, status_hard, _ = landing_engine.evaluate_landing_health(
        vz_ms=-3.8,
        vxy_ms=0.8,
        tilt_deg=6.0,
        slope_deg=6.0,
        roughness_m=0.8,
        fuel_pct=4.0,
        solar_pct=60.0,
        dte_pct=50.0,
    )
    assert 40.0 <= bd_hard.total_score < 75.0
    assert status_hard == "HARD_LANDING"

    # 3. Kaza (Crash) kriterleri (Yüksek düşey hız > 5 m/s)
    bd_crash, status_crash, _ = landing_engine.evaluate_landing_health(
        vz_ms=-6.5,
        vxy_ms=2.5,
        tilt_deg=18.0,
        slope_deg=14.0,
        roughness_m=2.0,
        fuel_pct=0.0,
        solar_pct=10.0,
        dte_pct=10.0,
    )
    assert bd_crash.total_score < 40.0
    assert status_crash == "CRASH"


def test_custom_coordinates_landing(landing_engine):
    """Özel tıklanan normalize koordinatlar için iniş testi."""
    res = landing_engine.simulate_landing(
        custom_norm_x=0.45,
        custom_norm_y=0.45,
        initial_altitude_m=2500.0,
        apply_noise=True,
    )
    assert res.target_site_id == "CUSTOM_TARGET"
    assert len(res.trajectory) > 10
    assert res.target_coords["norm_x"] == 0.45
    assert res.target_coords["norm_y"] == 0.45


def test_monte_carlo_stats_and_analysis_report(landing_engine):
    """Monte Carlo istatistikleri ve AI analiz raporu üretim testi."""
    stats = landing_engine.get_stats()
    assert stats["total_trials"] >= 50
    assert stats["success_rate_pct"] > 70.0
    assert "status_counts" in stats
    assert "metrics" in stats
    assert stats["metrics"]["mean_touchdown_vz_ms"] < 2.0

    report = landing_engine.generate_ai_analysis_report()
    assert "NASA Artemis" in report["title"]
    assert len(report["diagnostics"]) == 4
    assert len(report["recommendations"]) == 3
    assert report["recommended_site"]["site_id"] in landing_engine.candidate_sites


def test_simulation_artemis_candidate_regions(landing_engine):
    """Yeni Artemis III resmi aday bölgelerine iniş simülasyonu testleri."""
    test_regions = ["MALAPERT_MASSIF", "CONNECTING_RIDGE_EXT", "LEIBNITZ_BETA", "DE_GERLACHE_RIM_1"]
    for reg_id in test_regions:
        res = landing_engine.simulate_landing(
            site_id=reg_id,
            initial_altitude_m=3200.0,
            apply_noise=False,
        )
        assert res.target_site_id == reg_id
        assert res.status in ["PERFECT_TOUCHDOWN", "SAFE_TOUCHDOWN"]
        assert res.touchdown_vz_ms <= 1.5
        assert res.scoring.total_score >= 80.0
        assert len(res.trajectory) > 10
