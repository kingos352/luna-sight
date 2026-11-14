"""Güney kutup stereografik projeksiyonu (küresel Ay).

LOLA güney kutup DEM ürünleri, MOON_ME referans çerçevesinde ve kutupta
gerçek ölçekli (lat_ts = -90°) güney kutup stereografik projeksiyonunda
metre cinsinden X/Y koordinatlarıyla yayımlanır. Bu modül, ağır bir
projeksiyon kütüphanesine bağlı kalmadan bu dönüşümü ve azimut yönlerini
sağlar; böylece koordinat dönüşümü birim testlerle doğrulanabilir.

Sözleşme:
    - Boylam doğu-pozitif, derece (``docs/DATA_CONTRACT.md``).
    - Azimut kuzeyden saat yönünde, derece; kuzey 0°, doğu 90°.
    - Küre yarıçapı varsayılanı :data:`R_MOON_M`.
"""

from __future__ import annotations

import math

R_MOON_M = 1_737_400.0
"""Ay küresel yarıçapı (metre); LOLA kutup DEM ölçeğinde kullanılır."""

SOUTH_POLE_LON0_DEG = 0.0
"""Varsayılan merkez boylamı (projeksiyon başlangıç meridyeni)."""


def _normalize_longitude(lon_deg: float) -> float:
    """Boylamı [-180, 180) aralığına indirger."""
    wrapped = math.fmod(lon_deg + 180.0, 360.0)
    if wrapped < 0.0:
        wrapped += 360.0
    return wrapped - 180.0


def lonlat_to_xy(
    lon_deg: float,
    lat_deg: float,
    *,
    lon0_deg: float = SOUTH_POLE_LON0_DEG,
    radius_m: float = R_MOON_M,
) -> tuple[float, float]:
    """Boylam/enlem (derece) → stereografik X/Y (metre).

    Y ekseni ``lon0_deg`` meridyeni boyunca kuzeye, X ekseni doğuya bakar.
    ``lat_deg = -90`` kutupta ``(0, 0)`` döner.
    """
    if not -90.0 <= lat_deg <= 0.0:
        raise ValueError(
            f"Güney kutup stereografisi yalnızca güney yarımkürede tanımlı; "
            f"lat_deg={lat_deg} verildi."
        )
    if radius_m <= 0.0:
        raise ValueError(f"radius_m pozitif olmalı; {radius_m} verildi.")

    lat = math.radians(lat_deg)
    dlon = math.radians(_normalize_longitude(lon_deg - lon0_deg))
    rho = 2.0 * radius_m * math.tan(math.pi / 4.0 + lat / 2.0)
    return rho * math.sin(dlon), rho * math.cos(dlon)


def xy_to_lonlat(
    x_m: float,
    y_m: float,
    *,
    lon0_deg: float = SOUTH_POLE_LON0_DEG,
    radius_m: float = R_MOON_M,
) -> tuple[float, float]:
    """Stereografik X/Y (metre) → boylam/enlem (derece).

    Tam kutup noktasında boylam tanımsız olduğundan ``lon0_deg`` döner ve
    enlem -90° olur.
    """
    rho = math.hypot(x_m, y_m)
    lat_deg = math.degrees(2.0 * math.atan2(rho, 2.0 * radius_m) - math.pi / 2.0)
    if rho == 0.0:
        return _normalize_longitude(lon0_deg), -90.0
    lon_deg = lon0_deg + math.degrees(math.atan2(x_m, y_m))
    return _normalize_longitude(lon_deg), lat_deg


def north_unit_vector(lon_deg: float) -> tuple[float, float]:
    """Verilen boylamda yerel kuzey yönünün X/Y birim vektörü."""
    lon = math.radians(lon_deg)
    return math.sin(lon), math.cos(lon)


def east_unit_vector(lon_deg: float) -> tuple[float, float]:
    """Verilen boylamda yerel doğu yönünün X/Y birim vektörü."""
    lon = math.radians(lon_deg)
    return math.cos(lon), -math.sin(lon)


def azimuth_unit_vector(
    azimuth_deg: float,
    lon_deg: float,
    *,
    lon0_deg: float = SOUTH_POLE_LON0_DEG,
) -> tuple[float, float]:
    """Kuzeyden saat yönündeki azimutun X/Y düzlemindeki birim vektörü.

    ``azimuth_deg = 0`` kuzeyi, ``90`` doğuyu verir. ``lon_deg`` gözlemcinin
    boylamı, ``lon0_deg`` ise projeksiyon merkez meridyenidir.
    """
    lon = math.radians(_normalize_longitude(lon_deg - lon0_deg))
    az = math.radians(azimuth_deg)
    return math.sin(lon + az), math.cos(lon + az)
