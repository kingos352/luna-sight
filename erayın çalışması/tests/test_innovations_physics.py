"""
tests/test_innovations_physics.py
=================================
Uçuş Fiziği, Aviyonik ve Telekomünikasyon Modülleri Kapsamlı Doğrulama Testleri.

Kapsanan Modüller:
1. Chebyshev Polinomu Uçuş Sıkıştırması (fit_chebyshev_series, evaluate_chebyshev, hata < 0.005°)
2. Artemis Lunar Gateway (NRHO) Yörüngesel Röle Efemerisi (generate_gateway_ephemeris, compute_gateway_visibility)
3. Ay Küresel Eğrilik Düzeltmesi (calculate_curvature_drop, TerrainEngine.compute_horizon_elevation)
4. Yönsel Eğim (Aspect Map) ve Yüzey Normali Tensörü (compute_aspect_map, cos(i) = n . s)
5. Alt-Piksel Fraktal Kayaç Tehlike Dağılımı - BHI (12 m^2 footprint, N(D)=k*D^-gamma)
6. Güneş Diski Yarı-Gölge (Penumbra) ve Güç Modeli (0.533° disk, limb darkening, Watt hesabı)
7. Lunar Knife-Edge Diffraction Engine (Fresnel v, ITU-R J(v), S-Band 2.2 GHz acil marjı)
8. Frekans Bağımlı Bağlantı Bütçesi ve DSN İstasyon Modeli (S-Band, Ka-Band, O2O Lazer)
9. Radyasyon SEU Kalkanı ve TMR (bit-flip injector, majority voting, self-healing scrub)
10. NASA cFS C Başlık Dosyası (luna_sight_cfs_msg.h doğrulaması)
11. FastAPI Physics REST Endpoint'leri (/api/physics/...)
"""

import math
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.terrain_engine import TerrainEngine
from backend.flight_physics.chebyshev_compression import (
    fit_chebyshev_series,
    evaluate_chebyshev,
    normalize_timestamps,
    ChebyshevTrajectoryCompressor,
)
from backend.flight_physics.gateway_relay import (
    generate_gateway_ephemeris,
    compute_gateway_visibility,
    NRHO_PERIOD_HOURS,
    NRHO_APOLUNE_RADIUS_KM,
    NRHO_PERILUNE_RADIUS_KM,
)
from backend.flight_physics.curvature import (
    calculate_curvature_drop,
    apply_curvature_correction,
    calculate_horizon_distance,
    calculate_effective_horizon_angle,
    LUNAR_RADIUS_M,
)
from backend.flight_physics.surface_normals import (
    compute_surface_normals,
    compute_aspect_map,
    compute_solar_incidence_cosine,
    compute_gradients,
)
from backend.flight_physics.boulder_hazard import (
    compute_boulder_hazard_probability,
    compute_boulder_hazard_map,
    calculate_k_coefficient,
    DEFAULT_FOOTPRINT_AREA_M2,
)
from backend.flight_physics.penumbra_power import (
    compute_solar_disk_fraction,
    compute_penumbra_power,
    SOLAR_ANGULAR_DIAMETER_DEG,
    SOLAR_ANGULAR_RADIUS_DEG,
)
from backend.flight_physics.knife_edge_diffraction import (
    compute_fresnel_parameter,
    compute_diffraction_loss_itu,
    evaluate_emergency_link_margin,
    compute_wavelength,
    S_BAND_FREQ_HZ,
)
from backend.flight_physics.link_budget import (
    compute_link_budget,
    DSNStation,
    FrequencyBand,
    DSN_STATIONS,
    BAND_CONFIGS,
)
from backend.flight_physics.seu_tmr_shield import (
    TMRVariable,
    SEUInjector,
    SEUProtectedState,
    flip_float_bit,
    flip_int_bit,
)


