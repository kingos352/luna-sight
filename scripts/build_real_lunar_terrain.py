import json
import os

import numpy as np
import rasterio
from PIL import Image
from rasterio.windows import from_bounds


def build_terrain_for_site(
    site_id,
    tiff_path,
    center_x,
    center_y,
    width_m=8000.0,
    height_m=8000.0,
    grid_points=200,
):
    half_w = width_m / 2.0
    half_h = height_m / 2.0
    min_x = center_x - half_w
    max_x = center_x + half_w
    min_y = center_y - half_h
    max_y = center_y + half_h

    print(f"[{site_id}] Opening {tiff_path}...")
    with rasterio.open(tiff_path) as src:
        window = from_bounds(min_x, min_y, max_x, max_y, src.transform)
        # Read the elevation window
        elev_patch = src.read(1, window=window)
        # Replace any NaNs
        if np.isnan(elev_patch).any():
            valid_mean = np.nanmean(elev_patch)
            elev_patch = np.nan_to_num(elev_patch, nan=valid_mean)

        print(
            f"[{site_id}] Extracted patch shape: {elev_patch.shape}, "
            f"min: {elev_patch.min():.1f}m, max: {elev_patch.max():.1f}m"
        )

    # 1. Generate 200x200 downsampled grid for Three.js
    # Row 0 is max_y (top), Row 199 is min_y (bottom)
    # Col 0 is min_x (left), Col 199 is max_x (right)
    # Use bilinear / area interpolation via PIL for smooth high-quality mesh
    im_elev = Image.fromarray(elev_patch.astype(np.float32))
    im_elev_resampled = im_elev.resize((grid_points, grid_points), Image.Resampling.BILINEAR)
    grid_elev = np.array(im_elev_resampled, dtype=np.float32)

    # Convert to 2D list rounded to 1 decimal place
    elevations_surf = [[round(float(v), 1) for v in row] for row in grid_elev]

    # Get observer elevation at (center_x, center_y)
    obs_row = int(round((max_y - center_y) / height_m * (elev_patch.shape[0] - 1)))
    obs_col = int(round((center_x - min_x) / width_m * (elev_patch.shape[1] - 1)))
    obs_row = max(0, min(elev_patch.shape[0] - 1, obs_row))
    obs_col = max(0, min(elev_patch.shape[1] - 1, obs_col))
    z_ground = float(elev_patch[obs_row, obs_col])
    z_eye = z_ground + 2.0

    # Load existing JSON if available to preserve patch_corners, rays, etc.
    json_path = f"app/static/moon/data/terrain_{site_id.lower()}.json"
    existing_data = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"Could not read existing JSON: {e}")

    patch_corners = existing_data.get(
        "patch_corners_m",
        [
            {"x_m": center_x - 200.0, "y_m": center_y - 200.0},
            {"x_m": center_x + 200.0, "y_m": center_y - 200.0},
            {"x_m": center_x + 200.0, "y_m": center_y + 200.0},
            {"x_m": center_x - 200.0, "y_m": center_y + 200.0},
        ],
    )
    patch_center = existing_data.get("patch_center_m", {"x_m": center_x, "y_m": center_y})
    rays = existing_data.get("rays", {})

    output_data = {
        "bounds": {
            "min_x": float(min_x),
            "max_x": float(max_x),
            "min_y": float(min_y),
            "max_y": float(max_y),
            "width_m": float(width_m),
            "height_m": float(height_m),
        },
        "grid_size": [grid_points, grid_points],
        "resolution_m": round(float(width_m) / (grid_points - 1), 2),
        "observer_pos": {
            "x_m": float(center_x),
            "y_m": float(center_y),
            "z_ground_m": round(z_ground, 2),
            "z_eye_m": round(z_eye, 2),
        },
        "patch_corners_m": patch_corners,
        "patch_center_m": patch_center,
        "patch_dimensions_m": [400.0, 400.0],
        "rays": rays,
        "elevations_surf": elevations_surf,
    }

    # If there's elevations_err_clone1, resize it too
    if "elevations_err_clone1" in existing_data and existing_data["elevations_err_clone1"]:
        old_err = np.array(existing_data["elevations_err_clone1"], dtype=np.float32)
        im_err = Image.fromarray(old_err).resize(
            (grid_points, grid_points), Image.Resampling.BILINEAR
        )
        output_data["elevations_err_clone1"] = [
            [round(float(v), 2) for v in row] for row in np.array(im_err)
        ]

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f)
    print(f"[{site_id}] Wrote {json_path} ({os.path.getsize(json_path) / 1024:.1f} KB)")

    # 2. Generate 1024x1024 photorealistic Lunar Regolith Texture (Hillshade + Regolith noise)
    tex_size = 1024
    elev_tex = np.array(
        im_elev.resize((tex_size, tex_size), Image.Resampling.BICUBIC), dtype=np.float32
    )

    # Compute gradients (dz/dx, dz/dy)
    pixel_scale_m = width_m / float(tex_size)
    dy, dx = np.gradient(elev_tex, pixel_scale_m)

    # Normal vector components
    # Three.js / GL convention: X right, Y up, Z towards viewer
    # For hillshade:
    # Sun azimuth 210 deg (South-Southwest), Sun elevation 18 deg (dramatic lunar grazing light)
    az_rad = np.radians(210.0)
    alt_rad = np.radians(18.0)

    # Hillshade formula: cos(zenith)*cos(slope) + sin(zenith)*sin(slope)*cos(azimuth - aspect)
    slope = np.arctan(np.sqrt(dx**2 + dy**2))
    aspect = np.arctan2(-dx, dy)
    zenith = np.pi / 2.0 - alt_rad

    shaded = np.cos(zenith) * np.cos(slope) + np.sin(zenith) * np.sin(slope) * np.cos(
        az_rad - aspect
    )
    shaded = np.clip(shaded, 0.0, 1.0)

    # Add ambient diffuse tone + secondary fill light
    ambient = 0.22
    light_map = ambient + (1.0 - ambient) * shaded

    # Regolith lunar albedo baseline (grey: ~140 to 180)
    base_albedo = 160.0
    regolith_img = (light_map * base_albedo).clip(15, 245).astype(np.uint8)

    # Convert to RGB with slight lunar neutral color
    regolith_rgb = np.stack(
        [
            regolith_img,
            regolith_img,
            (regolith_img.astype(np.float32) * 1.02).clip(0, 255).astype(np.uint8),
        ],
        axis=-1,
    )

    tex_path = f"app/static/moon/textures/terrain_{site_id.lower()}_texture.jpg"
    Image.fromarray(regolith_rgb).save(tex_path, quality=92)
    print(f"[{site_id}] Wrote texture: {tex_path}")

    # 3. Generate 1024x1024 Normal Map (RGB encoding of tangent-space normals)
    # nx = -dx, ny = -dy, nz = 1.0 (with vertical exaggeration factor for depth)
    vert_scale = 1.8
    nx = -dx * vert_scale
    ny = dy * vert_scale  # invert Y for image coordinate
    nz = np.ones_like(nx)
    norm_len = np.sqrt(nx**2 + ny**2 + nz**2)
    nx /= norm_len
    ny /= norm_len
    nz /= norm_len

    # Map from [-1, 1] to [0, 255]
    r_channel = ((nx + 1.0) * 0.5 * 255.0).clip(0, 255).astype(np.uint8)
    g_channel = ((ny + 1.0) * 0.5 * 255.0).clip(0, 255).astype(np.uint8)
    b_channel = ((nz + 1.0) * 0.5 * 255.0).clip(0, 255).astype(np.uint8)
    normal_rgb = np.stack([r_channel, g_channel, b_channel], axis=-1)

    norm_path = f"app/static/moon/textures/terrain_{site_id.lower()}_normal.jpg"
    Image.fromarray(normal_rgb).save(norm_path, quality=92)
    print(f"[{site_id}] Wrote normal map: {norm_path}")


if __name__ == "__main__":
    # Site01: Connecting Ridge (center: x=-11000, y=-12000)
    build_terrain_for_site(
        site_id="Site01",
        tiff_path="data/cache/lola/Site01_final_adj_5mpp_surf.tif",
        center_x=-11000.0,
        center_y=-12000.0,
        width_m=8000.0,
        height_m=8000.0,
        grid_points=200,
    )

    # Site04: Shackleton Rim (center: x=-1000, y=-7000)
    build_terrain_for_site(
        site_id="Site04",
        tiff_path="data/cache/lola/Site04_final_adj_5mpp_surf.tif",
        center_x=-1000.0,
        center_y=-7000.0,
        width_m=8000.0,
        height_m=8000.0,
        grid_points=200,
    )
    print("Done building real lunar terrain datasets!")
