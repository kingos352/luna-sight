"""K3 motoru için komut satırı arayüzü.

Kullanım::

    python -m luna_sight.visibility --hours 24 --csv data/processed/demo.csv

Sağlayıcılar henüz K1/K2'den gelmediği için CLI, stub sağlayıcılarla çalışır.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from luna_sight.visibility.engine import run_demo
from luna_sight.visibility.timeline import summarize


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m luna_sight.visibility",
        description="Görünürlük motoru demosu (stub efemeris + sabit ufuk)",
    )
    parser.add_argument("--start-utc", default="2026-11-14T00:00:00Z")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--step-minutes", type=float, default=5.0)
    parser.add_argument("--uncertainty-deg", type=float, default=0.5)
    parser.add_argument("--horizon-deg", type=float, default=3.0)
    parser.add_argument("--csv", type=Path, default=None, help="Tabloyu CSV olarak yaz")
    args = parser.parse_args(argv)

    table = run_demo(
        start_utc=args.start_utc,
        hours=args.hours,
        step_minutes=args.step_minutes,
        uncertainty_deg=args.uncertainty_deg,
        horizon_deg=args.horizon_deg,
    )

    if args.csv is not None:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(args.csv, index=False, encoding="utf-8")
        print(f"{len(table)} satır yazıldı: {args.csv}")

    print(summarize(table).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
