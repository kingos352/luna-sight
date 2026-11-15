"""Artemis Lunar Gateway (NRHO 9:2 Güney Halo) röle efemerisi ve görünürlük analizi.

Dünya ile doğrudan görüş hattı (DTE) yerel krater duvarları veya dağ sırtları
tarafından kesilen bölgelerde (ör. ``Site04`` Shackleton sırtı), Dünya-Ay L2
9:2 rezonanslı Güney Halo yörüngesindeki (NRHO) Lunar Gateway yörünge zamanının
büyük bölümünü Ay Güney Kutbu üzerinde yüksek irtifada (~70.000 km apolun)
geçirerek yüksek yükseliş açılı kesintiye dayanıklı telekomünikasyon rölesi sağlar.

Sözleşme:
    - Tüm boylamlar doğu-pozitif ``[-180, 180]`` aralığındadır.
    - Tüm zaman damgaları UTC olarak işlenir.
    - Yerel ufuk engelleri K2 :class:`~luna_sight.visibility.profile.HorizonProfileLookup`
      üzerinden sorgulanır.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from luna_sight.visibility.engine import SampleResult, classify
from luna_sight.visibility.profile import HorizonProfileLookup
from luna_sight.visibility.series import Sample
from luna_sight.visibility.states import VISIBLE, VisibilityConfig

LUNAR_MEAN_RADIUS_M: float = 1_737_400.0
"""Ay küresel ortalama yarıçapı (metre); ``luna_sight.terrain.polar.R_MOON_M`` ile eşleşir."""

NRHO_PERIOD_HOURS: float = 168.0
"""Artemis 9:2 Güney Halo (NRHO) yaklaşık yörünge periyodu (saat, ~7 gün)."""

NRHO_SEMI_MAJOR_AXIS_KM: float = 36_600.0
"""NRHO yarı-büyük eksen uzunluğu (km)."""

NRHO_ECCENTRICITY: float = 0.912
"""NRHO yörünge basıklığı."""

NRHO_PERILUNE_KM: float = NRHO_SEMI_MAJOR_AXIS_KM * (1.0 - NRHO_ECCENTRICITY)
"""Perilun (Kuzey Kutbu üzeri en yakın geçiş) ay-merkezli yarıçapı (~3.221 km)."""

NRHO_APOLUNE_KM: float = NRHO_SEMI_MAJOR_AXIS_KM * (1.0 + NRHO_ECCENTRICITY)
"""Apolun (Güney Kutbu üzeri en uzak nokta) ay-merkezli yarıçapı (~69.979 km)."""


def _validate_coordinates(site_lat_deg: float, site_lon_deg_east: float) -> None:
    if not math.isfinite(site_lat_deg) or not -90.0 <= site_lat_deg <= 90.0:
        raise ValueError(f"site_lat_deg [-90, 90] aralığında olmalı; {site_lat_deg} verildi.")
    if not math.isfinite(site_lon_deg_east) or not -180.0 <= site_lon_deg_east <= 180.0:
        raise ValueError(
            f"site_lon_deg_east [-180, 180] aralığında olmalı; {site_lon_deg_east} verildi."
        )


def _solve_kepler(mean_anomaly: float, eccentricity: float, tolerance: float = 1e-9) -> float:
    """Kepler denklemini Newton-Raphson ile çözer: ``M = E - e * sin(E)``."""
    ecc_anomaly = mean_anomaly if eccentricity < 0.8 else math.pi
    for _ in range(50):
        residual = ecc_anomaly - eccentricity * math.sin(ecc_anomaly) - mean_anomaly
        derivative = 1.0 - eccentricity * math.cos(ecc_anomaly)
        step = residual / derivative
        ecc_anomaly -= step
        if abs(step) < tolerance:
            break
    return ecc_anomaly


def _to_utc_index(timestamps_utc: Any) -> pd.DatetimeIndex:
    if isinstance(timestamps_utc, (str, datetime, pd.Timestamp)):
        index = pd.DatetimeIndex([timestamps_utc])
    else:
        index = pd.DatetimeIndex(list(timestamps_utc))
    if len(index) == 0:
        raise ValueError("timestamps_utc boş olamaz.")
    if index.tz is None:
        return index.tz_localize("UTC")
    return index.tz_convert("UTC")


def generate_gateway_ephemeris(
    timestamps_utc: Sequence[datetime | str | pd.Timestamp] | pd.DatetimeIndex | pd.Series,
    site_lat_deg: float,
    site_lon_deg_east: float,
    *,
    site_elev_m: float = 0.0,
    epoch_utc: datetime | str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Verilen UTC zaman ızgarası için Lunar Gateway NRHO yörünge ve bakış açısı üretir.

    Parametreler:
        timestamps_utc: UTC zaman damgaları dizisi veya ``DatetimeIndex``.
        site_lat_deg: İniş sahası enlemi (derece, ``[-90, 90]``).
        site_lon_deg_east: İniş sahası doğu boylamı (derece, ``[-180, 180]``).
        site_elev_m: Yüzey kotu (metre, varsayılan ``0.0``).
        epoch_utc: Apolun başlangıç referans zamanı (``None`` ise ilk zaman damgası).

    Dönüş:
        ``timestamp_utc``, ``gateway_az_deg``, ``gateway_alt_deg``,
        ``gateway_range_km`` ve selenomerkezî koordinat sütunlarını içeren DataFrame.
    """
    _validate_coordinates(float(site_lat_deg), float(site_lon_deg_east))
    grid = _to_utc_index(timestamps_utc)

    if epoch_utc is None:
        t0 = grid[0]
    else:
        t0 = pd.Timestamp(epoch_utc)
        t0 = t0.tz_localize("UTC") if t0.tzinfo is None else t0.tz_convert("UTC")

    lat_rad = math.radians(float(site_lat_deg))
    lon_rad = math.radians(float(site_lon_deg_east))

    up_vec = np.array(
        [
            math.cos(lat_rad) * math.cos(lon_rad),
            math.cos(lat_rad) * math.sin(lon_rad),
            math.sin(lat_rad),
        ],
        dtype=np.float64,
    )
    east_vec = np.array([-math.sin(lon_rad), math.cos(lon_rad), 0.0], dtype=np.float64)
    north_vec = np.cross(up_vec, east_vec)
    north_vec = north_vec / np.linalg.norm(north_vec)

    site_pos_km = ((LUNAR_MEAN_RADIUS_M + float(site_elev_m)) / 1000.0) * up_vec
    mean_motion_rad_h = 2.0 * math.pi / NRHO_PERIOD_HOURS
    elapsed_hours = (grid - t0).total_seconds() / 3600.0

    rows: list[dict[str, object]] = []
    for ts, dt_hour in zip(grid, elapsed_hours, strict=True):
        # M0 = pi: apolunda (Güney Kutbu üzerinde yüksek irtifa) başlangıç fazı
        mean_anomaly = (math.pi + mean_motion_rad_h * float(dt_hour)) % (2.0 * math.pi)
        ecc_anomaly = _solve_kepler(mean_anomaly, NRHO_ECCENTRICITY)

        denom = 1.0 - NRHO_ECCENTRICITY * math.cos(ecc_anomaly)
        cos_nu = (math.cos(ecc_anomaly) - NRHO_ECCENTRICITY) / denom
        sin_nu = (math.sqrt(1.0 - NRHO_ECCENTRICITY**2) * math.sin(ecc_anomaly)) / denom
        true_anomaly = math.atan2(sin_nu, cos_nu)

        r_km = NRHO_SEMI_MAJOR_AXIS_KM * denom
        x_km = 0.35 * r_km * math.sin(true_anomaly)
        y_km = 0.20 * r_km * math.sin(2.0 * true_anomaly)
        z_km = r_km * math.cos(true_anomaly)

        gw_pos_km = np.array([x_km, y_km, z_km], dtype=np.float64)
        distance_km = float(np.linalg.norm(gw_pos_km))
        sub_lat_deg = math.degrees(math.asin(float(np.clip(z_km / distance_km, -1.0, 1.0))))
        sub_lon_deg_east = math.degrees(math.atan2(y_km, x_km))

        rho_vec = gw_pos_km - site_pos_km
        range_km = float(np.linalg.norm(rho_vec))
        rho_hat = rho_vec / range_km

        up_comp = float(np.dot(rho_hat, up_vec))
        east_comp = float(np.dot(rho_hat, east_vec))
        north_comp = float(np.dot(rho_hat, north_vec))

        alt_deg = math.degrees(math.asin(float(np.clip(up_comp, -1.0, 1.0))))
        az_deg = math.degrees(math.atan2(east_comp, north_comp)) % 360.0
        if az_deg >= 360.0:
            az_deg = 0.0

        rows.append(
            {
                "timestamp_utc": ts,
                "gateway_az_deg": az_deg,
                "gateway_alt_deg": alt_deg,
                "gateway_range_km": range_km,
                "gateway_distance_km": distance_km,
                "x_km": x_km,
                "y_km": y_km,
                "z_km": z_km,
                "sub_lat_deg": sub_lat_deg,
                "sub_lon_deg_east": sub_lon_deg_east,
                "in_southern_sweet_spot": bool(z_km < -15_000.0),
            }
        )

    return pd.DataFrame(rows)