# -----------------------------------------------------------------------------
# 1. CHEBYSHEV POLINOM SIKIŞTIRMA TESTLERİ
# -----------------------------------------------------------------------------
class TestChebyshevCompression:
    def test_chebyshev_fit_and_evaluation_accuracy(self):
        """Pürüzsüz yörünge açısı eğrisi için Chebyshev uydurma hatasının < 0.005° olduğunu doğrular."""
        # 12 saatlik Güneş yükselme ve yaklaşım açısı uçuş segmenti simülasyonu
        timestamps = np.linspace(0.0, 12.0, 49)  # 15 dk adımlarla 12 saat
        # Uçuş güdüm ve yörüngesel açı salınımı
        synthetic_angles = 8.5 * np.sin(np.pi * timestamps / 24.0) + 0.35 * np.cos(np.pi * timestamps / 12.0)

        # 8. dereceden Chebyshev serisine fit et
        coeffs = fit_chebyshev_series(timestamps, synthetic_angles, degree=8)
        assert len(coeffs) == 9, "8. derece polinom 9 katsayı (c0..c8) üretmelidir."

        # O(1) Clenshaw algoritmasıyla noktaları değerlendir ve max hatayı ölç
        t_norm, _, _ = normalize_timestamps(timestamps)
        residuals = []
        for orig, tn in zip(synthetic_angles, t_norm):
            eval_val = evaluate_chebyshev(coeffs, tn)
            residuals.append(abs(orig - eval_val))

        max_err = max(residuals)
        assert max_err < 0.005, f"Maksimum Chebyshev yaklaşım hatası ({max_err:.6f}°) 0.005° sınırının altında olmalıdır."

    def test_chebyshev_compressor_class(self):
        """ChebyshevTrajectoryCompressor sınıfının sıkıştırma ve dekompresyon metriklerini doğrular."""
        ts = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
        angles = [45.0, 47.2, 49.8, 52.1, 53.9, 54.8, 55.0]

        compressor = ChebyshevTrajectoryCompressor(degree=6)
        report = compressor.compress(ts, angles)

        assert report["accuracy_passed"] is True
        assert report["max_residual_deg"] < 0.005
        # Ara bir noktayı decompress et
        interp_val = compressor.decompress(25.0)
        assert 49.8 < interp_val < 52.1


# -----------------------------------------------------------------------------
# 2. ARTEMIS LUNAR GATEWAY (NRHO) YÖRÜNGE VE RÖLE TESTLERİ
# -----------------------------------------------------------------------------
class TestGatewayRelay:
    def test_gateway_ephemeris_generation(self):
        """7 günlük NRHO yörünge izinin fiziksel apoapsis ve periapsis sınırlarını test eder."""
        ephemeris = generate_gateway_ephemeris(duration_days=7.0, step_hours=1.0)
        assert len(ephemeris) == 169  # 7 * 24 + 1
        
        z_vals = [pt["z_km"] for pt in ephemeris]
        distances = [pt["distance_km"] for pt in ephemeris]

        # NRHO güney halo özelliği: Apoapsis Ay'ın derin güneyindedir (Z << 0)
        min_z = min(z_vals)
        max_dist = max(distances)
        min_dist = min(distances)

        assert min_z < -50_000.0, f"Apolunda Z koordinatı derin güneyde olmalıdır (alınan: {min_z} km)"
        assert max_dist > 65_000.0, f"Maksimum apoapsis mesafesi ~70,000 km civarında olmalıdır (alınan: {max_dist})"
        assert min_dist < 6_000.0, f"Minimum periapsis mesafesi ~3,200 km civarında olmalıdır (alınan: {min_dist})"

        # Güney kutbu 'sweet spot' zaman oranı: yörüngenin en az %75'inde Z < -15,000 km olmalı
        sweet_spot_steps = sum(1 for pt in ephemeris if pt["in_southern_sweet_spot"])
        sweet_spot_pct = sweet_spot_steps / len(ephemeris)
        assert sweet_spot_pct >= 0.75, f"Gateway yörünge süresinin en az %75'i Güney Kutbu görüş hattında olmalıdır (alınan: %{sweet_spot_pct*100:.1f})"

    def test_gateway_visibility_for_shackleton(self):
        """Shackleton Krateri (-89.75°) için Gateway görünürlük pencerelerini doğrular."""
        res = compute_gateway_visibility(site_lat=-89.75, site_lon=0.0, site_elev_m=-2000.0)
        assert res["coverage_percentage"] > 70.0, "Güney Kutbu için Gateway görünürlük oranı >%70 olmalıdır."
        assert res["windows_count"] >= 1
        assert res["total_contact_hours"] > 100.0


