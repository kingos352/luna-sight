"""K3 motoru için komut satırı arayüzü.

Kullanım::

    # Sentetik efemeris + K2 ufuk profili (efemeris henüz K1 gelmedi)
    python -m luna_sight.visibility \
        --profile outputs/k2/Site04_horizon_2000m.csv \
        --site-id Site04 --latitude -89.766811 --longitude -171.869898 \
        --hours 24 --csv outputs/k3/site04_visibility.csv

    # Gerçek K1 efemeris serisi (CSV) ile
    python -m luna_sight.visibility --series k1_site04.csv \
        --profile outputs/k2/Site04_horizon_2000m.csv \
        --csv outputs/k3/site04_visibility.csv \
        --windows-json outputs/k3/site04_windows.json \
        --summary-json outputs/k3/site04_summary.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from luna_sight.visibility.analysis import breakdown
from luna_sight.visibility.engine import BODIES, build_windows, evaluate_series
from luna_sight.visibility.providers import (
    ConstantHorizon,
    SyntheticEphemeris,
    load_horizon_profile,
)
from luna_sight.visibility.runner import RunnerConfig, Site, VisibilityRunner
from luna_sight.visibility.series import Sample, load_series_csv, validate_series
from luna_sight.visibility.summary import summarize
from luna_sight.visibility.table import results_to_frame, write_table_csv


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m luna_sight.visibility",
        description="Görünürlük motoru (K2 ufuk profili + K1 serisi veya sentetik)",
    )
    parser.add_argument("--start-utc", default="2026-11-14T00:00:00Z")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--step-minutes", type=float, default=5.0)
    parser.add_argument(
        "--margin-deg",
        type=float,
        default=0.10,
        help="Geçiş bandı yarı genişliği (derece)",
    )
    parser.add_argument(
        "--no-refine",
        action="store_true",
        help="Geçiş sınırı inceltmesini kapat",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=None,
        help="K2 ufuk profili CSV (azimuth_deg, horizon_deg)",
    )
    parser.add_argument(
        "--series",
        type=Path,
        default=None,
        help="K1 efemeris serisi CSV (timestamp_utc + az/alt sütunları)",
    )
    parser.add_argument("--horizon-deg", type=float, default=0.0, help="Sabit ufuk (profil yoksa)")
    parser.add_argument("--site-id", default=None)
    parser.add_argument("--latitude", type=float, default=None)
    parser.add_argument("--longitude", type=float, default=None)
    parser.add_argument("--csv", type=Path, default=None, help="Tabloyu CSV olarak yaz")
    parser.add_argument(
        "--windows-json", type=Path, default=None, help="Pencereleri JSON olarak yaz"
    )
    parser.add_argument(
        "--summary-json", type=Path, default=None, help="Özeti JSON olarak yaz"
    )
    return parser


def _resolve_horizon(args):
    if args.profile is not None:
        return load_horizon_profile(args.profile)
    return ConstantHorizon(args.horizon_deg)


def _resolve_series_site(args, samples: list[Sample]) -> Site:
    first = samples[0]
    site_id = args.site_id or first.site_id or "series"
    latitude = args.latitude if args.latitude is not None else first.latitude_deg
    longitude = (
        args.longitude if args.longitude is not None else first.longitude_deg_east
    )
    missing = [
        name
        for name, value in (("latitude", latitude), ("longitude", longitude))
        if value is None
    ]
    if missing:
        raise SystemExit(
            "--series için " + ", ".join(missing) + " gerekli (seride yoksa CLI'dan verin)"
        )
    return Site(site_id, float(latitude), float(longitude))


def _with_site(samples: list[Sample], site: Site, config: RunnerConfig) -> list[Sample]:
    default_parameters = json.dumps(
        {
            "rule": "altitude_vs_terrain_horizon",
            "margin_deg": config.margin_deg,
            "refine_boundaries": config.refine_boundaries,
        },
        sort_keys=True,
    )
    return [
        replace(
            sample,
            site_id=site.site_id,
            latitude_deg=site.latitude_deg,
            longitude_deg_east=site.longitude_deg_east,
            parameters=sample.parameters or default_parameters,
        )
        for sample in samples
    ]


def _windows_payload(results, config) -> dict[str, object]:
    visibility = config.visibility_config()
    return {
        body: [window.as_dict() for window in build_windows(results, body, visibility)]
        for body in BODIES
    }


def _summary_payload(site: Site, results, frame, config) -> dict[str, object]:
    summary = summarize(frame)
    table_row = json.loads(summary.to_json(orient="index"))[site.site_id]
    quality = sorted({sample.sample.quality_flag for sample in results})
    return {
        "site": site.as_dict(),
        "config": config.as_dict(),
        "series": {
            "samples": len(results),
            "start_utc": results[0].sample.timestamp_utc.isoformat(),
            "end_utc": results[-1].sample.timestamp_utc.isoformat(),
            "quality_flags": quality,
            "source_ids": sorted(
                {sample.sample.source_id for sample in results if sample.sample.source_id}
            ),
        },
        "table": table_row,
        "bodies": {
            body: breakdown(results, body, config.visibility_config()).as_dict()
            for body in BODIES
        },
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    config = RunnerConfig(
        start_utc=args.start_utc,
        hours=args.hours,
        step_minutes=args.step_minutes,
        margin_deg=args.margin_deg,
        refine_boundaries=not args.no_refine,
    )
    horizon = _resolve_horizon(args)

    if args.series is not None:
        samples = load_series_csv(args.series)
        if len(samples) < 2:
            raise SystemExit("--series en az iki örnek içermeli")
        site = _resolve_series_site(args, samples)
        samples = _with_site(samples, site, config)
        validate_series(samples)
        results = evaluate_series(samples, horizon, config.visibility_config())
        frame = results_to_frame(results)

        step_hours = (
            samples[1].timestamp_utc - samples[0].timestamp_utc
        ).total_seconds() / 3600.0
        span = (
            results[-1].sample.timestamp_utc - results[0].sample.timestamp_utc
        ).total_seconds() / 3600.0
        config = RunnerConfig(
            start_utc=results[0].sample.timestamp_utc.isoformat(),
            hours=step_hours * (len(samples) - 1),
            step_minutes=step_hours * 60.0,
            margin_deg=config.margin_deg,
            refine_boundaries=config.refine_boundaries,
            quality_flag_missing=config.quality_flag_missing,
        )
        print(f"Seri: {len(samples)} örnek, {span:.1f} saat")
    else:
        site = Site(
            args.site_id or "Demo",
            -89.5 if args.latitude is None else args.latitude,
            0.0 if args.longitude is None else args.longitude,
        )
        runner = VisibilityRunner(SyntheticEphemeris(), horizon, config)
        results = runner.evaluate(site)
        frame = results_to_frame(results)
        print(
            "UYARI: efemeris sentetik (test_fixture); bilimsel sonuç değildir. "
            "Gerçek K1 serisi için --series kullanın."
        )

    if args.csv is not None:
        write_table_csv(frame, args.csv)
        print(f"{len(frame)} satır yazıldı: {args.csv}")

    if args.windows_json is not None:
        _write_json(args.windows_json, _windows_payload(results, config))
        print(f"Pencereler yazıldı: {args.windows_json}")

    if args.summary_json is not None:
        _write_json(args.summary_json, _summary_payload(site, results, frame, config))
        print(f"Özet yazıldı: {args.summary_json}")

    print(summarize(frame).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
