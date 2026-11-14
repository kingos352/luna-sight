"""Gerçek Güneş ve Dünya zaman serisini üret, önbelleğe yaz, manifeste kaydet.

Kullanım:

    .venv\\Scripts\\python.exe -m luna_sight.ephemeris --start "2026-11-14 00:00"

Varsayılanlar veri sözleşmesinden gelir: 5 dakika tarama, 168 saat analiz.
Çıktı `data/cache/` altına yazılır ve Git tarafından izlenmez; her ham yanıt
için `data/manifest.csv` satırı eklenir.

`SITES` listesi geçicidir. Aday bölgelerin bilimsel sahibi K2'dir; kesin
liste `docs/DATA_CONTRACT.md` üzerinden geldiğinde burası ona bağlanır.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from luna_sight.ephemeris.horizons import Site, build_session
from luna_sight.ephemeris.series import append_manifest_row, build_site_timeseries, write_cache

#: Geçici örnek noktalar. Boylam doğu-pozitif. K2 kesinleştirecek.
SITES = [
    Site(site_id="shackleton_rim_a", latitude_deg=-89.45, longitude_deg_east=0.0),
    Site(site_id="connecting_ridge_a", latitude_deg=-89.45, longitude_deg_east=222.7),
]

DEFAULT_HOURS = 168
DEFAULT_STEP = "5 m"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="luna_sight.ephemeris", description=__doc__)
    parser.add_argument("--start", required=True, help="UTC başlangıç, örn. '2026-11-14 00:00'")
    parser.add_argument("--hours", type=int, default=DEFAULT_HOURS, help="analiz süresi (saat)")
    parser.add_argument("--step", default=DEFAULT_STEP, help="tarama adımı, örn. '5 m'")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="depo kökü")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    start = dt.datetime.strptime(args.start, "%Y-%m-%d %H:%M").replace(tzinfo=dt.UTC)
    stop = start + dt.timedelta(hours=args.hours)
    stop_text = stop.strftime("%Y-%m-%d %H:%M")

    cache_dir = args.repo_root / "data" / "cache"
    manifest = args.repo_root / "data" / "manifest.csv"
    session = build_session()

    for site in SITES:
        frame, responses = build_site_timeseries(
            site, args.start, stop_text, step=args.step, session=session
        )
        for response in responses.values():
            cached = write_cache(response, cache_dir)
            append_manifest_row(
                manifest,
                response,
                cached.relative_to(args.repo_root),
                status="valid",
            )

        output = cache_dir / f"ephemeris_{site.site_id}_{start:%Y%m%dT%H%M}_{args.hours}h.csv"
        frame.to_csv(output, index=False)
        counts = frame["quality_flag"].value_counts().to_dict()
        print(
            f"{site.site_id}: {len(frame)} satır, kalite={counts}, "
            f"model={frame['model_id'].iloc[0]}, çıktı={output.relative_to(args.repo_root)}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
