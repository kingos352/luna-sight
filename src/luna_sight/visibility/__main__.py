"""K3 motoru için komut satırı arayüzü.

Kullanım::

    # Stub sağlayıcılarla demo
    python -m luna_sight.visibility --hours 24

    # K2 ufuk profiliyle (efemeris şimdilik mock)
    python -m luna_sight.visibility --horizon-csv outputs/k2/Site04_horizon_2000m.csv \
        --site-id Site04 --latitude -89.766811 --longitude -171.869898 --csv outputs/k3/site04.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

from luna_sight.visibility.engine import EngineConfig, Site, VisibilityEngine, run_demo
from luna_sight.visibility.providers import MockEphemeris, load_horizon_profile
from luna_sight.visibility.timeline import summarize


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m luna_sight.visibility",
        description="Görünürlük motoru (K2 ufuk profili veya stub sağlayıcılar)",
    )
    parser.add_argument("--start-utc", default="2026-11-14T00:00:00Z")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--step-minutes", type=float, default=5.0)
    parser.add_argument("--uncertainty-deg", type=float, default=0.5)
    parser.add_argument("--horizon-deg", type=float, default=3.0, help="Stub sabit ufuk")
    parser.add_argument(
        "--horizon-csv",
        type=Path,
        default=None,
        help="K2 ufuk profili CSV (azimuth_deg, horizon_deg)",
    )
    parser.add_argument("--site-id", default=None)
    parser.add_argument("--latitude", type=float, default=None)
    parser.add_argument("--longitude", type=float, default=None)
    parser.add_argument("--csv", type=Path, default=None, help="Tabloyu CSV olarak yaz")
    args = parser.parse_args(argv)

    if args.horizon_csv is None:
        table = run_demo(
            start_utc=args.start_utc,
            hours=args.hours,
            step_minutes=args.step_minutes,
            uncertainty_deg=args.uncertainty_deg,
            horizon_deg=args.horizon_deg,
        )
    else:
        missing = [
            name
            for name, value in (
                ("--site-id", args.site_id),
                ("--latitude", args.latitude),
                ("--longitude", args.longitude),
            )
            if value is None
        ]
        if missing:
            parser.error("--horizon-csv ile birlikte " + ", ".join(missing) + " zorunlu")

        config = EngineConfig(
            hours=args.hours,
            step_minutes=args.step_minutes,
            uncertainty_deg=args.uncertainty_deg,
            source_id=f"k2:{args.site_id}",
            source_version="profile-csv",
        )
        engine = VisibilityEngine(
            MockEphemeris(), load_horizon_profile(args.horizon_csv), config
        )
        table = engine.run(
            Site(args.site_id, args.latitude, args.longitude), args.start_utc
        )
        print("Not: efemeris sağlayıcısı K1 gelene kadar mock; sonuçlar bilimsel değil.")

    if args.csv is not None:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(args.csv, index=False, encoding="utf-8")
        print(f"{len(table)} satır yazıldı: {args.csv}")

    print(summarize(table).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
