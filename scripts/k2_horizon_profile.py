"""K2: LOLA DEM'den aday iniş bölgeleri için ufuk profili üretir.

Kullanım::

    python scripts/k2_horizon_profile.py --radii 2000,4000

Betik, PGDA'dan (NASA GSFC) 5 m/piksel LOLA DEM'lerini indirir, her aday
nokta için iki analiz yarıçapında ufuk profili ve veri boşluğu raporu
üretir; ``outputs/k2/`` altına CSV/JSON yazar ve ``data/manifest.csv``
için satırları basar. İndirilen GeoTIFF'ler ``data/cache/`` altında kalır
ve depoya eklenmez.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from luna_sight.terrain import (  # noqa: E402
    HorizonConfig,
    compare_radii,
    load_lola_dem,
    scan_coverage,
)
from luna_sight.terrain.horizon import compute_horizon  # noqa: E402

PGDA_BASE = "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp"
PROVIDER = "NASA GSFC PGDA (LOLA Data Node)"
VERSION = "Barker et al. 2021 (PSS 203:105119)"
PARAMETERS = "MOON_ME;DE421;guney_kutup_stereografik;5mpp;piksel-merkezli"

SITES = {
    "Site01": "Connecting ridge",
    "Site04": "Shackleton rim",
}


def remote_files(site: str) -> dict[str, str]:
    return {
        "surf": f"{PGDA_BASE}/{site}/{site}_final_adj_5mpp_surf.tif",
        "ldec": f"{PGDA_BASE}/{site}/{site}_final_adj_5mpp_ldec.tif",
    }


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remote_size(url: str) -> int:
    response = requests.head(url, allow_redirects=True, timeout=60)
    response.raise_for_status()
    return int(response.headers.get("Content-Length", 0))


def download(url: str, target: Path) -> None:
    """Dosyayı indirir; yarım kalan indirmeleri yeniden başlatır."""
    expected = remote_size(url)
    if target.exists():
        size = target.stat().st_size
        if expected == 0 or size == expected:
            print(f"  mevcut: {target.name} ({size / 1e6:.1f} MB)", flush=True)
            return
        print(f"  eksik indirme siliniyor: {target.name}", flush=True)
        target.unlink()

    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + ".part")
    print(f"  indiriliyor: {url}", flush=True)
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        written = 0
        with part.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 20):
                handle.write(chunk)
                written += len(chunk)
    if expected and written != expected:
        part.unlink(missing_ok=True)
        raise RuntimeError(f"Eksik indirme: {written}/{expected} bayt ({url})")
    part.replace(target)
    print(f"  tamam: {target.name} ({written / 1e6:.1f} MB)", flush=True)


def manifest_rows(site: str, paths: dict[str, Path]) -> list[dict[str, str]]:
    stamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    urls = remote_files(site)
    rows = []
    for kind, path in paths.items():
        product = "LDEM" if kind == "surf" else "LDEC"
        rows.append(
            {
                "dataset_id": f"lola_{site.lower()}_5mpp_{kind}",
                "provider": PROVIDER,
                "product": f"{product} ({SITES[site]}, 5 m/piksel, duzeltilmis)",
                "version": VERSION,
                "source_url": urls[kind],
                "retrieved_utc": stamp,
                "parameters": PARAMETERS,
                "sha256": sha256_of(path),
                "local_path": path.relative_to(ROOT).as_posix(),
                "owner": "K2",
                "status": "valid",
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sites", default=",".join(SITES), help="Site01,Site04")
    parser.add_argument("--radii", default="2000,4000", help="metre, virgülle")
    parser.add_argument("--data-dir", default="data/cache/lola")
    parser.add_argument("--out", default="outputs/k2")
    parser.add_argument("--offline", action="store_true", help="indirme yapma")
    parser.add_argument("--azimuth-step", type=float, default=1.0)
    parser.add_argument("--radial-step", type=float, default=10.0)
    parser.add_argument("--observer-height", type=float, default=2.0)
    args = parser.parse_args()

    sites = [s.strip() for s in args.sites.split(",") if s.strip()]
    radii = tuple(float(r) for r in args.radii.split(","))
    data_dir = ROOT / args.data_dir
    out_dir = ROOT / args.out

    all_manifests: list[dict[str, str]] = []
    comparison: dict[str, object] = {}

    for site in sites:
        if site not in SITES:
            raise SystemExit(f"Bilinmeyen site: {site}. Seçenekler: {', '.join(SITES)}")
        print(f"[{site}] {SITES[site]}")
        urls = remote_files(site)
        paths = {
            "surf": data_dir / f"{site}_final_adj_5mpp_surf.tif",
            "ldec": data_dir / f"{site}_final_adj_5mpp_ldec.tif",
        }
        if not args.offline:
            for kind, url in urls.items():
                download(url, paths[kind])

        dem = load_lola_dem(paths["surf"], ldec_path=paths["ldec"], site_name=SITES[site])
        meta = dem.metadata
        assert meta is not None
        x0, y0 = dem.center_xy
        lon, lat = dem.center_lonlat()
        tile_extent_m = min(
            meta.bounds_xy_m[2] - meta.bounds_xy_m[0],
            meta.bounds_xy_m[3] - meta.bounds_xy_m[1],
        )
        max_radius = max(radii)
        if max_radius * 2.0 > tile_extent_m:
            print(
                f"  UYARI: {max_radius:.0f} m yarıçap, "
                f"{tile_extent_m:.0f} m'lik DEM kenarına yakın; kapsam notu eklenecek."
            )

        base = HorizonConfig(
            azimuth_step_deg=args.azimuth_step,
            radial_step_m=args.radial_step,
            observer_height_m=args.observer_height,
        )
        gaps = scan_coverage(dem, x0, y0, radii_m=radii, gap_tolerance=base.gap_tolerance)

        profiles = []
        for radius in radii:
            config = HorizonConfig(
                azimuth_step_deg=base.azimuth_step_deg,
                radial_step_m=base.radial_step_m,
                max_radius_m=radius,
                observer_height_m=base.observer_height_m,
                gap_tolerance=base.gap_tolerance,
            )
            profile = compute_horizon(dem, x0, y0, config)
            profile.site_id = site
            profile.notes.append(f"Aday bölge: {SITES[site]} ({meta.product}).")
            profiles.append(profile)

            csv_path = out_dir / f"{site}_horizon_{int(radius)}m.csv"
            write_csv(csv_path, profile.rows())
            print(
                f"  r={radius:>6.0f} m | ufuk {profile.summary()['horizon_min_deg']:+.2f}"
                f"..{profile.summary()['horizon_max_deg']:+.2f}° | "
                f"kalite={profile.quality_flag} | {csv_path.relative_to(ROOT)}"
            )

        summary = {
            "site_id": site,
            "site_name": SITES[site],
            "coordinate": {"lon_deg_east": round(lon, 6), "lat_deg": round(lat, 6)},
            "dem": meta.as_dict(),
            "tile_extent_m": round(tile_extent_m, 1),
            "gap_scan": gaps.as_dict(),
            "profiles": [p.summary() for p in profiles],
            "radius_comparison": compare_radii(dem, x0, y0, radii, base),
            "generated_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        }
        summary_path = out_dir / f"{site}_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        comparison[site] = summary
        all_manifests.extend(manifest_rows(site, paths))

    combined = out_dir / "k2_comparison.json"
    combined.write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    manifest_csv = out_dir / "manifest_rows.csv"
    write_csv(manifest_csv, all_manifests)
    print(f"\nÖzet: {combined.relative_to(ROOT)}")
    print(f"Manifest satırları: {manifest_csv.relative_to(ROOT)}")

    print("\n--- data/manifest.csv için ---")
    writer = csv.DictWriter(sys.stdout, fieldnames=list(all_manifests[0]))
    writer.writeheader()
    writer.writerows(all_manifests)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
