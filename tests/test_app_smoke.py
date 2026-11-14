"""K4 arayüzü duman testleri: gerçek K2/K3 çıktısı, mock mod ve yedek yol.

Gerçek çıktı dosyaları (``outputs/k2``, ``outputs/k3``) depoda olduğu için
testler doğrudan onları kullanır. Dosyalar yoksa ilgili testler atlanır.
"""

from __future__ import annotations

import importlib
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
