"""Ephemeris zaman serisi modeli ve doğrulaması.

Girdi, `docs/DATA_CONTRACT.md` içindeki azimut/yükseklik alanlarını taşıyan
bir CSV'dir. Zaman UTC olarak normalize edilir; boş ya da sayısal olmayan
hücreler ``None`` olarak korunur ve motorda ``uncertain`` üretir —
eksik veri sessizce sıfıra çevrilmez.
"""

from __future__ import annotations

import csv
import itertools
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REQUIRED_COLUMNS = (
    "timestamp_utc",
    "sun_az_deg",
    "sun_alt_deg",
    "earth_az_deg",
    "earth_alt_deg",
)

OPTIONAL_COLUMNS = (
    "site_id",
    "latitude_deg",
    "longitude_deg_east",
    "quality_flag",
    "source_id",
    "source_version",
    "model_id",
    "parameters",
)

_EMPTY_TOKENS = {"", "nan", "none", "null", "na", "n/a"}


def parse_utc(value: str | datetime) -> datetime:
    """ISO 8601 / UTC metnini zaman dilimi bilinçli ``datetime``e çevirir."""
    if isinstance(value, datetime):
        moment = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        if "T" not in text and " " in text:
            text = text.replace(" ", "T", 1)
        moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _EMPTY_TOKENS:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return None if math.isnan(number) else number


@dataclass(frozen=True)
class Sample:
    """Tek bir zaman damgasındaki Güneş/Dünya geometrisi."""

    timestamp_utc: datetime
    sun_az_deg: float | None
    sun_alt_deg: float | None
    earth_az_deg: float | None
    earth_alt_deg: float | None
    site_id: str = ""
    latitude_deg: float | None = None
    longitude_deg_east: float | None = None
    quality_flag: str = "valid"
    source_id: str = ""
    source_version: str = ""
    model_id: str = ""
    parameters: str = ""


def sample_from_row(row: dict[str, object]) -> Sample:
    """Sözlük satırından :class:`Sample` üretir."""
    return Sample(
        timestamp_utc=parse_utc(row["timestamp_utc"]),
        sun_az_deg=_optional_float(row.get("sun_az_deg")),
        sun_alt_deg=_optional_float(row.get("sun_alt_deg")),
        earth_az_deg=_optional_float(row.get("earth_az_deg")),
        earth_alt_deg=_optional_float(row.get("earth_alt_deg")),
        site_id=str(row.get("site_id", "") or ""),
        latitude_deg=_optional_float(row.get("latitude_deg")),
        longitude_deg_east=_optional_float(row.get("longitude_deg_east")),
        quality_flag=str(row.get("quality_flag", "valid") or "valid"),
        source_id=str(row.get("source_id", "") or ""),
        source_version=str(row.get("source_version", "") or ""),
        model_id=str(row.get("model_id", "") or ""),
        parameters=str(row.get("parameters", "") or ""),
    )


def load_series_csv(path: str | Path) -> list[Sample]:
    """Sözleşme sütunlarını taşıyan CSV'yi okur ve zaman sırasını doğrular."""
    rows: list[Sample] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: zorunlu sütunlar eksik: {', '.join(missing)}")
        for row in reader:
            rows.append(sample_from_row(row))
    validate_series(rows)
    return rows


def validate_series(samples: list[Sample]) -> None:
    """Boş seri ve azalan/tekrarlı zaman damgaları reddedilir."""
    if not samples:
        raise ValueError("Seri boş.")
    for previous, current in itertools.pairwise(samples):
        if current.timestamp_utc <= previous.timestamp_utc:
            raise ValueError(
                "Zaman damgaları kesin artan olmalı: "
                f"{previous.timestamp_utc.isoformat()} → {current.timestamp_utc.isoformat()}"
            )