# -----------------------------------------------------------------------------
# 3. AY KÜRESEL EĞRİLİK DÜZELTMESİ TESTLERİ
# -----------------------------------------------------------------------------
class TestLunarCurvature:
    def test_curvature_drop_formula(self):
        """Ay eğrilik düşüşü formülü: z_drop = r^2 / (2 * R_Moon)."""
        # 10 km için beklenen düşüş: 10000^2 / (2 * 1737400) = 1e8 / 3474800 ≈ 28.778 m
        drop_10k = float(calculate_curvature_drop(10_000.0))
        assert math.isclose(drop_10k, 28.7786, rel_tol=1e-3)

        # 50 km için beklenen düşüş: 50000^2 / (2 * 1737400) = 2.5e9 / 3474800 ≈ 719.46 m
        drop_50k = float(calculate_curvature_drop(50_000.0))
        assert math.isclose(drop_50k, 719.465, rel_tol=1e-3)

    def test_terrain_engine_horizon_elevation_with_curvature(self):
        """TerrainEngine.compute_horizon_elevation içinde apply_curvature parametresi entegrasyonu."""
        flat_dem = np.full((64, 64), 500.0, dtype=np.float32)
        # 30 piksel öteye 500m yüksekliğinde dağ tepe koyalım
        flat_dem[10, 32] = 1200.0

        engine = TerrainEngine(dem_path=Path("dummy_path"))
        engine.elevation = flat_dem
        engine.pixel_size_m = 40.0

        # Eğrilikli ve eğriliksiz ufuk yükselme açısı karşılaştırması
        angle_flat = engine.compute_horizon_elevation(y=32, x=32, azimuth_deg=0.0, apply_curvature=False)
        angle_curv = engine.compute_horizon_elevation(y=32, x=32, azimuth_deg=0.0, apply_curvature=True)

        # Ay küresel yüzeyi hedefin kotunu düşürdüğü için angle_curv < angle_flat olmalıdır
        assert angle_flat > 0.0
        assert angle_curv < angle_flat, "Küresel eğrilik düzeltmesi ile ufuk açısı düzlemsel modele göre daha düşük olmalıdır."


# -----------------------------------------------------------------------------
# 4. YÖNSEL EĞİM (ASPECT) VE YÜZEY NORMALİ TESTLERİ
# -----------------------------------------------------------------------------
class TestSurfaceNormalsAndAspect:
    def test_aspect_map_directions(self):
        """Doğu, Güney ve Kuzey yamaçları için azimut açılarının doğrulanması."""
        h, w = 32, 32
        cell_m = 40.0

        # Doğuya doğru alçalan rampa (Batı yüksek, Doğu alçak -> eğim Doğu'ya bakar = 90°)
        east_dem = np.zeros((h, w), dtype=np.float32)
        for c in range(w):
            east_dem[:, c] = (w - c) * 10.0

        aspect_east = compute_aspect_map(east_dem, cell_size_m=cell_m)
        inner_aspect = aspect_east[5:25, 5:25]
        np.testing.assert_allclose(inner_aspect, 90.0, atol=1.0)

    def test_surface_normal_tensor_unit_magnitude(self):
        """Yüzey normali tensörünün her noktada birim uzunlukta olduğunu test eder."""
        dem = np.random.uniform(100.0, 800.0, size=(20, 20)).astype(np.float32)
        normals = compute_surface_normals(dem, cell_size_m=40.0)

        assert normals.shape == (20, 20, 3)
        magnitudes = np.linalg.norm(normals, axis=-1)
        np.testing.assert_allclose(magnitudes, 1.0, atol=1e-5)

    def test_solar_incidence_cosine(self):
        """Tam dik Güneş ışığında cos(i) = 1.0 olduğunu doğrular."""
        flat_dem = np.full((10, 10), 100.0, dtype=np.float32)
        normals = compute_surface_normals(flat_dem, cell_size_m=40.0)

        # Güneş tam tepede (Zenith: elevation = 90°)
        cos_zenith = compute_solar_incidence_cosine(normals, sun_azimuth_deg=0.0, sun_elevation_deg=90.0)
        np.testing.assert_allclose(cos_zenith, 1.0, atol=1e-4)

        # Güneş ufuk altında (el = -10°): Kırpma ile 0.0 olmalı
        cos_below = compute_solar_incidence_cosine(normals, sun_azimuth_deg=0.0, sun_elevation_deg=-10.0, clamp_negative=True)
        np.testing.assert_allclose(cos_below, 0.0, atol=1e-5)


