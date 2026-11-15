#!/usr/bin/env python3
"""
scripts/generate_synthetic_dem.py
=================================
NASA LRO (Lunar Reconnaissance Orbiter) LOLA standardında
sentetik Ay Güney Kutbu kraterli yükseklik modeli (GeoTIFF) üretir.

Özellikler:
- Ay Güney Kutbu (Shackleton / Malapert Dağı benzeri) topografyası.
- Ana derin çarpma krateri (dik duvarlar, PSR - Permanently Shadowed Region).
- Yüksek irtifa zirveleri (Connecting Ridge / Zirveler - yüksek güneşlenme potansiyeli).
- İkincil küçük kraterler, yükseltiler ve fraktal yüzey pürüzlülüğü.
- Gerçekçi kot aralığı (-3500m ile +1500m arası).
"""

from __future__ import annotations

import math
from pathlib import Path
import numpy as np

# Proje dizinleri
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEM_DIR = PROJECT_ROOT / "data" / "dem"
DEFAULT_DEM_PATH = DEM_DIR / "lunar_south_pole_synthetic_dem.tif"


def generate_lunar_dem_array(
    width: int = 256,
    height: int = 256,
    pixel_size_m: float = 40.0,
    seed: int = 42,
) -> tuple[np.ndarray, dict]:
    """
    Gerçekçi sentetik Ay topografyası yükseklik matrisi üretir.
    Dönen değer: (elevation_m [height, width], metadata_dict)
    """
    np.random.seed(seed)
    x = np.linspace(-width / 2 * pixel_size_m, width / 2 * pixel_size_m, width)
    y = np.linspace(-height / 2 * pixel_size_m, height / 2 * pixel_size_m, height)
    xx, yy = np.meshgrid(x, y)
    r = np.sqrt(xx**2 + yy**2)

    # 1. Taban dalgalı Ay regolit platosu (büyük dalga boylu dalgalanma)
    base_elev = (
        np.sin(xx / 2400.0) * 80.0
        + np.cos(yy / 2100.0) * 110.0
        + np.sin((xx + yy) / 3500.0) * 150.0
    )

    # 2. Ana Çarpma Krateri (Shackleton benzeri - merkezde derin çukurluk ve yükseltilmiş sırt)
    crater_radius = 2400.0  # metre
    crater_depth = 1800.0   # metre
    rim_height = 450.0      # krater kenarındaki yükselti

    # Krater profili: sigmoid + gauss kenar halkası
    norm_r = r / crater_radius
    crater_profile = np.zeros_like(r)

    # Krater içi (r < crater_radius)
    inside_mask = norm_r < 1.0
    # Parabolik taban ve dik iç duvarlar
    crater_profile[inside_mask] = -crater_depth * (1.0 - (norm_r[inside_mask]) ** 2) ** 0.8

    # Krater kenar sırtı (rim crest)
    rim_crest = rim_height * np.exp(-((norm_r - 1.0) / 0.28) ** 2)

    # 3. Malapert / Connecting Ridge benzeri yükselti sırtı (kuzeybatı yönünde)
    ridge_mask = np.exp(-((xx + 1800.0) / 1200.0) ** 2 - ((yy - 2000.0) / 2800.0) ** 2)
    connecting_ridge = 950.0 * ridge_mask

    # 4. İkincil darbe kraterleri (rastgele dağılmış 15 adet küçük krater)
    secondary_craters = np.zeros_like(r)
    small_craters = [
        (2200.0, 1800.0, 500.0, 160.0),
        (-2500.0, -1500.0, 650.0, 220.0),
        (1200.0, -2800.0, 400.0, 110.0),
        (-1800.0, 2200.0, 480.0, 140.0),
        (3000.0, -500.0, 350.0, 90.0),
        (-500.0, 3200.0, 520.0, 170.0),
        (2800.0, 2600.0, 300.0, 80.0),
        (-3200.0, -2800.0, 420.0, 130.0),
    ]

    for cx, cy, cradius, cdepth in small_craters:
        cr_dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        c_norm = cr_dist / cradius
        c_mask = c_norm < 1.0
        c_rim = (cdepth * 0.25) * np.exp(-((c_norm - 1.0) / 0.25) ** 2)
        secondary_craters += c_rim
        secondary_craters[c_mask] -= cdepth * (1.0 - c_norm[c_mask] ** 2)

    # 5. Ay mikroyüzey pürüzlülüğü (regolit fraktal gürültü)
    noise = (
        np.random.normal(0, 1.8, (height, width))
        + np.sin(xx / 80.0) * np.cos(yy / 80.0) * 3.5
        + np.sin(xx / 25.0) * 1.2
    )

    # Toplam yükseklik matrisi
    total_elevation = (
        base_elev
        + crater_profile
        + rim_crest
        + connecting_ridge
        + secondary_craters
        + noise
    ).astype(np.float32)

    # Merkez koordinat: Ay Güney Kutbu (-89.9° Enlem, 0.0° Boylam civarı)
    meta = {
        "width": width,
        "height": height,
        "pixel_size_m": pixel_size_m,
        "center_lat": -89.75,
        "center_lon": 0.0,
        "elevation_min": float(np.min(total_elevation)),
        "elevation_max": float(np.max(total_elevation)),
        "elevation_mean": float(np.mean(total_elevation)),
    }

    return total_elevation, meta


