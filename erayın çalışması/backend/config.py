"""
backend/config.py
=================
Sistem Konfigürasyonu, Ay Fiziksel Sabitleri ve Dizin Tanımları.
"""

from __future__ import annotations
from pathlib import Path
from pydantic import BaseModel

# Proje Kök Dizini
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Dizin Yolları
DATA_DIR = PROJECT_ROOT / "data"
KERNEL_DIR = DATA_DIR / "kernels"
DEM_DIR = DATA_DIR / "dem"
REGIONS_DIR = DEM_DIR / "regions"
SHACKLETON_DEM_PATH = DEM_DIR / "shackleton_rim_dem.tif"
ARTEMIS_CANDIDATES_JSON_PATH = DEM_DIR / "artemis_candidates.json"
SHACKLETON_CANDIDATES_JSON_PATH = DEM_DIR / "shackleton_candidates.json"
CANDIDATES_JSON_PATH = ARTEMIS_CANDIDATES_JSON_PATH if ARTEMIS_CANDIDATES_JSON_PATH.exists() else SHACKLETON_CANDIDATES_JSON_PATH
DEFAULT_DEM_PATH = SHACKLETON_DEM_PATH if SHACKLETON_DEM_PATH.exists() else DEM_DIR / "lunar_south_pole_synthetic_dem.tif"

# Ay ve Güneş Fiziksel Sabitleri
LUNAR_MEAN_RADIUS_M: float = 1_737_400.0  # Ay ortalama yarıçapı (m)
LUNAR_POLAR_RADIUS_M: float = 1_736_000.0  # Ay kutup yarıçapı (m)
LUNAR_EQUATORIAL_RADIUS_M: float = 1_738_100.0  # Ay ekvator yarıçapı (m)

SOLAR_CONSTANT_1AU: float = 1361.0  # Güneş sabiti (W/m^2 @ 1 AU)
AU_METERS: float = 149_597_870_700.0  # 1 Astronomik Birim (m)
AU_KM: float = 149_597_870.7

SPEED_OF_LIGHT_KM_S: float = 299_792.458  # km/s

# İniş Kriterleri Sınır Değerleri (NASA Artemis / Görev Mühendisliği Standartları)
MAX_LANDING_SLOPE_DEG: float = 8.0  # İdeal iniş için azami eğim (derece)
ACCEPTABLE_SLOPE_DEG: float = 12.0  # Kabul edilebilir üst sınır
MAX_ROUGHNESS_M: float = 1.5  # TRI eşiği
MIN_SOLAR_ILLUMINATION_PCT: float = 40.0  # Asgari aydınlanma yüzdesi
MIN_DTE_VISIBILITY_PCT: float = 50.0  # Asgari Dünya görüş hattı yüzdesi


class SystemConfig(BaseModel):
    spice_kernel_dir: Path = KERNEL_DIR
    dem_dir: Path = DEM_DIR
    default_dem_file: Path = DEFAULT_DEM_PATH
    default_frame: str = "MOON_ME"  # Yüksek hassasiyetli frame (Mean Earth / Polar Axis)
    fallback_frame: str = "MOON_PA"