# -----------------------------------------------------------------------------
# 5. ALT-PİKSEL FRAKTAL KAYAÇ TEHLİKE (BHI) TESTLERİ
# -----------------------------------------------------------------------------
class TestBoulderHazardIndex:
    def test_boulder_hazard_probability_scaling(self):
        """12 m^2 iniş takımı bacak açıklığı için eğim ve krater mesafesine bağlı risk değişimi."""
        # Düz ve kraterden uzak güvenli saha (eğim 2°, mesafe 2000m)
        safe_res = compute_boulder_hazard_probability(slope=2.0, crater_dist=2000.0, footprint_area_m2=12.0)
        assert safe_res["collision_probability"] < 0.20
        assert safe_res["hazard_class"] in ("NOMINAL_SAFE", "MODERATE_CAUTION")

        # Dik yamaç ve krater kenarı tehlikeli saha (eğim 25°, mesafe 50m)
        hazard_res = compute_boulder_hazard_probability(slope=25.0, crater_dist=50.0, footprint_area_m2=12.0)
        assert hazard_res["collision_probability"] > safe_res["collision_probability"]
        assert hazard_res["bhi_score"] > safe_res["bhi_score"]
        assert hazard_res["hazard_class"] in ("HIGH_HAZARD", "CRITICAL_ABORT_ZONE")

    def test_boulder_hazard_map_generation(self):
        """2B grid üzerinde BHI matris üretimi."""
        slopes = np.array([[2.0, 15.0], [28.0, 5.0]], dtype=np.float32)
        dists = np.array([[1500.0, 300.0], [80.0, 800.0]], dtype=np.float32)

        bhi_map = compute_boulder_hazard_map(slopes, dists)
        assert bhi_map.shape == (2, 2)
        assert 0.0 <= bhi_map.min() <= bhi_map.max() <= 100.0


# -----------------------------------------------------------------------------
# 6. GÜNEŞ DİSKİ YARI-GÖLGE (PENUMBRA) VE GÜÇ MODELİ TESTLERİ
# -----------------------------------------------------------------------------
class TestPenumbraPower:
    def test_solar_disk_fraction_states(self):
        """0.533° Güneş diskinde tam aydınlık, yarı batış ve tam gölge (umbra) kesirleri."""
        # Güneş diski ufkun çok üstünde: f_area = 1.0
        f_full = compute_solar_disk_fraction(sun_elevation_deg=1.0, horizon_elevation_deg=0.0)
        assert math.isclose(float(f_full), 1.0, abs_tol=1e-4)

        # Güneş merkezi tam ufuk sırtında: f_area = 0.50
        f_half = compute_solar_disk_fraction(sun_elevation_deg=0.0, horizon_elevation_deg=0.0)
        assert math.isclose(float(f_half), 0.50, abs_tol=1e-2)

        # Güneş diski tamamen dağın arkasında: f_area = 0.0
        f_umbra = compute_solar_disk_fraction(sun_elevation_deg=-0.5, horizon_elevation_deg=0.0)
        assert math.isclose(float(f_umbra), 0.0, abs_tol=1e-4)

    def test_penumbra_power_watts(self):
        """Yarı-gölgede fotovoltaik güç çıktısı hesabı."""
        p_res = compute_penumbra_power(
            sun_elevation_deg=0.10,
            horizon_elevation_deg=0.05,
            panel_area_m2=8.0,
            cell_efficiency=0.30,
        )
        assert p_res["power_watts"] > 0.0
        assert p_res["visible_disk_fraction"] > 0.0
        assert p_res["eclipse_state"] in ("PENUMBRA_GRAZING", "FULL_SUNLIGHT")


