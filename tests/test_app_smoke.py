"""K4 arayüzü duman testleri: gerçek K2/K3 çıktısı, mock mod ve yedek yol.

Gerçek çıktı dosyaları (``outputs/k2``, ``outputs/k3``) depoda olduğu için
testler doğrudan onları kullanır. Dosyalar yoksa ilgili testler atlanır.
"""

from __future__ import annotations

import ast
import importlib
import json
import re
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


def test_globe_is_bidirectional_component_and_has_no_duplicate_ai_tab():
    at = _run_app()
    assert not at.exception
    assert not any(tab.label == "AI yüzey analizi" for tab in at.tabs)
    assert any(tab.label == "3B Ay küresi" for tab in at.tabs)
    components = at.get("component_instance")
    assert components
    assert "lunar_sight" in components[0].proto.component_name


def test_globe_build_contains_real_python_bridge():
    html = (app.GLOBE_DIR / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r'src="\./(assets/[^\"]+\.js)"', html)
    assert scripts, "AI component build is missing"
    bundle = "".join((app.GLOBE_DIR / path).read_text(encoding="utf-8") for path in scripts)
    assert "streamlit:setComponentValue" in bundle
    assert "streamlit:componentReady" in bundle
    assert "Moondream" not in bundle


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
    frame = app.load_site_series("Site01", "2026-11-15T00:00:00+00:00", 7, 60, app.SOURCE_REAL)
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

    frame = app.load_site_series("Site01", "2026-11-15T00:00:00+00:00", 1, 60, app.SOURCE_REAL)

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
    # Metriklerde nan% görünmemeli ve canlı GeoTIFF olmadan yanlış GeoTIFF başarı mesajı basılmamalı
    metric_vals = [str(m.value) for m in at.metric]
    assert all("nan%" not in v.lower() and "nan°" not in v.lower() for v in metric_vals)
    success_msgs = " ".join(s.value for s in at.success)
    info_msgs = " ".join(i.value for i in at.info)
    assert "Gerçek LOLA DEM yüklendi" not in success_msgs
    assert "Ön-hesaplanmış LOLA DEM özeti aktif" in success_msgs
    assert "11/12 Ön-hesaplanmış LOLA DEM" in info_msgs
    assert "1/12 Analitik Kutup Yükselti Modeli" in info_msgs
    # 12 aday bölgenin özet expander başlığı Arazi Riski sekmesinde yer almalı
    expander_labels = [e.label for e in at.expander]
    assert any("12 Bölge" in label for label in expander_labels)


@pytest.mark.skipif(not app.REAL_AVAILABLE, reason="gerçek K3 çıktısı yok")
def test_real_sites_discovers_all_12_artemis_sites(clean_caches):
    expected_ids = [
        "Site01",
        "Site02",
        "Site03",
        "Site04",
        "Site05",
        "Site06",
        "Site07",
        "Site08",
        "Site09",
        "Site11",
        "Site12",
        "Site13",
    ]
    assert list(app.REAL_SITES.keys()) == expected_ids

    for site_id in expected_ids:
        spec = app.REAL_SITES[site_id]
        assert spec.origin == "real"
        assert spec.name != site_id
        assert spec.horizon_csv is not None and spec.horizon_csv.is_file()
        azimuths, horizons, source = app._site_horizon_profile(spec)
        assert source == "K2"
        assert len(azimuths) == len(horizons) == 360

        frame = app.load_site_series(site_id, "2026-11-14T00:00:00+00:00", 7, 60, app.SOURCE_REAL)
        metrics = app.compute_metrics(frame, 60)
        assert metrics.total_hours > 0.0


