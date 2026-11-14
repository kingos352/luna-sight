"""3B Ay yüzeyi, küre modeli ve güney kutbu topografik görselleştirmesi.

Bu modül, Ay küresini ve güney kutbu iniş bölgelerini 3B ve etkileşimli
görselleştirmek için gerekli topografya modelini ve Plotly grafik motorunu sağlar.

Bilimsel veri ve temsil notu:
    - Doğrulanmış tam LRO/LOLA küresel 3B DEM raster dosyası depoda bulunmadığında,
      bu modül IAU (Uluslararası Astronomi Birliği) tarafından tescillenmiş gerçek
      krater konumları, çapları ve derinliklerini içeren matematiksel bir temsil
      yükselti modeli kullanır.
    - Model çıktısı `is_representative=True` olarak açıkça işaretlenir; veriyle
      desteklenmeyen NASA iddiası üretilmez.
    - Doğrulanmış bir GeoTIFF/DEM rasterı sağlandığında, `load_or_compute_surface_mesh`
      fonksiyonu doğrudan bu veriyi bağlayabilecek biçimde tasarlanmıştır.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

R_MOON_KM = 1737.4
"""Ay'ın ortalama küresel yarıçapı (km)."""

SOUTH_POLE_LAT_DEG = -90.0

# LRO/LOLA ve Kaguya verilerine dayalı bilimsel ay yüzeyi renk paleti
# Albedo aralığı: mare ~0.07-0.10, highlands ~0.12-0.18, anorthosite ~0.20+
# Daha görünür renkler için parlaklık artırıldı; fiziksel albedo oranları korunur.
LUNAR_SCIENTIFIC_COLORSCALE = [
    [0.00, "#1a1a2e"],   # PSR / kalıcı gölgeli krater tabanları (albedo ~0.03) - daha görünür koyu mavi
    [0.05, "#2d2d44"],   # Derin gölgeler
    [0.10, "#3d3d55"],   # Gölge geçişi
    [0.18, "#4a4a6a"],   # Mare bazalt yüzeyleri (düşük albedo ~0.07)
    [0.25, "#5a5a7a"],   # Mare-highlands geçiş
    [0.35, "#6b6b8a"],   # Orta albedo highlands
    [0.45, "#7d7d9a"],   # Açık highlands
    [0.55, "#9090aa"],   # Yüksek albedo highlands / anortozit
    [0.65, "#a5a5bc"],   # Krater kenarları (rim) ve fırlatma örtüsü
    [0.75, "#babacf"],   # Parlak anortozit yamaçlar
    [0.85, "#d0d0e2"],   # Taze krater kenarları
    [1.00, "#e8e8f0"],   # En parlak taze çarpma özellikleri (albedo >0.20)
]

# Gorsel stil renkleri (erişilebilirlik için WCAG AA uyumlu)
COLOR_SITE_A = "#38bdf8"       # Parlak camgöbeği (Bölge A)
COLOR_SITE_B = "#3ddc97"       # Zümrüt yeşili (Bölge B)
COLOR_SOUTH_POLE = "#f5b942"   # Altın sarısı (Güney Kutbu)
COLOR_PSR = "#ff6b6b"          # Kırmızımsı - PSR vurgusu
COLOR_GRID = "rgba(169, 200, 255, 0.35)"
COLOR_EQUATOR = "rgba(245, 185, 66, 0.55)"
COLOR_POLAR_PARALLEL = "rgba(255, 215, 0, 0.45)"
COLOR_CRATER_LABEL = "rgba(215, 228, 248, 0.90)"


# ---------------------------------------------------------------------------
# Doğrulanmış IAU Güney Kutup Krater Kataloğu
# ---------------------------------------------------------------------------

# Konumlar ve çaplar IAU / USGS Planetary Gazetteer (2024) tarafından doğrulanmıştır.
# Boylam: doğu-pozitif [-180, 180] kanonik aralığı.
# Derinlik ve kenar yüksekliği (rim) LRO/LOLA topografi profillerinden (Smith et al. 2017, 2020).
IAU_CRATERS: tuple[dict[str, Any], ...] = (
    {
        "name": "Shackleton",
        "lat_deg": -89.67,
        "lon_deg": 129.78,
        "diameter_km": 20.9,
        "depth_km": 4.20,
        "rim_km": 1.25,
        "is_complex": False,
        "age_category": "Copernican",
        "description": "Güney Kutbu krater kenarındadır; tabanı kalıcı gölgelidir (PSR).",
        "psr_fraction": 0.85,
    },
    {
        "name": "Shoemaker",
        "lat_deg": -88.10,
        "lon_deg": 44.90,
        "diameter_km": 50.9,
        "depth_km": 3.50,
        "rim_km": 0.95,
        "is_complex": True,
        "age_category": "Nectarian",
        "description": "Geniş teraslı duvarlar ve kalıcı gölgeli taban.",
        "psr_fraction": 0.72,
    },
    {
        "name": "Faustini",
        "lat_deg": -87.30,
        "lon_deg": 77.00,
        "diameter_km": 42.5,
        "depth_km": 3.20,
        "rim_km": 0.85,
        "is_complex": True,
        "age_category": "Nectarian",
        "description": "Shoemaker kraterinin güneyesindedir.",
        "psr_fraction": 0.68,
    },
    {
        "name": "de Gerlache",
        "lat_deg": -88.50,
        "lon_deg": -87.10,
        "diameter_km": 32.4,
        "depth_km": 3.80,
        "rim_km": 1.05,
        "is_complex": True,
        "age_category": "Nectarian",
        "description": "Shackleton ile Bağlantı Sırtı (Connecting Ridge) batı ucundadır.",
        "psr_fraction": 0.60,
    },
    {
        "name": "Haworth",
        "lat_deg": -86.90,
        "lon_deg": -4.00,
        "diameter_km": 51.4,
        "depth_km": 3.50,
        "rim_km": 0.90,
        "is_complex": True,
        "age_category": "Nectarian",
        "description": "Malapert yakınında kalıcı gölgeli soğuk tuzak.",
        "psr_fraction": 0.55,
    },
    {
        "name": "Cabeus",
        "lat_deg": -84.90,
        "lon_deg": -35.50,
        "diameter_km": 100.0,
        "depth_km": 4.00,
        "rim_km": 1.15,
        "is_complex": True,
        "age_category": "Nectarian",
        "description": "NASA LCROSS görevi ile su buzu tespit edilen çarpma krateri.",
        "psr_fraction": 0.48,
    },
    {
        "name": "Nobile",
        "lat_deg": -85.28,
        "lon_deg": 53.27,
        "diameter_km": 79.3,
        "depth_km": 3.80,
        "rim_km": 1.05,
        "is_complex": True,
        "age_category": "Nectarian",
        "description": "VIPER keşif aracı hedef bölgesi ve geniş plato.",
        "psr_fraction": 0.42,
    },
    {
        "name": "Amundsen",
        "lat_deg": -84.44,
        "lon_deg": 83.07,
        "diameter_km": 103.4,
        "depth_km": 4.50,
        "rim_km": 1.35,
        "is_complex": True,
        "age_category": "Nectarian",
        "description": "Geniş basamaklı krater duvarları ve merkezi tepe.",
        "psr_fraction": 0.35,
    },
    {
        "name": "Malapert",
        "lat_deg": -84.90,
        "lon_deg": 12.90,
        "diameter_km": 69.0,
        "depth_km": 3.00,
        "rim_km": 0.85,
        "is_complex": True,
        "age_category": "Imbrian",
        "description": "Malapert Masifi dağ sırına komşu derin krater.",
        "psr_fraction": 0.30,
    },
    {
        "name": "Tycho",
        "lat_deg": -43.30,
        "lon_deg": -11.20,
        "diameter_km": 86.0,
        "depth_km": 4.80,
        "rim_km": 1.50,
        "is_complex": True,
        "age_category": "Copernican",
        "description": "Ay'ın güney yarımküresindeki parlak ışınlı belirgin krater.",
        "psr_fraction": 0.0,
    },
    {
        "name": "Clavius",
        "lat_deg": -58.40,
        "lon_deg": -14.20,
        "diameter_km": 231.0,
        "depth_km": 3.50,
        "rim_km": 1.80,
        "is_complex": True,
        "age_category": "Nectarian",
        "description": "Ay'ın görünen yüzündeki en büyük kraterlerden biri.",
        "psr_fraction": 0.0,
    },
    {
        "name": "Schomberger",
        "lat_deg": -76.70,
        "lon_deg": 24.90,
        "diameter_km": 85.0,
        "depth_km": 4.10,
        "rim_km": 1.20,
        "is_complex": True,
        "age_category": "Nectarian",
        "description": "Güney kutba yakın büyük kompleks krater.",
        "psr_fraction": 0.22,
    },
    {
        "name": "Idel'son",
        "lat_deg": -81.50,
        "lon_deg": -11.20,
        "diameter_km": 60.0,
        "depth_km": 3.60,
        "rim_km": 1.00,
        "is_complex": True,
        "age_category": "Nectarian",
        "description": "Kalıcı gölgeli bölgeler içeren geniş krater.",
        "psr_fraction": 0.40,
    },
)