def _resolve_horizon_lookup(horizon_df_or_lookup: Any) -> Any:
    if isinstance(horizon_df_or_lookup, (str, Path)):
        return HorizonProfileLookup.from_csv(horizon_df_or_lookup)
    if isinstance(horizon_df_or_lookup, pd.DataFrame):
        if (
            "azimuth_deg" not in horizon_df_or_lookup.columns
            or "horizon_deg" not in horizon_df_or_lookup.columns
        ):
            raise ValueError(
                "Ufuk DataFrame'i 'azimuth_deg' ve 'horizon_deg' sütunlarını içermeli."
            )
        return HorizonProfileLookup(
            horizon_df_or_lookup["azimuth_deg"].to_numpy(dtype=float),
            horizon_df_or_lookup["horizon_deg"].to_numpy(dtype=float),
        )
    if hasattr(horizon_df_or_lookup, "elevation_at"):
        return horizon_df_or_lookup
    raise TypeError(
        "horizon_df_or_lookup HorizonProfileLookup, DataFrame, Path veya HorizonProvider olmalı."
    )


def _lookup_horizons(horizon_lookup: Any, azimuths_deg: np.ndarray) -> np.ndarray:
    if hasattr(horizon_lookup, "elevations_at"):
        return np.asarray(horizon_lookup.elevations_at(azimuths_deg), dtype=float)
    values = [horizon_lookup.elevation_at(float(az)) for az in azimuths_deg]
    return np.array([np.nan if v is None else float(v) for v in values], dtype=float)