def test_normalize_contract_and_engine_preserve_canonical_source_id(clean_caches):
    site = app.SITES["shackleton"]
    start_utc = app.dt.datetime(2026, 11, 15, 0, 0, tzinfo=app.dt.UTC)
    synthetic = app.generate_synthetic_series(site, start_utc, days=1, step_minutes=60)

    # İsteğe bağlı margin sütunları olmadan normalize_contract_frame hatasız çalışmalı
    minimal = synthetic.loc[:, app.DATA_CONTRACT_COLUMNS].copy()
    normalized_min = app.normalize_contract_frame(minimal)
    assert set(app.DATA_CONTRACT_COLUMNS).issubset(normalized_min.columns)

    # String margin değerleri (boşluk dahil) sayısal tipe dönüştürülmeli
    with_margins = minimal.copy()
    with_margins["sun_margin_deg"] = ["1.250000"] * (len(with_margins) - 1) + [""]
    with_margins["earth_margin_deg"] = "-0.500000"
    with_margins["joint_margin_deg"] = "-0.500000"
    normalized_margins = app.normalize_contract_frame(with_margins)
    assert pd.api.types.is_numeric_dtype(normalized_margins["sun_margin_deg"])
    assert pd.api.types.is_numeric_dtype(normalized_margins["earth_margin_deg"])
    assert pd.api.types.is_numeric_dtype(normalized_margins["joint_margin_deg"])
    assert normalized_margins["sun_margin_deg"].iloc[0] == pytest.approx(1.25)
    assert pd.isna(normalized_margins["sun_margin_deg"].iloc[-1])

    # _evaluate_with_engine kanonik source_id değerini '+K3' eklemeden korumalı
    canonical = synthetic.copy()
    canonical["source_id"] = "jpl-horizons"
    evaluated = app._evaluate_with_engine(canonical, site)
    if app._engine_available():
        assert evaluated is not None
        assert set(evaluated["source_id"]) == {"jpl-horizons"}
        assert not evaluated["source_id"].astype(str).str.contains(r"\+K3", regex=True).any()
        assert isinstance(evaluated["timestamp_utc"].dtype, pd.DatetimeTZDtype)
        for margin_col in ("sun_margin_deg", "earth_margin_deg", "joint_margin_deg"):
            assert pd.api.types.is_numeric_dtype(evaluated[margin_col])


@pytest.mark.skipif(not app.REAL_AVAILABLE, reason="gerçek K3 çıktısı yok")
def test_selecting_site08_and_site13_runs_cleanly(clean_caches):
    at = _run_app()
    at.selectbox(key="site_a_real").set_value("Site08").run()
    at.selectbox(key="site_b_real").set_value("Site13").run()

    assert not at.exception
    verdict_html = " ".join(m.value for m in at.markdown if "ls-verdict" in m.value)
    assert "notranslate" in verdict_html
    assert "Site08" in verdict_html
    assert "Site13" in verdict_html
    code_blocks = "\n".join(c.value for c in at.code)
    assert "Malapert massif" in code_blocks
    assert "Mons Mouton" in code_blocks
    info_msgs = " ".join(i.value for i in at.info)
    assert "Analitik Kutup Yükselti Modeli özeti aktif" in info_msgs


def test_moon_trek_static_data_synced_for_all_12_sites():
    expected_ids = [
        "Site01",
        "Site02",
        "Site03",
        "Site04",
        "Site05",
        "Site06",
        "Site07",
        "Site08",
        "Site09",
        "Site11",
        "Site12",
        "Site13",
    ]
    data_dir = ROOT / "app" / "static" / "moon" / "data"

    windows_payload = json.loads((data_dir / "windows.json").read_text(encoding="utf-8"))
    assert list(windows_payload.keys()) == expected_ids
    for site_id in expected_ids:
        entry = windows_payload[site_id]
        assert set(entry.keys()) == {"windows", "summary"}
        assert set(entry["windows"].keys()) == {"sun", "earth", "joint"}
        lon = entry["summary"]["coordinate"]["longitude_deg_east"]
        assert -180.0 <= float(lon) <= 180.0

    horizons_payload = json.loads((data_dir / "horizons.json").read_text(encoding="utf-8"))
    assert list(horizons_payload.keys()) == expected_ids
    for site_id in expected_ids:
        site_horizons = horizons_payload[site_id]
        assert "20000m" in site_horizons
        assert len(site_horizons["20000m"]["azimuth_deg"]) == 360
        assert len(site_horizons["20000m"]["horizon_deg"]) == 360
        assert len(site_horizons["20000m"]["occluder_distance_m"]) == 360
    assert {"2000m", "4000m", "20000m"}.issubset(horizons_payload["Site01"])
    assert {"2000m", "4000m", "20000m"}.issubset(horizons_payload["Site04"])

    geojson_payload = json.loads((data_dir / "survey_targets.geojson").read_text(encoding="utf-8"))
    features = geojson_payload["features"]
    polygons = [f for f in features if f["geometry"]["type"] == "Polygon"]
    points = [f for f in features if f["geometry"]["type"] == "Point"]
    assert len(polygons) == 5
    assert [p["properties"]["site_id"] for p in points] == expected_ids
    for point in points:
        lon, lat = point["geometry"]["coordinates"]
        assert -180.0 <= float(lon) <= 180.0
        assert -90.0 <= float(lat) <= 0.0
        assert point["properties"]["site_name"]
        assert point["properties"]["description"]