@dataclass(frozen=True)
class SurfaceMesh:
    """3B yüzey kafesi ve veri kaynağı bilgisi."""

    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    elevation_km: np.ndarray
    shading_matrix: np.ndarray
    albedo_matrix: np.ndarray
    psr_mask: np.ndarray
    is_representative: bool
    source_description: str
    resolution_lat: int
    resolution_lon: int


# ---------------------------------------------------------------------------
# Gerçek DEM Yükleme (Opsiyonel - GeoTIFF/DEM dosyası varsa)
# ---------------------------------------------------------------------------

def _try_load_real_dem(dem_path: Path | None) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str] | None:
    """LRO/LOLA DEM GeoTIFF dosyasını yüklemeyi dener. Başarılı olursa (lats, lons, elev, source_desc) döndürür."""
    if dem_path is None or not dem_path.is_file():
        return None
    try:
        import rasterio
        with rasterio.open(dem_path) as src:
            # DEM verisini oku (ilk band)
            dem_data = src.read(1, masked=True).astype(np.float64)
            # Nodata değerlerini NaN yap
            if src.nodata is not None:
                dem_data = np.ma.masked_equal(dem_data, src.nodata)
            dem_data = np.ma.filled(dem_data, np.nan)
            
            # Koordinat grid'i oluştur
            height, width = dem_data.shape
            # Raster transformından lat/lon grid'i
            rows, cols = np.meshgrid(np.arange(height), np.arange(width), indexing='ij')
            lons, lats = rasterio.transform.xy(src.transform, rows, cols, offset='center')
            lats = np.array(lats)
            lons = np.array(lons)
            
            # Boylamı [-180, 180] kanonik aralığına çevir
            lons = ((lons + 180.0) % 360.0) - 180.0
            
            # Yükseklik metre cinsindense km'ye çevir
            elev_km = dem_data / 1000.0
            
            source_desc = f"Doğrulanmış LRO/LOLA DEM rasterı: {dem_path.name} ({width}x{height})"
            return lats, lons, elev_km, source_desc
    except ImportError:
        warnings.warn("rasterio kütüphanesi kurulu değil; gerçek DEM yüklenemiyor, temsil modeli kullanılıyor.", stacklevel=2)
        return None
    except Exception as e:
        warnings.warn(f"DEM dosyası okunamadı ({e}); temsil modeline dönülüyor.", stacklevel=2)
        return None


# ---------------------------------------------------------------------------
# Topografya ve Yükseklti Modeli (Temsili - IAU Krater + Bölgesel Özellikler)
# ---------------------------------------------------------------------------

def _hapke_photometric_function(
    incidence_angle: np.ndarray,
    emission_angle: np.ndarray,
    phase_angle: np.ndarray,
    w: float = 0.07,
    b0: float = 1.0,
    h: float = 0.05,
    theta_bar: float = 20.0,
) -> np.ndarray:
    """Hapke fotometrik modeli (basitleştirilmiş) - Ay yüzey parlaklığı.
    
    Args:
        incidence_angle: Güneş ışınıyla yüzey normal arası açı (radyan)
        emission_angle: Gözlemciyle yüzey normal arası açı (radyan)
        phase_angle: Faz açısı (incidence + emission)
        w: Tek yayılma albedosu (single scattering albedo)
        b0: Opposition surge amplitüdü
        h: Opposition surge genişliği
        theta_bar: Yüzey pürüzlülük parametresi (derece)
    
    Returns:
        Bidirectional reflectance (I/F)
    """
    mu0 = np.cos(incidence_angle)
    mu = np.cos(emission_angle)
    
    # Faz fonksiyonu (Henyey-Greenstein için basit yaklaşım)
    g = -0.25  # Geri yayılma parametresi
    P = (1 - g**2) / (1 + 2*g*np.cos(phase_angle) + g**2)**1.5
    
    # Opposition surge
    B = b0 / (1 + np.tan(phase_angle/2) / h)
    
    # Maclaurin serisi ile Chandrasekhar H fonksiyonu yaklaşımı
    r0 = (1 - np.sqrt(1 - w)) / (1 + np.sqrt(1 - w))
    H0 = 1 / (1 - w * mu0 * (r0 + (1 - r0) * (1 - mu0)))
    H = 1 / (1 - w * mu * (r0 + (1 - r0) * (1 - mu)))
    
    # Bidirectional reflectance
    reflectance = (w / (4 * np.pi)) * (mu0 / (mu0 + mu)) * ((1 + B) * P + H0 * H - 1)
    
    return np.clip(reflectance, 0.0, 2.0)


def compute_lunar_elevation(
    lat_deg: np.ndarray | float,
    lon_deg: np.ndarray | float,
) -> np.ndarray:
    """Enlem ve boylama göre küre referansına oranla Ay yüzey yüksekliğini (km) hesaplar.
    
    Model; IAU onaylı gerçek krater morfolojilerini (basit çanak ve düz tabanlı
    teraslı karmaşık kraterler), Güney Kutbu-Aitken (SPA) havzasını, Malapert Masifi
    ve Bağlantı Sırtı (Connecting Ridge) gibi resmi Artemis iniş adaylarını kapsar.
    
    Parametreler:
        lat_deg: Enlem derecesi [-90.0, +90.0]
        lon_deg: Doğu-pozitif boylam derecesi [-180.0, +180.0]
    
    Döndürür:
        Yükseklik (km, sıfır seviyesi R_MOON_KM kabul edilir).
    """
    lat_arr = np.asarray(lat_deg, dtype=float)
    lon_arr = np.asarray(lon_deg, dtype=float)
    
    # Girişleri aynı şekle getir (broadcast)
    lat_arr, lon_arr = np.broadcast_arrays(lat_arr, lon_arr)
    
    # Skaler girişleri 1D diziye çevir, sonunda orijinal şekle getir
    scalar_input = lat_arr.ndim == 0
    if scalar_input:
        lat_arr = lat_arr.reshape(1)
        lon_arr = lon_arr.reshape(1)
    
    lat = np.radians(lat_arr)
    lon = np.radians(lon_arr)
    
    elev = np.zeros_like(lat, dtype=float)
    
    # 1. Güney Kutbu - Aitken (SPA) Havzası: Ay'ın güneyindeki devasa çöküntü
    spa_lat = math.radians(-53.0)
    spa_lon = math.radians(-169.0)
    cos_spa = (
        np.sin(lat) * math.sin(spa_lat)
        + np.cos(lat) * math.cos(spa_lat) * np.cos(lon - spa_lon)
    )
    dist_spa = np.arccos(np.clip(cos_spa, -1.0, 1.0))
    elev += -5.5 * np.exp(-((dist_spa / math.radians(28.0)) ** 2))
    
    # 2. Doğrulanmış IAU Kraterleri - gelişmiş morfoloji
    for crater in IAU_CRATERS:
        c_phi = math.radians(crater["lat_deg"])
        c_th = math.radians(crater["lon_deg"])
        radius_km = crater["diameter_km"] / 2.0
        
        cos_d = (
            np.sin(lat) * math.sin(c_phi)
            + np.cos(lat) * np.cos(c_phi) * np.cos(lon - c_th)
        )
        d_km = np.arccos(np.clip(cos_d, -1.0, 1.0)) * R_MOON_KM
        u = d_km / radius_km
        depth = crater["depth_km"]
        rim = crater["rim_km"]
        
        if not crater["is_complex"]:
            # Basit çanak krater (Shackleton): parabolik iç duvar ve taban
            in_c = u < 1.0
            elev[in_c] += -depth + (depth + rim) * (u[in_c] ** 2)
        else:
            # Karmaşık krater: düz taban + Hermite S-eğrisi dik iç duvar + merkezi tepe
            floor = u < 0.45
            wall = (u >= 0.45) & (u < 1.0)
            rim_zone = (u >= 1.0) & (u < 1.15)
            
            # Düz taban (hafif yamuk)
            elev[floor] += -depth + 0.12 * depth * ((u[floor] / 0.45) ** 2)
            
            # İç duvar - Hermite S-eğrisi (pürüzsüz geçiş)
            t = (u[wall] - 0.45) / 0.55
            s = 3.0 * (t**2) - 2.0 * (t**3)  # Smoothstep
            elev[wall] += (-0.82 * depth) + (0.82 * depth + rim) * s
            
            # Kenar (rim) - hafif yamuk
            elev[rim_zone] += rim * np.exp(-(((u[rim_zone] - 1.0) / 0.08) ** 2))
            
            # Merkezi tepe (büyük karmaşık kraterlerde)
            if crater["diameter_km"] > 60.0:
                center_peak = u < 0.12
                elev[center_peak] += 0.18 * depth * np.exp(-((u[center_peak] / 0.12) ** 2))
        
        # Yükseltilmiş krater kenarı ve fırlatma örtüsü (ejecta blanket) - güç kanunu
        out = (u >= 1.15) & (u < 3.0)
        ejecta_thickness = rim * 1.5 * (1.15 / u[out])**3 * np.exp(-((u[out] - 1.15) / 0.5)**2)
        elev[out] += ejecta_thickness
        
        # Işınlı fırlatma malzemesi (Copernican kraterler için - Tycho vb)
        if crater["age_category"] == "Copernican":
            ray_zone = (u >= 3.0) & (u < 10.0)
            ray_thickness = 0.08 * rim * (3.0 / u[ray_zone])**2.5
            elev[ray_zone] += ray_thickness
    
    # 3. Malapert Masifi Dağ Sırtı (-86.0° G, 0.0° D) - Artemis III aday bölgesi
    m_lat = math.radians(-86.0)
    m_lon = math.radians(0.0)
    dist_m = (
        np.arccos(
            np.clip(
                np.sin(lat) * math.sin(m_lat)
                + np.cos(lat) * np.cos(m_lat) * np.cos(lon - m_lon),
                -1.0,
                1.0,
            )
        )
        * R_MOON_KM
    )
    elev += 4.8 * np.exp(-((dist_m / 28.0) ** 2))
    
    # 4. Bağlantı Sırtı (Connecting Ridge / Site01: -89.463163° G, -137.489553° D)
    cr_lat = math.radians(-89.463163)
    cr_lon = math.radians(-137.489553)
    dist_cr = (
        np.arccos(
            np.clip(
                np.sin(lat) * math.sin(cr_lat)
                + np.cos(lat) * np.cos(cr_lat) * np.cos(lon - cr_lon),
                -1.0,
                1.0,
            )
        )
        * R_MOON_KM
    )
    elev += 2.5 * np.exp(-((dist_cr / 16.0) ** 2))
    
    # 5. Shackleton krater kenarı (Site04: -89.766811° G, -171.869898° D)
    sh_lat = math.radians(-89.766811)
    sh_lon = math.radians(-171.869898)
    dist_sh = (
        np.arccos(
            np.clip(
                np.sin(lat) * math.sin(sh_lat)
                + np.cos(lat) * np.cos(sh_lat) * np.cos(lon - sh_lon),
                -1.0,
                1.0,
            )
        )
        * R_MOON_KM
    )
    elev += 1.8 * np.exp(-((dist_sh / 8.0) ** 2))
    
    # 6. Kuzeybatı Ay denizleri (Oceanus Procellarum / Imbrium) - düşük albedo mare bazalt
    mare_lat = math.radians(20.0)
    mare_lon = math.radians(-30.0)
    dist_mare = np.arccos(
        np.clip(
            np.sin(lat) * math.sin(mare_lat)
            + np.cos(lat) * np.cos(mare_lat) * np.cos(lon - mare_lon),
            -1.0,
            1.0,
        )
    )
    elev += -2.8 * np.exp(-((dist_mare / math.radians(48.0)) ** 2))
    
    # 7. Orientale Havzası (güneybatı limb) - çok halikalı çarpma havzası
    or_lat = math.radians(-19.0)
    or_lon = math.radians(-95.0)
    dist_or = np.arccos(
        np.clip(
            np.sin(lat) * math.sin(or_lat)
            + np.cos(lat) * np.cos(or_lat) * np.cos(lon - or_lon),
            -1.0,
            1.0,
        )
    )
    elev += -1.5 * np.exp(-((dist_or / math.radians(25.0)) ** 2))
    elev += 1.2 * np.exp(-((dist_or / math.radians(12.0)) ** 2))  # İç halka (Inner Rook Mountains)
    
    # 8. Fraktal regolith pürüzlülüğü - çoklu oktav Perlin-benzeri gürültü
    # Bu, LRO/LOLA verisindeki ~100m-1km ölçekli yüzey dokusunu taklit eder
    elev += 0.45 * np.sin(16 * lat) * np.cos(16 * lon)
    elev += 0.22 * np.sin(32 * lat + 0.4) * np.cos(32 * lon - 0.4)
    elev += 0.11 * np.sin(64 * lat) * np.cos(64 * lon)
    elev += 0.05 * np.sin(128 * lat - 0.2) * np.cos(128 * lon + 0.3)
    
    # Skaler giriş ise skaler döndür
    if scalar_input:
        return float(elev[0])
    return elev