def _visible_bool_from_column(series: pd.Series) -> np.ndarray:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).to_numpy(dtype=bool)
    return (series.astype(str).str.strip().str.lower() == VISIBLE).to_numpy(dtype=bool)


def _classify_body_visible(
    az_series: pd.Series,
    alt_series: pd.Series,
    horizon_lookup: Any,
    quality_series: pd.Series | None,
    config: VisibilityConfig,
) -> np.ndarray:
    az_vals = pd.to_numeric(az_series, errors="coerce").to_numpy(dtype=float)
    alt_vals = pd.to_numeric(alt_series, errors="coerce").to_numpy(dtype=float)
    q_vals = (
        ["valid"] * len(az_vals)
        if quality_series is None
        else quality_series.fillna("valid").astype(str).tolist()
    )
    out = np.zeros(len(az_vals), dtype=bool)
    for idx, (az, alt, q_flag) in enumerate(zip(az_vals, alt_vals, q_vals, strict=True)):
        if not math.isfinite(az) or not math.isfinite(alt):
            continue
        horizon = horizon_lookup.elevation_at(float(az))
        state, _ = classify(float(alt), horizon, quality_flag=q_flag, config=config)
        out[idx] = state == VISIBLE
    return out


def _extract_series_inputs(
    series_df_or_samples: pd.DataFrame | Sequence[Sample] | Sequence[SampleResult],
    horizon_lookup: Any,
    config: VisibilityConfig,
) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray]:
    if isinstance(series_df_or_samples, pd.DataFrame):
        if series_df_or_samples.empty:
            raise ValueError("series_df_or_samples boş olamaz.")
        if "timestamp_utc" not in series_df_or_samples.columns:
            raise ValueError("series DataFrame'i 'timestamp_utc' sütunu içermeli.")
        timestamps = _to_utc_index(series_df_or_samples["timestamp_utc"])
        q_col = (
            series_df_or_samples["quality_flag"]
            if "quality_flag" in series_df_or_samples.columns
            else None
        )
        if "sun_visible" in series_df_or_samples.columns:
            sun_vis = _visible_bool_from_column(series_df_or_samples["sun_visible"])
        elif {"sun_az_deg", "sun_alt_deg"} <= set(series_df_or_samples.columns):
            sun_vis = _classify_body_visible(
                series_df_or_samples["sun_az_deg"],
                series_df_or_samples["sun_alt_deg"],
                horizon_lookup,
                q_col,
                config,
            )
        else:
            sun_vis = np.zeros(len(timestamps), dtype=bool)

        if "earth_visible" in series_df_or_samples.columns:
            earth_vis = _visible_bool_from_column(series_df_or_samples["earth_visible"])
        elif {"earth_az_deg", "earth_alt_deg"} <= set(series_df_or_samples.columns):
            earth_vis = _classify_body_visible(
                series_df_or_samples["earth_az_deg"],
                series_df_or_samples["earth_alt_deg"],
                horizon_lookup,
                q_col,
                config,
            )
        else:
            earth_vis = np.zeros(len(timestamps), dtype=bool)
        return timestamps, sun_vis, earth_vis

    items = list(series_df_or_samples)
    if not items:
        raise ValueError("series_df_or_samples boş olamaz.")

    first = items[0]
    if isinstance(first, SampleResult):
        timestamps = _to_utc_index([item.sample.timestamp_utc for item in items])
        sun_vis = np.array([item.sun.state == VISIBLE for item in items], dtype=bool)
        earth_vis = np.array([item.earth.state == VISIBLE for item in items], dtype=bool)
        return timestamps, sun_vis, earth_vis

    if isinstance(first, Sample):
        timestamps = _to_utc_index([item.timestamp_utc for item in items])
        sun_vis = np.zeros(len(items), dtype=bool)
        earth_vis = np.zeros(len(items), dtype=bool)
        for idx, item in enumerate(items):
            if item.sun_az_deg is not None and item.sun_alt_deg is not None:
                h_sun = horizon_lookup.elevation_at(item.sun_az_deg)
                sun_state, _ = classify(
                    item.sun_alt_deg, h_sun, quality_flag=item.quality_flag, config=config
                )
                sun_vis[idx] = sun_state == VISIBLE
            if item.earth_az_deg is not None and item.earth_alt_deg is not None:
                h_earth = horizon_lookup.elevation_at(item.earth_az_deg)
                earth_state, _ = classify(
                    item.earth_alt_deg, h_earth, quality_flag=item.quality_flag, config=config
                )
                earth_vis[idx] = earth_state == VISIBLE
        return timestamps, sun_vis, earth_vis

    raise TypeError(
        "series_df_or_samples pd.DataFrame, list[Sample] veya list[SampleResult] olmalı."
    )


