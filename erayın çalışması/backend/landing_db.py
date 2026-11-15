"""
backend/landing_db.py
=====================
SQLite Tabanlı Ay İniş Simülasyon Veritabanı (WAL Modu, Thread-Safe).
Tüm Monte Carlo ve canlı iniş telemetrilerini depolar, ML eğitimi için veri seti sağlar.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from backend.config import DATA_DIR

M_PROP_INITIAL_KG: float = 2800.0
M_TOTAL_INITIAL_KG: float = 5000.0
M_DRY_KG: float = 2200.0

DEFAULT_DB_PATH = DATA_DIR / "landing_simulations.db"

# Thread-safe kilit mekanizması
_DB_LOCK = threading.Lock()


def get_connection(db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    """Thread-safe, WAL modunda yapılandırılmış SQLite bağlantısı döner."""
    target_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target_path), check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row

    # Performans ve Eşzamanlılık PRAGMA ayarları
    with conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")

    return conn


def init_db(db_path: Optional[Union[str, Path]] = None) -> None:
    """Veritabanı tablolarını ve indekslerini oluşturur."""
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS landing_trials (
                        trial_id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        site_id TEXT,
                        target_lat REAL,
                        target_lon REAL,
                        target_norm_x REAL,
                        target_norm_y REAL,
                        initial_alt_m REAL,
                        initial_vh_ms REAL,
                        initial_vv_ms REAL,
                        final_alt_m REAL,
                        final_vh_ms REAL,
                        final_vv_ms REAL,
                        tilt_deg REAL,
                        fuel_rem_pct REAL,
                        fuel_consumed_kg REAL,
                        flight_time_s REAL,
                        slope_deg REAL,
                        roughness_tri_m REAL,
                        solar_illum_pct REAL,
                        dte_vis_pct REAL,
                        vertical_score REAL,
                        horizontal_score REAL,
                        tilt_score REAL,
                        terrain_score REAL,
                        fuel_score REAL,
                        env_score REAL,
                        total_score REAL,
                        status TEXT,
                        status_label_tr TEXT,
                        trajectory_summary_json TEXT
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trials_timestamp ON landing_trials(timestamp);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trials_site ON landing_trials(site_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trials_status ON landing_trials(status);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trials_site_time ON landing_trials(site_id, timestamp DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trials_status_time ON landing_trials(status, timestamp DESC);")
        finally:
            conn.close()


def insert_trial(trial_data: Any, db_path: Optional[Union[str, Path]] = None) -> str:
    """
    Yeni bir iniş denemesini kaydeder.
    trial_data bir sözlük veya AILandingEngine'den dönen LandingResult dataclass'ı olabilir.
    """
    init_db(db_path)

    # Veri dönüşümü
    if hasattr(trial_data, "__dataclass_fields__"):
        from dataclasses import asdict
        d = asdict(trial_data)
    elif isinstance(trial_data, dict):
        d = trial_data.copy()
    else:
        d = dict(trial_data)

    trial_id = d.get("trial_id") or f"TR-{uuid.uuid4().hex[:8].upper()}"
    timestamp = d.get("timestamp") or datetime.now(timezone.utc).isoformat()
    site_id = d.get("target_site_id") or d.get("site_id") or "CUSTOM"

    target_coords = d.get("target_coords") or {}
    target_lat = float(target_coords.get("lat", d.get("target_lat", -89.75)))
    target_lon = float(target_coords.get("lon", d.get("target_lon", 0.0)))
    target_norm_x = float(target_coords.get("norm_x", d.get("target_norm_x", 0.5)))
    target_norm_y = float(target_coords.get("norm_y", d.get("target_norm_y", 0.5)))

    # Telemetri başlangıç ve bitiş değerleri
    initial_alt_m = float(d.get("initial_alt_m", d.get("initial_altitude_m", 3200.0)))
    initial_vh_ms = float(d.get("initial_vh_ms", d.get("initial_v_horizontal_ms", 62.0)))
    initial_vv_ms = float(d.get("initial_vv_ms", d.get("initial_v_vertical_ms", -28.0)))

    final_alt_m = float(d.get("final_alt_m", 0.0))
    final_vh_ms = float(d.get("touchdown_vxy_ms", d.get("final_vh_ms", 0.2)))
    final_vv_ms = float(d.get("touchdown_vz_ms", d.get("final_vv_ms", -0.9)))
    tilt_deg = float(d.get("tilt_deg", 1.5))

    fuel_rem_pct = float(d.get("fuel_remaining_pct", d.get("fuel_rem_pct", 12.0)))
    if "fuel_consumed_kg" in d:
        fuel_consumed_kg = float(d["fuel_consumed_kg"])
    else:
        rem_kg = float(d.get("fuel_remaining_kg", (fuel_rem_pct / 100.0) * M_PROP_INITIAL_KG))
        fuel_consumed_kg = max(0.0, M_PROP_INITIAL_KG - rem_kg)

    flight_time_s = float(d.get("duration_s", d.get("flight_time_s", 95.0)))

    # Arazi ve Çevre Metrikleri
    terrain = d.get("terrain_metrics") or {}
    slope_deg = float(terrain.get("slope_deg", d.get("slope_deg", 4.2)))
    roughness_tri_m = float(terrain.get("roughness_tri_m", d.get("roughness_tri_m", 0.35)))
    solar_illum_pct = float(terrain.get("solar_illumination_pct", d.get("solar_illum_pct", 88.0)))
    dte_vis_pct = float(terrain.get("dte_visibility_pct", d.get("dte_vis_pct", 92.0)))

    # Skor Kırılımları
    scoring = d.get("scoring") or {}
    vertical_score = float(scoring.get("vertical_speed_score", d.get("vertical_score", 23.0)))
    horizontal_score = float(scoring.get("horizontal_speed_score", d.get("horizontal_score", 18.0)))
    tilt_score = float(scoring.get("tilt_angle_score", d.get("tilt_score", 14.0)))
    terrain_score = float(scoring.get("terrain_slope_roughness_score", d.get("terrain_score", 18.5)))
    fuel_score = float(scoring.get("fuel_reserve_score", d.get("fuel_score", 10.0)))
    env_score = float(scoring.get("environmental_score", d.get("env_score", 9.0)))
    total_score = float(scoring.get("total_score", d.get("total_score", 92.5)))

    status = d.get("status", "SAFE_TOUCHDOWN")
    status_label_tr = d.get("status_label_tr", "Güvenli İniş")

    # Yörünge özeti (ilk nokta, tepe, son nokta)
    trajectory = d.get("trajectory") or []
    if trajectory and isinstance(trajectory, list):
        summary = {
            "steps_count": len(trajectory),
            "start": trajectory[0] if trajectory else None,
            "end": trajectory[-1] if trajectory else None,
        }
        trajectory_summary_json = json.dumps(summary, default=str)
    else:
        trajectory_summary_json = json.dumps({"steps_count": 0})

    sql = """
    INSERT OR REPLACE INTO landing_trials (
        trial_id, timestamp, site_id, target_lat, target_lon, target_norm_x, target_norm_y,
        initial_alt_m, initial_vh_ms, initial_vv_ms, final_alt_m, final_vh_ms, final_vv_ms,
        tilt_deg, fuel_rem_pct, fuel_consumed_kg, flight_time_s, slope_deg, roughness_tri_m,
        solar_illum_pct, dte_vis_pct, vertical_score, horizontal_score, tilt_score, terrain_score,
        fuel_score, env_score, total_score, status, status_label_tr, trajectory_summary_json
    ) VALUES (
        ?, ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?, ?
    );
    """

    params = (
        trial_id, timestamp, site_id, target_lat, target_lon, target_norm_x, target_norm_y,
        initial_alt_m, initial_vh_ms, initial_vv_ms, final_alt_m, final_vh_ms, final_vv_ms,
        tilt_deg, fuel_rem_pct, fuel_consumed_kg, flight_time_s, slope_deg, roughness_tri_m,
        solar_illum_pct, dte_vis_pct, vertical_score, horizontal_score, tilt_score, terrain_score,
        fuel_score, env_score, total_score, status, status_label_tr, trajectory_summary_json
    )

    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                conn.execute(sql, params)
        finally:
            conn.close()

    return trial_id


def get_trials(
    limit: int = 50,
    offset: int = 0,
    site_id: Optional[str] = None,
    status: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Kayıtlı iniş denemelerini filtreleme ve sayfalama ile listeler."""
    init_db(db_path)

    conditions = []
    params: List[Any] = []

    if site_id:
        conditions.append("site_id = ?")
        params.append(site_id)
    if status:
        conditions.append("status = ?")
        params.append(status)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
    SELECT * FROM landing_trials
    {where_clause}
    ORDER BY timestamp DESC
    LIMIT ? OFFSET ?;
    """
    params.extend([max(1, limit), max(0, offset)])

    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.execute(sql, params)
            rows = [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    return rows


def get_stats(db_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Veritabanındaki genel iniş ve başarı metriklerini hesaplar."""
    init_db(db_path)

    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()

            # Toplam sayı
            cursor.execute("SELECT COUNT(*) FROM landing_trials;")
            total_count = cursor.fetchone()[0]

            if total_count == 0:
                return {
                    "total_trials": 0,
                    "success_rate_pct": 0.0,
                    "average_score": 0.0,
                    "status_counts": {"PERFECT_TOUCHDOWN": 0, "SAFE_TOUCHDOWN": 0, "HARD_LANDING": 0, "CRASH": 0},
                    "metrics": {
                        "mean_touchdown_vz_ms": 0.0,
                        "mean_touchdown_vxy_ms": 0.0,
                        "mean_fuel_consumed_kg": 0.0,
                        "mean_fuel_remaining_pct": 0.0,
                    },
                    "site_performance": {},
                }

            # Durum sayıları
            cursor.execute("SELECT status, COUNT(*) FROM landing_trials GROUP BY status;")
            status_counts = dict(cursor.fetchall())

            perfect = status_counts.get("PERFECT_TOUCHDOWN", 0)
            safe = status_counts.get("SAFE_TOUCHDOWN", 0) + status_counts.get("SAFE_TOUCHDOWN_RESTRICTED", 0)
            hard = status_counts.get("HARD_LANDING", 0)
            crash = status_counts.get("CRASH", 0)

            success_rate = ((perfect + safe) / total_count) * 100.0

            # İstatistiksel özetler
            cursor.execute(
                """
                SELECT 
                    AVG(total_score), MAX(total_score), MIN(total_score),
                    AVG(ABS(final_vv_ms)), AVG(final_vh_ms),
                    AVG(fuel_consumed_kg), AVG(fuel_rem_pct), AVG(flight_time_s)
                FROM landing_trials;
                """
            )
            row = cursor.fetchone()
            avg_score, max_score, min_score = row[0] or 0.0, row[1] or 0.0, row[2] or 0.0
            avg_vz, avg_vh = row[3] or 0.0, row[4] or 0.0
            avg_fuel_consumed, avg_fuel_rem, avg_time = row[5] or 0.0, row[6] or 0.0, row[7] or 0.0

            # Site bazında performans kırılımı
            cursor.execute(
                """
                SELECT site_id,
                       COUNT(*) as cnt,
                       AVG(total_score) as avg_sc,
                       SUM(CASE WHEN status IN ('PERFECT_TOUCHDOWN', 'SAFE_TOUCHDOWN', 'SAFE_TOUCHDOWN_RESTRICTED') THEN 1 ELSE 0 END) as succ_cnt
                FROM landing_trials
                GROUP BY site_id;
                """
            )
            site_performance = {}
            for s_id, cnt, avg_sc, s_cnt in cursor.fetchall():
                site_performance[s_id] = {
                    "total_trials": cnt,
                    "mean_score": round(float(avg_sc or 0.0), 1),
                    "success_rate_pct": round((float(s_cnt or 0) / cnt) * 100.0, 1) if cnt > 0 else 0.0,
                }

            return {
                "total_trials": total_count,
                "success_rate_pct": round(success_rate, 1),
                "perfect_count": perfect,
                "safe_count": safe,
                "hard_count": hard,
                "crash_count": crash,
                "average_score": round(float(avg_score), 1),
                "max_score": round(float(max_score), 1),
                "min_score": round(float(min_score), 1),
                "metrics": {
                    "mean_touchdown_vz_ms": round(float(avg_vz), 2),
                    "mean_touchdown_vxy_ms": round(float(avg_vh), 2),
                    "mean_fuel_consumed_kg": round(float(avg_fuel_consumed), 1),
                    "mean_fuel_remaining_pct": round(float(avg_fuel_rem), 1),
                    "mean_flight_time_s": round(float(avg_time), 1),
                },
                "status_counts": {
                    "PERFECT_TOUCHDOWN": perfect,
                    "SAFE_TOUCHDOWN": safe,
                    "HARD_LANDING": hard,
                    "CRASH": crash,
                },
                "site_performance": site_performance,
            }
        finally:
            conn.close()


