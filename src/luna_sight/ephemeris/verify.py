"""Bağımsız doğrulama: alt-nokta geometrisinden azimut ve yükseklik.

Horizons `OBSERVER` tablosu azimut ve yüksekliği doğrudan verir. Bu modül
aynı değeri **başka bir yoldan** üretir: Horizons'ın alt-güneş ve alt-dünya
noktası (`SunSub-LON/LAT`, `ObsSub-LON/LAT`) ile hedef uzaklığından yerel
ufuk çerçevesinde vektör hesabı yapar.

İki yol farklı Horizons niceliklerine ve farklı koda dayanır; sonuçların
buluşması, `OBSERVER` tablosunun bizim tarafımızda doğru yorumlandığının
kanıtıdır. Yorumun yanlış olduğu durumlar bu karşılaştırmada ortaya çıkar:
boylam yönünün ters alınması, azimutun güneyden ölçülmesi, enlem işareti
hatası, paralaks ihmali.

Çerçeve ve işaretler `docs/GOVERNANCE.md` bölüm 5 ile aynıdır: boylam
doğu-pozitif, azimut kuzeyden saat yönünde, açılar derece.
"""

from __future__ import annotations

import math

#: Horizons'ın Ay için bildirdiği küre yarıçapı (`Target radii: 1737.4 km`).
MOON_RADIUS_KM = 1737.4

#: 1 astronomik birim, km. Horizons `delta` alanını AU verir.
AU_KM = 149_597_870.7


def _unit_from_lonlat(lon_deg: float, lat_deg: float) -> tuple[float, float, float]:
    """Gövdeye sabit çerçevede birim vektör (doğu-pozitif boylam)."""
    lon = math.radians(lon_deg)
    lat = math.radians(lat_deg)
    return (
        math.cos(lat) * math.cos(lon),
        math.cos(lat) * math.sin(lon),
        math.sin(lat),
    )


def subpoint_azalt(
    site_lat_deg: float,
    site_lon_deg_east: float,
    sub_lon_deg_east: float,
    sub_lat_deg: float,
    distance_km: float,
    body_radius_km: float = MOON_RADIUS_KM,
) -> tuple[float, float]:
    """Alt-noktadan yerel azimut ve yükseklik hesapla.

    `sub_lon_deg_east` ve `sub_lat_deg`, hedefin gövde merkezinden görülen
    yönünün yüzeydeki izdüşümüdür. `distance_km` gövde merkezi ile hedef
    arasındaki uzaklıktır.

    Paralaks dahil edilir: gözlemci gövde merkezinde değil, yüzeyde
    `body_radius_km` uzaklıktadır. Güneş için bu düzeltme 0.001 derecenin
    altındadır; Dünya için 0.25 dereceye kadar çıkar ve ihmal edilirse
    ufka yakın geometride saatler mertebesinde görünürlük hatası üretir.

    Dönüş: (azimut, yükseklik) derece. Azimut kuzeyden saat yönünde [0, 360).
    """
    if distance_km <= 0:
        raise ValueError(f"distance_km pozitif olmalı: {distance_km}")
    if not -90.0 <= site_lat_deg <= 90.0:
        raise ValueError(f"site_lat_deg aralık dışı: {site_lat_deg}")

    target = _unit_from_lonlat(sub_lon_deg_east, sub_lat_deg)
    site = _unit_from_lonlat(site_lon_deg_east, site_lat_deg)

    # Gözlemciden hedefe vektör: merkez-hedef eksi merkez-gözlemci.
    vector = tuple(distance_km * t - body_radius_km * s for t, s in zip(target, site, strict=True))

    lon = math.radians(site_lon_deg_east)
    lat = math.radians(site_lat_deg)
    east = (-math.sin(lon), math.cos(lon), 0.0)
    north = (-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat))

    def dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    up_component = dot(vector, site)
    east_component = dot(vector, east)
    north_component = dot(vector, north)

    horizontal = math.hypot(east_component, north_component)
    altitude = math.degrees(math.atan2(up_component, horizontal))
    azimuth = math.degrees(math.atan2(east_component, north_component)) % 360.0
    return azimuth, altitude


def angular_difference(first_deg: float, second_deg: float) -> float:
    """İki açı arasındaki en kısa fark, derece. 359.9 ile 0.1 arası 0.2 verir."""
    return abs((first_deg - second_deg + 180.0) % 360.0 - 180.0)
