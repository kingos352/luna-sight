"""Veri sözleşmesine uygun Güneş ve Dünya zaman serisi, köken kaydıyla.

`build_site_timeseries` iki Horizons sorgusunu (Güneş, Dünya) tek tabloda
birleştirir. Üretilen kolonlar `docs/DATA_CONTRACT.md` zorunlu alanlarının
astronomik alt kümesidir. `terrain_horizon_*`, `*_visible` ve `joint_visible`
kolonları bilinçli olarak üretilmez: arazi ufku K2, görünürlük kararı K3
sahipliğindedir ve K1 bu değerleri tahmin etmez.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import requests

from luna_sight.ephemeris.horizons import (
    PRODUCT,
    PROVIDER,
    SOURCE_ID,
    HorizonsResponse,
    Site,
    build_session,
    fetch,
    parse_observer_table,
)

#: Bu modülün ürettiği kolonlar, veri sözleşmesindeki sırayla.
EPHEMERIS_COLUMNS = [
    "site_id",
    "latitude_deg",
    "longitude_deg_east",
    "timestamp_utc",
    "sun_az_deg",
    "sun_alt_deg",
    "earth_az_deg",
    "earth_alt_deg",
    "quality_flag",
    "source_id",
    "source_version",
    "model_id",
    "parameters",
]

_ANGLE_COLUMNS = ["sun_az_deg", "sun_alt_deg", "earth_az_deg", "earth_alt_deg"]

MANIFEST_FIELDS = [
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


def _quality_flag(row: pd.Series) -> str:
    """Satır kalitesini veri sözleşmesi sözlüğüne göre belirle.

    Dört açının tamamı sayısalsa `valid`, bir kısmı eksikse `partial`,
    hiçbiri yoksa `missing`. Eksik veri hiçbir durumda görünür ya da
    engelli sayılmaz.
    """
    present = int(row[_ANGLE_COLUMNS].notna().sum())
    if present == len(_ANGLE_COLUMNS):
        return "valid"
    return "partial" if present else "missing"


def build_site_timeseries(
    site: Site,
    start_utc: str,
    stop_utc: str,
    step: str = "5 m",
    session: requests.Session | None = None,
    quality_flag: str | None = None,
) -> tuple[pd.DataFrame, dict[str, HorizonsResponse]]:
    """Bir bölge için Güneş ve Dünya zaman serisini üret.

    `quality_flag` verilirse tüm satırlara zorlanır; test düzenekleri
    `test_fixture` etiketini bu yolla taşır.

    Dönüş: (tablo, gövde adı -> ham yanıt). Ham yanıtlar köken kaydı ve
    önbellek yazımı için çağırana bırakılır.
    """
    http = session or build_session()
    responses: dict[str, HorizonsResponse] = {}
    frames: dict[str, pd.DataFrame] = {}
    for body in ("sun", "earth"):
        response = fetch(body, site, start_utc, stop_utc, step=step, session=http)
        responses[body] = response
        frames[body] = parse_observer_table(response.raw_text).rename(
            columns={"az_deg": f"{body}_az_deg", "alt_deg": f"{body}_alt_deg"}
        )

    # Dış birleştirme: bir gövdede eksik zaman damgası diğerini düşürmez.
    merged = frames["sun"].merge(frames["earth"], on="timestamp_utc", how="outer")
    merged = merged.sort_values("timestamp_utc", ignore_index=True)

    merged["site_id"] = site.site_id
    merged["latitude_deg"] = site.latitude_deg
    merged["longitude_deg_east"] = site.longitude_deg_east
    merged["quality_flag"] = quality_flag if quality_flag else merged.apply(_quality_flag, axis=1)
    merged["source_id"] = SOURCE_ID
    # İki sorgu aynı API ve aynı efemeris çekirdeğini kullanır; farklıysa
    # köken alanı bunu görünür kılar.
    merged["source_version"] = "|".join(
        sorted({response.source_version for response in responses.values()})
    )
    merged["model_id"] = "|".join(sorted({response.model_id for response in responses.values()}))
    merged["parameters"] = responses["sun"].parameters_json
    return merged[EPHEMERIS_COLUMNS], responses


def write_cache(response: HorizonsResponse, cache_dir: Path) -> Path:
    """Ham yanıtı önbelleğe yaz ve yolunu döndür.

    Dosya adı içerik özetini taşır, böylece aynı sorgu iki kez yazılmaz ve
    manifest satırındaki `sha256` dosyadan doğrulanabilir. `data/cache/`
    Git tarafından izlenmez.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"horizons_{response.body}_{response.sha256[:12]}.txt"
    if not target.exists():
        target.write_text(response.raw_text, encoding="utf-8")
    return target


def append_manifest_row(
    manifest_path: Path,
    response: HorizonsResponse,
    local_path: Path,
    owner: str = "K1",
    status: str = "valid",
) -> None:
    """`data/manifest.csv` dosyasına köken satırı ekle.

    Veri politikası her gerçek veri dosyası için bir satır ister: kaynak
    adresi, sürüm, parametreler ve dosya özeti.
    """
    manifest_path = Path(manifest_path)
    exists = manifest_path.exists()
    with manifest_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(
            {
                "dataset_id": f"{response.site.site_id}_{response.body}_{response.sha256[:8]}",
                "provider": PROVIDER,
                "product": PRODUCT,
                "version": response.source_version,
                "source_url": response.url,
                "retrieved_utc": response.retrieved_utc,
                "parameters": response.parameters_json,
                "sha256": response.sha256,
                "local_path": local_path.as_posix(),
                "owner": owner,
                "status": status,
            }
        )
