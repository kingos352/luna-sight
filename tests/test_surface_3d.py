"""3B Ay yüzeyi ve küre görselleştirme birim testleri."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

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
