#!/usr/bin/env python3
"""K1 bağımsız doğrulama: iki ayrı yoldan hesaplanan azimut ve yüksekliği karşılaştır.

Issue #1 kabul ölçütü: "beş zaman damgası bağımsız sorguyla karşılaştırıldı".

**Yol A** — üretim hattı. `OBSERVER` efemeris türü, `QUANTITIES=4`; Horizons
azimut ve yüksekliği doğrudan verir, `luna_sight.ephemeris` ayrıştırır.

**Yol B** — bağımsız kontrol. Horizons'ın alt-güneş (`SunSub-LON/LAT`) ve
alt-dünya (`ObsSub-LON/LAT`) noktası artı gövde uzaklığı alınır; azimut ve
yükseklik `luna_sight.ephemeris.verify` içinde vektör hesabıyla yerel ufuk
çerçevesinde yeniden üretilir.

İki yol farklı Horizons niceliklerine dayanır. Buluşmaları, `OBSERVER`
tablosunun bizim tarafımızda doğru yorumlandığını gösterir. Yorumun yanlış
olduğu durumlar burada derece mertebesinde ayrışma üretir: boylamın ters
yönde alınması, azimutun güneyden ölçülmesi, enlem işareti hatası, Dünya
için paralaksın ihmali.

Kullanım:

    .venv\\Scripts\\python.exe scripts/k1_independent_check.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from luna_sight.ephemeris.horizons import (  # noqa: E402
    API_URL,
    Site,
    build_session,
)
from luna_sight.ephemeris.series import build_site_timeseries  # noqa: E402
from luna_sight.ephemeris.verify import (  # noqa: E402
    AU_KM,
    angular_difference,
    subpoint_azalt,
)

#: Aday noktalar K2'den (docs/K2_HORIZON.md bölüm 2).
SITES = [
    Site(site_id="Site01", latitude_deg=-89.463163, longitude_deg_east=-137.489553),
    Site(site_id="Site04", latitude_deg=-89.766811, longitude_deg_east=-171.869898),
]

START = "2026-11-14 00:00"
STOP = "2026-11-21 00:00"
#: 42 saat adım, iki uç dahil tam beş damga: 168 saatlik analiz penceresini tarar.
STEP = "42 h"


def _request(session: requests.Session, params: dict[str, str]) -> str:
    response = session.get(API_URL, params=params, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"Horizons HTTP {response.status_code}")
    return response.json()["result"]


def _subpoint_table(session: requests.Session) -> list[dict[str, float]]:
    """Ay'ın alt-güneş ve alt-dünya noktası ile Dünya uzaklığı.

    Gözlemci Dünya merkezi; alt-nokta değerleri gözlemciden bağımsızdır.
    """
    raw = _request(
        session,
        {
            "format": "json",
            "COMMAND": "'301'",
            "EPHEM_TYPE": "OBSERVER",
            "CENTER": "'500@399'",
            "START_TIME": f"'{START}'",
            "STOP_TIME": f"'{STOP}'",
            "STEP_SIZE": f"'{STEP}'",
            "QUANTITIES": "'14,15,20'",
            "ANG_FORMAT": "DEG",
            "CSV_FORMAT": "YES",
            "OBJ_DATA": "'NO'",
        },
    )
    rows = []
    block = raw.split("$$SOE", 1)[1].split("$$EOE", 1)[0].strip()
    for line in block.splitlines():
        fields = [value.strip() for value in line.split(",")]
        rows.append(
            {
                "earth_sub_lon": float(fields[3]),
                "earth_sub_lat": float(fields[4]),
                "sun_sub_lon": float(fields[5]),
                "sun_sub_lat": float(fields[6]),
                "earth_distance_km": float(fields[7]) * AU_KM,
            }
        )
    return rows


def _sun_distance_km(session: requests.Session) -> list[float]:
    """Ay merkezi ile Güneş arasındaki uzaklık."""
    raw = _request(
        session,
        {
            "format": "json",
            "COMMAND": "'10'",
            "EPHEM_TYPE": "OBSERVER",
            "CENTER": "'@301'",
            "START_TIME": f"'{START}'",
            "STOP_TIME": f"'{STOP}'",
            "STEP_SIZE": f"'{STEP}'",
            "QUANTITIES": "'20'",
            "ANG_FORMAT": "DEG",
            "CSV_FORMAT": "YES",
            "OBJ_DATA": "'NO'",
        },
    )
    block = raw.split("$$SOE", 1)[1].split("$$EOE", 1)[0].strip()
    return [float(line.split(",")[3].strip()) * AU_KM for line in block.splitlines()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="sonuçları JSON olarak yaz")
    args = parser.parse_args(argv)

    session = build_session()
    subpoints = _subpoint_table(session)
    sun_distances = _sun_distance_km(session)
    assert len(subpoints) == len(sun_distances) == 5, (len(subpoints), len(sun_distances))

    records = []
    print("Yol A: OBSERVER tablosu (QUANTITIES=4)   Yol B: alt-nokta + vektor hesabi")
    print(f"Pencere: {START}Z -> {STOP}Z, adim {STEP}, 5 damga\n")
    for site in SITES:
        frame, responses = build_site_timeseries(site, START, STOP, step=STEP, session=session)
        print(f"=== {site.site_id}  lat={site.latitude_deg}  lon_e={site.longitude_deg_east}")
        print(f"    model={frame['model_id'].iloc[0]}  surum={frame['source_version'].iloc[0]}")
        print(
            f"{'damga (UTC)':<20} {'govde':<6} {'A azimut':>10} {'B azimut':>10} "
            f"{'d_az':>8} {'A yuks':>9} {'B yuks':>9} {'d_alt':>8}"
        )
        for index, row in frame.iterrows():
            sub = subpoints[index]
            for body in ("sun", "earth"):
                if body == "sun":
                    az_b, alt_b = subpoint_azalt(
                        site.latitude_deg,
                        site.longitude_deg_east,
                        sub["sun_sub_lon"],
                        sub["sun_sub_lat"],
                        sun_distances[index],
                    )
                else:
                    az_b, alt_b = subpoint_azalt(
                        site.latitude_deg,
                        site.longitude_deg_east,
                        sub["earth_sub_lon"],
                        sub["earth_sub_lat"],
                        sub["earth_distance_km"],
                    )
                az_a = float(row[f"{body}_az_deg"])
                alt_a = float(row[f"{body}_alt_deg"])
                d_az = angular_difference(az_a, az_b)
                d_alt = abs(alt_a - alt_b)
                stamp = row["timestamp_utc"].strftime("%Y-%m-%dT%H:%MZ")
                print(
                    f"{stamp:<20} {body:<6} {az_a:10.4f} {az_b:10.4f} {d_az:8.4f} "
                    f"{alt_a:9.4f} {alt_b:9.4f} {d_alt:8.4f}"
                )
                records.append(
                    {
                        "site_id": site.site_id,
                        "timestamp_utc": stamp,
                        "body": body,
                        "observer_az_deg": az_a,
                        "subpoint_az_deg": az_b,
                        "delta_az_deg": d_az,
                        "observer_alt_deg": alt_a,
                        "subpoint_alt_deg": alt_b,
                        "delta_alt_deg": d_alt,
                        "source_version": frame["source_version"].iloc[0],
                        "model_id": frame["model_id"].iloc[0],
                    }
                )
        print(f"    ham yanit ozetleri: {[r.sha256[:8] for r in responses.values()]}\n")

    worst_az = max(records, key=lambda r: r["delta_az_deg"])
    worst_alt = max(records, key=lambda r: r["delta_alt_deg"])
    print("=== ozet (20 karsilastirma: 2 bolge x 5 damga x 2 govde) ===")
    print(
        f"en buyuk azimut farki   : {worst_az['delta_az_deg']:.4f} derece "
        f"({worst_az['site_id']} {worst_az['body']} {worst_az['timestamp_utc']})"
    )
    print(
        f"en buyuk yukseklik farki: {worst_alt['delta_alt_deg']:.4f} derece "
        f"({worst_alt['site_id']} {worst_alt['body']} {worst_alt['timestamp_utc']})"
    )

    if args.json:
        args.json.write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(f"JSON yazildi: {args.json}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