def get_dataset_for_ml(
    db_path: Optional[Union[str, Path]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str]]:
    """
    Makine öğrenimi motoru için özellik (X) ve hedef (y) matrislerini döner.
    
    Özellikler (X) [8 boyutlu]:
    [initial_alt_m, initial_vh_ms, initial_vv_ms, slope_deg, roughness_tri_m, solar_illum_pct, dte_vis_pct, total_mass_kg]
    
    Hedefler:
    - y_reg (2 boyutlu): [total_score, fuel_consumed_kg]
    - y_cls (1 boyutlu): status etiketleri ("SAFE", "HARD", "CRASH")
    
    Returns:
        (X, y_reg, y_cls, feature_names)
    """
    init_db(db_path)

    feature_names = [
        "initial_alt_m",
        "initial_vh_ms",
        "initial_vv_ms",
        "slope_deg",
        "roughness_tri_m",
        "solar_illum_pct",
        "dte_vis_pct",
        "total_mass_kg",
    ]

    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    initial_alt_m, initial_vh_ms, initial_vv_ms,
                    slope_deg, roughness_tri_m, solar_illum_pct, dte_vis_pct,
                    total_score, fuel_consumed_kg, status
                FROM landing_trials;
                """
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

    if not rows:
        return (
            np.empty((0, len(feature_names)), dtype=np.float64),
            np.empty((0, 2), dtype=np.float64),
            np.empty((0,), dtype=object),
            feature_names,
        )

    X_list = []
    y_reg_list = []
    y_cls_list = []

    for r in rows:
        # X: [alt, vh, vv, slope, tri, solar, dte, mass]
        alt = float(r[0] or 3200.0)
        vh = float(r[1] or 62.0)
        vv = float(r[2] or -28.0)
        slope = float(r[3] or 4.0)
        tri = float(r[4] or 0.3)
        solar = float(r[5] or 80.0)
        dte = float(r[6] or 85.0)
        total_mass = float(M_TOTAL_INITIAL_KG)

        score = float(r[7] or 0.0)
        fuel_cons = float(r[8] or 0.0)
        raw_status = str(r[9] or "SAFE_TOUCHDOWN")

        # 3 ana sınıfa standartlaştırma: SAFE, HARD, CRASH
        if "CRASH" in raw_status:
            cls_label = "CRASH"
        elif "HARD" in raw_status:
            cls_label = "HARD"
        else:
            cls_label = "SAFE"

        X_list.append([alt, vh, vv, slope, tri, solar, dte, total_mass])
        y_reg_list.append([score, fuel_cons])
        y_cls_list.append(cls_label)

    return (
        np.array(X_list, dtype=np.float64),
        np.array(y_reg_list, dtype=np.float64),
        np.array(y_cls_list, dtype=object),
        feature_names,
    )


def clear_database(db_path: Optional[Union[str, Path]] = None) -> bool:
    """Veritabanındaki tüm simülasyon kayıtlarını temizler."""
    init_db(db_path)
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                conn.execute("DELETE FROM landing_trials;")
            return True
        finally:
            conn.close()


def seed_initial_trials(count: int = 50, db_path: Optional[Union[str, Path]] = None) -> int:
    """
    Veritabanına gerçekçi Ay iniş denemeleri (Monte Carlo varyasyonları) tohumlar.
    Eğer veritabanında zaten kayıt varsa mevcut kayıtları korur ve belirtilen sayıda yeni ekler.
    """
    import random
    from backend.config import CANDIDATES_JSON_PATH

    init_db(db_path)

    # Aday bölgeleri yükle
    candidates = []
    if CANDIDATES_JSON_PATH.exists():
        try:
            with open(CANDIDATES_JSON_PATH, "r", encoding="utf-8") as f:
                c_data = json.load(f)
                for c in c_data.get("candidate_sites", []):
                    candidates.append({
                        "id": c["site_id"],
                        "lat": c["coordinates"]["latitude_deg"],
                        "lon": c["coordinates"]["longitude_deg"],
                        "slope": c["topography"]["slope_deg"],
                        "tri": c["topography"]["roughness_tri_m"],
                        "solar": c["environment_and_visibility"]["solar_illumination_pct"],
                        "dte": c["environment_and_visibility"]["dte_visibility_pct"],
                    })
        except Exception:
            pass

    if not candidates:
        candidates = [
            {"id": "MALAPERT_MASSIF", "lat": -86.04, "lon": 2.7, "slope": 3.1, "tri": 0.22, "solar": 92.4, "dte": 94.6},
            {"id": "CONNECTING_RIDGE_EXT", "lat": -89.47, "lon": -136.2, "slope": 4.85, "tri": 0.29, "solar": 85.2, "dte": 79.8},
            {"id": "LEIBNITZ_BETA", "lat": -85.82, "lon": 29.5, "slope": 3.65, "tri": 0.26, "solar": 88.6, "dte": 91.4},
            {"id": "DE_GERLACHE_RIM_1", "lat": -88.71, "lon": -68.7, "slope": 3.82, "tri": 0.26, "solar": 82.5, "dte": 81.0},
            {"id": "DE_GERLACHE_RIM_2", "lat": -88.35, "lon": -67.8, "slope": 4.15, "tri": 0.28, "solar": 80.4, "dte": 84.2},
            {"id": "AMUNDSEN_RIM", "lat": -84.45, "lon": 85.6, "slope": 3.95, "tri": 0.27, "solar": 81.5, "dte": 85.0},
            {"id": "NOBILE_RIM_2", "lat": -85.28, "lon": 36.15, "slope": 4.35, "tri": 0.31, "solar": 79.8, "dte": 82.5},
            {"id": "DE_GERLACHE_KOCHER", "lat": -85.78, "lon": -123.35, "slope": 4.95, "tri": 0.34, "solar": 77.2, "dte": 79.5},
            {"id": "HAWORTH", "lat": -87.87, "lon": -5.1, "slope": 5.8, "tri": 0.41, "solar": 68.5, "dte": 71.0},
            {"id": "SITE_ALPHA", "lat": -89.78, "lon": 120.4, "slope": 3.8, "tri": 0.28, "solar": 89.2, "dte": 92.5},
            {"id": "SITE_BETA", "lat": -89.72, "lon": 94.1, "slope": 5.2, "tri": 0.42, "solar": 81.5, "dte": 88.0},
            {"id": "SITE_GAMMA", "lat": -89.84, "lon": 145.8, "slope": 7.1, "tri": 0.65, "solar": 74.0, "dte": 79.5},
            {"id": "SITE_DELTA", "lat": -89.91, "lon": 0.0, "slope": 12.8, "tri": 1.15, "solar": 18.0, "dte": 32.0},
            {"id": "SHOEMAKER_RIM", "lat": -86.68, "lon": 48.28, "slope": 3.85, "tri": 0.28, "solar": 87.5, "dte": 91.0},
            {"id": "FAUSTINI_RIM", "lat": -86.49, "lon": 80.72, "slope": 1.15, "tri": 0.24, "solar": 89.0, "dte": 94.5},
            {"id": "CABEUS_RIDGE", "lat": -83.80, "lon": -41.07, "slope": 2.65, "tri": 0.26, "solar": 88.2, "dte": 92.0},
            {"id": "SLATER_RIM", "lat": -84.68, "lon": 160.41, "slope": 2.95, "tri": 0.27, "solar": 84.0, "dte": 88.5},
            {"id": "SVERDRUP_RIM", "lat": -89.45, "lon": -137.31, "slope": 1.45, "tri": 0.25, "solar": 91.5, "dte": 93.0},
        ]

    inserted = 0
    now_ts = datetime.now(timezone.utc).timestamp()

    for i in range(count):
        site = random.choice(candidates)
        # Stokastik başlangıç koşulları
        init_alt = random.uniform(2800.0, 3600.0)
        init_vh = random.uniform(55.0, 75.0)
        init_vv = random.uniform(-35.0, -22.0)

        slope_var = max(0.5, site["slope"] + random.gauss(0.0, 0.8))
        tri_var = max(0.05, site["tri"] + random.gauss(0.0, 0.08))
        solar_var = min(100.0, max(0.0, site["solar"] + random.gauss(0.0, 3.0)))
        dte_var = min(100.0, max(0.0, site["dte"] + random.gauss(0.0, 3.0)))

        # Simülasyon sonucu üret (fiziksel gerçekçi)
        # Delta bölgesi gibi zorlu arazilerde daha fazla kaza/sert iniş riski
        prob_hard = 0.10 if site["id"] != "SITE_DELTA" else 0.45
        prob_crash = 0.04 if site["id"] != "SITE_DELTA" else 0.35

        r_outcome = random.random()
        if r_outcome < prob_crash:
            status = "CRASH"
            status_label_tr = "Kritik Kaza (Gövde Devrilmesi / Aşırı Hız)"
            touchdown_vz = random.uniform(4.8, 8.5)
            touchdown_vh = random.uniform(1.2, 3.5)
            tilt = random.uniform(14.0, 26.0)
            fuel_rem_pct = random.uniform(0.0, 4.0)
            fuel_cons_kg = random.uniform(2650.0, 2800.0)
            score = random.uniform(15.0, 38.0)
        elif r_outcome < (prob_crash + prob_hard):
            status = "HARD_LANDING"
            status_label_tr = "Sert İniş (Riskli Temas)"
            touchdown_vz = random.uniform(2.6, 4.2)
            touchdown_vh = random.uniform(0.6, 1.8)
            tilt = random.uniform(6.0, 11.5)
            fuel_rem_pct = random.uniform(4.0, 8.5)
            fuel_cons_kg = random.uniform(2500.0, 2680.0)
            score = random.uniform(55.0, 74.0)
        else:
            status = "PERFECT_TOUCHDOWN" if random.random() > 0.35 else "SAFE_TOUCHDOWN"
            status_label_tr = "Mükemmel Yumuşak İniş" if status == "PERFECT_TOUCHDOWN" else "Güvenli Temas"
            touchdown_vz = random.uniform(0.4, 1.4)
            touchdown_vh = random.uniform(0.05, 0.38)
            tilt = random.uniform(0.8, 4.2)
            fuel_rem_pct = random.uniform(8.0, 18.5)
            fuel_cons_kg = random.uniform(2250.0, 2550.0)
            score = random.uniform(84.0, 98.5)

        flight_time = random.uniform(85.0, 115.0)
        item_ts = datetime.fromtimestamp(now_ts - (count - i) * 60, timezone.utc).isoformat()

        record = {
            "trial_id": f"SEED-{1000 + i}",
            "timestamp": item_ts,
            "target_site_id": site["id"],
            "target_lat": site["lat"],
            "target_lon": site["lon"],
            "target_norm_x": 0.5 + (site["lon"] / 360.0),
            "target_norm_y": 0.5 + (site["lat"] + 90.0) / 180.0,
            "initial_alt_m": round(init_alt, 1),
            "initial_vh_ms": round(init_vh, 1),
            "initial_vv_ms": round(init_vv, 1),
            "final_alt_m": 0.0,
            "final_vh_ms": round(touchdown_vh, 2),
            "final_vv_ms": round(-touchdown_vz, 2),
            "touchdown_vxy_ms": round(touchdown_vh, 2),
            "touchdown_vz_ms": round(touchdown_vz, 2),
            "tilt_deg": round(tilt, 1),
            "fuel_rem_pct": round(fuel_rem_pct, 1),
            "fuel_consumed_kg": round(fuel_cons_kg, 1),
            "flight_time_s": round(flight_time, 1),
            "slope_deg": round(slope_var, 2),
            "roughness_tri_m": round(tri_var, 3),
            "solar_illum_pct": round(solar_var, 1),
            "dte_vis_pct": round(dte_var, 1),
            "total_score": round(score, 1),
            "status": status,
            "status_label_tr": status_label_tr,
        }

        insert_trial(record, db_path=db_path)
        inserted += 1

    return inserted
