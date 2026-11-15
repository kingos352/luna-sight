"""3B Ay yüzeyi ve küre görselleştirme birim testleri."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from luna_sight.terrain.dem import DemGrid  # noqa: E402
from luna_sight.terrain.hazard import (  # noqa: E402
    LUNAR_RADIUS_M,
    apply_curvature_correction,
    calculate_curvature_drop,
    calculate_horizon_distance,
    compute_aspect_map,
    compute_boulder_hazard_map,
    compute_boulder_hazard_probability,
    compute_solar_incidence_cosine,
    compute_surface_normals,
    evaluate_landing_footprint,
)
from luna_sight.terrain.horizon import merge_hybrid_profiles  # noqa: E402
from luna_sight.terrain.pathfinder import PSR_TARGETS, find_safe_corridor  # noqa: E402
from luna_sight.terrain.risk import (  # noqa: E402
    RISK_SOURCE_PRECOMPUTED,
    RISK_SOURCE_REPRESENTATIVE,
    analyze_all_sites_risk,
    analyze_site_risk,
    compute_crater_metrics,
    compute_slope_stats,
    format_side_by_side_comparison,
    load_precomputed_slope_summary,
)
from luna_sight.terrain.sites import CANDIDATE_SITES  # noqa: E402
from luna_sight.terrain.surface_3d import (  # noqa: E402
    IAU_CRATERS,
    R_MOON_KM,
    build_crater_label_traces,
    build_lunar_globe_figure,
    build_polar_relief_figure,
    build_south_pole_marker_traces,
    calculate_camera_view,
    compute_lunar_elevation,
    generate_lunar_globe_mesh,
    generate_polar_relief_mesh,
)


@dataclass(frozen=True)
class DummySiteSpec:
    site_id: str
    name: str
    latitude_deg: float
    longitude_deg_east: float


SITE_A = DummySiteSpec(
    site_id="Site01",
    name="Connecting ridge",
    latitude_deg=-89.463163,
    longitude_deg_east=-137.489553,
)

SITE_B = DummySiteSpec(
    site_id="Site04",
    name="Shackleton rim",
    latitude_deg=-89.766811,
    longitude_deg_east=-171.869898,
)


def test_compute_lunar_elevation_range():
    """Yükselti değerleri Ay topoğrafyası için fiziksel sınırlar içinde kalmalıdır."""
    lats = np.linspace(-90.0, 90.0, 45)
    lons = np.linspace(-180.0, 180.0, 90)
    lat_grid, lon_grid = np.meshgrid(lats, lons)

    elev = compute_lunar_elevation(lat_grid, lon_grid)

    assert elev.shape == lat_grid.shape
    assert np.all(np.isfinite(elev))
    assert -9.0 <= elev.min() < 0.0
    assert 0.0 < elev.max() <= 9.0


def test_compute_lunar_elevation_known_features():
    """Shackleton, Shoemaker ve Malapert Masifi beklenen göreli yükseltiye sahip olmalıdır."""
    shackleton_elev = float(compute_lunar_elevation(-89.67, 129.78))
    shoemaker_elev = float(compute_lunar_elevation(-88.10, 44.90))
    malapert_elev = float(compute_lunar_elevation(-86.0, 0.0))

    # Shackleton ve Shoemaker derin krater çukurlarıdır (negatif yükselti)
    assert shackleton_elev < 0.0
    assert shoemaker_elev < 0.0
    # Malapert Masifi yüksek bir dağ kütlesidir (pozitif yükselti)
    assert malapert_elev > 0.0
    assert malapert_elev > shackleton_elev


def test_generate_lunar_globe_mesh():
    """3B Ay küresi kafesi doğru boyut ve koordinat sınırlarında üretilmelidir."""
    mesh = generate_lunar_globe_mesh(n_lat=30, n_lon=60, exaggeration=1.8)

    assert mesh.x.shape == (30, 60)
    assert mesh.y.shape == (30, 60)
    assert mesh.z.shape == (30, 60)
    assert mesh.shading_matrix.shape == (30, 60)
    assert 0.0 <= mesh.shading_matrix.min()
    assert mesh.shading_matrix.max() <= 1.0
    assert mesh.is_representative is True
    assert "Temsili" in mesh.source_description

    # Güney kutbunda (lat = -90°): x ~ 0, y ~ 0, z ~ -R
    south_idx = 0  # ilk enlem -90°
    assert np.allclose(mesh.x[south_idx, :], 0.0, atol=1e-3)
    assert np.allclose(mesh.y[south_idx, :], 0.0, atol=1e-3)
    assert mesh.z[south_idx, 0] < -R_MOON_KM * 0.9


def test_generate_polar_relief_mesh():
    """Güney kutbu yerel rölyef kafesi doğru boyutta olmalıdır (dairesel maske NaN)."""
    mesh = generate_polar_relief_mesh(extent_km=100.0, resolution=40, exaggeration=2.0)

    assert mesh.x.shape == (40, 40)
    assert mesh.y.shape == (40, 40)
    assert mesh.z.shape == (40, 40)
    assert mesh.shading_matrix.shape == (40, 40)
    # Maske içinde sonlu değerler olmalı
    rho = np.hypot(mesh.x, mesh.y)
    mask = rho <= 100.0
    assert np.all(np.isfinite(mesh.z[mask]))
    assert np.all(np.isnan(mesh.z[~mask]))


def test_build_lunar_globe_figure_trace_counts():
    """Izgara, kutup, krater ve aday bölge açıp kapatma seçenekleri iz sayısını yönetmelidir."""
    # 1. Tam görünüm (tüm katmanlar açık)
    fig_full = build_lunar_globe_figure(
        SITE_A,
        SITE_B,
        show_grid=True,
        show_south_pole=True,
        show_sites=True,
        show_craters=True,
    )
    assert isinstance(fig_full, go.Figure)
    full_count = len(fig_full.data)

    # 2. Yalnızca yüzey (tüm katmanlar kapalı)
    fig_surface_only = build_lunar_globe_figure(
        SITE_A,
        SITE_B,
        show_grid=False,
        show_south_pole=False,
        show_sites=False,
        show_craters=False,
    )
    assert len(fig_surface_only.data) == 1
    assert isinstance(fig_surface_only.data[0], go.Surface)
    assert full_count > 1


def test_south_pole_marker_traces():
    """Güney Kutbu işaret izleri doğru konumda olmalıdır."""
    traces = build_south_pole_marker_traces(exaggeration=1.8)
    # Yeni implementasyon: cross, stem, pin, PSR ring = 4 trace
    assert len(traces) == 4
    # pin tepe noktası (3. index) tam (x=0, y=0) üzerinde ve negatif z ekseninde
    pin_trace = traces[2]
    assert pin_trace.x[0] == 0.0
    assert pin_trace.y[0] == 0.0
    assert pin_trace.z[0] < -R_MOON_KM
    # PSR ring trace kontrolü
    psr_trace = traces[3]
    assert psr_trace.line.dash == "dot"
    assert psr_trace.line.color == "#ff6b6b"


def test_crater_label_traces_match_iau():
    """IAU krater etiketleri kataloğu (max_labels ile sınırlı) kapsamalıdır."""
    traces = build_crater_label_traces(exaggeration=1.8, max_labels=5)
    assert len(traces) == 1
    trace = traces[0]
    # max_labels=5 ile sadece en önemli 5 krater
    assert len(trace.x) == 5
    assert any("Shackleton" in text for text in trace.text)
    assert any("Shoemaker" in text for text in trace.text)
    # Tüm kraterleri isteme durumu
    traces_all = build_crater_label_traces(exaggeration=1.8, max_labels=100)
    trace_all = traces_all[0]
    assert len(trace_all.x) == len(IAU_CRATERS)


def test_build_lunar_globe_camera_presets():
    """Tüm kamera odak modları geçerli kamera açıları üretmelidir."""
    for focus in ("south_pole", "south_pole_zoom", "site_a", "site_b", "global"):
        cam = calculate_camera_view(focus, SITE_A, SITE_B)
        assert "eye" in cam
        assert "up" in cam
        assert "center" in cam
        for axis in ("x", "y", "z"):
            assert math.isfinite(cam["eye"][axis])
            assert math.isfinite(cam["up"][axis])


def test_build_polar_relief_figure():
    """Güney kutbu 3B rölyef figürü başarıyla oluşturulmalıdır."""
    fig = build_polar_relief_figure(
        SITE_A,
        SITE_B,
        show_grid=True,
        show_south_pole=True,
        show_sites=True,
        show_craters=True,
    )

    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1
    assert isinstance(fig.data[0], go.Surface)


def test_compute_slope_stats_synthetic_dem():
    """Sentetik DEM ızgarasında dairesel bölge eğim hesabı IndexError vermemelidir."""
    pixel_size = 50.0
    rows, cols = 40, 40
    # x = -1000..+1000 m aralığında sabit %10 eğimli düzlem -> ~5.7106 derece
    xs = -1000.0 + (np.arange(cols) + 0.5) * pixel_size
    heights = np.tile(0.1 * xs, (rows, 1))
    # Daire içine 1 adet geçersiz (NaN) piksel ekleyerek valid maskesi doğrulansın
    heights[20, 20] = np.nan

    dem = DemGrid(
        heights_m=heights,
        transform=(pixel_size, 0.0, -1000.0, 0.0, 50.0, -1000.0),
    )
    stats = compute_slope_stats(dem, center_x_m=0.0, center_y_m=0.0, radius_m=500.0)

    expected_deg = math.degrees(math.atan(0.1))
    assert stats.mean_deg == pytest.approx(expected_deg, abs=0.05)
    assert stats.median_deg == pytest.approx(expected_deg, abs=0.05)
    assert stats.fraction_above_5deg == pytest.approx(1.0)
    assert stats.fraction_above_10deg == pytest.approx(0.0)
    assert 0.85 < stats.valid_fraction < 1.0


def test_risk_analysis_and_comparison_no_nan_strings():
    """Krater metrikleri, site riski ve karşılaştırma tablosu 'nan°'/'nan%' üretmemelidir."""
    crater_metrics = compute_crater_metrics(-89.463163, -137.489553, radius_m=50000.0)
    assert crater_metrics.nearest_crater_name != ""
    assert crater_metrics.nearest_crater_distance_m >= 0.0

    site_risk = analyze_site_risk(CANDIDATE_SITES["Site01"], analysis_radius_m=5000.0)
    assert site_risk.site_id == "Site01"
    assert site_risk.analysis_radius_m == pytest.approx(5000.0)

    all_risk = analyze_all_sites_risk()
    expected_sites = {
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
    }
    assert len(all_risk) == 12
    assert set(all_risk) == expected_sites
    assert set(all_risk) == set(CANDIDATE_SITES)

    comparison = format_side_by_side_comparison(all_risk)
    assert "Site01" in comparison
    assert "Site04" in comparison
    assert "13 krater" in comparison
    assert "Karşılaştırma için" not in comparison
    assert "nan°" not in comparison
    assert "nan%" not in comparison

    comparison_custom = format_side_by_side_comparison(all_risk, "Site01", "Site08")
    assert "Site01" in comparison_custom
    assert "Site08" in comparison_custom
    assert "Connecting ridge" in comparison_custom
    assert "Malapert massif" in comparison_custom
    assert "nan°" not in comparison_custom
    assert "nan%" not in comparison_custom


def test_side_by_side_comparison_fallbacks():
    """Eksik site veya 2'den az site durumlarında güvenli geri dönüş sağlanmalıdır."""
    all_risk = analyze_all_sites_risk()

    assert format_side_by_side_comparison({}) == "Karşılaştırma için en az 2 site gerekli."
    assert (
        format_side_by_side_comparison({"Site01": all_risk["Site01"]})
        == "Karşılaştırma için en az 2 site gerekli."
    )

    subset = {"Site02": all_risk["Site02"], "Site08": all_risk["Site08"]}
    subset_cmp = format_side_by_side_comparison(subset)
    assert "Site02" in subset_cmp
    assert "Site08" in subset_cmp
    assert "nan%" not in subset_cmp

    missing_b = format_side_by_side_comparison(all_risk, "Site08", "Site99")
    assert "Site08" in missing_b
    assert "Site04" in missing_b
    assert "nan%" not in missing_b

    missing_a = format_side_by_side_comparison(all_risk, "Site99", "Site01")
    assert "Site01" in missing_a
    assert "Site02" in missing_a
    assert "nan%" not in missing_a


