"""Uçuş fiziği modülleri (Gateway NRHO, Penumbra, Kırınım/DSN Link Bütçesi) ve
çok bölgeli K3 duyarlılık betiği testleri.
"""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from luna_sight.terrain.sites import CANDIDATE_SITES
from luna_sight.visibility import (
    DSN_STATIONS,
    NRHO_APOLUNE_KM,
    NRHO_PERILUNE_KM,
    NRHO_PERIOD_HOURS,
    SOLAR_ANGULAR_DIAMETER_DEG,
    SOLAR_ANGULAR_RADIUS_DEG,
    ConstantHorizon,
    DSNStation,
    FrequencyBand,
    HorizonProfileLookup,
    classify_diffraction_regime,
    compare_band_link_budgets,
    compute_diffraction_loss_itu,
    compute_fresnel_parameter,
    compute_gateway_visibility,
    compute_link_budget,
    compute_penumbra_power,
    compute_solar_disk_fraction,
    evaluate_emergency_link_margin,
    generate_gateway_ephemeris,
    load_series_csv,
)

ROOT = Path(__file__).resolve().parents[1]
K2_DIR = ROOT / "outputs" / "k2"
K3_DIR = ROOT / "outputs" / "k3"
CACHE_DIR = ROOT / "data" / "cache"