def test_render_globe_tab_bridge_query_params(monkeypatch):
    captured_urls: list[str] = []
    monkeypatch.setattr(app.components, "iframe", lambda url, **kwargs: captured_urls.append(url))
    monkeypatch.setattr(app.st, "caption", lambda *args, **kwargs: None)

    url_default = app.render_globe_tab()
    assert url_default == app.GLOBE_URL

    site_a = app.SiteSpec("Site08", "Malapert massif", -86.0, 2.7)
    site_b = app.SiteSpec("Site13", "Mons Mouton", -84.6, 31.0)
    url_pair = app.render_globe_tab(site_a, site_b)
    assert url_pair == f"{app.GLOBE_URL}?siteA=Site08&siteB=Site13"
    assert captured_urls == [app.GLOBE_URL, f"{app.GLOBE_URL}?siteA=Site08&siteB=Site13"]


def test_build_south_pole_map_corridors_optional():
    from luna_sight.terrain import find_safe_corridor

    site_a = app.SiteSpec("Site01", "Connecting ridge", -89.463163, -137.489553)
    site_b = app.SiteSpec("Site04", "Shackleton rim", -89.766811, -171.869898)

    fig_base = app.build_south_pole_map(site_a, site_b)
    assert len(fig_base.data) == 4

    corridor_a = find_safe_corridor("Site01")
    corridor_b = find_safe_corridor("Site04")
    fig_corridor = app.build_south_pole_map(
        site_a, site_b, corridor_a=corridor_a, corridor_b=corridor_b
    )
    assert len(fig_corridor.data) == 8
    trace_names = [trace.name for trace in fig_corridor.data]
    assert any("A* Koridor A" in name for name in trace_names)
    assert any("A* Koridor B" in name for name in trace_names)
    assert any("PSR Hedef A" in name for name in trace_names)
    assert any("PSR Hedef B" in name for name in trace_names)


def test_slider_order_invariant_for_demo_recorder():
    """k5_record_demo.py focus_last_slider() her zaman horizon_tab zaman kaydırıcısını seçmeli."""
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    def _slider_calls(node: ast.AST) -> list[tuple[int, str]]:
        calls: list[tuple[int, str]] = []
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if isinstance(func, ast.Attribute) and func.attr == "slider":
                label = ""
                if child.args and isinstance(child.args[0], ast.Constant):
                    label = str(child.args[0].value)
                calls.append((child.lineno, label))
        return sorted(calls)

    # render_risk_tab, render_data_tab ve alt yardımcılarında hiç st.slider olmamalı
    forbidden_funcs = {
        "render_risk_tab",
        "render_data_tab",
        "_render_landing_hazard_section",
        "_render_gateway_relay_section",
        "_render_comms_link_section",
    }
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
        if fn.name in forbidden_funcs:
            assert _slider_calls(fn) == [], f"{fn.name} içinde st.slider yasak!"

    # main() içindeki son st.slider çağrısı horizon_tab'daki zaman adımı olmalı
    main_fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    main_sliders = _slider_calls(main_fn)
    assert main_sliders, "main() içinde zaman adımı kaydırıcısı bulunamadı"
    assert main_sliders[-1][1] == "Zaman adımı (0 = görev başlangıcı)"

    # timeline_tab / map_tab / risk_tab / data_tab satırlarından sonra slider gelmemeli
    timeline_line = next(
        idx for idx, line in enumerate(source.splitlines(), start=1) if "with timeline_tab:" in line
    )
    assert main_sliders[-1][0] < timeline_line