def test_precomputed_slope_summaries_and_tier2_fallback(tmp_path: Path):
    """Önceden hesaplanmış LOLA DEM eğim özetleri ve 3 katmanlı geri dönüş doğrulanmalıdır."""
    for site_id in CANDIDATE_SITES:
        payload = load_precomputed_slope_summary(site_id)
        assert payload is not None
        assert payload["site_id"] == site_id
        assert -180.0 <= float(payload["longitude_deg_east"]) <= 180.0
        assert "slope" in payload
        assert "boulder_hazard" in payload
        if site_id == "Site13":
            assert payload["source_id"] == "synthetic-analytic"
            assert payload["dem_source"] == RISK_SOURCE_REPRESENTATIVE
        else:
            assert payload["source_id"] == "pgda-lola-5mpp"
            assert payload["dem_source"] == RISK_SOURCE_PRECOMPUTED

    assert load_precomputed_slope_summary("Site01", precomputed_dir=tmp_path) is None

    site01_pre = analyze_site_risk(CANDIDATE_SITES["Site01"], use_precomputed=True)
    assert site01_pre.dem_available is True
    assert site01_pre.dem_source == RISK_SOURCE_PRECOMPUTED
    assert math.isfinite(site01_pre.slope.mean_deg)
    assert site01_pre.dem_metadata is not None

    all_pre = analyze_all_sites_risk(use_precomputed=True)
    cmp_pre = format_side_by_side_comparison(all_pre, "Site01", "Site07")
    assert "DEM bekleniyor" not in cmp_pre

    site01_no_pre = analyze_site_risk(CANDIDATE_SITES["Site01"], use_precomputed=False)
    assert site01_no_pre.dem_available is False
    assert site01_no_pre.dem_source == RISK_SOURCE_REPRESENTATIVE
    assert math.isnan(site01_no_pre.slope.mean_deg)


