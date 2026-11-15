"""
tests/test_orbital_engine.py
============================
MOON_ME referans çerçevesi, ENU dönüşümleri ve ephemeris hesaplamalarını
doğrulayan birim testler.
"""

import math
import numpy as np
import pytest

from backend.config import LUNAR_MEAN_RADIUS_M, SOLAR_CONSTANT_1AU
from backend.orbital_engine import OrbitalEngine


class TestOrbitalEngine:
    def setup_method(self):
        self.engine = OrbitalEngine()

    def test_moon_me_cartesian_transformations(self):
        """MOON_ME Selenosentrik kartezyen koordinat doğrulaması."""
        R = LUNAR_MEAN_RADIUS_M

        # 1. Ay Ön Yüz Merkezi (0°, 0°)
        pos_origin = OrbitalEngine.latlon_to_cartesian(0.0, 0.0, 0.0)
        np.testing.assert_allclose(pos_origin, [R, 0.0, 0.0], atol=1e-3)

        # 2. Güney Kutbu (-90°, 0°)
        pos_sp = OrbitalEngine.latlon_to_cartesian(-90.0, 0.0, 0.0)
        np.testing.assert_allclose(pos_sp, [0.0, 0.0, -R], atol=1e-3)

        # 3. Kuzey Kutbu (+90°, 0°)
        pos_np = OrbitalEngine.latlon_to_cartesian(90.0, 0.0, 0.0)
        np.testing.assert_allclose(pos_np, [0.0, 0.0, R], atol=1e-3)

        # 4. 90° Doğu Ekvator (0°, 90°)
        pos_east = OrbitalEngine.latlon_to_cartesian(0.0, 90.0, 0.0)
        np.testing.assert_allclose(pos_east, [0.0, R, 0.0], atol=1e-3)

        # 5. İrtifa / Kot ekleme (1000m rakım)
        pos_elev = OrbitalEngine.latlon_to_cartesian(0.0, 0.0, 1000.0)
        np.testing.assert_allclose(pos_elev, [R + 1000.0, 0.0, 0.0], atol=1e-3)

    def test_enu_basis_orthonormality(self):
        """Yerel ENU (East-North-Up) baz vektörlerinin dikliği ve birimliği."""
        test_coords = [
            (0.0, 0.0),
            (-89.75, 0.0),    # Ay Güney Kutbu
            (-45.0, 45.0),
            (30.0, -60.0),
        ]

        for lat, lon in test_coords:
            u_east, u_north, u_up = OrbitalEngine.get_enu_basis(lat, lon)

            # Birim vektör normları = 1.0
            assert math.isclose(np.linalg.norm(u_east), 1.0, abs_tol=1e-7)
            assert math.isclose(np.linalg.norm(u_north), 1.0, abs_tol=1e-7)
            assert math.isclose(np.linalg.norm(u_up), 1.0, abs_tol=1e-7)

            # Birbirlerine diklik (İç çarpım = 0)
            assert math.isclose(float(np.dot(u_east, u_north)), 0.0, abs_tol=1e-7)
            assert math.isclose(float(np.dot(u_east, u_up)), 0.0, abs_tol=1e-7)
            assert math.isclose(float(np.dot(u_north, u_up)), 0.0, abs_tol=1e-7)

            # Sağ el kuralı (Up = East x North)
            cross_up = np.cross(u_east, u_north)
            np.testing.assert_allclose(cross_up, u_up, atol=1e-7)

    def test_enu_to_azimuth_elevation(self):
        """ENU vektöründen Azimut ve Elevation dönüşüm doğruluğu."""
        # Tam Kuzey: [0, 10, 0] -> Az=0°, El=0°
        az_n, el_n, d_n = OrbitalEngine.enu_to_azimuth_elevation(np.array([0.0, 10.0, 0.0]))
        assert math.isclose(az_n, 0.0, abs_tol=1e-4)
        assert math.isclose(el_n, 0.0, abs_tol=1e-4)
        assert math.isclose(d_n, 10.0, abs_tol=1e-4)

        # Tam Doğu: [10, 0, 0] -> Az=90°, El=0°
        az_e, el_e, _ = OrbitalEngine.enu_to_azimuth_elevation(np.array([10.0, 0.0, 0.0]))
        assert math.isclose(az_e, 90.0, abs_tol=1e-4)
        assert math.isclose(el_e, 0.0, abs_tol=1e-4)

        # Tam Güney: [0, -10, 0] -> Az=180°, El=0°
        az_s, el_s, _ = OrbitalEngine.enu_to_azimuth_elevation(np.array([0.0, -10.0, 0.0]))
        assert math.isclose(az_s, 180.0, abs_tol=1e-4)
        assert math.isclose(el_s, 0.0, abs_tol=1e-4)

        # Tam Başucu (Zenith): [0, 0, 10] -> El=90°
        _, el_z, _ = OrbitalEngine.enu_to_azimuth_elevation(np.array([0.0, 0.0, 10.0]))
        assert math.isclose(el_z, 90.0, abs_tol=1e-4)

        # 45° Yükseklik ve Kuzeydoğu: [10, 10, 14.142] -> Az=45°, El=45°
        az_ne, el_ne, _ = OrbitalEngine.enu_to_azimuth_elevation(
            np.array([10.0, 10.0, 10.0 * math.sqrt(2)])
        )
        assert math.isclose(az_ne, 45.0, abs_tol=1e-3)
        assert math.isclose(el_ne, 45.0, abs_tol=1e-3)

    def test_solar_flux_physics(self):
        """Güneş ışınım akısı fiziği doğrulaması."""
        # 1 AU mesafede başucu (el=90°) -> ~1361 W/m^2
        flux_zenith = OrbitalEngine.calculate_solar_flux(149597870.7, 90.0)
        assert math.isclose(flux_zenith, SOLAR_CONSTANT_1AU, rel_tol=1e-3)

        # 30° Yükseklik -> 1361 * sin(30°) = 680.5 W/m^2
        flux_30 = OrbitalEngine.calculate_solar_flux(149597870.7, 30.0)
        assert math.isclose(flux_30, SOLAR_CONSTANT_1AU * 0.5, rel_tol=1e-3)

        # Ufkun altı (el = -5°) -> 0 W/m^2
        flux_night = OrbitalEngine.calculate_solar_flux(149597870.7, -5.0)
        assert flux_night == 0.0

    def test_compute_ephemeris_range(self):
        """24 saatlik zaman serisi efemeris üretim testi."""
        res = self.engine.compute_ephemeris_range(
            lat_deg=-89.75,
            lon_deg=0.0,
            elevation_m=500.0,
            utc_start="2026-11-15T00:00:00Z",
            utc_end="2026-11-16T00:00:00Z",
            step_hours=1.0,
        )

        assert res["count"] == 25
        assert len(res["sun_azimuth_deg"]) == 25
        assert len(res["earth_elevation_deg"]) == 25
        assert "MOON_ME" in res["frame_used"]

        # Dünya Ay Güney Kutbu'nda ufka yakın salınır (-5° ile +10° arası)
        earth_els = res["earth_elevation_deg"]
        assert np.all(earth_els >= -15.0) and np.all(earth_els <= 15.0)
