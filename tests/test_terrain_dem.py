"""DEM okuma, LDEC boşluk maskesi ve projeksiyon doğrulaması (test_fixture)."""

import math

import numpy as np
import pytest

from luna_sight.terrain.polar import R_MOON_M, lonlat_to_xy

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import Affine  # noqa: E402
from rasterio.warp import transform as warp_transform  # noqa: E402

from luna_sight.terrain.dem import load_lola_dem  # noqa: E402

SOUTH_POLAR_PROJ = (
    f"+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 "
    f"+R={R_MOON_M:.1f} +units=m +no_defs"
)


def write_geotiff(path, array, *, nodata=None):
    rows, cols = array.shape
    transform = Affine(5.0, 0.0, -cols * 2.5, 0.0, -5.0, rows * 2.5)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=rows,
        width=cols,
        count=1,
        dtype=array.dtype,
        crs=SOUTH_POLAR_PROJ,
        transform=transform,
        nodata=nodata,
    ) as ds:
        ds.write(array, 1)
    return transform


@pytest.fixture()
def lola_pair(tmp_path):
    heights = np.full((40, 40), 1200.0, dtype="float32")
    heights[0, 0] = -9999.0  # no_data
    ldec = np.full((40, 40), 4, dtype="int16")
    ldec[:, :4] = 0  # dönüş yok → boşluk
    surf_path = tmp_path / "Site04_final_adj_5mpp_surf.tif"
    ldec_path = tmp_path / "Site04_final_adj_5mpp_ldec.tif"
    write_geotiff(surf_path, heights, nodata=-9999.0)
    write_geotiff(ldec_path, ldec)
    return surf_path, ldec_path


def test_load_lola_dem_metadata_and_gap_mask(lola_pair):
    surf_path, ldec_path = lola_pair
    dem = load_lola_dem(surf_path, ldec_path=ldec_path, site_name="Shackleton rim")

    meta = dem.metadata
    assert meta is not None
    assert meta.site_id == "Site04"
    assert meta.site_name == "Shackleton rim"
    assert meta.pixel_size_m == pytest.approx(5.0)
    assert meta.units == "m"
    assert "MOON_ME" in meta.datum
    assert meta.width == 40 and meta.height == 40
    assert dem._extra["ldec_used"] is True

    # LDEC = 0 olan ilk dört sütunda gerçek dönüş yok → kapsam dışı,
    # ancak enterpolasyonlu yüzey yüksekliği hâlâ kullanılabilir.
    assert not dem.coverage[:, :4].any()
    assert dem.coverage[:, 4:].all()
    assert dem.valid[:, 4:].all()
    assert dem.valid.sum() > dem.coverage.sum()
    # no_data pikseli her iki maskede de geçersiz.
    assert not dem.valid[0, 0]
    assert not dem.coverage[0, 0]

    lon, lat = dem.center_lonlat()
    assert lat < -89.0
    assert -180.0 <= lon <= 180.0


def test_load_lola_dem_without_ldec_marks_flag(lola_pair):
    surf_path, _ = lola_pair
    dem = load_lola_dem(surf_path)
    assert dem._extra["ldec_used"] is False
    assert not dem.valid[0, 0]


def test_projection_matches_gdal():
    """Kendi stereografik dönüşümümüz GDAL/PROJ ile aynı sonucu vermeli."""
    points = [(0.0, -89.9), (45.0, -89.0), (-120.0, -88.0)]
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    xs, ys = warp_transform(f"+proj=longlat +R={R_MOON_M:.1f} +no_defs", SOUTH_POLAR_PROJ, lons, lats)

    for (lon, lat), gx, gy in zip(points, xs, ys, strict=True):
        mx, my = lonlat_to_xy(lon, lat)
        assert mx == pytest.approx(gx, abs=1e-3)
        assert my == pytest.approx(gy, abs=1e-3)


def test_bilinear_sampling_at_pixel_centers_and_bounds():
    heights = np.arange(9, dtype=float).reshape(3, 3)
    from luna_sight.terrain.dem import DemGrid

    dem = DemGrid(heights_m=heights, transform=(10.0, 0.0, 0.0, 0.0, -10.0, 30.0))

    # Piksel merkezleri: x = 5 + 10*col, y = 25 - 10*row
    xs = np.array([5.0, 15.0, 25.0])
    ys_rows = np.array([25.0, 15.0, 5.0])

    values, ok = dem.sample(xs, np.full(3, 25.0))
    assert ok.all()
    assert values == pytest.approx(heights[0])

    column, ok_col = dem.sample(np.full(3, 5.0), ys_rows)
    assert ok_col.all()
    assert column == pytest.approx(heights[:, 0])

    outside, ok_out = dem.sample(np.array([-15.0]), np.array([-15.0]))
    assert not ok_out.any()
    assert np.isnan(outside).all()

