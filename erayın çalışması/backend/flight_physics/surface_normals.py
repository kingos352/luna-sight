"""
backend/flight_physics/surface_normals.py
=========================================
Yönsel Eğim (Aspect Map), Yüzey Normali Tensörü ve Güneş Geliş Açısı Modülü.

Gereksinim:
- compute_aspect_map(dem) -> np.ndarray (0–360° azimut açısı)
- Güneş geliş açısı kosinüsü: cos(i) = n_hat . s_hat
- Yüzey normali tensörü: (H, W, 3) şeklindeki birim vektörler

Ay kutup kraterlerinde yamaçların Güneş'e bakan (aydınlık) veya Güneş'ten kaçan
(sürekli gölgeli) taraflarını belirlemek ve fotovoltaik enerji verimini hesaplamak
için yüzey normalleri esastır.
"""

from __future__ import annotations
import math
from typing import Tuple, Union
import numpy as np


def compute_gradients(
    dem: np.ndarray,
    cell_size_m: float = 40.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Horn algoritması ile DEM üzerinden dz/dx (Doğu yönü) ve dz/dy (Kuzey yönü) gradyanlarını hesaplar.

    Not: Görüntü matrisinde satır indeksi (y) Kuzeyden Güneye arttığı için,
    Kuzey yönlü gradyan dz/dy_north = -dz/dy_matrix olarak alınır.
    """
    dem_arr = np.asarray(dem, dtype=np.float32)
    h, w = dem_arr.shape
    padded = np.pad(dem_arr, 1, mode="edge")

    z1 = padded[0:h, 0:w]      # Kuzey-Batı
    z2 = padded[0:h, 1:w + 1]  # Kuzey
    z3 = padded[0:h, 2:w + 2]  # Kuzey-Doğu

    z4 = padded[1:h + 1, 0:w]      # Batı
    z5 = padded[1:h + 1, 2:w + 2]  # Doğu

    z6 = padded[2:h + 2, 0:w]      # Güney-Batı
    z7 = padded[2:h + 2, 1:w + 1]  # Güney
    z8 = padded[2:h + 2, 2:w + 2]  # Güney-Doğu

    # Doğu (+X) yönündeki Horn türevi
    dz_dx = ((z3 + 2.0 * z5 + z8) - (z1 + 2.0 * z4 + z6)) / (8.0 * cell_size_m)
    # Matris satır (+Y_matrix = Güney) türevi
    dz_dy_matrix = ((z6 + 2.0 * z7 + z8) - (z1 + 2.0 * z2 + z3)) / (8.0 * cell_size_m)
    # Coğrafi Kuzey yönündeki türev (+Y_geo = Kuzey)
    dz_dy_north = -dz_dy_matrix

    return dz_dx, dz_dy_north


def compute_surface_normals(
    dem: np.ndarray,
    cell_size_m: float = 40.0,
) -> np.ndarray:
    """
    Her DEM pikseli için gökyüzüne doğru yönelmiş birim yüzey normali tensörünü hesaplar.

    Koordinat Sistemi:
        X: Doğu (+X)
        Y: Kuzey (+Y)
        Z: Yerel Düşey / Zenit (+Z)

    Dönüş:
        np.ndarray: shape (H, W, 3) boyutunda birim normal vektörler dizisi.
    """
    dz_dx, dz_dy_north = compute_gradients(dem, cell_size_m=cell_size_m)

    # Yüzey tanjantları: T_x = (1, 0, dz/dx), T_y = (0, 1, dz/dy)
    # Dışa bakan normal: T_x x T_y = (-dz/dx, -dz/dy, 1)
    nx = -dz_dx
    ny = -dz_dy_north
    nz = np.ones_like(nx, dtype=np.float32)

    norm = np.sqrt(nx**2 + ny**2 + nz**2)
    norm = np.maximum(norm, 1e-8)

    nx = nx / norm
    ny = ny / norm
    nz = nz / norm

    return np.stack([nx, ny, nz], axis=-1)


def compute_aspect_map(
    dem: np.ndarray,
    cell_size_m: float = 40.0,
) -> np.ndarray:
    """
    Her piksel için yönsel eğim açısını (Aspect Map / Azimut) hesaplar.
    Dönüş: 0° - 360° arasında azimut açısı:
        0°: Kuzey
        90°: Doğu
        180°: Güney
        270°: Batı
        Tam düz zeminler için 0.0° döndürülür.
    """
    dz_dx, dz_dy_north = compute_gradients(dem, cell_size_m=cell_size_m)

    # İniş/yamaç akış yönü: z'nin azaldığı yön (-grad z)
    downhill_x = -dz_dx
    downhill_y = -dz_dy_north

    # Azimut: Kuzeyden saat yönünde (atan2(x, y))
    aspect_rad = np.arctan2(downhill_x, downhill_y)
    aspect_deg = np.degrees(aspect_rad)
    aspect_deg = np.mod(aspect_deg + 360.0, 360.0)

    # Eğim neredeyse sıfır olan düz yerleri 0.0 yap
    slope_mag = np.sqrt(dz_dx**2 + dz_dy_north**2)
    aspect_deg[slope_mag < 1e-5] = 0.0

    return aspect_deg.astype(np.float32)


def compute_solar_incidence_cosine(
    surface_normals: np.ndarray,
    sun_azimuth_deg: float,
    sun_elevation_deg: float,
    clamp_negative: bool = True,
) -> np.ndarray:
    """
    Yüzey normalleri ile Güneş yön vektörü arasındaki geliş açısının kosinüsünü hesaplar:
        cos(i) = n_hat . s_hat

    Parametreler:
        surface_normals: (H, W, 3) şeklinde birim normaller
        sun_azimuth_deg: Güneş azimutu (0° Kuzey, 90° Doğu)
        sun_elevation_deg: Güneş ufuk yükselme açısı (derece)
        clamp_negative: Kendi kendine gölgelenen (cos(i) < 0) yüzeyleri 0.0'a kırpar

    Dönüş:
        np.ndarray: (H, W) şeklinde cos(i) matrisi
    """
    az_rad = math.radians(sun_azimuth_deg)
    el_rad = math.radians(sun_elevation_deg)

    # Güneş yön birim vektörü (s_hat)
    # X: Doğu, Y: Kuzey, Z: Yukarı
    sx = math.cos(el_rad) * math.sin(az_rad)
    sy = math.cos(el_rad) * math.cos(az_rad)
    sz = math.sin(el_rad)
    s_hat = np.array([sx, sy, sz], dtype=np.float32)

    # Nokta çarpım (n_hat . s_hat)
    cos_i = np.sum(surface_normals * s_hat, axis=-1)

    if clamp_negative:
        cos_i = np.maximum(0.0, cos_i)

    return cos_i.astype(np.float32)
