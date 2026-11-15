"""LOLA DEM'den ölçeği ve yapay aydınlatması kayıtlı topoğrafik görsel."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.windows import Window, from_bounds

from luna_sight.ai.imaging import (
    MAX_SIDE_PX,
    ImagePreparationError,
    PreparedImage,
    _to_data_url,
    validate_image,
)


def prepare_dem_hillshade(
    surface_path: Path,
    latitude_deg: float,
    longitude_deg_east: float,
    *,
    span_m: float = 4000.0,
    azimuth_deg: float = 315.0,
    altitude_deg: float = 45.0,
) -> PreparedImage:
    """Bölge merkezinden metre cinsinden kare kırp; büyütme yapma.

    Aydınlatma harita kuzeyine göredir. Bu bir ışın izleme veya gerçek
    Güneş gölgesi hesabı değildir. Boşluk ve türev komşuları siyah gösterilir.
    """
    if (
        not np.isfinite([latitude_deg, longitude_deg_east, span_m, azimuth_deg, altitude_deg]).all()
        or not -90 <= latitude_deg <= 90
        or not -180 <= longitude_deg_east <= 180
        or span_m <= 0
        or not 0 < altitude_deg <= 90
    ):
        raise ImagePreparationError("Geçersiz hillshade konumu veya aydınlatma parametresi.")
    try:
        with rasterio.open(surface_path) as ds:
            crs = CRS.from_user_input(ds.crs)
            if (
                not crs.is_projected
                or abs(crs.ellipsoid.semi_major_metre - 1737400) > 100
                or any(axis.unit_conversion_factor != 1 for axis in crs.axis_info)
                or ds.transform.b
                or ds.transform.d
                or ds.transform.a <= 0
                or ds.transform.e >= 0
            ):
                raise ImagePreparationError(
                    "DEM, metre birimli kuzeyi yukarı Ay projeksiyonunda olmalı."
                )
            x, y = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True).transform(
                longitude_deg_east, latitude_deg
            )
            half = span_m / 2
            requested = from_bounds(x - half, y - half, x + half, y + half, ds.transform)
            col, row = int(np.floor(requested.col_off)), int(np.floor(requested.row_off))
            width = int(np.ceil(requested.col_off + requested.width)) - col
            height = int(np.ceil(requested.row_off + requested.height)) - row
            if col < 0 or row < 0 or col + width > ds.width or row + height > ds.height:
                raise ImagePreparationError("Seçilen pencere DEM kapsamının dışında.")
            scale = min(1.0, MAX_SIDE_PX / max(width, height))
            out_width, out_height = max(1, int(width * scale)), max(1, int(height * scale))
            window = Window(col, row, width, height)
            data = ds.read(
                1,
                window=window,
                masked=True,
                out_shape=(out_height, out_width),
                resampling=Resampling.bilinear,
            )
            native_m = abs(ds.transform.a)
            dx = ds.transform.a * width / out_width
            dy = abs(ds.transform.e) * height / out_height
    except ImagePreparationError:
        raise
    except (rasterio.errors.RasterioError, ValueError, TypeError) as exc:
        raise ImagePreparationError(
            "Ay DEM dosyası okunamadı veya koordinat sistemi geçersiz."
        ) from exc

    valid = ~np.ma.getmaskarray(data) & np.isfinite(data.data)
    if min(data.shape) < 32 or not valid.any():
        raise ImagePreparationError("DEM penceresinde yeterli geçerli veri yok.")
    heights = np.where(valid, data.data, 0).astype(float)
    dz_row, dz_x = np.gradient(heights, dy, dx)
    dz_y = -dz_row
    azimuth, altitude = np.deg2rad([azimuth_deg, altitude_deg])
    intensity = (
        -dz_x * np.cos(altitude) * np.sin(azimuth)
        - dz_y * np.cos(altitude) * np.cos(azimuth)
        + np.sin(altitude)
    ) / np.sqrt(1 + dz_x**2 + dz_y**2)
    # Boşluk kenarında hayali sarp yamaç üretme.
    safe = valid.copy()
    safe[1:] &= valid[:-1]
    safe[:-1] &= valid[1:]
    safe[:, 1:] &= valid[:, :-1]
    safe[:, :-1] &= valid[:, 1:]
    pixels = np.where(safe, np.clip(intensity, 0, 1) * 255, 0).astype("uint8")
    image = Image.fromarray(pixels).convert("RGB")
    validate_image(image)
    return PreparedImage(
        data_url=_to_data_url(image, fmt="PNG"),
        width=image.width,
        height=image.height,
        source_label=f"LOLA DEM hillshade ({surface_path.name})",
        is_rendered=True,
        provenance_note=(
            f"LOLA yükseklik verisinden türetilmiş hillshade; fotoğraf değildir. "
            f"Merkez {latitude_deg:.6f}°, {longitude_deg_east:.6f}° doğu-pozitif; "
            f"istenen pencere {span_m:g} m. Kaynak ızgara {native_m:g} m/piksel; "
            f"gönderilen görüntü {dx:g} × {dy:g} m/piksel. "
            f"Yapay ışık: harita azimutu {azimuth_deg:g}°, yüksekliği {altitude_deg:g}°. "
            f"Geçerli türev kapsamı {safe.mean():.1%}; boşluklar siyahtır. "
            "Gerçek Güneş gölgesi, albedo, yüzey dokusu veya küçük kaya blokları "
            "bu üründen doğrulanamaz. Enterpolasyon gerçek LOLA dönüşü değildir."
        ),
    )