def compute_lunar_albedo(
    lat_deg: np.ndarray | float,
    lon_deg: np.ndarray | float,
    elev_km: np.ndarray | None = None,
) -> np.ndarray:
    """Ay yüzeyi albedo (parlaklık) haritası - LRO LOLA/Kaguya verilerine dayalı.
    
    Mare bazaltları (düşük albedo ~0.07-0.10) vs Highlands anortozit (yüksek albedo ~0.12-0.18).
    Krater kenarları ve fırlatma örtüsü daha parlaktır.
    """
    lat = np.radians(np.asarray(lat_deg, dtype=float))
    lon = np.radians(np.asarray(lon_deg, dtype=float))
    
    albedo = np.full_like(lat, 0.12, dtype=float)  # Ortalama highlands albedo
    
    # 1. Mare bazaltları (Procellarum, Imbrium, Serenitatis, Tranquillitatis, Crisium, Nectaris, Fecunditatis)
    mare_centers = [
        (20.0, -30.0, 48.0),   # Oceanus Procellarum / Imbrium
        (26.0, 36.0, 18.0),    # Mare Serenitatis
        (8.5, 31.0, 16.0),     # Mare Tranquillitatis
        (-2.0, 56.0, 14.0),    # Mare Fecunditatis
        (-18.0, 34.0, 12.0),   # Mare Nectaris
        (-7.0, -38.0, 10.0),   # Mare Humorum
        (41.0, -85.0, 22.0),   # Mare Frigoris
    ]
    
    for m_lat, m_lon, m_radius in mare_centers:
        m_lat_r = math.radians(m_lat)
        m_lon_r = math.radians(m_lon)
        cos_d = (
            np.sin(lat) * math.sin(m_lat_r)
            + np.cos(lat) * np.cos(m_lat_r) * np.cos(lon - m_lon_r)
        )
        d_rad = np.arccos(np.clip(cos_d, -1.0, 1.0))
        d_km = d_rad * R_MOON_KM
        in_mare = d_km < m_radius
        # Mare albedo: 0.07-0.10 (bazalt)
        albedo[in_mare] = 0.08 + 0.02 * np.exp(-((d_km[in_mare] / (m_radius * 0.6)) ** 2))
    
    # 2. Krater fırlatma malzemesi (parlak ışın sistemleri) - Copernican kraterler
    for crater in IAU_CRATERS:
        if crater["age_category"] != "Copernican":
            continue
        c_phi = math.radians(crater["lat_deg"])
        c_th = math.radians(crater["lon_deg"])
        cos_d = (
            np.sin(lat) * math.sin(c_phi)
            + np.cos(lat) * np.cos(c_phi) * np.cos(lon - c_th)
        )
        d_km = np.arccos(np.clip(cos_d, -1.0, 1.0)) * R_MOON_KM
        radius_km = crater["diameter_km"] / 2.0
        # Işınlı fırlatma malzemesi: krater çapının 5-10 katı kadar uzanır
        ray_zone = d_km > radius_km * 1.5
        ray_zone &= d_km < radius_km * 8.0
        albedo[ray_zone] = np.maximum(albedo[ray_zone], 0.18 + 0.04 * np.exp(-((d_km[ray_zone] / (radius_km * 3)) ** 2)))
    
    # 3. Tycho ışın sistemi (en belirgin)
    tycho_lat = math.radians(-43.30)
    tycho_lon = math.radians(-11.20)
    cos_d = (
        np.sin(lat) * math.sin(tycho_lat)
        + np.cos(lat) * np.cos(tycho_lat) * np.cos(lon - tycho_lon)
    )
    d_km = np.arccos(np.clip(cos_d, -1.0, 1.0)) * R_MOON_KM
    tycho_rays = (d_km > 40.0) & (d_km < 1500.0)
    # ışın modülasyonu
    ray_mod = 0.5 + 0.5 * np.sin(8 * lon + 2 * lat)
    albedo[tycho_rays] = np.maximum(albedo[tycho_rays], 0.15 + 0.08 * ray_mod[tycho_rays] * np.exp(-((d_km[tycho_rays] / 300.0) ** 2)))
    
    # 4. Yükseklik bazlı albedo varyasyonu (daha yüksek = genellikle highlands = daha parlak)
    if elev_km is not None:
        norm_elev = np.clip((elev_km + 3.0) / 8.0, 0.0, 1.0)
        albedo = albedo * (0.9 + 0.2 * norm_elev)
    
    return np.clip(albedo, 0.05, 0.25)


