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
    frame = app.load_site_series(
        "Site01", "2026-11-15T00:00:00+00:00", 7, 60, app.SOURCE_REAL
    )
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

    frame = app.load_site_series(
        "Site01", "2026-11-15T00:00:00+00:00", 1, 60, app.SOURCE_REAL
    )

    assert not frame.empty
    assert frame.attrs["data_source"] == app.SOURCE_MOCK
    assert "fallback_reason" in frame.attrs
    assert "bulunamadı" in frame.attrs["fallback_reason"]
    assert set(frame["quality_flag"]) == {"test_fixture"}
    assert set(app.DATA_CONTRACT_COLUMNS).issubset(frame.columns)