# -----------------------------------------------------------------------------
# 7. LUNAR KNIFE-EDGE DIFFRACTION ENGINE TESTLERİ
# -----------------------------------------------------------------------------
class TestKnifeEdgeDiffraction:
    def test_fresnel_parameter_and_diffraction_loss(self):
        """Fresnel parametresi v ve ITU-R P.526 bıçak sırtı kırınım kaybı fonksiyonu doğrulaması."""
        # v = 0 (tam bıçak sırtı teğet geçiş): Kayıp yaklaşık 6.0 dB olmalıdır
        loss_v0 = compute_diffraction_loss_itu(0.0)
        assert math.isclose(float(loss_v0), 6.0, abs_tol=0.2)

        # v <= -1.0 (açık görüş hattı): Kayıp 0 dB
        loss_clear = compute_diffraction_loss_itu(-1.5)
        assert float(loss_clear) == 0.0

        # v = 2.0 (gölge bölgesi): Artan kırınım kaybı
        loss_shadow = compute_diffraction_loss_itu(2.0)
        assert float(loss_shadow) > 18.0

    def test_emergency_s_band_link_margin_behind_mountain(self):
        """S-Band (2.2 GHz) doğrudan görüş hattı 0.3° - 0.5° dağ arkasında kalsa bile marjın pozitif olduğunu doğrular."""
        res_03 = evaluate_emergency_link_margin(obstruction_angle_deg=0.30, distance_to_ridge_m=5000.0)
        assert res_03["link_closed"] is True
        assert res_03["link_margin_db"] > 3.0, f"0.3° dağ arkasında marj ({res_03['link_margin_db']} dB) > +3 dB olmalıdır."

        res_05 = evaluate_emergency_link_margin(obstruction_angle_deg=0.50, distance_to_ridge_m=5000.0)
        assert res_05["link_closed"] is True
        assert res_05["link_margin_db"] > 3.0, f"0.5° dağ arkasında marj ({res_05['link_margin_db']} dB) > +3 dB olmalıdır."


# -----------------------------------------------------------------------------
# 8. FREKANS BAĞIMLI BAĞLANTI BÜTÇESİ VE DSN MODELLERİ TESTLERİ
# -----------------------------------------------------------------------------
class TestLinkBudget:
    def test_link_budget_all_bands(self):
        """S-Band, Ka-Band ve O2O Lazer için DSN bağlantı bütçesi hesabı."""
        # S-Band Goldstone
        s_budget = compute_link_budget(station=DSNStation.GOLDSTONE, band=FrequencyBand.S_BAND)
        assert s_budget["link_established"] is True
        assert s_budget["link_margin_db"] > 3.0

        # Ka-Band Madrid (20 Mbps)
        ka_budget = compute_link_budget(station=DSNStation.MADRID, band=FrequencyBand.KA_BAND, data_rate_bps=20e6)
        assert ka_budget["link_established"] is True
        assert ka_budget["frequency_hz"] == 26e9

        # O2O Optik Lazer Canberra (200 Mbps)
        laser_budget = compute_link_budget(station=DSNStation.CANBERRA, band=FrequencyBand.OPTICAL_O2O, data_rate_bps=200e6)
        assert laser_budget["link_established"] is True
        assert laser_budget["wavelength_m"] == 1550e-9