def _max_outage_hours(timestamps: pd.DatetimeIndex, gateway_visible: np.ndarray) -> float:
    """Kesintisiz en uzun Gateway körlük süresini (saat) örnek orta-noktalarıyla hesaplar."""
    n = len(timestamps)
    if n < 2 or bool(np.all(gateway_visible)):
        return 0.0

    times_sec = (timestamps - timestamps[0]).total_seconds().to_numpy(dtype=np.float64)
    boundaries = np.empty(n + 1, dtype=np.float64)
    boundaries[0] = times_sec[0]
    boundaries[-1] = times_sec[-1]
    boundaries[1:-1] = 0.5 * (times_sec[:-1] + times_sec[1:])
    sample_durations_h = (boundaries[1:] - boundaries[:-1]) / 3600.0

    max_hours = 0.0
    current_hours = 0.0
    for is_vis, dur_h in zip(gateway_visible, sample_durations_h, strict=True):
        if not is_vis:
            current_hours += float(dur_h)
            max_hours = max(max_hours, current_hours)
        else:
            current_hours = 0.0
    return max_hours


def compute_gateway_visibility(
    series_df_or_samples: pd.DataFrame | Sequence[Sample] | Sequence[SampleResult],
    horizon_df_or_lookup: HorizonProfileLookup | pd.DataFrame | str | Path | Any,
    site_lat_deg: float,
    site_lon_deg_east: float,
    margin_deg: float = 0.0,
    *,
    site_elev_m: float = 0.0,
    epoch_utc: datetime | str | pd.Timestamp | None = None,
) -> dict[str, Any]:
    """İniş sahası için doğrudan Dünya ve Lunar Gateway NRHO röle görünürlüğünü karşılaştırır.

    Parametreler:
        series_df_or_samples: K3 görünürlük tablosu, K1 efemeris DataFrame'i veya
            ``Sample`` / ``SampleResult`` listesi.
        horizon_df_or_lookup: K2 :class:`HorizonProfileLookup`, DataFrame veya profil CSV yolu.
        site_lat_deg: Saha enlemi (derece).
        site_lon_deg_east: Saha doğu boylamı (derece, ``[-180, 180]``).
        margin_deg: Geçiş bandı güvenlik marjı (derece, varsayılan ``0.0``).
        site_elev_m: Yüzey kotu (metre).
        epoch_utc: İsteğe bağlı Gateway apolun referans zamanı.

    Dönüş:
        ``direct_earth_pct``, ``gateway_relay_pct``, ``combined_comms_pct``,
        ``solar_and_gateway_pct``, ``max_relay_outage_hours``,
        ``mean_gateway_elevation_deg`` ve çizim için ``series`` DataFrame içeren sözlük.
    """
    _validate_coordinates(float(site_lat_deg), float(site_lon_deg_east))
    if margin_deg < 0.0:
        raise ValueError(f"margin_deg negatif olamaz; {margin_deg} verildi.")

    config = VisibilityConfig(margin_deg=float(margin_deg))
    horizon_lookup = _resolve_horizon_lookup(horizon_df_or_lookup)
    timestamps, sun_vis, earth_vis = _extract_series_inputs(
        series_df_or_samples, horizon_lookup, config
    )

    gw_eph = generate_gateway_ephemeris(
        timestamps,
        site_lat_deg,
        site_lon_deg_east,
        site_elev_m=site_elev_m,
        epoch_utc=epoch_utc,
    )
    gw_az = gw_eph["gateway_az_deg"].to_numpy(dtype=float)
    gw_alt = gw_eph["gateway_alt_deg"].to_numpy(dtype=float)
    horizon_gw = _lookup_horizons(horizon_lookup, gw_az)

    gw_states: list[str] = []
    gw_vis = np.zeros(len(gw_alt), dtype=bool)
    gw_margins = np.full(len(gw_alt), np.nan, dtype=float)
    for idx, (alt, h_el) in enumerate(zip(gw_alt, horizon_gw, strict=True)):
        horizon_val = None if not math.isfinite(h_el) else float(h_el)
        state, _ = classify(float(alt), horizon_val, config=config)
        gw_states.append(state)
        gw_vis[idx] = state == VISIBLE
        if horizon_val is not None:
            gw_margins[idx] = float(alt) - horizon_val

    combined_comms = earth_vis | gw_vis
    solar_and_gateway = sun_vis & gw_vis

    series_df = gw_eph.copy()
    series_df["terrain_horizon_gateway_deg"] = horizon_gw
    series_df["gateway_margin_deg"] = gw_margins
    series_df["gateway_state"] = gw_states
    series_df["gateway_visible"] = gw_vis
    series_df["direct_earth_visible"] = earth_vis
    series_df["sun_visible"] = sun_vis
    series_df["combined_comms_visible"] = combined_comms
    series_df["solar_and_gateway_visible"] = solar_and_gateway

    return {
        "site_lat_deg": float(site_lat_deg),
        "site_lon_deg_east": float(site_lon_deg_east),
        "margin_deg": float(margin_deg),
        "samples": int(len(series_df)),
        "direct_earth_pct": round(float(np.mean(earth_vis) * 100.0), 4),
        "gateway_relay_pct": round(float(np.mean(gw_vis) * 100.0), 4),
        "combined_comms_pct": round(float(np.mean(combined_comms) * 100.0), 4),
        "solar_and_gateway_pct": round(float(np.mean(solar_and_gateway) * 100.0), 4),
        "max_relay_outage_hours": round(_max_outage_hours(timestamps, gw_vis), 4),
        "mean_gateway_elevation_deg": round(float(np.mean(gw_alt)), 4),
        "series": series_df,
    }


__all__ = [
    "LUNAR_MEAN_RADIUS_M",
    "NRHO_APOLUNE_KM",
    "NRHO_ECCENTRICITY",
    "NRHO_PERIOD_HOURS",
    "NRHO_PERILUNE_KM",
    "NRHO_SEMI_MAJOR_AXIS_KM",
    "compute_gateway_visibility",
    "generate_gateway_ephemeris",
]
