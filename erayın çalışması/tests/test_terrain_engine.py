"""
tests/test_terrain_engine.py
============================
Horn eğim hesabı, TRI pürüzlülük indeksi, 360° ufuk ray-casting
ve iniş uygunluk skorunu doğrulayan birim testler.
"""

import math
import numpy as np
import pytest

from backend.config import MAX_LANDING_SLOPE_DEG, ACCEPTABLE_SLOPE_DEG
from backend.terrain_engine import TerrainEngine


class TestTerrainEngine:
    def test_horn_slope_calculation_known_geometry(self):
        """Horn eğim algoritmasının analitik düzlemlerde doğrulanması."""
        cell_size = 40.0
        h, w = 64, 64

        # 1. Tam düz zemin (kot = sabit 100m) -> Eğim 0° olmalı
        flat_dem = np.full((h, w), 100.0, dtype=np.float32)
        slope_flat = TerrainEngine.compute_slope_horn(flat_dem, cell_size)
        np.testing.assert_allclose(slope_flat, 0.0, atol=1e-5)

        # 2. X yönünde 8° eğimli rampa (İdeal iniş sınır eşiği)
        # tan(8°) = dz / dx -> dz = dx * tan(8°)
        target_deg = 8.0
        tan_slope = math.tan(math.radians(target_deg))

        x_coords = np.arange(w, dtype=np.float32) * cell_size
        ramp_dem = np.tile(x_coords * tan_slope, (h, 1)).astype(np.float32)

        slope_ramp = TerrainEngine.compute_slope_horn(ramp_dem, cell_size)
        # Kenarlar hariç iç bölgede tam target_deg beklenir
        inner_slope = slope_ramp[2:-2, 2:-2]
        np.testing.assert_allclose(inner_slope, target_deg, atol=1e-2)

        # 3. Y yönünde 45° dik yamaç
        tan_45 = math.tan(math.radians(45.0))
        y_coords = np.arange(h, dtype=np.float32) * cell_size
        steep_dem = np.tile((y_coords * tan_45)[:, np.newaxis], (1, w)).astype(np.float32)
        slope_steep = TerrainEngine.compute_slope_horn(steep_dem, cell_size)
        np.testing.assert_allclose(slope_steep[2:-2, 2:-2], 45.0, atol=1e-2)

    def test_tri_roughness_calculation(self):
        """TRI (Terrain Ruggedness Index) hesabı testi."""
        h, w = 32, 32
        flat_dem = np.full((h, w), 50.0, dtype=np.float32)
        tri_flat = TerrainEngine.compute_roughness_tri(flat_dem)
        np.testing.assert_allclose(tri_flat, 0.0, atol=1e-5)

        # Basamak atlamalı pürüzlü zemin
        noisy_dem = flat_dem.copy()
        noisy_dem[10, 10] += 5.0
        tri_noisy = TerrainEngine.compute_roughness_tri(noisy_dem)
        assert tri_noisy[10, 10] > 0.0
        assert tri_noisy[10, 11] > 0.0

    def test_horizon_ray_casting_algorithm(self):
        """360° Ufuk ray-casting engel yükselme açısı algoritması testi."""
        # 128x128 sentetik zemin ve ortasında derin krater
        h, w = 128, 128
        cell_size = 40.0
        xx, yy = np.meshgrid(
            np.linspace(-w/2 * cell_size, w/2 * cell_size, w),
            np.linspace(-h/2 * cell_size, h/2 * cell_size, h)
        )
        r = np.sqrt(xx**2 + yy**2)

        # Merkezde 1000m yarıçaplı, 500m derinliğinde çukur
        dem = np.zeros((h, w), dtype=np.float32)
        inside = r < 1000.0
        dem[inside] = -500.0 * (1.0 - (r[inside] / 1000.0) ** 2)

        engine = TerrainEngine(pixel_size_m=cell_size)
        engine.elevation = dem

        mask = engine.compute_horizon_mask(num_azimuths=16, max_radius_pixels=32)
        assert mask.shape == (16, h, w)

        # Kraterin tam merkezindeki piksel (h//2, w//2)
        center_elev_angles = mask[:, h//2, w//2]
        # Krater tabanından çevre duvarlar yukarıda görünmeli (açı > 0°)
        assert np.all(center_elev_angles > 5.0)

        # Düzlükteki (krater dışı) bir piksel
        flat_point_angles = mask[:, 5, 5]
        # Kraterden uzak dış düzlükte ufuk açısı ~0° olmalı
        assert np.mean(flat_point_angles) < 1.0

    def test_landing_suitability_scoring_rules(self):
        """NASA kriterli iniş uygunluk skorlama mantığı doğrulaması."""
        engine = TerrainEngine()
        # Sentetik veriyi yükle/hesapla
        assert engine.elevation is not None
        assert engine.slope is not None
        assert engine.roughness is not None

        # Efemeris simülasyonu
        orbital_res = {
            "sun_azimuth_deg": np.array([0.0, 90.0, 180.0, 270.0]),
            "sun_elevation_deg": np.array([2.5, 3.0, 1.5, 2.0]),
            "earth_azimuth_deg": np.array([45.0, 45.0, 45.0, 45.0]),
            "earth_elevation_deg": np.array([5.0, 5.0, 5.0, 5.0]),
            "sun_distance_km": np.array([149597870.7] * 4),
            "timestamps": ["2026-11-15T00:00:00Z"] * 4,
        }

        temporal = engine.simulate_temporal_layers(orbital_res)
        scores = temporal["suitability_score"]

        # Skor 0 ile 100 arasında olmalı
        assert np.all(scores >= 0.0) and np.all(scores <= 100.0)

        # Eğim > 12° (ACCEPTABLE_SLOPE_DEG) olan yerler kesinlikle 0 olmalı (Veto)
        unsafe_mask = engine.slope > ACCEPTABLE_SLOPE_DEG
        if np.any(unsafe_mask):
            assert np.all(scores[unsafe_mask] == 0.0)

        # Düzlük ve aydınlanan alanlarda skor yüksek olmalı (> 60)
        safe_mask = (engine.slope <= 4.0) & (temporal["illumination_pct"] > 50.0)
        if np.any(safe_mask):
            assert np.mean(scores[safe_mask]) > 60.0
