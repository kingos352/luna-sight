"""Ortak veri sözleşmesine uygun görünürlük tablosu (K3).

Motorun ``SampleResult`` kayıtlarını `docs/DATA_CONTRACT.md` sütunlarıyla
pandas tablosuna çevirir. Sözleşme sütunlarına ek olarak teşhis (diagnostics)
sütunları eklenir; bunlar kararın nedenini ve marjını görünür kılar ama
sözleşmeyi değiştirmez.
"""

from __future__ import annotations

import pandas as pd

from luna_sight.visibility.engine import SampleResult
from luna_sight.visibility.states import REASONS, STATES

#: `docs/DATA_CONTRACT.md` sırasıyla zorunlu çıktı alanları.
CONTRACT_COLUMNS = (
    "site_id",
    "latitude_deg",
    "longitude_deg_east",
    "timestamp_utc",
    "sun_az_deg",
    "sun_alt_deg",
    "earth_az_deg",
    "earth_alt_deg",
    "terrain_horizon_sun_deg",
    "terrain_horizon_earth_deg",
    "sun_visible",
    "earth_visible",
    "joint_visible",
    "quality_flag",
    "source_id",
    "source_version",
    "model_id",
    "parameters",
)

#: Kararın nedenini ve marjını gösteren ek alanlar (sözleşme dışı).
DIAGNOSTIC_COLUMNS = (
    "sun_margin_deg",
    "earth_margin_deg",
    "joint_margin_deg",
    "sun_reason",
    "earth_reason",
    "joint_reason",
)

TABLE_COLUMNS = CONTRACT_COLUMNS + DIAGNOSTIC_COLUMNS

NUMERIC_COLUMNS = (
    "latitude_deg",
    "longitude_deg_east",
    "sun_az_deg",
    "sun_alt_deg",
    "earth_az_deg",
    "earth_alt_deg",
    "terrain_horizon_sun_deg",
    "terrain_horizon_earth_deg",
    "sun_margin_deg",
    "earth_margin_deg",
    "joint_margin_deg",
)

STATE_COLUMNS = ("sun_visible", "earth_visible", "joint_visible")

QUALITY_VALUES = ("valid", "partial", "missing", "test_fixture")


def results_to_frame(results: list[SampleResult]) -> pd.DataFrame:
    """``SampleResult`` listesini sözleşme tablosuna çevirir."""
    if not results:
        raise ValueError("Sonuç listesi boş olamaz.")

    frame = pd.DataFrame([result.as_row() for result in results])
    frame["timestamp_utc"] = _to_utc(frame["timestamp_utc"])
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    return validate_table(frame.loc[:, TABLE_COLUMNS])


def _to_utc(values) -> pd.Series:
    parsed = pd.to_datetime(values, errors="raise", utc=True)
    if not isinstance(parsed, pd.Series):
        parsed = pd.Series(parsed)
    return parsed.dt.tz_convert("UTC")


def validate_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Sözleşme sütunlarını, durum değerlerini ve zaman sırasını doğrular."""
    missing = [name for name in CONTRACT_COLUMNS if name not in frame.columns]
    if missing:
        raise ValueError("eksik sütun(lar): " + ", ".join(missing))
    if frame.empty:
        raise ValueError("tablo boş olamaz")

    data = frame.copy().reset_index(drop=True)

    if data["site_id"].isna().any() or (data["site_id"].astype(str).str.strip() == "").any():
        raise ValueError("site_id boş olamaz")

    timestamp = pd.to_datetime(data["timestamp_utc"], errors="raise", utc=True)
    data["timestamp_utc"] = timestamp

    for column in STATE_COLUMNS:
        unknown = set(data[column].dropna().unique()) - set(STATES)
        if unknown:
            raise ValueError(
                f"{column} geçersiz durum içeriyor: {', '.join(sorted(map(str, unknown)))}"
            )

    reason_columns = [name for name in DIAGNOSTIC_COLUMNS if name.endswith("_reason")]
    for column in reason_columns:
        if column not in data.columns:
            continue
        unknown = set(data[column].dropna().unique()) - set(REASONS)
        if unknown:
            raise ValueError(
                f"{column} geçersiz gerekçe içeriyor: {', '.join(sorted(map(str, unknown)))}"
            )

    if data.duplicated(["site_id", "timestamp_utc"]).any():
        raise ValueError("aynı site_id ve timestamp_utc birden fazla kez geçemez")

    return data.sort_values(["site_id", "timestamp_utc"]).reset_index(drop=True)


def write_table_csv(frame: pd.DataFrame, path) -> None:
    """Tabloyu UTF-8 CSV olarak yazar (dizin yoksa oluşturur)."""
    from pathlib import Path

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = validate_table(frame).copy()
    data["timestamp_utc"] = data["timestamp_utc"].map(lambda value: value.isoformat())
    data.to_csv(target, index=False, encoding="utf-8")


__all__ = [
    "CONTRACT_COLUMNS",
    "DIAGNOSTIC_COLUMNS",
    "NUMERIC_COLUMNS",
    "QUALITY_VALUES",
    "STATE_COLUMNS",
    "TABLE_COLUMNS",
    "results_to_frame",
    "validate_table",
    "write_table_csv",
]
