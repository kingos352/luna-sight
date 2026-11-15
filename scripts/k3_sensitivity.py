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
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from luna_sight.visibility import (  # noqa: E402
    HorizonProfileLookup,
    VisibilityConfig,
    evaluate_series,
    load_series_csv,
    sensitivity_rows,
)
from luna_sight.visibility.series import (  # noqa: E402
    REQUIRED_COLUMNS,
    Sample,
    sample_from_row,
    validate_series,
)
from luna_sight.visibility.synthetic import synthetic_series  # noqa: E402

PROFILE_PATTERN = re.compile(r"^(?P<site>[A-Za-z0-9_-]+)_horizon_(?P<radius>\d+)m\.csv$")
SERIES_FILE_PATTERN = re.compile(
    r"^ephemeris_(?P<site>[A-Za-z0-9_-]+)_(?P<stamp>\d{8}T\d{4})_(?P<hours>\d+(?:\.\d+)?)h\.csv$"
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


def _resolve_repo_path(raw: str | Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def _display_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()


def discover_profiles(directory: Path | None = None) -> list[Path]:
    """``outputs/k2`` altındaki tüm ufuk profillerini bölge ve yarıçapa göre bulur."""
    base = directory or (ROOT / "outputs" / "k2")
    paths = list(base.glob("*_horizon_*m.csv"))
    return sorted(
        paths,
        key=lambda path: (
            profile_metadata(path)[0],
            profile_metadata(path)[1] if profile_metadata(path)[1] is not None else -1,
            path.name,
        ),
    )


def profile_metadata(path: Path) -> tuple[str, int | None]:
    """Dosya adından bölge kimliğini ve yarıçapı çıkarır."""
    match = PROFILE_PATTERN.match(path.name)
    if match is None:
        return path.name.split("_")[0], None
    return match.group("site"), int(match.group("radius"))


def discover_series_file(series_dir: Path, site_id: str) -> Path:
    """``series_dir`` içinde ``site_id`` için en uzun veya güncel efemerisi seçer."""
    candidates = sorted(series_dir.glob(f"ephemeris_{site_id}_*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"{series_dir} içinde {site_id} için ephemeris_{site_id}_*.csv bulunamadı."
        )

    def _rank(path: Path) -> tuple[float, str, str]:
        match = SERIES_FILE_PATTERN.match(path.name)
        if match is None:
            return (0.0, "", path.name)
        return (float(match.group("hours")), match.group("stamp"), path.name)

    return max(candidates, key=_rank)


def load_series_grouped(path: str | Path) -> tuple[dict[str, list[Sample]], list[Sample] | None]:
    """Tek veya çok bölgeli efemeris CSV'sini ``site_id`` bazında yükler ve doğrular.

    Çok bölgeli birleştirilmiş CSV'lerde zaman damgaları bölge geçişinde
    başa dönebildiği için kronolojik artış denetimi her ``site_id`` dilimi
    üzerinde ayrı uygulanır.
    """
    csv_path = Path(path)
    raw_samples: list[Sample] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{csv_path}: zorunlu sütunlar eksik: {', '.join(missing)}")
        for row in reader:
            raw_samples.append(sample_from_row(row))

    if not raw_samples:
        raise ValueError("Seri boş.")

    present = {sample.site_id for sample in raw_samples if sample.site_id}
    if not present:
        validate_series(raw_samples)
        return {}, raw_samples

    grouped: dict[str, list[Sample]] = defaultdict(list)
    for sample in raw_samples:
        if not sample.site_id:
            raise ValueError(f"{csv_path}: çok bölgeli seride boş site_id satırı var.")
        grouped[sample.site_id].append(sample)

    for site_samples in grouped.values():
        validate_series(site_samples)
    return dict(grouped), None


def series_for_site(samples: list[Sample], site_id: str) -> list[Sample]:
    """Seriyi bölgeye göre filtreler ve seçilen dilimin zaman sırasını doğrular.

    Seri satırlarında ``site_id`` yoksa tüm seri kullanılır. Farklı bölgeler
    tek seride karışıksa yalnızca istenen bölgenin satırları alınır; istenen
    bölge seride yoksa sessizce başka bölgenin efemerisi kullanılmaz.
    """
    present = {sample.site_id for sample in samples if sample.site_id}
    if not present:
        validate_series(samples)
        return samples
    selected = [sample for sample in samples if sample.site_id == site_id]
    if not selected:
        raise ValueError(f"Seride {site_id} yok (bulunan: {', '.join(sorted(present))}).")
    validate_series(selected)
    return selected


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profiles",
        nargs="*",
        default=None,
        help="Profil CSV'leri (varsayılan: outputs/k2/*_horizon_*m.csv)",
    )
    parser.add_argument("--margins", default=DEFAULT_MARGINS)
    parser.add_argument("--series", default=None, help="Sözleşme sütunlu ephemeris CSV")
    parser.add_argument(
        "--series-dir",
        default=None,
        help="Bölge başına ephemeris_<site_id>_*.csv dosyalarının bulunduğu dizin",
    )
    parser.add_argument("--hours", type=float, default=168.0)
    parser.add_argument("--step-minutes", type=float, default=5.0)
    parser.add_argument("--start", default="2026-11-15T00:00:00Z")
    parser.add_argument("--out", default="outputs/k3/sensitivity.csv")
    args = parser.parse_args(argv)

    if args.series and args.series_dir:
        parser.error("--series ve --series-dir aynı anda kullanılamaz.")

    margins = parse_margins(args.margins)
    profile_paths = (
        [_resolve_repo_path(item) for item in args.profiles]
        if args.profiles
        else discover_profiles()
    )
    if not profile_paths:
        print("HATA: outputs/k2 altında ufuk profili bulunamadı.")
        return 1

    series_cache: dict[str, list[Sample]] = {}
    fallback_series: list[Sample] | None = None
    series_dir: Path | None = None

    if args.series_dir:
        series_dir = _resolve_repo_path(args.series_dir)
        if not series_dir.is_dir():
            raise FileNotFoundError(f"Efemeris dizini bulunamadı: {series_dir}")
        print(f"Seri dizini: {_display_path(series_dir)}")
    elif args.series:
        series_path = _resolve_repo_path(args.series)
        grouped, fallback_series = load_series_grouped(series_path)
        series_cache.update(grouped)
        total_count = (
            len(fallback_series)
            if fallback_series is not None
            else sum(len(items) for items in series_cache.values())
        )
        print(f"Seri: {args.series} ({total_count} örnek, {len(series_cache) or 1} bölge)")
    else:
        print(
            "UYARI: --series / --series-dir verilmedi; hızlandırılmış SENARYO serisi "
            "kullanılıyor (test_fixture, bilimsel değil)."
        )

    rows: list[dict[str, object]] = []
    for profile_path in profile_paths:
        site_id, radius_m = profile_metadata(profile_path)
        profile = HorizonProfileLookup.from_csv(profile_path)
        profile_label = _display_path(profile_path)

        if series_dir is not None:
            if site_id not in series_cache:
                ephem_path = discover_series_file(series_dir, site_id)
                loaded = load_series_csv(ephem_path)
                series_cache[site_id] = series_for_site(loaded, site_id)
            samples = series_cache[site_id]
        elif args.series:
            if fallback_series is not None:
                samples = fallback_series
            elif site_id in series_cache:
                samples = series_cache[site_id]
            else:
                raise ValueError(
                    f"Seride {site_id} yok (bulunan: {', '.join(sorted(series_cache))})."
                )
        else:
            if site_id not in series_cache:
                series_cache[site_id] = synthetic_series(
                    start_utc=datetime.fromisoformat(args.start.replace("Z", "+00:00")).astimezone(
                        UTC
                    ),
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

    out_path = _resolve_repo_path(args.out)
    write_csv(out_path, rows)

    print(
        f"\n{'bölge':<8} {'yarıçap':>8} {'marj':>6} "
        f"{'ortak görünür %':>16} {'en uzun (sa)':>13} {'belirsiz %':>11}"
    )
    for row in rows:
        if row["body"] != "joint":
            continue
        visible = row["visible_fraction"]
        uncertain = row["uncertain_fraction"]
        longest = row["longest_visible_hours"]
        print(
            f"{row['site_id']:<8} {str(row['radius_m']):>8} "
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

    print(f"\nÇıktı: {_display_path(out_path)} ({len(rows)} satır)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