def save_dem_geotiff(
    elevation: np.ndarray,
    output_path: Path,
    pixel_size_m: float = 40.0,
    center_lat: float = -89.75,
    center_lon: float = 0.0,
) -> Path:
    """Yükseklik matrisini GeoTIFF olarak kaydeder (rasterio varsa tam formatta)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    height, width = elevation.shape

    try:
        import rasterio
        from rasterio.transform import from_origin

        # Ay stereografik veya yerel koordinat projeksiyonu
        x_min = - (width / 2.0) * pixel_size_m
        y_max = (height / 2.0) * pixel_size_m
        transform = from_origin(x_min, y_max, pixel_size_m, pixel_size_m)

        with rasterio.open(
            output_path,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype=elevation.dtype,
            crs="+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs",
            transform=transform,
        ) as dst:
            dst.write(elevation, 1)
            dst.update_tags(
                TITLE="LRO LOLA Synthetic Lunar South Pole DEM",
                CENTER_LAT=str(center_lat),
                CENTER_LON=str(center_lon),
                PIXEL_SIZE_M=str(pixel_size_m),
            )
        print(f"[+] Rasterio ile GeoTIFF başarıyla yazıldı: {output_path}")
    except ImportError:
        # Rasterio henüz yoksa basit binary / numpy olarak da yedekle
        np_path = output_path.with_suffix(".npy")
        np.save(np_path, elevation)
        print(f"[!] Rasterio bulunamadı, DEM NumPy dizisi olarak saklandı: {np_path}")

    return output_path


def main() -> None:
    print("=" * 70)
    print("   LUNAR SOUTH POLE SENTETİK DEM ÜRETİCİ")
    print("=" * 70)
    elev, meta = generate_lunar_dem_array(width=256, height=256, pixel_size_m=40.0)
    print(f"Çözünürlük: {meta['width']}x{meta['height']} piksel ({meta['pixel_size_m']}m/piksel)")
    print(f"Kapsanan Alan: {meta['width']*meta['pixel_size_m']/1000:.1f} km x {meta['height']*meta['pixel_size_m']/1000:.1f} km")
    print(f"Kot Aralığı: [{meta['elevation_min']:.1f} m, {meta['elevation_max']:.1f} m] (Ortalama: {meta['elevation_mean']:.1f} m)")

    dest = save_dem_geotiff(elev, DEFAULT_DEM_PATH, pixel_size_m=meta["pixel_size_m"])
    print(f"[+] Sentetik DEM hazır: {dest}")


if __name__ == "__main__":
    main()