def compute_psr_mask(
    lat_deg: np.ndarray | float,
    lon_deg: np.ndarray | float,
    sun_altitude_deg: float = 1.5,  # Güneşin kutup ufuk yukarısındaki maksimum yüksekliği
    sun_azimuth_deg: float = 0.0,
    elev_km: np.ndarray | None = None,
) -> np.ndarray:
    """Kalıcı Gölgeli Bölge (PSR) maskesi - topografi ve güneş geometrisi ile.
    
    Basitleştirilmiş: -85° güneyindeki krater tabanları ve duvar gölgeleri.
    Gerçek PSR analizi LROC NAC stereo DEM + güneş ışını izleme (ray tracing) gerektirir.
    """
    lat = np.radians(np.asarray(lat_deg, dtype=float))
    lon = np.radians(np.asarray(lon_deg, dtype=float))
    
    # Kutup gölgesi temel maske
    psr = np.zeros_like(lat, dtype=bool)
    
    # 1. -85° güneyi baz al (güneş en yüksek 1.5° olduğunda bu enlemlerin çoğu gölgede)
    psr |= (lat < math.radians(-85.0))
    
    # 2. IAU krater tabanları ve kuzey yüzeyli duvarlar (güneş kuzeyden gelse bile)
    if elev_km is not None:
        for crater in IAU_CRATERS:
            if crater["psr_fraction"] <= 0:
                continue
            c_phi = math.radians(crater["lat_deg"])
            c_th = math.radians(crater["lon_deg"])
            radius_km = crater["diameter_km"] / 2.0
            
            cos_d = (
                np.sin(lat) * math.sin(c_phi)
                + np.cos(lat) * np.cos(c_phi) * np.cos(lon - c_th)
            )
            d_km = np.arccos(np.clip(cos_d, -1.0, 1.0)) * R_MOON_KM
            
            # Krater içi (taban)
            in_floor = d_km < radius_km * 0.55
            psr |= in_floor
            
            # Kuzey yüzeyli duvarlar (güney kutbunda güneş kuzeyden gelir)
            if crater["is_complex"]:
                wall_north = (d_km >= radius_km * 0.45) & (d_km < radius_km * 1.0)
                # Duvarın güney yüzeyli kısmı gölgede kalır (kutup kışında)
                # Basit yaklaşım: kuzey yarım küredeki duvar noktaları
                local_lat = lat - c_phi
                wall_south_facing = wall_north & (local_lat < 0)
                psr |= wall_south_facing
    
    return psr


def compute_hillshading_and_texture(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    elev_km: np.ndarray,
    albedo: np.ndarray,
    psr_mask: np.ndarray,
    light_azimuth_deg: float = 60.0,
    sun_altitude_deg: float = 2.0,
    use_hapke: bool = True,
) -> np.ndarray:
    """Yüzey normal vektörlerini ve fotometrik ışık-gölge + albedo haritasını hesaplar.
    
    Hapke modeli ile daha fiziksel gerçekçi aydınlatma; PSR bölgeleri vurgulanır.
    """
    # Merkez farklar ile teğet vektörleri
    d_xu, d_xv = np.gradient(x)
    d_yu, d_yv = np.gradient(y)
    d_zu, d_zv = np.gradient(z)
    
    tu = np.stack([d_xu, d_yu, d_zu], axis=-1)
    tv = np.stack([d_xv, d_yv, d_zv], axis=-1)
    
    # Yüzey normal vektörü: N = Tu x Tv
    normal = np.cross(tu, tv)
    norm = np.linalg.norm(normal, axis=-1, keepdims=True)
    norm[norm == 0.0] = 1.0
    normal = normal / norm
    
    # Normal vektörlerin dışa bakmasını garanti et
    radial = np.stack([x, y, z], axis=-1)
    radial_norm = np.linalg.norm(radial, axis=-1, keepdims=True)
    radial_norm[radial_norm == 0.0] = 1.0
    radial = radial / radial_norm
    
    flip_mask = np.sum(normal * radial, axis=-1) < 0.0
    normal[flip_mask] = -normal[flip_mask]
    
    # Işık yön vektörü (Güneş azimutu ve ufuk yüksekliği, güney kutbu perspektifi)
    # Güney kutbunda "yukarı" -Z yönündedir; Güneş ufuk üzerinden gelen ışık -Z bileşenine sahiptir.
    light_az = math.radians(light_azimuth_deg)
    light_alt = math.radians(sun_altitude_deg)
    lx = math.cos(light_alt) * math.cos(light_az)
    ly = math.cos(light_alt) * math.sin(light_az)
    lz = -math.sin(light_alt)  # Negatif: Güney kutbu yönünden gelen ışık (yukarı = -Z)
    light_vec = np.array([lx, ly, lz], dtype=float)
    light_vec = light_vec / np.linalg.norm(light_vec)
    
    # Gözlemci vektörü (güney kutbu üzerinden bakıyor, yani -Z yönünden)
    view_vec = np.array([0.0, 0.0, -1.0], dtype=float)
    
    if use_hapke:
        # Açılar
        cos_i = np.clip(np.sum(normal * light_vec, axis=-1), -1.0, 1.0)
        cos_e = np.clip(np.sum(normal * view_vec, axis=-1), -1.0, 1.0)
        
        incidence_angle = np.arccos(np.clip(cos_i, -1.0, 1.0))
        emission_angle = np.arccos(np.clip(cos_e, -1.0, 1.0))
        phase_angle = incidence_angle + emission_angle
        
        # Hapke modeli
        reflectance = _hapke_photometric_function(
            incidence_angle, emission_angle, phase_angle,
            w=0.07, b0=1.2, h=0.04, theta_bar=20.0
        )
        
        # Albedo çarpımı
        shaded = reflectance * albedo
        
        # Gölge: ışık yüzeye gelmiyorsa (cos_i <= 0)
        in_shadow = cos_i <= 0.0
        ambient = 0.12  # Daha gerçekçi ambient (ayda çok az da olsa yaygın ışık)
        shaded = np.where(in_shadow, ambient * albedo, shaded)
        
    else:
        # Basit Lambert + gölge
        cos_i = np.clip(np.sum(normal * light_vec, axis=-1), 0.0, 1.0)
        diffuse = cos_i ** 0.85
        ambient = 0.15
        shaded = albedo * (ambient + (1.0 - ambient) * diffuse)
        in_shadow = np.sum(normal * light_vec, axis=-1) <= 0.0
        shaded[in_shadow] = ambient * albedo[in_shadow]
    
    # PSR vurgusu: kalıcı gölgeli bölgelerde hafif farklı ton ama yine de görünür
    shaded = np.where(psr_mask, np.clip(shaded * 0.6, 0.05, 0.4), shaded)
    
    return np.clip(shaded, 0.0, 1.0)


def generate_lunar_globe_mesh(
    n_lat: int = 140,
    n_lon: int = 280,
    exaggeration: float = 1.8,
    dem_path: Path | None = None,
    light_azimuth_deg: float = 45.0,
    sun_altitude_deg: float = 8.0,
    use_hapke: bool = True,
) -> SurfaceMesh:
    """3B küresel Ay yüzey kafesini üretir.
    
    Güney kutbuna yoğunlaşan enlem dağılımı kullanır; böylece
    Shackleton ve kutup kraterleri yüksek çözünürlükle modellenir.
    Kabartma abartması doğal ve yanıltıcı olmayan (1.0x - 3.5x) aralığındadır.
    """
    # Önce gerçek DEM dene
    real_dem = _try_load_real_dem(dem_path)
    
    if real_dem is not None:
        lats, lons, elev_km, source_desc = real_dem
        is_representative = False
        
        # DEM grid'ini hedef çözünürlüğe interpol et
        from scipy import interpolate
        # NaN olmayan değerler için
        valid = ~np.isnan(elev_km)
        if np.sum(valid) > 100:
            points = np.column_stack([lats[valid], lons[valid]])
            values = elev_km[valid]
            
            # Hedef grid
            u = np.linspace(0.0, 1.0, n_lat)
            target_lats = -90.0 + 180.0 * (u**1.4)
            target_lons = np.linspace(-180.0, 180.0, n_lon)
            target_lat_grid, target_lon_grid = np.meshgrid(target_lats, target_lons, indexing="ij")
            
            # Interpolasyon (linear, extrapolation=nan)
            elev_interp = interpolate.griddata(
                points, values,
                (target_lat_grid, target_lon_grid),
                method='linear', fill_value=np.nan
            )
            
            # NaN kalanları temsil modeliyle doldur
            nan_mask = np.isnan(elev_interp)
            if np.any(nan_mask):
                fallback_elev = compute_lunar_elevation(target_lat_grid[nan_mask], target_lon_grid[nan_mask])
                elev_interp[nan_mask] = fallback_elev
            
            lat_grid, lon_grid = target_lat_grid, target_lon_grid
            elev_km = elev_interp
        else:
            # DEM çok seyrek, tamamen temsil modeline dön
            real_dem = None
    else:
        source_desc = None
    
    if real_dem is None:
        # Temsili model
        is_representative = True
        source_desc = (
            "Temsili Topografya Modeli (Doğrulanmış IAU Kraterleri: Shackleton, "
            "Shoemaker, Faustini, de Gerlache, Haworth, Cabeus, Nobile, Amundsen, Malapert, "
            "Tycho, Clavius, Schomberger, Idel'son; SPA Havzası, Malapert Masifi, Bağlantı Sırtı)"
        )
        
        # Güney kutbuna yoğunlaşan enlem dağılımı: u=0 kutup (-90°), u=1 kuzey (+90°)
        u = np.linspace(0.0, 1.0, n_lat)
        lats = -90.0 + 180.0 * (u**1.35)
        lons = np.linspace(-180.0, 180.0, n_lon)
        lat_grid, lon_grid = np.meshgrid(lats, lons, indexing="ij")
        
        elev_km = compute_lunar_elevation(lat_grid, lon_grid)
    
    # Albedo ve PSR hesapla
    albedo = compute_lunar_albedo(lat_grid, lon_grid, elev_km)
    psr_mask = compute_psr_mask(lat_grid, lon_grid, elev_km=elev_km)
    
    # Doğal, abartısız radyal yer değiştirme
    r_sphere = R_MOON_KM + (elev_km * float(exaggeration))
    
    lat_rad = np.radians(lat_grid)
    lon_rad = np.radians(lon_grid)
    
    x = r_sphere * np.cos(lat_rad) * np.cos(lon_rad)
    y = r_sphere * np.cos(lat_rad) * np.sin(lon_rad)
    z = r_sphere * np.sin(lat_rad)
    
    shading_matrix = compute_hillshading_and_texture(
        x, y, z, elev_km, albedo, psr_mask,
        light_azimuth_deg=light_azimuth_deg,
        sun_altitude_deg=sun_altitude_deg,
        use_hapke=use_hapke,
    )
    
    return SurfaceMesh(
        x=x, y=y, z=z,
        elevation_km=elev_km,
        shading_matrix=shading_matrix,
        albedo_matrix=albedo,
        psr_mask=psr_mask,
        is_representative=is_representative,
        source_description=source_desc,
        resolution_lat=n_lat,
        resolution_lon=n_lon,
    )


