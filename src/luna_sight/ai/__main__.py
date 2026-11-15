"""python -m luna_sight.ai: ön kontrol, DEM hazırlama ve açıkça istenen çıkarım."""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path

from luna_sight.ai.client import NimClient, NimError, load_config
from luna_sight.ai.hillshade import prepare_dem_hillshade
from luna_sight.ai.imaging import REPO_ROOT, ImagePreparationError
from luna_sight.ai.orchestrator import analyze_region, load_region_context
from luna_sight.ai.store import save
from luna_sight.terrain.sites import CANDIDATE_SITES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", choices=CANDIDATE_SITES, default="Site01")
    parser.add_argument("--dem-dir", type=Path)
    parser.add_argument(
        "--probe", action="store_true", help="Model listesini kontrol et; çıkarım yapmaz"
    )
    parser.add_argument("--infer", action="store_true", help="Gerçek model çağrısı yap")
    args = parser.parse_args(argv)
    try:
        config = load_config()
        client = NimClient(config)
        if args.probe:
            ready, message = client.probe()
            print(config.describe())
            print(message)
            return 0 if ready else 2
        site = CANDIDATE_SITES[args.site]
        dem_dir = args.dem_dir or Path(
            os.environ.get("LUNA_SIGHT_DEM_DIR", str(REPO_ROOT / "data/cache/lola"))
        )
        path = dem_dir / f"{site.site_id}_final_adj_5mpp_surf.tif"
        image = prepare_dem_hillshade(path, site.latitude_deg, site.longitude_deg_east)
        output_dir = REPO_ROOT / "data/cache/ai_images"
        output_dir.mkdir(parents=True, exist_ok=True)
        preview = output_dir / f"{site.site_id}_hillshade.png"
        preview.write_bytes(base64.b64decode(image.data_url.split(",", 1)[1]))
        preview.with_suffix(".json").write_text(
            json.dumps(
                {
                    "source": str(path.resolve()),
                    "width": image.width,
                    "height": image.height,
                    "is_rendered": image.is_rendered,
                    "provenance": image.provenance_note,
                    "inference_executed": False,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Görüntü hazır: {preview} ({image.width}x{image.height})")
        print(image.provenance_note)
        if not args.infer:
            print("Model çağrılmadı. Gerçek çıkarım için --infer kullanın.")
            return 0
        ready, message = client.probe()
        if not ready:
            print(message)
            return 2
        analysis = analyze_region(load_region_context(args.site), image, client)
        print(f"Analiz: {save(analysis)} · durum={analysis.metadata.status}")
        return 0 if analysis.metadata.status == "completed" else 2
    except (NimError, ImagePreparationError) as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
