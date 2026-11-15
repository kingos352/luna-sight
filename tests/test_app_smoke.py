"""K4 arayüzü duman testleri: gerçek K2/K3 çıktısı, mock mod ve yedek yol.

Gerçek çıktı dosyaları (``outputs/k2``, ``outputs/k3``) depoda olduğu için
testler doğrudan onları kullanır. Dosyalar yoksa ilgili testler atlanır.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app" / "app.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

app = importlib.import_module("app.app")


@pytest.fixture()
def clean_caches():
    """``st.cache_data`` önbelleğini testler arasında temizler."""
    app.load_real_site_data.clear()
    app.load_site_series.clear()
    yield
    app.load_real_site_data.clear()
    app.load_site_series.clear()


def _run_app() -> AppTest:
    at = AppTest.from_file(str(APP_PATH), default_timeout=120)
    at.run()
    return at


@pytest.mark.skipif(not app.REAL_AVAILABLE, reason="gerçek K3 çıktısı yok")
def test_default_real_mode_runs_without_exception(clean_caches):
    at = _run_app()

    assert not at.exception
    assert at.selectbox(key="source_mode").value == app.SOURCE_REAL
    assert at.selectbox(key="site_a_real").value == "Site01"
    assert at.selectbox(key="site_b_real").value == "Site04"
    captions = " ".join(m.value for m in at.markdown if "satır" in m.value)
    assert "Connecting ridge" in captions
    assert "Shackleton rim" in captions
    # Gerçek çıktı 168 saatlik pencereye kırpılır: 169 saatlik örnek.
    assert "169 satır" in captions

    # A/B panellerinde kesintisiz ortak iletişim metriği iki kez görünür.
    metric_labels = [metric.label for metric in at.metric]
    assert metric_labels.count("En Uzun Kesintisiz İletişim (Güneş+Dünya)") == 2

    badges = " ".join(m.value for m in at.markdown if "ls-badge" in m.value)
    assert "K1 · JPL Horizons · Efemeris · Tam Entegre · Aktif" in badges
    assert "K2 · LOLA DEM · Topoğrafya · Tam Entegre · Aktif" in badges
    assert "K3 · Görünürlük ve Pencere Motoru · Tam Entegre · Aktif" in badges


@pytest.mark.skipif(not app.REAL_AVAILABLE, reason="gerçek K3 çıktısı yok")
def test_mock_mode_can_be_selected(clean_caches):
    at = _run_app()
    at.selectbox(key="source_mode").set_value(app.SOURCE_MOCK).run()

    assert not at.exception
    assert at.selectbox(key="site_a_mock").value == "shackleton"
    assert any("Çevrimdışı mock" in info.value for info in at.info)


@pytest.mark.skipif(not app.REAL_AVAILABLE, reason="gerçek K3 çıktısı yok")
def test_real_loader_matches_contract(clean_caches):
    frame = app.load_real_site_data("Site01")

    assert not frame.empty
    missing = [column for column in app.DATA_CONTRACT_COLUMNS if column not in frame]
    assert not missing, missing
    assert isinstance(frame["timestamp_utc"].dtype, pd.DatetimeTZDtype)
    assert frame["timestamp_utc"].is_monotonic_increasing
    assert frame.attrs["data_path"].endswith("Site01_visibility.csv")


@pytest.mark.skipif(not app.REAL_AVAILABLE, reason="gerçek K2 çıktısı yok")
def test_horizon_profile_comes_from_k2(clean_caches):
    azimuths, horizons, source = app._site_horizon_profile(app.REAL_SITES["Site04"])

    assert source == "K2"
    assert len(azimuths) == len(horizons) == 360


@pytest.mark.skipif(not app.REAL_AVAILABLE, reason="gerçek K3 çıktısı yok")
def test_longest_joint_window_matches_k3_summary(clean_caches):
    frame = app.load_site_series("shackleton", "2026-11-15T00:00:00+00:00", 7, 60, app.SOURCE_REAL)
    metrics = app.compute_metrics(frame, 60)

    summary = json.loads(
        (ROOT / "outputs" / "k3" / "Site01_summary.json").read_text(encoding="utf-8")
    )
    expected = summary["bodies"]["joint"]["longest_visible_hours"]

    assert metrics.longest_joint_window > 0.0
    assert metrics.longest_joint_window <= metrics.joint_hours
    # 1 saatlik örnekleme nedeniyle K3'ün 5 dk çözünürlüklü değerinden sapabilir.
    assert metrics.longest_joint_window == pytest.approx(expected, abs=1.5)


def test_integration_badges_reflect_real_modules():
    statuses = {code: ready for code, _, ready in app._integration_statuses()}

    assert set(statuses) == {"K1", "K2", "K3"}
    assert statuses["K2"] is True
    assert statuses["K3"] is True
    # K1 efemeris modülü depoya eklenirse bu rozet otomatik yeşile döner.
    assert isinstance(statuses["K1"], bool)

    html = app._integration_badges_html()
    assert html.count("Tam Entegre · Aktif") == 3
    assert "ls-badge-ok" in html


def test_missing_real_file_falls_back_to_synthetic(clean_caches, monkeypatch, tmp_path):
    monkeypatch.setattr(app, "OUTPUT_K3_DIR", tmp_path)
    app.load_real_site_data.clear()
    app.load_site_series.clear()

    frame = app.load_site_series("shackleton", "2026-11-15T00:00:00+00:00", 1, 60, app.SOURCE_REAL)

    assert not frame.empty
    assert frame.attrs["data_source"] == app.SOURCE_MOCK
    assert "fallback_reason" in frame.attrs
    assert "bulunamadı" in frame.attrs["fallback_reason"]
    assert set(frame["quality_flag"]) == {"test_fixture"}
    assert set(app.DATA_CONTRACT_COLUMNS).issubset(frame.columns)


def test_lunar_surface_distance_and_south_pole_map():
    site_a = app.SiteSpec("Site01", "Connecting ridge", -89.463163, -137.489553)
    site_b = app.SiteSpec("Site04", "Shackleton rim", -89.766811, -171.869898)

    dist = app.lunar_surface_distance_km(
        site_a.latitude_deg,
        site_a.longitude_deg_east,
        site_b.latitude_deg,
        site_b.longitude_deg_east,
    )
    # Bölgeler arası beklenen büyük daire mesafesi ~10-12 km
    assert 9.0 <= dist <= 13.0

    fig = app.build_south_pole_map(site_a, site_b)
    assert fig is not None
    assert len(fig.data) == 4
    trace_names = [t.name for t in fig.data]
    assert any("Güney Kutbu" in name for name in trace_names)
    assert any("Bölge A" in name for name in trace_names)
    assert any("Bölge B" in name for name in trace_names)


def test_flight_briefing_card_generation():
    site = app.SiteSpec("Site01", "Connecting ridge", -89.463163, -137.489553)
    now = app.dt.datetime(2026, 11, 15, 0, 0, tzinfo=app.dt.UTC)
    metrics = app.SiteMetrics(
        total_hours=168.0,
        sun_hours=100.0,
        earth_hours=80.0,
        joint_hours=75.0,
        longest_earth_window=40.0,
        longest_joint_window=30.0,
        longest_earth_blackout=12.0,
        optimal_landing_time="2026-11-16 04:00 UTC",
        sun_share=0.85,
        earth_share=0.50,
        joint_uncertain_share=0.02,
        terrain_blocked_share=0.1,
        horizon_mean=1.5,
        horizon_max=3.2,
        horizon_max_az=120.0,
    )

    card = app.generate_flight_briefing_card(
        site, metrics, now, days=7, min_sun_req=70, max_blackout_tol=24
    )
    assert "ARTEMIS-LS-Site01" in card
    assert "SUHAIL STANDARDI" in card
    assert "GO (UÇUŞA UYGUN)" in card
    assert "🟢 GO" in card
    assert "2026-11-16 04:00 UTC" in card


@pytest.mark.skipif(not app.REAL_AVAILABLE, reason="gerçek K3 çıktısı yok")
def test_site_catalog_and_risk_tab_consistency(clean_caches):
    """de_gerlache boylam tutarlılığı ve Arazi Riski sekmesi DEM durumu doğrulanır."""
    assert app.SITES["de_gerlache"].longitude_deg_east == pytest.approx(-87.10)

    at = _run_app()
    assert not at.exception
    # Karar bandı mevcut olmalı
    assert any("ls-verdict" in m.value for m in at.markdown)
    # Metriklerde nan% görünmemeli ve DEM yoksa yanlış başarı mesajı basılmamalı
    metric_vals = [str(m.value) for m in at.metric]
    assert all("nan%" not in v.lower() and "nan°" not in v.lower() for v in metric_vals)
    success_msgs = " ".join(s.value for s in at.success)
    assert "Gerçek LOLA DEM yüklendi" not in success_msgs