def _load_sensitivity_module():
    path = ROOT / "scripts" / "k3_sensitivity.py"
    spec = importlib.util.spec_from_file_location("k3_sensitivity", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ----------------------------------------------------------------- Gateway NRHO
def test_gateway_constants_and_ephemeris_orbit():
    assert NRHO_PERIOD_HOURS == pytest.approx(168.0)
    assert 1_737.4 < NRHO_PERILUNE_KM < 5_000.0
    assert 60_000.0 < NRHO_APOLUNE_KM < 80_000.0

    site = CANDIDATE_SITES["Site04"]
    grid = pd.date_range("2026-11-14T00:00:00Z", periods=169, freq="1h", tz="UTC")
    eph = generate_gateway_ephemeris(grid, site.latitude_deg, site.longitude_deg_east)

    expected_cols = {
        "timestamp_utc",
        "gateway_az_deg",
        "gateway_alt_deg",
        "gateway_range_km",
        "gateway_distance_km",
        "sub_lat_deg",
        "sub_lon_deg_east",
        "in_southern_sweet_spot",
    }
    assert expected_cols <= set(eph.columns)
    assert len(eph) == 169
    assert (eph["sub_lon_deg_east"] >= -180.0).all()
    assert (eph["sub_lon_deg_east"] <= 180.0).all()
    assert (eph["gateway_az_deg"] >= 0.0).all()
    assert (eph["gateway_az_deg"] < 360.0).all()
    # Başlangıçta apolun: derin güney ve yüksek açı
    assert eph["z_km"].iloc[0] < -60_000.0
    assert eph["gateway_alt_deg"].iloc[0] > 75.0
    assert eph["in_southern_sweet_spot"].mean() > 0.75


def test_gateway_coordinate_validation():
    grid = pd.date_range("2026-11-14T00:00:00Z", periods=3, freq="1h", tz="UTC")
    with pytest.raises(ValueError, match="site_lon_deg_east"):
        generate_gateway_ephemeris(grid, -89.5, 222.5)
    with pytest.raises(ValueError, match="site_lat_deg"):
        generate_gateway_ephemeris(grid, -95.0, 0.0)


@pytest.mark.skipif(
    not (K3_DIR / "Site04_visibility.csv").exists()
    or not (K2_DIR / "Site04_horizon_4000m.csv").exists(),
    reason="Site04 gerçek K2/K3 çıktıları yok",
)
def test_gateway_rescues_site04_and_enhances_site01():
    s4 = CANDIDATE_SITES["Site04"]
    df4 = pd.read_csv(K3_DIR / "Site04_visibility.csv")
    h4 = HorizonProfileLookup.from_csv(K2_DIR / "Site04_horizon_4000m.csv")
    res4 = compute_gateway_visibility(df4, h4, s4.latitude_deg, s4.longitude_deg_east)

    assert res4["direct_earth_pct"] == pytest.approx(0.0, abs=0.1)
    assert res4["gateway_relay_pct"] > 75.0
    assert res4["combined_comms_pct"] > 75.0
    assert res4["solar_and_gateway_pct"] > 75.0
    assert 0.5 < res4["max_relay_outage_hours"] < 12.0
    assert res4["mean_gateway_elevation_deg"] > 60.0
    assert isinstance(res4["series"], pd.DataFrame)
    assert len(res4["series"]) == len(df4)

    s1 = CANDIDATE_SITES["Site01"]
    df1 = pd.read_csv(K3_DIR / "Site01_visibility.csv")
    h1 = HorizonProfileLookup.from_csv(K2_DIR / "Site01_horizon_4000m.csv")
    res1 = compute_gateway_visibility(df1, h1, s1.latitude_deg, s1.longitude_deg_east)

    assert 25.0 < res1["direct_earth_pct"] < 40.0
    assert res1["gateway_relay_pct"] > 90.0
    assert res1["combined_comms_pct"] >= res1["direct_earth_pct"]


def test_gateway_supports_samples_dataframe_and_margin():
    grid = pd.date_range("2026-11-14T00:00:00Z", periods=25, freq="1h", tz="UTC")
    raw_df = pd.DataFrame(
        {
            "timestamp_utc": grid,
            "sun_az_deg": 90.0,
            "sun_alt_deg": 1.0,
            "earth_az_deg": 180.0,
            "earth_alt_deg": -2.0,
        }
    )
    horizon_df = pd.DataFrame(
        {
            "azimuth_deg": [0.0, 90.0, 180.0, 270.0],
            "horizon_deg": [0.0, 0.0, 0.0, 0.0],
        }
    )
    res_df = compute_gateway_visibility(raw_df, horizon_df, -89.5, 0.0, margin_deg=0.0)
    res_tight = compute_gateway_visibility(raw_df, ConstantHorizon(0.0), -89.5, 0.0, margin_deg=5.0)
    assert res_df["direct_earth_pct"] == pytest.approx(0.0)
    assert res_df["gateway_relay_pct"] >= res_tight["gateway_relay_pct"]

    if (CACHE_DIR / "ephemeris_Site04_20261114T0000_168h.csv").exists():
        samples = load_series_csv(CACHE_DIR / "ephemeris_Site04_20261114T0000_168h.csv")[:25]
        s4 = CANDIDATE_SITES["Site04"]
        res_samples = compute_gateway_visibility(
            samples, ConstantHorizon(0.0), s4.latitude_deg, s4.longitude_deg_east
        )
        assert res_samples["samples"] == 25
        assert res_samples["gateway_relay_pct"] > 90.0


# --------------------------------------------------------------------- Penumbra
def test_solar_disk_fraction_bounds_symmetry_and_limb_darkening():
    assert SOLAR_ANGULAR_DIAMETER_DEG == pytest.approx(0.533)
    assert SOLAR_ANGULAR_RADIUS_DEG == pytest.approx(0.2665)

    assert compute_solar_disk_fraction(-1.0, 0.0) == pytest.approx(0.0)
    assert compute_solar_disk_fraction(-SOLAR_ANGULAR_RADIUS_DEG, 0.0) == pytest.approx(0.0)
    assert compute_solar_disk_fraction(0.0, 0.0) == pytest.approx(0.5)
    assert compute_solar_disk_fraction(SOLAR_ANGULAR_RADIUS_DEG, 0.0) == pytest.approx(1.0)
    assert compute_solar_disk_fraction(1.0, 0.0) == pytest.approx(1.0)

    deltas = np.linspace(-SOLAR_ANGULAR_RADIUS_DEG, SOLAR_ANGULAR_RADIUS_DEG, 41)
    f_limb = compute_solar_disk_fraction(deltas, 0.0, limb_darkening=True)
    f_geom = compute_solar_disk_fraction(deltas, 0.0, limb_darkening=False)

    assert isinstance(f_limb, np.ndarray)
    assert np.all((f_limb >= 0.0) & (f_limb <= 1.0))
    assert np.all(np.diff(f_limb) >= -1e-12)
    # Antisimetri: f(-delta) + f(+delta) == 1
    assert f_limb + f_limb[::-1] == pytest.approx(1.0, abs=1e-12)
    # Kenar kararması etkisi: pozitif yarıda parlak merkez görünür -> f_limb > f_geom
    assert np.all(f_limb[21:-1] > f_geom[21:-1])
    assert np.all(f_limb[1:20] < f_geom[1:20])

    # NaN korunumu
    nan_out = compute_solar_disk_fraction(np.array([0.0, np.nan]), np.array([0.0, 0.0]))
    assert nan_out[0] == pytest.approx(0.5)
    assert np.isnan(nan_out[1])


def test_compute_penumbra_power_ramp_and_real_sites():
    sun_el = np.linspace(-0.5, 0.5, 121)
    result = compute_penumbra_power(sun_el, 0.0, step_minutes=5.0, max_power_w=1000.0)

    expected_keys = {
        "point_source_hours",
        "effective_penumbra_hours",
        "penumbra_transition_hours",
        "point_energy_wh",
        "penumbra_energy_wh",
        "energy_delta_wh",
        "point_power_w",
        "penumbra_power_w",
        "disk_fraction",
    }
    assert expected_keys <= set(result)
    assert result["penumbra_transition_hours"] > 4.0
    assert result["point_energy_wh"] == pytest.approx(
        result["point_source_hours"] * 1000.0, abs=0.1
    )
    assert result["penumbra_energy_wh"] == pytest.approx(
        result["effective_penumbra_hours"] * 1000.0, abs=0.1
    )
    assert np.sum(result["penumbra_power_w"]) * (5.0 / 60.0) == pytest.approx(
        result["penumbra_energy_wh"], abs=1e-3
    )
    assert result["energy_delta_wh"] == pytest.approx(
        result["penumbra_energy_wh"] - result["point_energy_wh"], abs=1e-3
    )
    assert len(result["point_power_w"]) == len(sun_el)
    assert len(result["penumbra_power_w"]) == len(sun_el)
    assert len(result["disk_fraction"]) == len(sun_el)

    if (K3_DIR / "Site04_visibility.csv").exists() and (
        K2_DIR / "Site04_horizon_20000m.csv"
    ).exists():
        df4 = pd.read_csv(K3_DIR / "Site04_visibility.csv")
        prof20 = HorizonProfileLookup.from_csv(K2_DIR / "Site04_horizon_20000m.csv")
        h20 = prof20.elevations_at(df4["sun_az_deg"].to_numpy())
        p20 = compute_penumbra_power(
            df4["sun_alt_deg"].to_numpy(), h20, step_minutes=5.0, max_power_w=1000.0
        )
        assert p20["penumbra_transition_hours"] > 30.0
        assert p20["energy_delta_wh"] < -1000.0

    with pytest.raises(ValueError):
        compute_penumbra_power(sun_el, 0.0, step_minutes=0.0)
    with pytest.raises(ValueError):
        compute_penumbra_power(sun_el, 0.0, max_power_w=-10.0)


# --------------------------------------------------------------- Comms / DSN
def test_dsn_stations_canonical_longitudes():
    assert set(DSN_STATIONS) == {DSNStation.GOLDSTONE, DSNStation.MADRID, DSNStation.CANBERRA}
    for info in DSN_STATIONS.values():
        assert -90.0 <= info.latitude_deg <= 90.0
        assert -180.0 <= info.longitude_deg_east <= 180.0
    assert DSN_STATIONS[DSNStation.GOLDSTONE].longitude_deg_east == pytest.approx(-116.89)
    assert DSN_STATIONS[DSNStation.MADRID].longitude_deg_east == pytest.approx(-4.25)
    assert DSN_STATIONS[DSNStation.CANBERRA].longitude_deg_east == pytest.approx(148.98)


def test_itu_diffraction_loss_across_fresnel_regimes():
    v_clear = compute_fresnel_parameter(-2.0, distance_to_ridge_m=5_000.0)
    assert v_clear < -0.78
    assert classify_diffraction_regime(v_clear) == "clear_los"
    assert compute_diffraction_loss_itu(v_clear) == pytest.approx(0.0)

    assert classify_diffraction_regime(-0.3) == "fresnel_grazing"
    assert 0.0 < compute_diffraction_loss_itu(-0.3) < 6.02

    assert classify_diffraction_regime(0.0) == "fresnel_grazing"
    assert compute_diffraction_loss_itu(0.0) == pytest.approx(6.02, abs=0.05)

    assert classify_diffraction_regime(0.5) == "shallow_shadow"
    assert 6.0 < compute_diffraction_loss_itu(0.5) < 13.0

    v_deep = compute_fresnel_parameter(0.4, distance_to_ridge_m=5_000.0)
    assert v_deep > 1.0
    assert classify_diffraction_regime(v_deep) == "deep_shadow"
    assert compute_diffraction_loss_itu(v_deep) > 13.0

    losses = compute_diffraction_loss_itu(np.array([-2.0, -0.3, 0.0, 0.5, 2.0]))
    assert np.all(np.diff(losses) >= 0.0)


def test_emergency_link_margin_and_band_presets():
    # S-Band acil telemetri 0.3°-0.5° dağ sırtı arkasında kapanır
    s_emergency = evaluate_emergency_link_margin(
        obstruction_angle_deg=0.4, distance_to_ridge_m=5000
    )
    assert s_emergency["link_closed"] is True
    assert s_emergency["link_margin_db"] >= 3.0
    assert s_emergency["diffraction_regime"] == "deep_shadow"

    # Engelsiz tüm bantlar
    budgets = compare_band_link_budgets(station=DSNStation.MADRID)
    for band_key in ("S_BAND", "KA_BAND", "OPTICAL_O2O"):
        b = budgets[band_key]
        assert {
            "fspl_db",
            "diffraction_loss_db",
            "total_path_loss_db",
            "rx_power_dbm",
            "eb_n0_db",
            "link_margin_db",
            "achievable_data_rate_mbps",
            "link_closed",
            "diffraction_regime",
        } <= set(b)
        assert b["link_closed"] is True
        assert b["diffraction_loss_db"] == pytest.approx(0.0)
        assert b["diffraction_regime"] == "clear_los"

    assert (
        budgets["S_BAND"]["fspl_db"]
        < budgets["KA_BAND"]["fspl_db"]
        < budgets["OPTICAL_O2O"]["fspl_db"]
    )

    # 0.4° sırt engeli altında: S-Band hayatta kalır, Ka-Band ve Optik düşer
    s_obs = compute_link_budget("canberra", "S-Band", obstruction_angle_deg=0.4)
    ka_obs = compute_link_budget(
        DSNStation.GOLDSTONE, FrequencyBand.KA_BAND, obstruction_angle_deg=0.4
    )
    opt_obs = compute_link_budget("madrid", "1550nm", obstruction_angle_deg=0.4)

    assert s_obs["link_closed"] is True
    assert ka_obs["link_closed"] is False
    assert opt_obs["link_closed"] is False
    assert (
        opt_obs["diffraction_loss_db"]
        > ka_obs["diffraction_loss_db"]
        > s_obs["diffraction_loss_db"]
    )


# ------------------------------------------------ k3_sensitivity multi-site
def _write_test_series_csv(
    path: Path,
    rows: list[tuple[str, str, float, float, float, float]],
) -> None:
    header = (
        "site_id,latitude_deg,longitude_deg_east,timestamp_utc,"
        "sun_az_deg,sun_alt_deg,earth_az_deg,earth_alt_deg,"
        "quality_flag,source_id,source_version,model_id,parameters\n"
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        handle.write(header)
        writer = csv.writer(handle, lineterminator="\n")
        for site_id, ts, s_az, s_alt, e_az, e_alt in rows:
            writer.writerow(
                [
                    site_id,
                    -89.5,
                    -137.5,
                    ts,
                    s_az,
                    s_alt,
                    e_az,
                    e_alt,
                    "valid",
                    "jpl-horizons",
                    "1.2",
                    "DE441",
                    "{}",
                ]
            )


def _write_flat_horizon(path: Path, elevation: float = 0.0) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["azimuth_deg", "horizon_deg"])
        for az in (0.0, 90.0, 180.0, 270.0):
            writer.writerow([az, elevation])


def test_k3_sensitivity_series_dir_and_combined_multi_site(tmp_path: Path):
    sens = _load_sensitivity_module()

    prof1 = tmp_path / "Site01_horizon_2000m.csv"
    prof4 = tmp_path / "Site04_horizon_4000m.csv"
    _write_flat_horizon(prof1, 0.0)
    _write_flat_horizon(prof4, 0.0)

    # 1) --series-dir en uzun pencereyi (168h > 24h) seçmeli
    series_dir = tmp_path / "cache"
    series_dir.mkdir()
    _write_test_series_csv(
        series_dir / "ephemeris_Site01_20261114T0000_24h.csv",
        [
            ("Site01", "2026-11-14T00:00:00Z", 10.0, -2.0, 20.0, -2.0),
            ("Site01", "2026-11-14T01:00:00Z", 11.0, -2.0, 21.0, -2.0),
        ],
    )
    _write_test_series_csv(
        series_dir / "ephemeris_Site01_20261114T0000_168h.csv",
        [
            ("Site01", "2026-11-14T00:00:00Z", 10.0, 2.0, 20.0, 2.0),
            ("Site01", "2026-11-14T01:00:00Z", 11.0, 2.0, 21.0, 2.0),
        ],
    )
    _write_test_series_csv(
        series_dir / "ephemeris_Site04_20261114T0000_168h.csv",
        [
            ("Site04", "2026-11-14T00:00:00Z", 10.0, 2.0, 20.0, -2.0),
            ("Site04", "2026-11-14T01:00:00Z", 11.0, 2.0, 21.0, -2.0),
        ],
    )

    chosen = sens.discover_series_file(series_dir, "Site01")
    assert chosen.name.endswith("_168h.csv")

    out_dir_csv = tmp_path / "sens_dir.csv"
    rc = sens.main(
        [
            "--profiles",
            str(prof1),
            str(prof4),
            "--margins",
            "0.1",
            "--series-dir",
            str(series_dir),
            "--out",
            str(out_dir_csv),
        ]
    )
    assert rc == 0
    df_dir = pd.read_csv(out_dir_csv)
    assert len(df_dir) == 6
    s1_joint = df_dir[(df_dir["site_id"] == "Site01") & (df_dir["body"] == "joint")].iloc[0]
    s4_joint = df_dir[(df_dir["site_id"] == "Site04") & (df_dir["body"] == "joint")].iloc[0]
    assert s1_joint["visible_fraction"] == pytest.approx(1.0)
    assert s4_joint["visible_fraction"] == pytest.approx(0.0)

    # 2) --series çok bölgeli birleşik CSV'de zaman damgaları yeniden başlasa bile çökmemeli
    combined = tmp_path / "combined.csv"
    _write_test_series_csv(
        combined,
        [
            ("Site01", "2026-11-14T00:00:00Z", 10.0, 2.0, 20.0, 2.0),
            ("Site01", "2026-11-14T01:00:00Z", 11.0, 2.0, 21.0, 2.0),
            ("Site04", "2026-11-14T00:00:00Z", 10.0, 2.0, 20.0, -2.0),
            ("Site04", "2026-11-14T01:00:00Z", 11.0, 2.0, 21.0, -2.0),
        ],
    )
    out_comb_csv = tmp_path / "sens_comb.csv"
    rc2 = sens.main(
        [
            "--profiles",
            str(prof1),
            str(prof4),
            "--margins",
            "0.1",
            "--series",
            str(combined),
            "--out",
            str(out_comb_csv),
        ]
    )
    assert rc2 == 0
    df_comb = pd.read_csv(out_comb_csv)
    assert df_comb["visible_fraction"].tolist() == pytest.approx(
        df_dir["visible_fraction"].tolist()
    )

    # 3) --series ve --series-dir aynı anda reddedilmeli
    with pytest.raises(SystemExit):
        sens.main(["--series", str(combined), "--series-dir", str(series_dir)])


@pytest.mark.skipif(not (K3_DIR / "sensitivity.csv").exists(), reason="sensitivity.csv yok")
def test_committed_sensitivity_csv_covers_all_k2_profiles():
    df = pd.read_csv(K3_DIR / "sensitivity.csv")
    k2_profiles = sorted(K2_DIR.glob("*_horizon_*m.csv"))
    assert len(df) == len(k2_profiles) * 3 * 3
    assert set(df["site_id"]) == set(CANDIDATE_SITES)
