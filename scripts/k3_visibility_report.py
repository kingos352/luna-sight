"""K3: ufuk profili + ephemeris serisinden görünürlük ve pencere raporu.

Kullanım::

    python scripts/k3_visibility_report.py --profile outputs/k2/Site04_horizon_4000m.csv
    python scripts/k3_visibility_report.py --profile ... --series k1_series.csv

``--series`` verilmezse hızlandırılmış bir **senaryo** serisi üretilir ve
tüm satırlar ``test_fixture`` olarak işaretlenir. Gerçek bilimsel sonuç için
K1'in JPL Horizons serisi kullanılmalıdır.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from luna_sight.visibility import (  # noqa: E402
    BODY_EARTH,
    BODY_JOINT,
    BODY_SUN,
    HorizonProfileLookup,
    VisibilityConfig,
    build_windows,
    evaluate_series,
    load_series_csv,
    summarize_windows,
)
from luna_sight.visibility.synthetic import synthetic_series  # noqa: E402


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_site_coordinate(site_id: str) -> tuple[float | None, float | None]:
    """K2 özet dosyasından bölge koordinatını okur (varsa).

    Koordinat ufuk profilinin üretildiği DEM karo merkezidir; seri
    kendi koordinatını taşımıyorsa çıktı satırlarına buradan yazılır.
    """
    path = ROOT / "outputs" / "k2" / f"{site_id}_summary.json"
    if not path.exists():
        return None, None
    data = json.loads(path.read_text(encoding="utf-8"))
    coordinate = data.get("coordinate", {})
    return coordinate.get("lon_deg_east"), coordinate.get("lat_deg")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile", default="outputs/k2/Site04_horizon_4000m.csv", help="K2 profil CSV"
    )
    parser.add_argument("--series", default=None, help="Sözleşme sütunlu ephemeris CSV")
    parser.add_argument("--out", default="outputs/k3")
    parser.add_argument("--site-id", default=None)
    parser.add_argument("--hours", type=float, default=168.0)
    parser.add_argument("--step-minutes", type=float, default=5.0)
    parser.add_argument("--start", default="2026-11-15T00:00:00Z")
    parser.add_argument("--margin", type=float, default=0.10)
    args = parser.parse_args()

    profile_path = ROOT / args.profile
    out_dir = ROOT / args.out
    site_id = args.site_id or profile_path.name.split("_")[0]

    profile = HorizonProfileLookup.from_csv(profile_path)
    config = VisibilityConfig(margin_deg=args.margin)

    if args.series:
        samples = load_series_csv(ROOT / args.series)
        synthetic = False
        print(f"Seri: {args.series} ({len(samples)} örnek)")
    else:
        start = datetime.fromisoformat(args.start.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
        samples = synthetic_series(
            start_utc=start,
            hours=args.hours,
            step_minutes=args.step_minutes,
            site_id=site_id,
        )
        synthetic = True
        print(
            "UYARI: --series verilmedi; hızlandırılmış SENARYO serisi kullanılıyor "
            "(test_fixture, bilimsel değil)."
        )

    lon_deg_east, lat_deg = load_site_coordinate(site_id)
    if lon_deg_east is not None or lat_deg is not None:
        samples = [
            replace(
                sample,
                site_id=sample.site_id or site_id,
                latitude_deg=(
                    sample.latitude_deg if sample.latitude_deg is not None else lat_deg
                ),
                longitude_deg_east=(
                    sample.longitude_deg_east
                    if sample.longitude_deg_east is not None
                    else lon_deg_east
                ),
            )
            for sample in samples
        ]

    results = evaluate_series(samples, profile, config)
    rows = [result.as_row() for result in results]
    csv_path = out_dir / f"{site_id}_visibility.csv"
    write_csv(csv_path, rows)

    span_hours = (
        results[-1].sample.timestamp_utc - results[0].sample.timestamp_utc
    ).total_seconds() / 3600.0

    windows_by_body = {
        body: [
            window.as_dict()
            for window in build_windows(results, body, config)
        ]
        for body in (BODY_SUN, BODY_EARTH, BODY_JOINT)
    }
    summary = {
        "site_id": site_id,
        "coordinate": {
            "latitude_deg": lat_deg,
            "longitude_deg_east": lon_deg_east,
        },
        "profile": str(profile_path.relative_to(ROOT)),
        "profile_summary": profile.summary(),
        "config": config.as_dict(),
        "series": {
            "source": args.series or "synthetic-scenario-v1",
            "synthetic_test_fixture": synthetic,
            "samples": len(samples),
            "start_utc": samples[0].timestamp_utc.isoformat(),
            "end_utc": samples[-1].timestamp_utc.isoformat(),
            "span_hours": round(span_hours, 4),
            "quality_flag": samples[0].quality_flag,
        },
        "bodies": {
            body: summarize_windows(
                build_windows(results, body, config), span_hours=span_hours
            )
            for body in (BODY_SUN, BODY_EARTH, BODY_JOINT)
        },
        "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }

    windows_path = out_dir / f"{site_id}_windows.json"
    windows_path.write_text(
        json.dumps(windows_by_body, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    summary_path = out_dir / f"{site_id}_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n{site_id} — {len(samples)} örnek, {span_hours:.1f} saat")
    print(f"{'gövde':<6} {'görünür %':>10} {'pencere':>8} {'en uzun (sa)':>13}")
    for body in (BODY_SUN, BODY_EARTH, BODY_JOINT):
        stats = summary["bodies"][body]
        fraction = stats["visible_fraction"]
        longest = stats["longest_visible_hours"]
        print(
            f"{body:<6} {('-' if fraction is None else f'{fraction * 100:.1f}'):>10} "
            f"{stats['window_count']:>8} {('-' if longest is None else f'{longest:.2f}'):>13}"
        )
    print(f"\nÇıktı: {csv_path.relative_to(ROOT)}, {windows_path.relative_to(ROOT)}, "
          f"{summary_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