def test_merge_hybrid_profiles():
    """Hibrit ufuk birleştirici azimut hizalaması, max engel seçimi ve meta veriyi korumalıdır."""
    near = pd.DataFrame(
        {
            "azimuth_deg": [0.0, 90.0, 180.0, 270.0],
            "horizon_elevation_deg": [4.0, 1.0, 3.0, np.nan],
            "horizon_distance_m": [300.0, 500.0, 400.0, np.nan],
            "site_id": ["Site01"] * 4,
        }
    )
    far = pd.DataFrame(
        {
            "azimuth_deg": [0.0, 180.0],
            "horizon_elevation_deg": [2.0, 6.0],
            "horizon_distance_m": [15000.0, 18000.0],
            "site_id": ["Site01"] * 2,
        }
    )

    merged = merge_hybrid_profiles(near, far)
    assert list(merged["azimuth_deg"]) == [0.0, 90.0, 180.0, 270.0]
    assert merged["source_range"].eq("hybrid").all()
    assert merged["site_id"].eq("Site01").all()

    # 0°: yakın (4.0° > 2.0°) seçilir -> mesafe 300 m
    assert merged.loc[0, "horizon_elevation_deg"] == pytest.approx(4.0)
    assert merged.loc[0, "horizon_distance_m"] == pytest.approx(300.0)
    # 90°: uzak profil 0° (2.0°) ile 180° (6.0°) arasında 4.0° enterpole eder (> 1.0°)
    assert merged.loc[1, "horizon_elevation_deg"] == pytest.approx(4.0)
    # 180°: uzak (6.0° > 3.0°) seçilir -> mesafe 18000 m
    assert merged.loc[2, "horizon_elevation_deg"] == pytest.approx(6.0)
    assert merged.loc[2, "horizon_distance_m"] == pytest.approx(18000.0)
    # 270°: yakın NaN iken uzak enterpole (4.0°) değeri doldurur
    assert merged.loc[3, "horizon_elevation_deg"] == pytest.approx(4.0)

    # K2 CSV şeması (horizon_deg + occluder_distance_m) uyumluluğu
    near_csv_schema = near.rename(
        columns={
            "horizon_elevation_deg": "horizon_deg",
            "horizon_distance_m": "occluder_distance_m",
        }
    )
    far_csv_schema = far.rename(
        columns={
            "horizon_elevation_deg": "horizon_deg",
            "horizon_distance_m": "occluder_distance_m",
        }
    )
    merged_csv = merge_hybrid_profiles(near_csv_schema, far_csv_schema)
    assert "horizon_deg" in merged_csv.columns
    assert "occluder_distance_m" in merged_csv.columns
    assert merged_csv.loc[2, "occluder_distance_m"] == pytest.approx(18000.0)


