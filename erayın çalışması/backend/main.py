"""
backend/main.py
================
Yerel Ay İniş Sahası Navigasyon ve Yörünge Simülasyon Sistemi REST API.

FastAPI Endpoint'leri:
1. GET  /api/status          - Sistem, SPICE ve DEM sağlık durumu
2. GET  /api/terrain/mesh    - Three.js 3B arazisi için yükseklik matrisi ve sınırlar
3. GET  /api/terrain/layers  - Eğim, Pürüzlülük, Güneşlenme, DTE ve İniş Uygunluk katmanları
4. POST /api/simulate        - Seçilen koordinat ve zaman aralığı için Güneş/Dünya efemerisi ve analiz
5. POST /api/terrain/inspect - 3B harita üzerinden seçilen piksel için detaylı iniş analizi
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import numpy as np

from backend.config import PROJECT_ROOT, DEFAULT_DEM_PATH, CANDIDATES_JSON_PATH, ARTEMIS_CANDIDATES_JSON_PATH
from backend.orbital_engine import OrbitalEngine
from backend.terrain_engine import TerrainEngine
from backend.ai_landing_engine import AILandingEngine
from backend import landing_db
from backend.ml_engine import ml_engine

from backend.flight_physics.gateway_relay import generate_gateway_ephemeris, compute_gateway_visibility
from backend.flight_physics.link_budget import compute_link_budget, DSNStation, FrequencyBand
from backend.flight_physics.boulder_hazard import compute_boulder_hazard_probability
from backend.flight_physics.knife_edge_diffraction import evaluate_emergency_link_margin
from backend.flight_physics.penumbra_power import compute_penumbra_power, compute_solar_disk_fraction
from backend.flight_physics.seu_tmr_shield import TMRVariable, SEUInjector, SEUProtectedState
from backend.flight_physics.chebyshev_compression import fit_chebyshev_series, evaluate_chebyshev
from backend.flight_physics.curvature import calculate_curvature_drop, apply_curvature_correction

app = FastAPI(
    title="Lunar Landing Site Navigator & Orbit Simulation",
    description="Offline LRO DEM ve NASA SPICE MOON_ME Destekli Ay İniş Sahası ve Yörünge Simülasyonu",
    version="1.0.0",
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Motor örnekleri (Tekil önbellek)
orbital_engine = OrbitalEngine()
terrain_engine = TerrainEngine(dem_path=DEFAULT_DEM_PATH)
ai_landing_engine = AILandingEngine(candidates_file=CANDIDATES_JSON_PATH)

# Frontend statik dizini
FRONTEND_DIR = PROJECT_ROOT / "frontend"


# -----------------------------------------------------------------------------
# PYDANTIC MODELLERİ
# -----------------------------------------------------------------------------
class SimulateRequest(BaseModel):
    lat: float = Field(default=-89.75, description="Ay Enlemi (-90° ile +90°)")
    lon: float = Field(default=0.0, description="Ay Boylamı (-180° ile +180°)")
    elevation_m: float = Field(default=0.0, description="Yüzey Rakımı (m)")
    region_id: Optional[str] = Field(default=None, description="Bölgesel DEM ID'si (MALAPERT_MASSIF, CABEUS_RIDGE, FAUSTINI_RIM vb.)")
    utc_start: str = Field(default="2026-11-15T00:00:00Z", description="Başlangıç UTC zamanı")
    utc_end: str = Field(default="2026-11-16T00:00:00Z", description="Bitiş UTC zamanı")
    step_hours: float = Field(default=1.0, ge=0.1, le=24.0, description="Zaman adımı (saat)")


class InspectRequest(BaseModel):
    norm_x: float = Field(ge=0.0, le=1.0, description="Normalleştirilmiş X koordinatı (0=Batı, 1=Doğu)")
    norm_y: float = Field(ge=0.0, le=1.0, description="Normalleştirilmiş Y koordinatı (0=Kuzey, 1=Güney)")
    region_id: Optional[str] = Field(default=None, description="Aday bölge ID'si")
    utc_start: Optional[str] = Field(default="2026-11-15T00:00:00Z")
    utc_end: Optional[str] = Field(default="2026-11-16T00:00:00Z")
    step_hours: Optional[float] = Field(default=1.0)


class AILandingRunRequest(BaseModel):
    site_id: Optional[str] = Field(default="SITE_ALPHA", description="Aday saha ID'si (SITE_ALPHA, SITE_BETA, SITE_GAMMA, SITE_DELTA)")
    norm_x: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Özel iniş hedefi X koordinatı")
    norm_y: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Özel iniş hedefi Y koordinatı")
    initial_altitude_m: Optional[float] = Field(default=3200.0, ge=500.0, le=10000.0, description="Başlangıç irtifası (m)")
    initial_v_horizontal_ms: Optional[float] = Field(default=62.0, ge=0.0, le=200.0, description="Başlangıç yatay hızı (m/s)")
    initial_v_vertical_ms: Optional[float] = Field(default=-28.0, ge=-100.0, le=0.0, description="Başlangıç düşey hızı (m/s)")
    apply_noise: Optional[bool] = Field(default=True, description="Stokastik sensör ve itki gürültüsü uygulansın mı")


class MLTrainRequest(BaseModel):
    force_seed: Optional[bool] = Field(default=False, description="Zorunlu olarak yeni Monte Carlo kayıtları tohumlansın mı")
    min_samples: Optional[int] = Field(default=20, ge=5, le=1000, description="Eğitim için asgari kayıt sayısı")


class MLPredictRequest(BaseModel):
    initial_alt_m: Optional[float] = Field(default=3200.0, ge=500.0, le=10000.0, description="Başlangıç irtifası (m)")
    initial_vh_ms: Optional[float] = Field(default=62.0, ge=0.0, le=200.0, description="Başlangıç yatay hızı (m/s)")
    initial_vv_ms: Optional[float] = Field(default=-28.0, ge=-100.0, le=0.0, description="Başlangıç düşey hızı (m/s)")
    slope_deg: Optional[float] = Field(default=4.0, ge=0.0, le=45.0, description="İniş alanı yüzey eğimi (°)")
    roughness_tri_m: Optional[float] = Field(default=0.35, ge=0.0, le=5.0, description="Yüzey pürüzlülüğü TRI (m)")
    solar_illum_pct: Optional[float] = Field(default=85.0, ge=0.0, le=100.0, description="Güneşlenme oranı (%)")
    dte_vis_pct: Optional[float] = Field(default=90.0, ge=0.0, le=100.0, description="Dünya görüş hattı DTE (%)")
    total_mass_kg: Optional[float] = Field(default=5000.0, ge=2000.0, le=10000.0, description="Uzay aracı toplam kütlesi (kg)")


class LinkBudgetRequest(BaseModel):
    station: Optional[str] = Field(default="GOLDSTONE", description="DSN İstasyonu (GOLDSTONE, MADRID, CANBERRA)")
    band: Optional[str] = Field(default="S_BAND", description="Bant (S_BAND, KA_BAND, OPTICAL_O2O)")
    tx_power_w: Optional[float] = Field(default=None, description="İletici gücü (W)")
    data_rate_bps: Optional[float] = Field(default=None, description="Veri hızı (bps)")
    distance_km: Optional[float] = Field(default=384400.0, description="Mesafe (km)")
    obstacle_diffraction_loss_db: Optional[float] = Field(default=0.0, description="Dağ kırınım kaybı (dB)")


class BoulderHazardRequest(BaseModel):
    slope_deg: float = Field(default=6.5, ge=0.0, le=90.0, description="Zemin eğimi (°)")
    crater_dist_m: float = Field(default=450.0, ge=0.0, description="En yakın krater sırtına mesafe (m)")
    footprint_area_m2: Optional[float] = Field(default=12.0, ge=1.0, le=100.0, description="İniş ayak açıklığı alanı (m^2)")
    critical_diameter_m: Optional[float] = Field(default=0.35, ge=0.05, le=5.0, description="Kritik engel kayaç çapı (m)")


class KnifeEdgeDiffractionRequest(BaseModel):
    obstruction_angle_deg: float = Field(default=0.35, description="Görüş hattı engellenme açısı (°)")
    distance_to_ridge_m: Optional[float] = Field(default=5000.0, ge=100.0, description="Dağ sırtına mesafe (m)")
    frequency_hz: Optional[float] = Field(default=2.2e9, description="Taşıyıcı frekans (Hz)")
    tx_power_w: Optional[float] = Field(default=10.0, ge=0.1, le=100.0, description="İletici gücü (W)")


class SEUTestRequest(BaseModel):
    storm_level: Optional[str] = Field(default="SOLAR_STORM", description="Uzay radyasyon seviyesi (QUIET, MODERATE, SOLAR_STORM)")
    inject_bit_flip: Optional[bool] = Field(default=True, description="Bit bozulması enjekte edilsin mi")
    target_var: Optional[str] = Field(default="altitude_m", description="Hedef aviyonik değişken")
    copy_target: Optional[str] = Field(default="B", description="Bozulacak bellek kopyası (A, B veya C)")
    bit_index: Optional[int] = Field(default=14, ge=0, le=63, description="Çevrilecek bit indeksi")


# -----------------------------------------------------------------------------
# ENDPOINT'LER
# -----------------------------------------------------------------------------
@app.get("/api/status")
def get_system_status() -> Dict[str, Any]:
    """Sistem durumu, yüklenen SPICE çekirdekleri ve DEM bilgilerini döner."""
    return {
        "status": "online_offline_capable",
        "mode": "100% Offline Local Engine",
        "spice_active": orbital_engine.spice_active,
        "frame_used": orbital_engine.target_frame,
        "kernels_loaded": orbital_engine.kernels_loaded,
        "dem_loaded": terrain_engine.elevation is not None,
        "dem_shape": list(terrain_engine.elevation.shape) if terrain_engine.elevation is not None else None,
        "center_lat": terrain_engine.center_lat,
        "center_lon": terrain_engine.center_lon,
        "pixel_size_m": terrain_engine.pixel_size_m,
    }


@app.get("/api/terrain/mesh")
def get_terrain_mesh(
    resolution: int = Query(default=128, ge=32, le=512),
    region_id: Optional[str] = Query(default=None, description="Aday bölge ID'si (MALAPERT_MASSIF, CABEUS_RIDGE, FAUSTINI_RIM, SITE_ALPHA vb.)"),
) -> Dict[str, Any]:
    """Frontend 3B Three.js sahnesi için optimize edilmiş yükseklik matrisi döner."""
    try:
        engine = TerrainEngine.get_engine_for_region(region_id)
        return engine.get_mesh_data(target_resolution=resolution)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mesh verisi oluşturulamadı: {str(e)}")


@app.get("/api/terrain/layers")
def get_terrain_layers(
    resolution: int = Query(default=128, ge=32, le=512),
    region_id: Optional[str] = Query(default=None, description="Aday bölge ID'si (MALAPERT_MASSIF, CABEUS_RIDGE, FAUSTINI_RIM, SITE_ALPHA vb.)"),
) -> Dict[str, Any]:
    """Hesaplanan eğim, pürüzlülük, güneşlenme, DTE ve iniş uygunluk katmanlarını döner."""
    try:
        engine = TerrainEngine.get_engine_for_region(region_id)
        return engine.get_layers_dict(target_resolution=resolution)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Katman verileri oluşturulamadı: {str(e)}")


@app.get("/api/terrain/candidates")
def get_landing_candidates() -> Dict[str, Any]:
    """NASA Artemis III Güney Kutbu resmi aday iniş bölgelerini ve detaylı LRO LOLA analizini döner."""
    target_path = ARTEMIS_CANDIDATES_JSON_PATH if ARTEMIS_CANDIDATES_JSON_PATH.exists() else CANDIDATES_JSON_PATH
    if target_path.exists():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Adaylar dosyası okunamadı: {str(e)}")
    raise HTTPException(status_code=404, detail="artemis_candidates.json bulunamadı.")


@app.post("/api/simulate")
def run_simulation(req: SimulateRequest) -> Dict[str, Any]:
    """
    Seçilen koordinat ve zaman aralığı için Güneş ve Dünya açılarını,
    güneş akısını ve arazi genelindeki katman simülasyonunu günceller.
    """
    try:
        engine = TerrainEngine.get_engine_for_region(req.region_id)
        # 1. Ephemeris zaman serisini hesapla
        orbital_res = orbital_engine.compute_ephemeris_range(
            lat_deg=req.lat,
            lon_deg=req.lon,
            elevation_m=req.elevation_m,
            utc_start=req.utc_start,
            utc_end=req.utc_end,
            step_hours=req.step_hours,
        )

        # 2. Arazi katmanlarını bu efemeris ile simüle et
        temporal_layers = engine.simulate_temporal_layers(orbital_res)

        # 3. İstatistikler
        illum = temporal_layers["illumination_pct"]
        dte = temporal_layers["dte_pct"]
        score = temporal_layers["suitability_score"]

        summary = {
            "mean_illumination_pct": round(float(np.mean(illum)), 1),
            "max_illumination_pct": round(float(np.max(illum)), 1),
            "mean_dte_pct": round(float(np.mean(dte)), 1),
            "mean_suitability_score": round(float(np.mean(score)), 1),
            "max_suitability_score": round(float(np.max(score)), 1),
            "landing_eligible_pixel_count": int(np.sum(score >= 75.0)),
        }

        # JSON uyumlu tipler
        return {
            "status": "success",
            "orbital": {
                "timestamps": orbital_res["timestamps"],
                "sun_azimuth_deg": [round(float(x), 2) for x in orbital_res["sun_azimuth_deg"]],
                "sun_elevation_deg": [round(float(x), 2) for x in orbital_res["sun_elevation_deg"]],
                "sun_distance_km": [round(float(x), 1) for x in orbital_res["sun_distance_km"]],
                "solar_flux_w_m2": [round(float(x), 1) for x in orbital_res["solar_flux_w_m2"]],
                "earth_azimuth_deg": [round(float(x), 2) for x in orbital_res["earth_azimuth_deg"]],
                "earth_elevation_deg": [round(float(x), 2) for x in orbital_res["earth_elevation_deg"]],
                "earth_distance_km": [round(float(x), 1) for x in orbital_res["earth_distance_km"]],
                "frame_used": orbital_res["frame_used"],
                "spice_active": orbital_res["spice_active"],
            },
            "summary": summary,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simülasyon çalıştırılamadı: {str(e)}")


@app.post("/api/terrain/inspect")
def inspect_point(req: InspectRequest) -> Dict[str, Any]:
    """3B harita üzerinden seçilen noktanın iniş uygunluğunu ve zaman serisini döner."""
    try:
        engine = TerrainEngine.get_engine_for_region(req.region_id)
        # Efemeris hesapla
        orbital_res = orbital_engine.compute_ephemeris_range(
            lat_deg=engine.center_lat,
            lon_deg=engine.center_lon,
            elevation_m=0.0,
            utc_start=req.utc_start or "2026-11-15T00:00:00Z",
            utc_end=req.utc_end or "2026-11-16T00:00:00Z",
            step_hours=req.step_hours or 1.0,
        )
        return engine.inspect_point(req.norm_x, req.norm_y, orbital_res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nokta analizi başarısız: {str(e)}")


# -----------------------------------------------------------------------------
# YAPAY ZEKA OTONOM İNİŞ VE YÖRÜNGE ENDPOINT'LERİ
# -----------------------------------------------------------------------------
@app.get("/api/ai/landing/stats")
def get_ai_landing_stats() -> Dict[str, Any]:
    """Monte Carlo otonom iniş istatistikleri, başarı oranı ve geçmiş denemeleri döner."""
    try:
        return ai_landing_engine.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"İniş istatistikleri alınamadı: {str(e)}")


@app.post("/api/ai/landing/run")
def run_ai_landing_simulation(req: AILandingRunRequest) -> Dict[str, Any]:
    """
    Belirli bir aday saha veya seçilen koordinat için Ay iniş fiziği ve
    Apollo polinom güdümüyle simülasyon çalıştırır, 3B yörünge adımlarını döner.
    """
    try:
        engine = TerrainEngine.get_engine_for_region(req.site_id)
        result = ai_landing_engine.simulate_landing(
            site_id=req.site_id,
            custom_norm_x=req.norm_x,
            custom_norm_y=req.norm_y,
            initial_altitude_m=req.initial_altitude_m or 3200.0,
            initial_v_horizontal_ms=req.initial_v_horizontal_ms or 62.0,
            initial_v_vertical_ms=req.initial_v_vertical_ms or -28.0,
            apply_noise=req.apply_noise if req.apply_noise is not None else True,
            terrain_engine=engine,
        )
        return asdict(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI iniş simülasyonu başarısız: {str(e)}")


@app.get("/api/ai/landing/analysis")
def get_ai_landing_analysis() -> Dict[str, Any]:
    """Yapay zeka detaylı iniş teşhis ve optimizasyon raporunu döner."""
    try:
        return ai_landing_engine.generate_ai_analysis_report()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analiz raporu üretilemedi: {str(e)}")


# -----------------------------------------------------------------------------
# VERİTABANI VE MAKİNE ÖĞRENİMİ (ML) ENDPOINT'LERİ
# -----------------------------------------------------------------------------
@app.get("/api/database/trials")
def get_database_trials(
    limit: int = Query(default=50, ge=1, le=500, description="Kayıt limiti"),
    offset: int = Query(default=0, ge=0, description="Başlangıç ötelemesi"),
    site_id: Optional[str] = Query(default=None, description="Aday saha filtresi"),
    status: Optional[str] = Query(default=None, description="İniş durumu filtresi (SAFE_TOUCHDOWN, HARD_LANDING, CRASH vb.)"),
) -> Dict[str, Any]:
    """Veritabanında saklanan iniş denemelerini ve telemetrilerini listeler."""
    try:
        trials = landing_db.get_trials(limit=limit, offset=offset, site_id=site_id, status=status)
        return {
            "trials": trials,
            "count": len(trials),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Veritabanı kayıtları alınamadı: {str(e)}")


@app.get("/api/database/stats")
def get_database_stats() -> Dict[str, Any]:
    """Veritabanındaki tüm simülasyonların genel istatistik ve metrik özetini döner."""
    try:
        return landing_db.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Veritabanı istatistikleri alınamadı: {str(e)}")


@app.get("/api/ml/status")
def get_ml_status() -> Dict[str, Any]:
    """Makine öğrenimi motoru eğitim durumunu, R², RMSE, Doğruluk ve özellik önem düzeylerini döner."""
    try:
        return ml_engine.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ML durumu alınamadı: {str(e)}")


@app.post("/api/ml/train")
def train_ml_model(req: Optional[MLTrainRequest] = None) -> Dict[str, Any]:
    """Veritabanındaki telemetrilerle ML regresyon ve sınıflandırıcı modellerini yeniden eğitir."""
    try:
        force_seed = req.force_seed if req else False
        min_samples = req.min_samples if req else 20
        return ml_engine.train(force_seed=force_seed, min_samples=min_samples)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ML eğitimi başarısız: {str(e)}")


@app.post("/api/ml/predict")
def predict_ml_risk(req: MLPredictRequest) -> Dict[str, Any]:
    """Verilen başlangıç koşulları ve arazi özelliklerine göre uçuş öncesi ML risk ve güdüm marjı tahmini yapar."""
    try:
        telemetry = req.model_dump() if hasattr(req, "model_dump") else req.dict()
        return ml_engine.predict_risk(telemetry)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ML risk tahmini başarısız: {str(e)}")


# -----------------------------------------------------------------------------
# UÇUŞ FİZİĞİ, AVİYONİK VE TELEKOMÜNİKASYON ENDPOINT'LERİ
# -----------------------------------------------------------------------------
@app.get("/api/physics/gateway-relay")
def get_gateway_relay_visibility(
    region_id: Optional[str] = Query(default=None, description="Bölgesel DEM ID'si (MALAPERT_MASSIF, CABEUS_RIDGE, FAUSTINI_RIM vb.)"),
    duration_days: float = Query(default=7.0, ge=1.0, le=14.0, description="Simülasyon süresi (gün)"),
    step_hours: float = Query(default=1.0, ge=0.25, le=12.0, description="Adım boyutu (saat)"),
) -> Dict[str, Any]:
    """Artemis Lunar Gateway (NRHO) 7 günlük yörüngesel röle efemerisi ve iniş sahası görüş pencerelerini (AOS/LOS) döner."""
    try:
        engine = TerrainEngine.get_engine_for_region(region_id)
        site_lat = engine.center_lat
        site_lon = engine.center_lon
        site_elev_m = 0.0
        if engine.elevation is not None:
            h, w = engine.elevation.shape
            site_elev_m = float(engine.elevation[h // 2, w // 2])

        ephemeris = generate_gateway_ephemeris(duration_days=duration_days, step_hours=step_hours)
        visibility = compute_gateway_visibility(
            site_lat=site_lat,
            site_lon=site_lon,
            site_elev_m=site_elev_m,
            ephemeris=ephemeris,
            terrain_engine=engine,
        )
        return {
            "region_id": region_id or "DEFAULT",
            "ephemeris_count": len(ephemeris),
            "visibility": visibility,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gateway röle analizi başarısız: {str(e)}")


@app.post("/api/physics/link-budget")
def calculate_link_budget_endpoint(req: LinkBudgetRequest) -> Dict[str, Any]:
    """S-Band (2.2 GHz), Ka-Band (26 GHz) ve Optik O2O için NASA DSN yer istasyonu bağlantı bütçesini hesaplar."""
    try:
        station_str = (req.station or "GOLDSTONE").upper()
        band_str = (req.band or "S_BAND").upper()
        station_enum = DSNStation(station_str)
        band_enum = FrequencyBand(band_str)
        dist_m = (req.distance_km * 1000.0) if req.distance_km else 384_400_000.0
        return compute_link_budget(
            station=station_enum,
            band=band_enum,
            distance_m=dist_m,
            tx_power_w=req.tx_power_w,
            data_rate_bps=req.data_rate_bps,
            additional_obstacle_loss_db=req.obstacle_diffraction_loss_db or 0.0,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bağlantı bütçesi hesabı başarısız: {str(e)}")


@app.post("/api/physics/boulder-hazard")
def calculate_boulder_hazard_endpoint(req: BoulderHazardRequest) -> Dict[str, Any]:
    """12 m^2 iniş takımı bacak açıklığı için güç yasasıyla alt-piksel kayaç çarpma riski (BHI) hesabı."""
    try:
        return compute_boulder_hazard_probability(
            slope=req.slope_deg,
            crater_dist=req.crater_dist_m,
            footprint_area_m2=req.footprint_area_m2 or 12.0,
            d_crit_m=req.critical_diameter_m or 0.35,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kayaç tehlike hesabı başarısız: {str(e)}")


@app.post("/api/physics/knife-edge-diffraction")
def calculate_knife_edge_diffraction_endpoint(req: KnifeEdgeDiffractionRequest) -> Dict[str, Any]:
    """Dağ arkasında kalan görüş hattı için Fresnel parametresi ve ITU-R bıçak sırtı kırınımlı acil telsiz marjı."""
    try:
        return evaluate_emergency_link_margin(
            obstruction_angle_deg=req.obstruction_angle_deg,
            distance_to_ridge_m=req.distance_to_ridge_m or 5000.0,
            frequency_hz=req.frequency_hz or 2.2e9,
            tx_power_w=req.tx_power_w or 10.0,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bıçak sırtı kırınım hesabı başarısız: {str(e)}")


@app.get("/api/physics/solar-penumbra")
def get_solar_penumbra_power(
    region_id: Optional[str] = Query(default=None),
    sun_elevation_deg: float = Query(default=0.15, description="Güneş merkez açısı (derece)"),
    horizon_elevation_deg: float = Query(default=0.0, description="Ufuk sırtı engel açısı (derece)"),
    panel_area_m2: float = Query(default=8.0, ge=0.5, le=100.0, description="Güneş paneli alanı (m^2)"),
    cell_efficiency: float = Query(default=0.30, ge=0.05, le=0.50, description="Hücre verimi"),
    apply_limb_darkening: bool = Query(default=True, description="Kenar kararması uygulansın mı"),
) -> Dict[str, Any]:
    """Güneş diskinin 0.533° açısal çapı için dağ arkasında yarı-gölge (penumbra) kesri ve fotovoltaik güç çıktısı."""
    try:
        effective_horizon = horizon_elevation_deg
        if region_id is not None and horizon_elevation_deg == 0.0:
            try:
                eng = TerrainEngine.get_engine_for_region(region_id)
                h, w = eng.elevation.shape
                effective_horizon = eng.get_horizon_elevation_at(h // 2, w // 2, 0.0)
            except Exception:
                pass

        return compute_penumbra_power(
            sun_elevation_deg=sun_elevation_deg,
            horizon_elevation_deg=effective_horizon,
            panel_area_m2=panel_area_m2,
            cell_efficiency=cell_efficiency,
            apply_limb_darkening=apply_limb_darkening,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Yarı-gölge ve güç hesabı başarısız: {str(e)}")


@app.post("/api/physics/seu-test")
def test_seu_tmr_injection(req: SEUTestRequest) -> Dict[str, Any]:
    """Kozmik ışın bit-çevirme (SEU) enjeksiyonu ve TMR çoğunluk oylaması testi."""
    try:
        state = SEUProtectedState()

        var_map = {
            "altitude_m": state.alt_m,
            "v_horizontal_ms": state.v_horizontal_ms,
            "v_vertical_ms": state.v_vertical_ms,
            "target_norm_x": state.target_x,
            "target_norm_y": state.target_y,
            "thrust_pct": state.thrust_pct,
        }
        target_var = var_map.get(req.target_var, state.alt_m)
        orig_val = target_var.get()

        injected_details = {}
        if req.inject_bit_flip:
            target_copy = (req.copy_target or "B").upper()
            bit_idx = req.bit_index if req.bit_index is not None else 14
            target_var.corrupt_copy(target_copy, bit_index=bit_idx)
            injected_details = {
                "variable": target_var.name,
                "corrupted_copy": target_copy,
                "bit_index": bit_idx,
                "corrupted_value_in_copy": getattr(target_var, f"copy_{target_copy.lower()}"),
            }

        safe_val, was_repaired = target_var.vote_and_repair()
        scrub_report = state.run_health_check_and_scrub()

        return {
            "test_status": "SUCCESS",
            "storm_level": req.storm_level,
            "injection": injected_details,
            "original_value": orig_val,
            "voted_safe_value": safe_val,
            "bit_flip_detected_and_repaired": was_repaired,
            "scrub_summary": scrub_report,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SEU/TMR simülasyonu başarısız: {str(e)}")



# -----------------------------------------------------------------------------
# STATİK FRONTEND VE SPA SUNUMU
# -----------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def serve_index() -> FileResponse:
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            response = FileResponse(index_file)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response
        raise HTTPException(status_code=404, detail="Frontend index.html bulunamadı.")