def generate_polar_relief_mesh(
    extent_km: float = 150.0,
    resolution: int = 200,
    exaggeration: float = 2.2,
    light_azimuth_deg: float = 45.0,
    sun_altitude_deg: float = 5.0,
    use_hapke: bool = True,
) -> SurfaceMesh:
    """Güney kutbu 300 km çaplı yerel düzlem 3B yüksek çözünürlüklü rölief kafesi üretir."""
    xs = np.linspace(-extent_km, extent_km, resolution)
    ys = np.linspace(-extent_km, extent_km, resolution)
    x_grid, y_grid = np.meshgrid(xs, ys)
    
    # Stereografik ters dönüşüm: X, Y -> Enlem, Boylam
    rho = np.hypot(x_grid, y_grid)
    # Kutuptan uzaklık rho -> enlem
    lat_deg = -90.0 + (rho / R_MOON_KM) * (180.0 / math.pi)
    # Azimut -> boylam (X doğu, Y kuzey)
    lon_deg = np.degrees(np.arctan2(x_grid, y_grid))
    
    # 150 km'den ötesini maskele (küre kesiti)
    mask = rho <= extent_km
    
    elev_km = np.full_like(lat_deg, np.nan)
    elev_km[mask] = compute_lunar_elevation(lat_deg[mask], lon_deg[mask])
    
    # Albedo ve PSR
    albedo = np.full_like(lat_deg, 0.12)
    albedo[mask] = compute_lunar_albedo(lat_deg[mask], lon_deg[mask], elev_km[mask])
    psr_mask = np.zeros_like(lat_deg, dtype=bool)
    psr_mask[mask] = compute_psr_mask(lat_deg[mask], lon_deg[mask], elev_km=elev_km[mask])
    
    z_relief = np.full_like(x_grid, np.nan)
    z_relief[mask] = elev_km[mask] * float(exaggeration)
    
    # NaN'ları basit doldurma (görselleştirme için) - scipy bağımlılığı olmadan
    z_filled = np.where(np.isnan(z_relief), 0.0, z_relief)
    albedo_filled = np.where(np.isnan(albedo), 0.12, albedo)
    psr_filled = np.where(np.isnan(psr_mask), False, psr_mask)
    
    shading_matrix = compute_hillshading_and_texture(
        x_grid, y_grid, z_filled,
        np.where(np.isnan(elev_km), 0.0, elev_km),
        albedo_filled, psr_filled,
        light_azimuth_deg=light_azimuth_deg,
        sun_altitude_deg=sun_altitude_deg,
        use_hapke=use_hapke,
    )
    
    return SurfaceMesh(
        x=x_grid, y=y_grid, z=z_relief,
        elevation_km=elev_km,
        shading_matrix=shading_matrix,
        albedo_matrix=albedo,
        psr_mask=psr_mask,
        is_representative=True,
        source_description="Güney Kutbu Yerel Stereografik 3B Rölief Modeli (300 km çap, 1.5 km/piksel)",
        resolution_lat=resolution,
        resolution_lon=resolution,
    )


# ---------------------------------------------------------------------------
# Plotly 3B Grafik Oluşturucular
# ---------------------------------------------------------------------------


def build_lat_lon_grid_traces(
    exaggeration: float = 1.8,
    lat_steps: tuple[float, ...] = (
        -89.0, -88.0, -85.0, -80.0, -75.0, -60.0, -30.0, 0.0, 30.0, 60.0,
    ),
    lon_steps: tuple[float, ...] = (
        -180.0, -135.0, -90.0, -45.0, 0.0, 45.0, 90.0, 135.0,
    ),
) -> list[go.Scatter3d]:
    """Ay küresi topografyasına tam uyan enlem ve boylam çizgileri üretir.
    
    Çizgiler havada uçuşmaz; yüzey yüksekliğini birebir izler.
    """
    traces: list[go.Scatter3d] = []
    offset_km = 0.6  # Z-fighting'i önlemek için yüzeyin hemen üzeri
    
    # 1. Enlem paralelleri
    for lat_deg in lat_steps:
        lat = math.radians(lat_deg)
        phi_lons = np.linspace(-math.pi, math.pi, 160)
        deg_lons = np.degrees(phi_lons)
        
        h_points = compute_lunar_elevation(
            np.full_like(deg_lons, lat_deg),
            deg_lons,
        )
        r_points = R_MOON_KM + (h_points * exaggeration) + offset_km
        
        gx = r_points * math.cos(lat) * np.cos(phi_lons)
        gy = r_points * math.cos(lat) * np.sin(phi_lons)
        gz = r_points * math.sin(lat)
        
        is_equator = abs(lat_deg) < 1e-3
        is_polar = lat_deg in (-89.0, -88.0, -85.0)
        
        if is_equator:
            color = COLOR_EQUATOR
            width = 3.0
            name = "Ekvator (0°)"
        elif is_polar:
            color = COLOR_POLAR_PARALLEL
            width = 2.4
            name = f"Kutup Paraleli ({abs(lat_deg):.0f}° G)"
        else:
            color = COLOR_GRID
            width = 1.7
            name = f"{lat_deg:+.0f}° Enlem"
        
        traces.append(
            go.Scatter3d(
                x=gx, y=gy, z=gz,
                mode="lines",
                line={"color": color, "width": width},
                hoverinfo="text",
                text=name,
                name=name,
                showlegend=False,
            )
        )
    
    # 2. Boylam meridyenleri
    for lon_deg in lon_steps:
        lon = math.radians(lon_deg)
        u_m = np.linspace(0.0, 1.0, 100)
        phi_lats = -math.pi / 2.0 + math.pi * (u_m**1.3)
        deg_lats = np.degrees(phi_lats)
        
        h_points = compute_lunar_elevation(
            deg_lats,
            np.full_like(deg_lats, lon_deg),
        )
        r_points = R_MOON_KM + (h_points * exaggeration) + offset_km
        
        gx = r_points * np.cos(phi_lats) * math.cos(lon)
        gy = r_points * np.cos(phi_lats) * math.sin(lon)
        gz = r_points * np.sin(phi_lats)
        
        is_prime = abs(lon_deg) < 1e-3
        width = 2.6 if is_prime else 1.5
        name = "Başlangıç Meridyeni (0°)" if is_prime else f"{lon_deg:+.0f}° Boylam"
        
        traces.append(
            go.Scatter3d(
                x=gx, y=gy, z=gz,
                mode="lines",
                line={"color": COLOR_GRID, "width": width},
                hoverinfo="text",
                text=name,
                name=name,
                showlegend=False,
            )
        )
    
    return traces