@pytest.mark.skipif(not app.REAL_AVAILABLE, reason="gerçek K3 çıktısı yok")
def test_wave2_cockpit_physics_sections_render_cleanly(clean_caches):
    at = _run_app()
    assert not at.exception

    # Canlı DOM'daki ana gövdedeki son slider horizon_tab'daki zaman kaydırıcısı olmalı
    assert at.main.slider[-1].label == "Zaman adımı (0 = görev başlangıcı)"

    expander_labels = [e.label for e in at.expander]
    assert any("Penumbra" in label for label in expander_labels)

    metric_labels = {m.label for m in at.metric}
    expected_labels = {
        # Penumbra (Extra 2)
        "Noktasal Güneş Saati",
        "Efektif Penumbra Saati",
        "Yarı-Gölge Geçiş Süresi",
        "Enerji Farkı (Wh)",
        # A* Corridor (Extra 4)
        "Rota Mesafesi",
        "Tahmini EVA Süresi",
        "Maks. Rota Eğimi",
        "Ort. Rota Eğimi",
        "Güneş-Güvenli %",
        # 3σ Hazard (Extra 5)
        "3σ Güvenli Alan %",
        "Kayaç Çarpma Olasılığı",
        "Güvenlik Skoru / 100",
        "HLS <10° Uyumluluğu",
        "Karar",
        # Gateway NRHO (Extra 3)
        "Doğrudan Dünya %",
        "Gateway NRHO %",
        "Birleşik Haberleşme %",
        "Maks. Kesinti (sa)",
        "Ort. Gateway Yüksekliği",
        # DSN Link Budget + ITU-R P.526 (Extra 1)
        "Kırınım Rejimi",
        "FSPL",
        "Kırınım Kaybı",
        "Link Marjı",
        "Veri Hızı (Mbps)",
        "10W S-Band Acil Durum İşaretçisi",
    }
    missing = expected_labels - metric_labels
    assert not missing, f"Eksik metrikler: {sorted(missing)}"

    # Site04 (Shackleton rim) için Gateway röle kurtarma bildirimi görünmeli
    success_msgs = " ".join(s.value for s in at.success)
    assert "Gateway Röle Kurtarması (Site04)" in success_msgs

    # Etkileşimli kontroller: DSN istasyon, frekans bandı ve PSR seçimi hatasız çalışmalı
    at.selectbox(key="risk_dsn_station").set_value(app.DSNStation.MADRID).run()
    assert not at.exception
    at.selectbox(key="risk_freq_band").set_value(app.FrequencyBand.KA_BAND).run()
    assert not at.exception
    at.selectbox(key="map_psr_real").set_value("Shackleton PSR").run()
    assert not at.exception
    at.checkbox(key="map_corridor_real").set_value(False).run()
    assert not at.exception
    assert at.main.slider[-1].label == "Zaman adımı (0 = görev başlangıcı)"

    # Mock modunda da A* ve 3σ guardları ile yeni bölümler hatasız çalışmalı
    at.selectbox(key="source_mode").set_value(app.SOURCE_MOCK).run()
    assert not at.exception
    assert at.main.slider[-1].label == "Zaman adımı (0 = görev başlangıcı)"

    # Geriye dönük 2-argümanlı render_risk_tab sözleşmesi korunmalı
    app.render_risk_tab("Site01", "Site04")
