"""K3: ufuk yarıçapı ve geçiş bandı duyarlılık analizi.

Kullanım::

    python scripts/k3_sensitivity.py
    python scripts/k3_sensitivity.py --margins 0.02,0.05,0.1,0.2
    python scripts/k3_sensitivity.py --profiles outputs/k2/Site04_horizon_4000m.csv

Varsayılan olarak ``outputs/k2/`` altındaki tüm ``*_horizon_*m.csv``
profillerini bulur, her bölge için bir kez seri üretir ve
profil × marj kombinasyonlarını aynı seri üzerinde değerlendirir. Böylece
görünürlük farkı yalnızca ufuk profili ya da marj seçiminden kaynaklanır.

``--series`` verilmezse senaryo (``test_fixture``) serisi kullanılır; bu
durumda çıktı bilimsel değil, **yöntem** karşılaştırmasıdır.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from luna_sight.visibility import (
    HorizonProfileLookup,
    VisibilityConfig,
    evaluate_series,
    load_series_csv,
    sensitivity_rows,
)
from luna_sight.visibility.series import Sample
from luna_sight.visibility.synthetic import synthetic_series

PROFILE_PATTERN = re.compile(
    r"^(?P<site>[A-Za-z0-9_-]+)_horizon_(?P<radius>\d+)m\.csv$"
)
DEFAULT_MARGINS = "0.05,0.10,0.20"


def parse_margins(text: str) -> list[float]:
    """Virgülle ayrılmış marj listesini doğrular."""
    margins: list[float] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        value = float(part)
        if value < 0.0:
            raise ValueError(f"Marj negatif olamaz: {value}")
        if value not in margins:
            margins.append(value)
    if not margins:
        raise ValueError("En az bir marj değeri gerekli.")
    return margins


def discover_profiles() -> list[Path]:
    """``outputs/k2`` altındaki tüm ufuk profillerini bulur."""
    directory = ROOT / "outputs" / "k2"
    return sorted(directory.glob("*_horizon_*m.csv"))


def profile_metadata(path: Path) -> tuple[str, int | None]:
    """Dosya adından bölge kimliğini ve yarıçapı çıkarır."""
    match = PROFILE_PATTERN.match(path.name)
    if match is None:
        return path.name.split("_")[0], None
    return match.group("site"), int(match.group("radius"))


def series_for_site(samples: list[Sample], site_id: str) -> list[Sample]:
    """Seriyi bölgeye göre filtreler.

    Seri satırlarında ``site_id`` yoksa tüm seri kullanılır. Farklı bölgeler
    tek seride karışıksa yalnızca istenen bölgenin satırları alınır; istenen
    bölge seride yoksa sessizce başka bölgenin efemerisi kullanılmaz.
    """
    present = {sample.site_id for sample in samples if sample.site_id}
    if not present:
        return samples
    selected = [sample for sample in samples if sample.site_id == site_id]
    if not selected:
        raise ValueError(
            f"Seride {site_id} yok (bulunan: {', '.join(sorted(present))})."
        )
    return selected


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profiles",
        nargs="*",
        default=None,
        help="Profil CSV'leri (varsayılan: outputs/k2/*_horizon_*m.csv)",
    )
    parser.add_argument("--margins", default=DEFAULT_MARGINS)
    parser.add_argument("--series", default=None, help="Sözleşme sütunlu ephemeris CSV")
    parser.add_argument("--hours", type=float, default=168.0)
    parser.add_argument("--step-minutes", type=float, default=5.0)
    parser.add_argument("--start", default="2026-11-15T00:00:00Z")
    parser.add_argument("--out", default="outputs/k3/sensitivity.csv")
    args = parser.parse_args()

    margins = parse_margins(args.margins)
    profile_paths = (
        [ROOT / item for item in args.profiles]
        if args.profiles
        else discover_profiles()
    )
    if not profile_paths:
        print("HATA: outputs/k2 altında ufuk profili bulunamadı.")
        return 1

    series_cache: dict[str, list[Sample]] = {}
    all_series: list[Sample] | None = None
    if args.series:
        all_series = load_series_csv(ROOT / args.series)
        print(f"Seri: {args.series} ({len(all_series)} örnek)")
    else:
        datetime.fromisoformat(args.start).astimezone(
            UTC
        )
        print(
            "UYARI: --series verilmedi; hızlandırılmış SENARYO serisi kullanılıyor "
            "(test_fixture, bilimsel değil)."
        )

    rows: list[dict[str, object]] = []
    for profile_path in profile_paths:
        site_id, radius_m = profile_metadata(profile_path)
        profile = HorizonProfileLookup.from_csv(profile_path)
        profile_label = profile_path.relative_to(ROOT).as_posix()

        if all_series is not None:
            samples = series_for_site(all_series, site_id)
        else:
            if site_id not in series_cache:
                series_cache[site_id] = synthetic_series(
                    start_utc=datetime.fromisoformat(
                        args.start
                    ).astimezone(UTC),
                    hours=args.hours,
                    step_minutes=args.step_minutes,
                    site_id=site_id,
                )
            samples = series_cache[site_id]

        for margin in margins:
            config = VisibilityConfig(margin_deg=margin)
            results = evaluate_series(samples, profile, config)
            rows.extend(
                sensitivity_rows(
                    results,
                    config,
                    site_id=site_id,
                    profile=profile_label,
                    radius_m=radius_m,
                )
            )

    out_path = ROOT / args.out
    write_csv(out_path, rows)

    print(f"\n{'bölge':<8} {'yarıçap':>8} {'marj':>6} "
          f"{'ortak görünür %':>16} {'en uzun (sa)':>13} {'belirsiz %':>11}")
    for row in rows:
        if row["body"] != "joint":
            continue
        visible = row["visible_fraction"]
        uncertain = row["uncertain_fraction"]
        longest = row["longest_visible_hours"]
        print(
            f"{row['site_id']:<8} {row['radius_m']!s:>8} "
            f"{row['margin_deg']:>6} "
            f"{('-' if visible is None else f'{visible * 100:.1f}'):>16} "
            f"{('-' if longest is None else f'{longest:.2f}'):>13} "
            f"{('-' if uncertain is None else f'{uncertain * 100:.1f}'):>11}"
        )

    baseline = 0.10 if 0.10 in margins else margins[len(margins) // 2]
    print(f"\nReferans marj: {baseline}°")
    for row in rows:
        if row["body"] != "joint" or row["margin_deg"] != baseline:
            continue
        if row["radius_m"] is None:
            continue
        reference = next(
            (
                other
                for other in rows
                if other["body"] == "joint"
                and other["site_id"] == row["site_id"]
                and other["margin_deg"] == baseline
                and other["radius_m"] is not None
                and other["radius_m"] > row["radius_m"]
            ),
            None,
        )
        if reference is None or row["visible_fraction"] is None:
            continue
        delta = reference["visible_fraction"] - row["visible_fraction"]
        print(
            f"{row['site_id']}: {row['radius_m']} m -> {reference['radius_m']} m "
            f"ortak görünürlük farkı {delta * 100:+.1f} yüzde puan"
        )

    print(f"\nÇıktı: {out_path.relative_to(ROOT)} ({len(rows)} satır)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