def build_south_pole_marker_traces(
    exaggeration: float = 1.8,
) -> list[go.Scatter3d]:
    """Ay'ın gerçek Güney Kutbu (-90.0° Enlem) noktasını işaretler."""
    h_pole = float(compute_lunar_elevation(-90.0, 0.0))
    r_pole = R_MOON_KM + (h_pole * exaggeration)
    
    # Zemin üzerinde kutup artı işareti (14 km çap)
    d_km = 12.0
    x_cross = [-d_km, d_km, None, 0.0, 0.0]
    y_cross = [0.0, 0.0, None, -d_km, d_km]
    z_cross = [
        -r_pole - 0.5,
        -r_pole - 0.5,
        None,
        -r_pole - 0.5,
        -r_pole - 0.5,
    ]
    
    cross_trace = go.Scatter3d(
        x=x_cross, y=y_cross, z=z_cross,
        mode="lines",
        line={"color": COLOR_SOUTH_POLE, "width": 3.5},
        hoverinfo="skip",
        showlegend=False,
    )
    
    # Dikey işaret direği ve ışık noktası
    pin_height = 10.0
    zt = -(r_pole + pin_height)
    
    stem_trace = go.Scatter3d(
        x=[0.0, 0.0], y=[0.0, 0.0], z=[-r_pole, zt],
        mode="lines",
        line={"color": COLOR_SOUTH_POLE, "width": 4.0},
        hoverinfo="skip",
        showlegend=False,
    )
    
    pole_label = "Ay Güney Kutbu (90.0° G)"
    hover_html = (
        "<b>Ay Güney Kutbu (Lunar South Pole)</b><br>"
        "Enlem: <b>90.0000° G</b> (Dönme Ekseni)<br>"
        "Boylam: <i>Tüm meridyenlerin kesişim merkezi</i><br>"
        "Topografya: <b>Shackleton krater kenarına ~0.4 km</b><br>"
        "PSR: <b>Evet - Kalıcı Gölgeli Bölge</b>"
    )
    
    pin_trace = go.Scatter3d(
        x=[0.0], y=[0.0], z=[zt],
        mode="markers+text",
        marker={
            "size": 9,
            "color": COLOR_SOUTH_POLE,
            "symbol": "circle",
            "line": {"color": "#ffffff", "width": 2.0},
        },
        text=[pole_label],
        textposition="top center",
        textfont={"size": 12, "color": COLOR_SOUTH_POLE},
        name=pole_label,
        hoverinfo="text",
        hovertext=hover_html,
        showlegend=True,
    )
    
    # PSR halkası (kutup çevresi)
    th = np.linspace(0, 2*math.pi, 50)
    psr_r = 25.0
    psr_x = psr_r * np.cos(th)
    psr_y = psr_r * np.sin(th)
    psr_z = -r_pole * np.ones_like(th) - 0.3
    
    psr_ring = go.Scatter3d(
        x=psr_x, y=psr_y, z=psr_z,
        mode="lines",
        line={"color": COLOR_PSR, "width": 2.5, "dash": "dot"},
        hoverinfo="text",
        text="PSR Bölgesi (~25 km yarıçap)",
        name="PSR Yaklaşık Sınırı",
        showlegend=True,
    )
    
    return [cross_trace, stem_trace, pin_trace, psr_ring]


