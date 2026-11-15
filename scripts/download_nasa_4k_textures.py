"""Download and stitch TRUE 4K (4096x2048) tiles from NASA Moon Trek WMTS.

Fetches:
1. LRO WAC Global Mosaic (303 ppd v02) -> moon_trek_wac_4k.jpg
2. LOLA Color Hillshade (128 ppd v04) -> moon_quickmap_topo_4k.jpg
"""

from __future__ import annotations

import concurrent.futures
import io
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from PIL import Image

LEVEL = 3
COLS = 16
ROWS = 8
TILE_SIZE = 256
WIDTH = COLS * TILE_SIZE   # 4096
HEIGHT = ROWS * TILE_SIZE  # 2048

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_TEXTURES = REPO_ROOT / "app" / "static" / "moon" / "textures"
FRONTEND_TEXTURES = REPO_ROOT / "frontend" / "public" / "textures"
LUNAEK2_TEXTURES = Path("C:/Users/yukse/Desktop/LunaEk2/public/textures")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LunaSight/1.0"}


def fetch_tile(url: str, retries: int = 4) -> bytes | None:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return resp.read()
        except Exception as e:
            if attempt == retries - 1:
                print(f"Failed {url}: {e}", file=sys.stderr)
            time.sleep(0.5 * (2 ** attempt))
    return None


def download_layer(name: str, template: str, out_filename: str) -> Path:
    print(f"\n[1/2] Downloading {name} (4096x2048, 128 tiles)...")
    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        for r in range(ROWS):
            for c in range(COLS):
                tile_url = template.format(level=LEVEL, row=r, col=c)
                tasks.append((r, c, pool.submit(fetch_tile, tile_url)))

        stitched = Image.new("RGB", (WIDTH, HEIGHT))
        completed = 0
        for r, c, fut in tasks:
            data = fut.result()
            if data:
                tile_img = Image.open(io.BytesIO(data)).convert("RGB")
                stitched.paste(tile_img, (c * TILE_SIZE, r * TILE_SIZE))
                completed += 1
            else:
                print(f"Missing tile at row={r}, col={c}", file=sys.stderr)

    print(f"Completed {completed}/128 tiles for {name}.")
    out_path = STATIC_TEXTURES / out_filename
    STATIC_TEXTURES.mkdir(parents=True, exist_ok=True)
    stitched.save(out_path, format="JPEG", quality=95, optimize=True)
    print(f"Saved: {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")

    # Copy to frontend and LunaEk2 if directories exist
    for target_dir in [FRONTEND_TEXTURES, LUNAEK2_TEXTURES]:
        if target_dir.parent.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out_path, target_dir / out_filename)
            print(f"Mirrored to: {target_dir / out_filename}")

    return out_path


def main():
    t0 = time.time()
    # 1. NASA Moon Trek LRO WAC 4K Mosaic
    wac_tpl = "https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/{level}/{row}/{col}.jpg"
    download_layer("NASA Moon Trek LRO WAC 4K Mosaic", wac_tpl, "moon_trek_wac_4k.jpg")

    # 2. NASA Moon Trek LOLA Topography Color Hillshade 4K
    topo_tpl = "https://trek.nasa.gov/tiles/Moon/EQ/LRO_LOLA_ClrShade_Global_128ppd_v04/1.0.0/default/default028mm/{level}/{row}/{col}.png"
    download_layer("NASA Moon Trek LOLA Topography Color Hillshade 4K", topo_tpl, "moon_quickmap_topo_4k.jpg")

    print(f"\nAll true 4K textures downloaded and stitched in {time.time() - t0:.1f}s!")


if __name__ == "__main__":
    main()
