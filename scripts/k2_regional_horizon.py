"""K2: 240 m/px bölgesel LOLA DEM üzerinden 20 km ufuk profili üretimi.

Kullanım::

    python scripts/k2_regional_horizon.py

Bu betik:
1. `data/LDEM_60S_240MPP_ADJ.tiff` dosyasını `load_lola_dem` ile yükler.
2. Resmi K2 aday bölgeleri (Site01 Connecting ridge, Site04 Shackleton rim) için
   20,000 metre (20 km) yarıçapında azimut bazlı ufuk profili hesaplar.
3. Çıktıları `outputs/k2/<Site>_horizon_20000m.csv` ve özet JSON olarak kaydeder.
4. 4 km yerel profil ile 20 km bölgesel profil arasındaki ufuk farkını analiz eder.
5. Veriyi `data/manifest.csv` dosyasına işler.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from luna_sight.terrain import (  # noqa: E402
    CANDIDATE_SITES,
    HorizonConfig,
    compute_horizon,
    load_lola_dem,
)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_manifest_if_missing(
    manifest_path: Path,
    row: dict[str, str],
) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = set()
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                existing_ids.add(r.get("dataset_id"))

    if row["dataset_id"] not in existing_ids:
        fieldnames = [
            "dataset_id",
            "provider",
            "product",
            "version",
            "source_url",
            "retrieved_utc",
            "parameters",
            "sha256",
            "local_path",
            "owner",
            "status",
        ]
        write_header = not manifest_path.exists() or manifest_path.stat().st_size == 0
        with manifest_path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        print(f"Manifest satırı eklendi: {row['dataset_id']}")
    else:
        print(f"Manifest satırı zaten mevcut: {row['dataset_id']}")


def main() -> int:
    dem_path = ROOT / "data" / "LDEM_60S_240MPP_ADJ.tiff"
    if not dem_path.exists():
        print(f"HATA: Bölgesel DEM dosyası bulunamadı: {dem_path}")
        return 1

    print("Bölgesel DEM yükleniyor...")
    dem = load_lola_dem(dem_path, site_name="Moon South Pole Regional 240m")
    print(f"DEM yüklendi: Boyut {dem.shape}, Çözünürlük {dem.pixel_size_m} m/px")

    out_dir = ROOT / "outputs" / "k2"
    out_dir.mkdir(parents=True, exist_ok=True)

    config_20km = HorizonConfig(
        azimuth_step_deg=1.0,
        radial_step_m=240.0,
        max_radius_m=20_000.0,
        observer_height_m=2.0,
        gap_tolerance=0.05,
        coverage_tolerance=0.05,
    )

    summaries = {}

    for site_id, site in CANDIDATE_SITES.items():
        print(f"\n[{site_id}] {site.site_name} için 20 km ufuk profili hesaplanıyor...")
        profile = compute_horizon(
            dem,
            site.x_m,
            site.y_m,
            config_20km,
            lon_deg=site.longitude_deg_east,
        )
        profile.site_id = site_id

        # CSV Çıktısı (360 satır)
        csv_path = out_dir / f"{site_id}_horizon_20000m.csv"
        rows = profile.rows()
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "azimuth_deg",
                    "horizon_deg",
                    "occluder_distance_m",
                    "gap_fraction",
                    "native_coverage_fraction",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV kaydedildi: {csv_path.name} ({len(rows)} satır)")

        summary = profile.summary()
        summary["site_id"] = site_id
        summary["site_name"] = site.site_name
        summaries[site_id] = summary

        json_path = out_dir / f"{site_id}_summary_20000m.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"JSON özeti kaydedildi: {json_path.name}")
        print(
            f"  Ufuk: min={summary['horizon_min_deg']}°, "
            f"max={summary['horizon_max_deg']}°, ort={summary['horizon_mean_deg']}°, "
            f"kalite={summary['quality_flag']}"
        )

    # Genel Karşılaştırma JSON'ı
    comparison_path = out_dir / "regional_20000m_comparison.json"
    with comparison_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "analysis_radius_m": 20_000.0,
                "dem_resolution_m": 240.0,
                "product": "LOLA LDEM 240mpp South Polar Regional (Barker et al. 2021)",
                "datum": "MOON_ME (JPL DE421)",
                "sites": summaries,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"\nGenel karşılaştırma kaydedildi: {comparison_path.name}")

    # Manifest kaydı
    print("\nManifeste bölgesel DEM ürünü kaydediliyor...")
    file_sha = sha256_of(dem_path)
    append_manifest_if_missing(
        ROOT / "data" / "manifest.csv",
        {
            "dataset_id": "lola_south_pole_240mpp_adj",
            "provider": "NASA GSFC / LRO LOLA Science Team",
            "product": "LDEM_60S_240MPP_ADJ (Ay Guney Kutbu Bolgesel DEM, 240 m/piksel)",
            "version": "Barker et al. 2021 (PSS 203:105119)",
            "source_url": "https://pgda.gsfc.nasa.gov/data/LOLA_240mpp/LDEM_60S_240MPP_ADJ.tiff",
            "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "parameters": "MOON_ME;DE421;guney_kutup_stereografik;240mpp;60S_kutup",
            "sha256": file_sha,
            "local_path": "data/LDEM_60S_240MPP_ADJ.tiff",
            "owner": "K2",
            "status": "valid",
        },
    )

    print("\nK2 Bölgesel DEM Analizi başarıyla tamamlandı!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