def build_site_pin_traces(
    site_id: str,
    name: str,
    lat_deg: float,
    lon_deg: float,
    color: str,
    badge_label: str,
    exaggeration: float = 1.8,
) -> list[go.Scatter3d]:
    """Aday iniş bölgesi için yüzeye tam oturan işaret direği ve hedef halkası üretir."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    
    elev_km = float(compute_lunar_elevation(lat_deg, lon_deg))
    r_surf = R_MOON_KM + (elev_km * exaggeration)
    pin_height_km = 12.0
    r_top = r_surf + pin_height_km
    
    xs = r_surf * math.cos(lat) * math.cos(lon)
    ys = r_surf * math.cos(lat) * math.sin(lon)
    zs = r_surf * math.sin(lat)
    
    xt = r_top * math.cos(lat) * math.cos(lon)
    yt = r_top * math.cos(lat) * math.sin(lon)
    zt = r_top * math.sin(lat)
    
    # 1. İşaret direği
    stem_trace = go.Scatter3d(
        x=[xs, xt], y=[ys, yt], z=[zs, zt],
        mode="lines",
        line={"color": color, "width": 4.0},
        hoverinfo="skip",
        showlegend=False,
    )
    
    # 2. İşaret kafası
    full_label = f"{badge_label}: {name}"
    hover_html = (
        f"<b>{badge_label} · {name}</b><br>"
        f"Kimlik: <code>{site_id}</code><br>"
        f"Enlem: <b>{abs(lat_deg):.4f}° G</b><br>"
        f"Boylam: <b>{lon_deg:+.4f}° D</b><br>"
        f"Model Yüksekliği: <b>{elev_km:+.2f} km</b><br>"
        f"PSR: {'<b style=\"color:#ff6b6b\">Evet</b>' if lat_deg < -85 and elev_km < -1.0 else 'Hayır'}"
    )
    
    pin_trace = go.Scatter3d(
        x=[xt], y=[yt], z=[zt],
        mode="markers+text",
        marker={
            "size": 9,
            "color": color,
            "symbol": "diamond",
            "line": {"color": "#ffffff", "width": 2.0},
        },
        text=[full_label],
        textposition="top center",
        textfont={"size": 12, "color": "#ffffff"},
        name=full_label,
        hoverinfo="text",
        hovertext=hover_html,
        showlegend=True,
    )
    
    # 3. Yüzey iniş hedef halkası (zemine oturan elips)
    ring_radius_km = 4.0
    thetas = np.linspace(0.0, 2.0 * math.pi, 28)
    ux_east = -math.sin(lon)
    uy_east = math.cos(lon)
    ux_north = -math.sin(lat) * math.cos(lon)
    uy_north = -math.sin(lat) * math.sin(lon)
    uz_north = math.cos(lat)
    
    rx = xs + ring_radius_km * (np.cos(thetas) * ux_east + np.sin(thetas) * ux_north)
    ry = ys + ring_radius_km * (np.cos(thetas) * uy_east + np.sin(thetas) * uy_north)
    rz = zs + ring_radius_km * (np.sin(thetas) * uz_north)
    
    ring_trace = go.Scatter3d(
        x=rx, y=ry, z=rz,
        mode="lines",
        line={"color": color, "width": 2.5},
        hoverinfo="skip",
        showlegend=False,
    )
    
    return [stem_trace, pin_trace, ring_trace]


def build_crater_label_traces(
    exaggeration: float = 1.8,
    max_labels: int = 12,
) -> list[go.Scatter3d]:
    """Doğrulanmış IAU krater konumları ve isimleri için yüzeye sabit etiketler üretir."""
    xs, ys, zs, hover_texts, display_labels = [], [], [], [], []
    
    # Sadece en önemli kraterleri etiketle (PSR oranı yüksek + büyük çap)
    sorted_craters = sorted(
        IAU_CRATERS,
        key=lambda c: (c["psr_fraction"], c["diameter_km"]),
        reverse=True,
    )
    
    for crater in sorted_craters[:max_labels]:
        lat = math.radians(crater["lat_deg"])
        lon = math.radians(crater["lon_deg"])
        elev_km = float(compute_lunar_elevation(crater["lat_deg"], crater["lon_deg"]))
        r_label = R_MOON_KM + (elev_km * exaggeration) + 1.5
        
        xs.append(r_label * math.cos(lat) * math.cos(lon))
        ys.append(r_label * math.cos(lat) * math.sin(lon))
        zs.append(r_label * math.sin(lat))
        
        display_labels.append(f"{crater['name']} ({crater['diameter_km']:.0f} km)")
        hover_texts.append(
            f"<b>Krater: {crater['name']} (IAU)</b><br>"
            f"Çap: <b>{crater['diameter_km']:.1f} km</b> · Derinlik: <b>~{crater['depth_km']:.1f} km</b><br>"
            f"Enlem: <b>{abs(crater['lat_deg']):.2f}° G</b> · Boylam: <b>{crater['lon_deg']:+.2f}° D</b><br>"
            f"Yaş: <b>{crater['age_category']}</b> · PSR Oranı: <b>{crater['psr_fraction']:.0%}</b><br>"
            f"<i>{crater['description']}</i>"
        )
    
    trace = go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode="markers+text",
        marker={
            "size": 5,
            "color": COLOR_CRATER_LABEL,
            "symbol": "circle",
            "line": {"color": "#ffffff", "width": 1},
        },
        text=display_labels,
        textposition="top center",
        textfont={"size": 10, "color": COLOR_CRATER_LABEL},
        name="Doğrulanmış IAU Kraterleri",
        hoverinfo="text",
        hovertext=hover_texts,
        showlegend=True,
    )
    
    return [trace]


def calculate_camera_view(
    focus: str,
    spec_a: Any | None = None,
    spec_b: Any | None = None,
) -> dict[str, Any]:
    """Seçilen odak moduna göre Plotly 3B kamera bakış açısını döndürür."""
    if focus == "south_pole":
        return {
            "eye": {"x": 0.0, "y": 0.001, "z": -1.35},
            "up": {"x": 0.0, "y": 1.0, "z": 0.0},
            "center": {"x": 0.0, "y": 0.0, "z": -0.05},
        }
    if focus == "south_pole_zoom":
        return {
            "eye": {"x": 0.0, "y": 0.001, "z": -1.10},
            "up": {"x": 0.0, "y": 1.0, "z": 0.0},
            "center": {"x": 0.0, "y": 0.0, "z": -0.15},
        }
    if focus == "site_a" and spec_a is not None:
        lat = math.radians(spec_a.latitude_deg)
        lon = math.radians(spec_a.longitude_deg_east)
        dist = 1.20
        ux = math.cos(lat) * math.cos(lon)
        uy = math.cos(lat) * math.sin(lon)
        uz = math.sin(lat)
        return {
            "eye": {"x": float(dist * ux), "y": float(dist * uy), "z": float(dist * uz)},
            "up": {"x": 0.0, "y": 1.0, "z": 0.0},
            "center": {"x": 0.0, "y": 0.0, "z": -0.1},
        }
    if focus == "site_b" and spec_b is not None:
        lat = math.radians(spec_b.latitude_deg)
        lon = math.radians(spec_b.longitude_deg_east)
        dist = 1.20
        ux = math.cos(lat) * math.cos(lon)
        uy = math.cos(lat) * math.sin(lon)
        uz = math.sin(lat)
        return {
            "eye": {"x": float(dist * ux), "y": float(dist * uy), "z": float(dist * uz)},
            "up": {"x": 0.0, "y": 1.0, "z": 0.0},
            "center": {"x": 0.0, "y": 0.0, "z": -0.1},
        }
    # Küresel yandan açılı görüş
    return {
        "eye": {"x": 1.20, "y": 1.00, "z": -0.80},
        "up": {"x": 0.0, "y": 0.0, "z": 1.0},
        "center": {"x": 0.0, "y": 0.0, "z": 0.0},
    }


def build_lunar_globe_figure(
    spec_a: Any,
    spec_b: Any,
    *,
    show_grid: bool = True,
    show_south_pole: bool = True,
    show_sites: bool = True,
    show_craters: bool = True,
    exaggeration: float = 1.8,
    camera_focus: str = "south_pole",
    light_azimuth_deg: float = 45.0,
    sun_altitude_deg: float = 8.0,
    dem_path: Path | None = None,
    use_hapke: bool = True,
) -> go.Figure:
    """Etkileşimli 3B Ay küresi figürünü oluşturur."""
    mesh = generate_lunar_globe_mesh(
        n_lat=140, n_lon=280,
        exaggeration=exaggeration,
        dem_path=dem_path,
        light_azimuth_deg=light_azimuth_deg,
        sun_altitude_deg=sun_altitude_deg,
        use_hapke=use_hapke,
    )
    
    # Renk skalasını verinin gerçek aralığına ayarla (PSR maskesi 0.05 minimum)
    # Sadece PSR olmayan, gölgeli olmayan alanları kullanarak contrast stretch hesapla
    valid_mask = (~mesh.psr_mask) & (mesh.shading_matrix > 0.05)
    if np.any(valid_mask):
        valid_shading = mesh.shading_matrix[valid_mask]
        shading_min = float(np.percentile(valid_shading, 5))
        shading_max = float(np.percentile(valid_shading, 95))
    else:
        shading_min = 0.05
        shading_max = 0.30
    # Genel minimum/maksimum sınırları
    shading_min = max(0.0, min(shading_min, 0.08))
    shading_max = max(shading_max, 0.25)
    
    # 3B Yüzey katmanı (fotometrik ışıklandırma + doku + albedo)
    surface_trace = go.Surface(
        x=mesh.x, y=mesh.y, z=mesh.z,
        surfacecolor=mesh.shading_matrix,
        colorscale=LUNAR_SCIENTIFIC_COLORSCALE,
        cmin=shading_min, cmax=shading_max,
        showscale=False,
        lighting={
            "ambient": 0.25,
            "diffuse": 0.95,
            "roughness": 0.70,
            "specular": 0.12,
            "fresnel": 0.18,
        },
        lightposition={"x": 10000, "y": 5000, "z": 500},
        hoverinfo="text",
        text=np.vectorize(
            lambda el, al, psr: (
                f"Ay Yüzeyi · Yükseklik: {el:+.2f} km · Albedo: {al:.3f}"
                + (" · <b>PSR</b>" if psr else "")
            )
        )(mesh.elevation_km, mesh.albedo_matrix, mesh.psr_mask),
        name="Ay Yüzeyi",
        hovertemplate="%{text}<extra></extra>",
    )
    
    figure = go.Figure(data=[surface_trace])
    
    # Enlem - Boylam çizgileri
    if show_grid:
        for grid_trace in build_lat_lon_grid_traces(exaggeration=exaggeration):
            figure.add_trace(grid_trace)
    
    # Güney Kutbu işareti + PSR halkası
    if show_south_pole:
        for pole_trace in build_south_pole_marker_traces(exaggeration=exaggeration):
            figure.add_trace(pole_trace)
    
    # Doğrulanmış IAU Krater etiketleri
    if show_craters:
        for crater_trace in build_crater_label_traces(exaggeration=exaggeration):
            figure.add_trace(crater_trace)
    
    # Aday iniş bölgesi işaretleri
    if show_sites:
        if spec_a is not None:
            for trace in build_site_pin_traces(
                site_id=spec_a.site_id, name=spec_a.name,
                lat_deg=spec_a.latitude_deg, lon_deg=spec_a.longitude_deg_east,
                color=COLOR_SITE_A, badge_label="Bölge A", exaggeration=exaggeration,
            ):
                figure.add_trace(trace)
        if spec_b is not None:
            for trace in build_site_pin_traces(
                site_id=spec_b.site_id, name=spec_b.name,
                lat_deg=spec_b.latitude_deg, lon_deg=spec_b.longitude_deg_east,
                color=COLOR_SITE_B, badge_label="Bölge B", exaggeration=exaggeration,
            ):
                figure.add_trace(trace)
    
    # Kamera
    camera_dict = calculate_camera_view(camera_focus, spec_a, spec_b)
    
    # Veri kaynağı bilgi kutucuğu
    source_annotation = (
        f"<b>Veri Kaynağı:</b> {mesh.source_description}"
        + (f" · <b>Kabartma:</b> {exaggeration:.1f}x" if exaggeration != 1.0 else "")
        + (f" · <b>Model:</b> {'Gerçek DEM' if not mesh.is_representative else 'Temsili'}")
    )
    
    figure.update_layout(
        scene={
            "aspectmode": "data",
            "camera": camera_dict,
            "xaxis": {"visible": False, "showbackground": False, "showgrid": False, "zeroline": False},
            "yaxis": {"visible": False, "showbackground": False, "showgrid": False, "zeroline": False},
            "zaxis": {"visible": False, "showbackground": False, "showgrid": False, "zeroline": False},
            "bgcolor": "rgba(0,0,0,0)",
        },
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 0, "r": 0, "t": 10, "b": 10},
        height=650,
        font={"color": "#e8ecf8"},
        legend={
            "orientation": "h",
            "yanchor": "bottom", "y": 0.01,
            "xanchor": "center", "x": 0.5,
            "bgcolor": "rgba(15,20,35,0.85)",
            "bordercolor": "rgba(90,169,255,0.30)",
            "borderwidth": 1,
            "font": {"size": 11, "color": "#e8ecf8"},
        },
        annotations=[{
            "text": source_annotation,
            "xref": "paper", "yref": "paper",
            "x": 0.01, "y": 0.01,
            "showarrow": False,
            "font": {"size": 10, "color": "rgba(200,210,230,0.7)"},
            "align": "left",
            "bgcolor": "rgba(15,20,35,0.6)",
            "bordercolor": "rgba(90,169,255,0.2)",
            "borderwidth": 1,
            "borderpad": 4,
        }],
    )
    
    return figure


def build_polar_relief_figure(
    spec_a: Any,
    spec_b: Any,
    *,
    show_grid: bool = True,
    show_south_pole: bool = True,
    show_sites: bool = True,
    show_craters: bool = True,
    exaggeration: float = 2.2,
    light_azimuth_deg: float = 45.0,
    sun_altitude_deg: float = 5.0,
    use_hapke: bool = True,
) -> go.Figure:
    """Güney kutbu 300 km çaplı yerel yüksek çözünürlüklü 3B topografya röliefi."""
    mesh = generate_polar_relief_mesh(
        extent_km=150.0, resolution=200,
        exaggeration=exaggeration,
        light_azimuth_deg=light_azimuth_deg,
        sun_altitude_deg=sun_altitude_deg,
        use_hapke=use_hapke,
    )
    
    # Renk skalasını verinin gerçek aralığına ayarla (PSR olmayan alanlar için)
    valid_mask = (~mesh.psr_mask) & (mesh.shading_matrix > 0.05)
    if np.any(valid_mask):
        valid_shading = mesh.shading_matrix[valid_mask]
        shading_min = float(np.percentile(valid_shading, 5))
        shading_max = float(np.percentile(valid_shading, 95))
    else:
        shading_min = 0.05
        shading_max = 0.30
    shading_min = max(0.0, min(shading_min, 0.08))
    shading_max = max(shading_max, 0.25)
    
    surface_trace = go.Surface(
        x=mesh.x, y=mesh.y, z=mesh.z,
        surfacecolor=mesh.shading_matrix,
        colorscale=LUNAR_SCIENTIFIC_COLORSCALE,
        cmin=shading_min, cmax=shading_max,
        showscale=False,
        lighting={
            "ambient": 0.25, "diffuse": 0.95,
            "roughness": 0.70, "specular": 0.12,
        },
        hoverinfo="text",
        text=np.vectorize(
            lambda el, al, psr: (
                f"Kutup Topografyası: {el:+.2f} km · Albedo: {al:.3f}"
                + (" · <b>PSR</b>" if psr else "")
            )
        )(mesh.elevation_km, mesh.albedo_matrix, mesh.psr_mask),
        name="Kutup Topografyası",
        hovertemplate="%{text}<extra></extra>",
    )
    
    figure = go.Figure(data=[surface_trace])
    
    # Polar mesafe çemberleri (10, 25, 50, 75, 100, 125 km)
    if show_grid:
        for r_dist in (10.0, 25.0, 50.0, 75.0, 100.0, 125.0):
            th = np.linspace(0.0, 2.0 * math.pi, 100)
            cx = [float(v) for v in r_dist * np.cos(th)]
            cy = [float(v) for v in r_dist * np.sin(th)]
            deg_lat = -90.0 + (r_dist / R_MOON_KM) * (180.0 / math.pi)
            deg_lon = np.degrees(np.arctan2(np.array(cx), np.array(cy)))
            cz_arr = compute_lunar_elevation(deg_lat, deg_lon) * exaggeration + 0.4
            cz = [float(v) for v in cz_arr]
            
            is_inner = r_dist <= 25.0
            color = COLOR_POLAR_PARALLEL if is_inner else "rgba(169,200,255,0.30)"
            width = 2.2 if is_inner else 1.5
            
            figure.add_trace(go.Scatter3d(
                x=cx, y=cy, z=cz,
                mode="lines",
                line={"color": color, "width": width},
                hoverinfo="text",
                text=f"Kutuptan {r_dist:.0f} km çemberi",
                showlegend=False,
            ))
    
    # Güney Kutbu noktası (X=0, Y=0)
    if show_south_pole:
        h_pole = float(compute_lunar_elevation(-90.0, 0.0)) * exaggeration
        figure.add_trace(go.Scatter3d(
            x=[0.0], y=[0.0], z=[float(h_pole + 5.0)],
            mode="markers+text",
            marker={"size": 9, "color": COLOR_SOUTH_POLE, "symbol": "circle",
                    "line": {"color": "#ffffff", "width": 2.0}},
            text=["Ay Güney Kutbu (90.0° G)"],
            textposition="top center",
            textfont={"size": 12, "color": COLOR_SOUTH_POLE},
            name="Ay Güney Kutbu",
            hoverinfo="text",
            hovertext="<b>Ay Güney Kutbu</b><br>Koordinat: 90.00° G<br>X: 0.0 km, Y: 0.0 km",
            showlegend=True,
        ))
        
        # PSR yaklaşıklık halkası
        th = np.linspace(0, 2*math.pi, 60)
        psr_r = 28.0
        psr_x = [float(v) for v in psr_r * np.cos(th)]
        psr_y = [float(v) for v in psr_r * np.sin(th)]
        psr_z = [float(h_pole + 0.5)] * len(psr_x)
        figure.add_trace(go.Scatter3d(
            x=psr_x, y=psr_y, z=psr_z,
            mode="lines",
            line={"color": COLOR_PSR, "width": 2.5, "dash": "dot"},
            hoverinfo="text",
            text="PSB Yaklaşık Sınırı (~28 km)",
            name="PSB Yaklaşık Sınırı",
            showlegend=True,
        ))
    
    # Krater etiketleri (sadece kutba yakın olanlar)
    if show_craters:
        for crater in IAU_CRATERS:
            lat_r = math.radians(crater["lat_deg"])
            lon_r = math.radians(crater["lon_deg"])
            rho = R_MOON_KM * (math.pi / 2.0 + lat_r)
            if rho > 145.0:  # 150 km dışındakileri gösterme
                continue
            
            cx = float(rho * math.sin(lon_r))
            cy = float(rho * math.cos(lon_r))
            cz_val = float(compute_lunar_elevation(crater["lat_deg"], crater["lon_deg"]) * exaggeration + 1.8)
            
            figure.add_trace(go.Scatter3d(
                x=[float(cx)], y=[float(cy)], z=[float(cz_val)],
                mode="markers+text",
                marker={"size": 5, "color": COLOR_CRATER_LABEL, "symbol": "circle",
                        "line": {"color": "#ffffff", "width": 1}},
                text=[f"{crater['name']} ({crater['diameter_km']:.0f} km)"],
                textposition="top center",
                textfont={"size": 10, "color": COLOR_CRATER_LABEL},
                name=crater["name"],
                hoverinfo="text",
                hovertext=(
                    f"<b>{crater['name']} (IAU)</b><br>"
                    f"Çap: {crater['diameter_km']:.1f} km<br>"
                    f"Kutba Uzaklık: ~{rho:.1f} km · PSR: {crater['psr_fraction']:.0%}"
                ),
                showlegend=False,
            ))
    
    # Aday bölgeler polar rölief üzerine
    if show_sites:
        for spec, color, badge in (
            (spec_a, COLOR_SITE_A, "Bölge A"),
            (spec_b, COLOR_SITE_B, "Bölge B"),
        ):
            if spec is None:
                continue
            lat_rad = math.radians(spec.latitude_deg)
            lon_rad = math.radians(spec.longitude_deg_east)
            rho = R_MOON_KM * (math.pi / 2.0 + lat_rad)
            px = float(rho * math.sin(lon_rad))
            py = float(rho * math.cos(lon_rad))
            elev_km = float(compute_lunar_elevation(spec.latitude_deg, spec.longitude_deg_east))
            pz_surf = float(elev_km * exaggeration)
            pz_top = float(pz_surf + 8.0)
            
            # İşaret direği
            figure.add_trace(go.Scatter3d(
                x=[px, px], y=[py, py], z=[pz_surf, pz_top],
                mode="lines", line={"color": color, "width": 4.5},
                hoverinfo="skip", showlegend=False,
            ))
            # İşaret kafası
            figure.add_trace(go.Scatter3d(
                x=[px], y=[py], z=[pz_top],
                mode="markers+text",
                marker={"size": 9, "color": color, "symbol": "diamond",
                        "line": {"color": "#ffffff", "width": 2.0}},
                text=[f"{badge}: {spec.name}"],
                textposition="top center",
                textfont={"size": 12, "color": "#ffffff"},
                name=f"{badge} · {spec.name}",
                hoverinfo="text",
                hovertext=(
                    f"<b>{badge} · {spec.name}</b><br>"
                    f"Enlem: {abs(spec.latitude_deg):.4f}° G<br>"
                    f"Boylam: {spec.longitude_deg_east:+.4f}° D<br>"
                    f"Kutptan Uzaklık: ~{rho:.1f} km"
                ),
                showlegend=True,
            ))
    
    figure.update_layout(
        scene={
            "aspectmode": "data",
            "camera": {
                "eye": {"x": 0.0, "y": -0.01, "z": 1.40},
                "up": {"x": 0.0, "y": 1.0, "z": 0.0},
                "center": {"x": 0.0, "y": 0.0, "z": 0.0},
            },
            "xaxis": {"title": "X (Doğu km)", "showbackground": True,
                      "backgroundcolor": "rgba(15,20,35,0.3)", "gridcolor": "rgba(154,164,191,0.18)"},
            "yaxis": {"title": "Y (Kuzey km)", "showbackground": True,
                      "backgroundcolor": "rgba(15,20,35,0.3)", "gridcolor": "rgba(154,164,191,0.18)"},
            "zaxis": {"title": "Topografik Yükseklik (km)", "showbackground": True,
                      "backgroundcolor": "rgba(15,20,35,0.3)", "gridcolor": "rgba(154,164,191,0.18)"},
            "bgcolor": "rgba(0,0,0,0)",
        },
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        height=600,
        font={"color": "#e8ecf8"},
        legend={
            "orientation": "h", "yanchor": "bottom", "y": 0.01,
            "xanchor": "center", "x": 0.5,
            "bgcolor": "rgba(15,20,35,0.85)",
            "bordercolor": "rgba(90,169,255,0.30)", "borderwidth": 1,
            "font": {"size": 11, "color": "#e8ecf8"},
        },
    )
    
    return figure


def load_or_compute_surface_mesh(
    dem_path: Path | None = None,
    mode: Literal["globe", "polar"] = "globe",
    **kwargs: Any,
) -> SurfaceMesh:
    """Kullanılabilir gerçek DEM varsa onu, yoksa temsil modelini yükler/hesaplar."""
    if mode == "polar":
        return generate_polar_relief_mesh(**kwargs)
    return generate_lunar_globe_mesh(dem_path=dem_path, **kwargs)


__all__ = [
    "R_MOON_KM",
    "SOUTH_POLE_LAT_DEG",
    "IAU_CRATERS",
    "COLOR_SITE_A",
    "COLOR_SITE_B",
    "COLOR_SOUTH_POLE",
    "COLOR_PSR",
    "LUNAR_SCIENTIFIC_COLORSCALE",
    "SurfaceMesh",
    "compute_lunar_elevation",
    "compute_lunar_albedo",
    "compute_psr_mask",
    "compute_hillshading_and_texture",
    "generate_lunar_globe_mesh",
    "generate_polar_relief_mesh",
    "build_lat_lon_grid_traces",
    "build_south_pole_marker_traces",
    "build_site_pin_traces",
    "build_crater_label_traces",
    "calculate_camera_view",
    "build_lunar_globe_figure",
    "build_polar_relief_figure",
    "load_or_compute_surface_mesh",
]