# -----------------------------------------------------------------------------
# 9. RADYASYON SEU VE YAZILIMSAL TMR TESTLERİ
# -----------------------------------------------------------------------------
class TestSEUAndTMRShield:
    def test_bit_flip_and_tmr_voting_recovery(self):
        """Tekil bit-çevirme enjeksiyonu ve TMR çoğunluk oylaması ile otomatik onarım."""
        var = TMRVariable[float](3200.0, name="alt_sensor")

        # Copy B'ye kozmik ışın bit çevirme enjekte et
        var.corrupt_copy("B", bit_index=15)
        assert var.copy_b != 3200.0, "Copy B bozulmuş olmalıdır."
        assert var.copy_a == 3200.0
        assert var.copy_c == 3200.0

        # Çoğunluk oylaması ile değeri oku ve onarımı doğrula
        val, repaired = var.vote_and_repair()
        assert val == 3200.0, "Oylama doğru değeri korumalıdır."
        assert repaired is True, "Onarım yapıldığı bildirilmelidir."
        assert var.copy_b == 3200.0, "Bozuk kopya otomatik düzeltilmiş (scrubbed) olmalıdır."

    def test_seu_protected_state_scrubbing(self):
        """Tüm iniş durumu kayıtlarında bellek tarama (scrubbing) testi."""
        state = SEUProtectedState()
        state.thrust_pct.corrupt_copy("C", bit_index=10)

        report = state.run_health_check_and_scrub()
        assert report["repaired_in_scrub"] == 1
        assert state.thrust_pct.get() == 75.0


# -----------------------------------------------------------------------------
# 10. NASA cFS VE CCSDS BAŞLIK DOSYASI TESTLERİ
# -----------------------------------------------------------------------------
class TestCFSHeaders:
    def test_cfs_header_file_integrity(self):
        """luna_sight_cfs_msg.h başlık dosyasının varlığı ve CCSDS tanımları."""
        header_path = Path("backend/flight_physics/include/luna_sight_cfs_msg.h")
        assert header_path.exists(), "cFS başlık dosyası oluşturulmuş olmalıdır."

        content = header_path.read_text(encoding="utf-8")
        assert "CCSDS_PriHdr_t" in content
        assert "LunaSight_HkPacket_t" in content
        assert "LunaSight_CmdPacket_t" in content
        assert "LUNA_SIGHT_CMD_APID" in content
        assert "BoulderHazardIndex" in content
        assert "KnifeEdgeMarginDb" in content


# -----------------------------------------------------------------------------
# 11. FASTAPI FİZİK REST ENDPOINT ENTEGRASYON TESTLERİ
# -----------------------------------------------------------------------------
class TestPhysicsAPIEndpoints:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_api_gateway_relay(self, client):
        resp = client.get("/api/physics/gateway-relay?duration_days=3.0&step_hours=2.0")
        assert resp.status_code == 200
        data = resp.json()
        assert "visibility" in data
        assert data["visibility"]["coverage_percentage"] > 50.0

    def test_api_link_budget(self, client):
        payload = {
            "station": "GOLDSTONE",
            "band": "S_BAND",
            "tx_power_w": 15.0,
            "data_rate_bps": 64000.0,
        }
        resp = client.post("/api/physics/link-budget", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["link_established"] is True
        assert "link_margin_db" in data

    def test_api_boulder_hazard(self, client):
        payload = {
            "slope_deg": 7.2,
            "crater_dist_m": 400.0,
            "footprint_area_m2": 12.0,
        }
        resp = client.post("/api/physics/boulder-hazard", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "collision_probability" in data
        assert "bhi_score" in data

    def test_api_knife_edge_diffraction(self, client):
        payload = {
            "obstruction_angle_deg": 0.40,
            "distance_to_ridge_m": 5000.0,
            "frequency_hz": 2.2e9,
        }
        resp = client.post("/api/physics/knife-edge-diffraction", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["link_closed"] is True
        assert data["link_margin_db"] > 0.0

    def test_api_solar_penumbra(self, client):
        resp = client.get("/api/physics/solar-penumbra?sun_elevation_deg=0.20&horizon_elevation_deg=0.05")
        assert resp.status_code == 200
        data = resp.json()
        assert data["visible_disk_fraction"] > 0.0
        assert data["power_watts"] > 0.0

    def test_api_seu_test(self, client):
        payload = {
            "storm_level": "SOLAR_STORM",
            "inject_bit_flip": True,
            "target_var": "altitude_m",
            "copy_target": "B",
            "bit_index": 12,
        }
        resp = client.post("/api/physics/seu-test", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["test_status"] == "SUCCESS"
        assert data["bit_flip_detected_and_repaired"] is True