def test_hazard_physics_and_landing_footprint():
    """Eğrilik, yüzey normalleri, kayaç tehlikesi ve HLS ayak izi değerlendirmesi çalışmalıdır."""
    drop_10km = calculate_curvature_drop(10_000.0)
    assert drop_10km == pytest.approx((10_000.0**2) / (2.0 * LUNAR_RADIUS_M), rel=1e-6)
    assert apply_curvature_correction(100.0, 10_000.0) == pytest.approx(100.0 - drop_10km)
    assert calculate_horizon_distance(2.0) == pytest.approx(
        math.sqrt(2.0 * LUNAR_RADIUS_M * 2.0 + 4.0)
    )

    # Düzlem ve doğuya yükselen yamaçta yüzey normali / yön / güneş geliş kosinüsü
    flat = np.zeros((10, 10), dtype=float)
    normals_flat = compute_surface_normals(flat, cell_size_m=10.0)
    assert normals_flat.shape == (10, 10, 3)
    assert np.allclose(normals_flat[5, 5], [0.0, 0.0, 1.0], atol=1e-6)
    aspect_flat = compute_aspect_map(flat, cell_size_m=10.0)
    assert np.allclose(aspect_flat, 0.0)

    xs = np.arange(10, dtype=float) * 10.0
    east_rising = np.tile(0.2 * xs, (10, 1))
    aspect_east = compute_aspect_map(east_rising, cell_size_m=10.0)
    assert aspect_east[5, 5] == pytest.approx(270.0, abs=0.5)  # iniş yönü batı (270°)
    normals_east = compute_surface_normals(east_rising, cell_size_m=10.0)
    cos_west_sun = compute_solar_incidence_cosine(normals_east, 270.0, 15.0)
    cos_east_sun = compute_solar_incidence_cosine(normals_east, 90.0, 15.0)
    assert cos_west_sun[5, 5] > cos_east_sun[5, 5]

    # Kayaç çarpma olasılığı tekil ve matris çağrıları
    low_risk = compute_boulder_hazard_probability(2.0, 5000.0)
    high_risk = compute_boulder_hazard_probability(20.0, 200.0)
    assert isinstance(low_risk, dict) and isinstance(high_risk, dict)
    assert high_risk["collision_probability"] > low_risk["collision_probability"]

    bhi_map = compute_boulder_hazard_map(np.array([[2.0, 15.0]]), np.array([[5000.0, 300.0]]))
    assert bhi_map.shape == (1, 2)
    assert 0.0 <= bhi_map[0, 0] < bhi_map[0, 1] <= 100.0

    # İniş ayak izi değerlendirmesi
    fp_haworth = evaluate_landing_footprint("Site07")
    fp_shackleton = evaluate_landing_footprint("Site04")
    fp_site01_10 = evaluate_landing_footprint("Site01", max_safe_slope_deg=10.0)
    fp_site01_15 = evaluate_landing_footprint("Site01", max_safe_slope_deg=15.0)

    assert fp_haworth["hls_10deg_compliant"] is True
    assert fp_haworth["hls_15deg_compliant"] is True
    assert fp_haworth["landing_safety_score"] > fp_shackleton["landing_safety_score"]
    assert fp_shackleton["hls_10deg_compliant"] is False
    assert fp_site01_15["footprint_safe_pct"] >= fp_site01_10["footprint_safe_pct"]
    assert "verdict" in fp_haworth

    with pytest.raises(KeyError):
        evaluate_landing_footprint("Site99")
    with pytest.raises(ValueError):
        evaluate_landing_footprint("Site01", semi_major_m=-10.0)


