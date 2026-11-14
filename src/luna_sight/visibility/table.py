"""Ortak veri sözleşmesine uygun görünürlük tablosu üretimi (K3)."""

from __future__ import annotations

import json

import pandas as pd

from luna_sight.visibility.classification import (
    DEFAULT_UNCERTAINTY_DEG,
    classify_states,
    combine_states,
)

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

#: Sınıflandırmada kullanılan ölçüm sütunları.
MEASUREMENT_COLUMNS = (
    "sun_az_deg",
    "sun_alt_deg",
    "earth_az_deg",
    "earth_alt_deg",
    "terrain_horizon_sun_deg",
    "terrain_horizon_earth_deg",
)

REQUIRED_INPUT_COLUMNS = (
    "site_id",
    "latitude_deg",
    "longitude_deg_east",
    "timestamp_utc",
) + MEASUREMENT_COLUMNS

QUALITY_VALUES = ("valid", "partial", "missing", "test_fixture")

DEFAULT_MODEL_ID = "visibility-v1"

_PARAMETERS_RULE = "altitude_vs_terrain_horizon"


def _to_utc(values) -> pd.Series:
    parsed = pd.to_datetime(values, errors="raise")
    if parsed.dt.tz is None:
        raise ValueError("timestamp_utc saat dilimi içermeli (UTC, ISO 8601)")
    return parsed.dt.tz_convert("UTC")


def derive_quality_flags(frame: pd.DataFrame) -> pd.Series:
    """Ölçüm sütunlarının doluluğuna göre kalite bayrağı üretir."""
    missing_counts = frame.loc[:, MEASUREMENT_COLUMNS].isna().sum(axis=1)
    quality = pd.Series("valid", index=frame.index, dtype="object")
    quality[missing_counts > 0] = "partial"
    quality[missing_counts == len(MEASUREMENT_COLUMNS)] = "missing"
    return quality


def build_visibility_table(
    frame: pd.DataFrame,
    *,
    uncertainty_deg: float = DEFAULT_UNCERTAINTY_DEG,
    source_id: str = "unknown",
    source_version: str = "unknown",
    model_id: str = DEFAULT_MODEL_ID,
    parameters: dict | None = None,
    quality_flag: str | None = None,
) -> pd.DataFrame:
    """Gözlem satırlarından sözleşmeye uygun görünürlük tablosu üretir.

    Girdi: ``site_id``, konum, UTC zaman damgası, Güneş/Dünya azimut ve
    yükseklikleri ile iki topoğrafik ufuk değeri. Eksik ölçümler ``uncertain``
    durumuna ve ``partial``/``missing`` kalite bayrağına dönüşür.
    """
    missing_columns = [name for name in REQUIRED_INPUT_COLUMNS if name not in frame.columns]
    if missing_columns:
        raise ValueError("eksik sütun(lar): " + ", ".join(missing_columns))
    if frame.empty:
        raise ValueError("girdi çerçevesi boş olamaz")
    if quality_flag is not None and quality_flag not in QUALITY_VALUES:
        raise ValueError(f"geçersiz quality_flag: {quality_flag}")

    data = frame.copy().reset_index(drop=True)
    if data["site_id"].isna().any():
        raise ValueError("site_id boş olamaz")

    data["timestamp_utc"] = _to_utc(data["timestamp_utc"])

    for column, lower, upper in (
        ("latitude_deg", -90.0, 90.0),
        ("longitude_deg_east", -180.0, 180.0),
    ):
        values = pd.to_numeric(data[column], errors="coerce")
        outside = values.notna() & ((values < lower) | (values > upper))
        if outside.any():
            raise ValueError(f"{column} {lower}..{upper} aralığında olmalı")
        data[column] = values

    if data.duplicated(["site_id", "timestamp_utc"]).any():
        raise ValueError("aynı site_id ve timestamp_utc birden fazla kez geçemez")

    for column in MEASUREMENT_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data["sun_visible"] = classify_states(
        data["sun_alt_deg"], data["terrain_horizon_sun_deg"], uncertainty_deg
    )
    data["earth_visible"] = classify_states(
        data["earth_alt_deg"], data["terrain_horizon_earth_deg"], uncertainty_deg
    )
    data["joint_visible"] = combine_states(data["sun_visible"], data["earth_visible"])

    data["quality_flag"] = (
        quality_flag if quality_flag is not None else derive_quality_flags(data)
    )
    data["source_id"] = source_id
    data["source_version"] = source_version
    data["model_id"] = model_id

    parameter_record = {
        "rule": _PARAMETERS_RULE,
        "uncertainty_deg": float(uncertainty_deg),
    }
    if parameters:
        parameter_record.update(parameters)
    data["parameters"] = json.dumps(parameter_record, sort_keys=True, ensure_ascii=False)

    return (
        data.loc[:, CONTRACT_COLUMNS]
        .sort_values(["site_id", "timestamp_utc"])
        .reset_index(drop=True)
    )