def test_pathfinder_psr_corridors():
    """PSR hedefleri ve A* güvenli rota planlayıcı kanonik sözleşmeye uymalıdır."""
    assert len(PSR_TARGETS) >= 9
    for target in PSR_TARGETS.values():
        assert -180.0 <= float(target["longitude_deg_east"]) <= 180.0
        assert float(target["radius_km"]) > 0.0

    corridor = find_safe_corridor("Site01", grid_size=25, max_slope_deg=15.0)
    assert corridor["site_id"] == "Site01"
    assert corridor["target_name"] == "Shackleton PSR"
    assert -180.0 <= float(corridor["target_lon_deg_east"]) <= 180.0
    assert float(corridor["total_distance_km"]) > 0.0
    assert float(corridor["estimated_eva_hours"]) > 0.0
    assert 0.0 <= float(corridor["solar_safe_fraction_pct"]) <= 100.0
    assert float(corridor["mean_route_slope_deg"]) <= float(corridor["max_route_slope_deg"])

    waypoints = corridor["waypoints"]
    assert len(waypoints) >= 2
    assert waypoints[0]["step"] == 0
    assert waypoints[0]["cumulative_km"] == pytest.approx(0.0)
    assert waypoints[-1]["cumulative_km"] == pytest.approx(corridor["total_distance_km"])
    for idx, wp in enumerate(waypoints):
        assert -180.0 <= float(wp["lon_deg_east"]) <= 180.0
        if idx > 0:
            assert float(wp["cumulative_km"]) >= float(waypoints[idx - 1]["cumulative_km"])

    explicit = find_safe_corridor("Site08", target_psr="Haworth", grid_size=21)
    assert explicit["target_name"] == "Haworth PSR"

    with pytest.raises(KeyError):
        find_safe_corridor("Site01", target_psr="BilinmeyenPSR")
