"""LUNA SIGHT: Ay İniş Alanı Navigatörü - K4 Streamlit uygulaması.

Gerekli paketler (requirements.txt içinde pinli):
    streamlit, pandas, numpy, plotly

Çalıştırma:
    python -m venv .venv
    .venv\\Scripts\\python.exe -m pip install -r requirements-dev.txt
    .venv\\Scripts\\python.exe -m streamlit run app\\app.py

Mimari notu
-----------
Uygulama üç katmandan oluşur:

1. Veri katmanı  : `load_site_series()` -> veri sözleşmesine uygun DataFrame.
   K1/K2/K3 modülleri hazır olduğunda `_external_series()` fonksiyonu gerçek
   veriyi döndürür; şu an analitik sentetik veri üretilir ve `test_fixture`
   olarak etiketlenir (docs/DATA_CONTRACT.md).
2. Hesaplama     : `compute_metrics()` -> görünürlük süreleri ve pencere metrikleri.
3. Sunum         : Plotly ufuk grafiği + zaman çizelgesi + A/B panelleri.

Veri sözleşmesi alanları (docs/DATA_CONTRACT.md) birebir korunur; gerçek
modüller bağlandığında arayüz kodu değişmeden çalışır.
"""

from __future__ import annotations

import datetime as dt
import importlib
import json
import math
import os
import sys
import textwrap
import zlib
from dataclasses import dataclass, fields, replace
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# `src/` düzenindeki bilimsel modüller (K1/K2/K3) birleştiğinde içe aktarılabilsin.
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
HORIZON_DIR = REPO_ROOT / "data" / "derived"
if SRC_DIR.is_dir() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

APP_TITLE = "LUNA SIGHT: Ay İniş Alanı Navigatörü"
APP_SUBTITLE = (
    "Ay'ın güney kutbundaki aday iniş bölgelerini, Güneş ve Dünya'nın yerel ufka "
    "göre konumları üzerinden karşılaştırır."
)

VISIBLE = "visible"
BLOCKED = "blocked"
UNCERTAIN = "uncertain"

# Veri sözleşmesindeki zorunlu alanlar (docs/DATA_CONTRACT.md)
DATA_CONTRACT_COLUMNS = [
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
]

NUMERIC_COLUMNS = [
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
]

# K3 motoru bağlandığında gelen isteğe bağlı tanılama sütunları.
OPTIONAL_DIAGNOSTIC_COLUMNS = [
    "sun_margin_deg",
    "earth_margin_deg",
    "joint_margin_deg",
    "sun_reason",
    "earth_reason",
    "joint_reason",
]

# Kenar çubuğundaki örnekleme seçenekleri: etiket -> dakika
SAMPLE_STEP_OPTIONS: dict[str, int] = {
    "15 dakika": 15,
    "30 dakika": 30,
    "1 saat": 60,
    "3 saat": 180,
    "6 saat": 360,
}

STATE_COLORS = {
    VISIBLE: "#3ddc97",
    BLOCKED: "#4a5169",
    UNCERTAIN: "#f5b942",
}

STATE_LABELS = {
    VISIBLE: "Görünür",
    BLOCKED: "Engellenmiş",
    UNCERTAIN: "Belirsiz",
}

# Veri kaynağı modları
SOURCE_REAL = "real"
SOURCE_MOCK = "mock"
SOURCE_LABELS = {
    SOURCE_REAL: "Gerçek Ekip Çıktısı (K2/K3)",
    SOURCE_MOCK: "Çevrimdışı Mock Modu (Test Verisi)",
}

# Ekip çıktıları
OUTPUT_K2_DIR = REPO_ROOT / "outputs" / "k2"
OUTPUT_K3_DIR = REPO_ROOT / "outputs" / "k3"


# Batarya gösterimi: oranlar bir araç tasarımından türetilmemiştir. Tek yerde
# tutulur ki grafik ile kullanıcıya gösterilen varsayım metni ayrışmasın.
BATTERY_START_SOC = 90.0
BATTERY_CHARGE_PER_HOUR = 4.0
BATTERY_DISCHARGE_PER_HOUR = 1.5
BATTERY_RESERVE_SOC = 20.0
BATTERY_ASSUMPTIONS = (
    f"Batarya eğrisi **gösterim amaçlıdır, güç bütçesi değildir.** Varsayımlar: "
    f"başlangıç %{BATTERY_START_SOC:.0f} şarj, Güneş görünürken "
    f"+%{BATTERY_CHARGE_PER_HOUR:.1f}/saat, görünmezken "
    f"−%{BATTERY_DISCHARGE_PER_HOUR:.1f}/saat, kritik rezerv "
    f"%{BATTERY_RESERVE_SOC:.0f}. Bu oranlar bir araç tasarımından veya kaynaktan "
    f"türetilmemiştir; yalnızca görünürlük penceresinin enerji üzerindeki etkisini "
    f"görselleştirir. Gerçek güç bütçesi panel verimi, termal yük ve görev yük "
    f"profilini gerektirir."
)


def repo_relative(path: Path) -> str:
    """Yolu depo köküne göre göster.

    Arayüzde ve indirilen çıktıda mutlak yerel yol görünmemeli: ekran
    görüntüsünde geliştiricinin dosya sistemini sızdırır ve başka bir
    makinede tekrar üretilemez.
    """
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


@dataclass(frozen=True)
class SiteSpec:
    """Aday iniş bölgesi tanımı.

    Sentetik modda analitik ufuk/Güneş parametreleri kullanılır. Gerçek ekip
    çıktısı modunda bu alanlar kullanılmaz; ufuk profili ``horizon_csv``
    dosyasından, görünürlük ise K3 CSV'sinden gelir.
    """

    site_id: str
    name: str
    latitude_deg: float
    longitude_deg_east: float
    sun_offset_deg: float = 0.0
    sun_amplitude_deg: float = 0.0
    sun_phase: float = 0.0
    earth_phase: float = 0.0
    earth_az_deg: float = 0.0
    horizon_base_deg: float = 0.0
    horizon_amp1_deg: float = 0.0
    horizon_phase1_deg: float = 0.0
    horizon_amp2_deg: float = 0.0
    horizon_phase2_deg: float = 0.0
    horizon_csv: Path | None = None
    origin: str = "synthetic"

    @property
    def coordinates(self) -> str:
        return f"{self.latitude_deg:.2f}°, {self.longitude_deg_east:+.2f}° (doğu-pozitif)"

    @property
    def label(self) -> str:
        return f"{self.site_id} · {self.name}" if self.origin == "real" else self.name


# Koordinatlar yaklaşıktır; nihai değerler K2 (LOLA) doğrulamasından gelecektir.
SITES: dict[str, SiteSpec] = {
    "shackleton": SiteSpec(
        site_id="SITE-SHACKLETON",
        name="Shackleton Krater Kenarı",
        latitude_deg=-89.90,
        longitude_deg_east=0.00,
        sun_offset_deg=1.7,
        sun_amplitude_deg=1.8,
        sun_phase=0.35,
        earth_phase=0.20,
        earth_az_deg=6.0,
        horizon_base_deg=2.0,
        horizon_amp1_deg=1.4,
        horizon_phase1_deg=40.0,
        horizon_amp2_deg=0.7,
        horizon_phase2_deg=130.0,
    ),
    "malapert": SiteSpec(
        site_id="SITE-MALAPERT",
        name="Malapert Massif",
        latitude_deg=-86.00,
        longitude_deg_east=0.00,
        sun_offset_deg=2.6,
        sun_amplitude_deg=5.0,
        sun_phase=2.10,
        earth_phase=1.40,
        earth_az_deg=352.0,
        horizon_base_deg=2.2,
        horizon_amp1_deg=1.6,
        horizon_phase1_deg=250.0,
        horizon_amp2_deg=0.8,
        horizon_phase2_deg=20.0,
    ),
    "de_gerlache": SiteSpec(
        site_id="SITE-DE-GERLACHE",
        name="de Gerlache Krater Kenarı",
        latitude_deg=-88.50,
        longitude_deg_east=87.10,
        sun_offset_deg=1.4,
        sun_amplitude_deg=2.8,
        sun_phase=4.20,
        earth_phase=2.60,
        earth_az_deg=318.0,
        horizon_base_deg=6.8,
        horizon_amp1_deg=4.1,
        horizon_phase1_deg=160.0,
        horizon_amp2_deg=2.0,
        horizon_phase2_deg=60.0,
    ),
}

SITE_NAMES = {key: spec.name for key, spec in SITES.items()}
DEFAULT_SITE_A = "shackleton"
DEFAULT_SITE_B = "malapert"


def _read_json(path: Path) -> dict:
    """JSON dosyasını okur; hata durumunda boş sözlük döndürür."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - bozuk/eksik çıktı
        return {}
    return payload if isinstance(payload, dict) else {}


def _discover_real_sites() -> dict[str, SiteSpec]:
    """``outputs/k3/*_summary.json`` dosyalarından gerçek bölgeleri keşfeder.

    Koordinat ve özet K3'ten, bölge adı ile ufuk profili K2 çıktılarından
    alınır. Hiç dosya yoksa boş sözlük döner ve arayüz mock moda düşer.
    """
    discovered: dict[str, SiteSpec] = {}
    for summary_path in sorted(OUTPUT_K3_DIR.glob("*_summary.json")):
        payload = _read_json(summary_path)
        site_id = str(payload.get("site_id") or "").strip()
        coordinate = payload.get("coordinate") or {}
        try:
            latitude = float(coordinate["latitude_deg"])
            longitude = float(coordinate["longitude_deg_east"])
        except (KeyError, TypeError, ValueError):
            continue
        if not site_id:
            continue

        k2_summary = _read_json(OUTPUT_K2_DIR / f"{site_id}_summary.json")
        if not k2_summary:
            k2_summary = _read_json(OUTPUT_K2_DIR / f"{site_id}_summary_20000m.json")
        name = str(k2_summary.get("site_name") or site_id)

        horizon_csv = OUTPUT_K2_DIR / f"{site_id}_horizon_4000m.csv"
        if not horizon_csv.is_file():
            horizon_csv = OUTPUT_K2_DIR / f"{site_id}_horizon_2000m.csv"
        if not horizon_csv.is_file():
            horizon_csv = OUTPUT_K2_DIR / f"{site_id}_horizon_20000m.csv"
        discovered[site_id] = SiteSpec(
            site_id=site_id,
            name=name,
            latitude_deg=latitude,
            longitude_deg_east=longitude,
            horizon_csv=horizon_csv if horizon_csv.is_file() else None,
            origin="real",
        )
    return discovered


REAL_SITES = _discover_real_sites()
REAL_AVAILABLE = bool(REAL_SITES)
DEFAULT_REAL_SITE_A = "Site01" if "Site01" in REAL_SITES else next(iter(REAL_SITES), "")
DEFAULT_REAL_SITE_B = (
    "Site04"
    if "Site04" in REAL_SITES
    else next((key for key in REAL_SITES if key != DEFAULT_REAL_SITE_A), "")
)


def _site_catalog(source_mode: str) -> dict[str, SiteSpec]:
    """Seçili moda göre bölge kataloğu (gerçek çıktı yoksa mock)."""
    if source_mode == SOURCE_REAL and REAL_SITES:
        return REAL_SITES
    return SITES


def _site_defaults(source_mode: str) -> tuple[str, str]:
    """Moda göre varsayılan A/B bölgeleri."""
    if source_mode == SOURCE_REAL and REAL_SITES:
        return (
            DEFAULT_REAL_SITE_A,
            DEFAULT_REAL_SITE_B or DEFAULT_REAL_SITE_A,
        )
    return DEFAULT_SITE_A, DEFAULT_SITE_B


# Sentetik model sabitleri (gerçek efemeris yerine kullanılan analitik yaklaşım)
SOLAR_SYNODIC_DAYS = 29.53059
EARTH_LIBRATION_DAYS = 27.21222
TERRAIN_JITTER_DEG = 0.12

# Gerçek çıktı okunamazsa kullanılan analitik yedek parametreleri. Bu değerler
# Shackleton kenarı için kalibre edilmiş sentetik profildir; yalnızca çevrimdışı
# modda ve `test_fixture` etiketiyle kullanılır.
SYNTHETIC_FALLBACK_PARAMS: dict[str, float] = {
    "sun_offset_deg": 1.7,
    "sun_amplitude_deg": 1.8,
    "sun_phase": 0.35,
    "earth_phase": 0.20,
    "earth_az_deg": 6.0,
    "horizon_base_deg": 2.0,
    "horizon_amp1_deg": 1.4,
    "horizon_phase1_deg": 40.0,
    "horizon_amp2_deg": 0.7,
    "horizon_phase2_deg": 130.0,
}


# ---------------------------------------------------------------------------
# Veri katmanı
# ---------------------------------------------------------------------------


def _terrain_horizon_deg(azimuth_deg: np.ndarray, site: SiteSpec) -> np.ndarray:
    """Azimuta bağlı topoğrafik ufuk yüksekliği (derece, >= 0)."""
    az = np.deg2rad(azimuth_deg)
    horizon = (
        site.horizon_base_deg
        + site.horizon_amp1_deg * np.cos(az - np.deg2rad(site.horizon_phase1_deg))
        + site.horizon_amp2_deg * np.cos(2.0 * (az - np.deg2rad(site.horizon_phase2_deg)))
    )
    return np.clip(horizon, 0.0, None)


def generate_synthetic_series(
    site: SiteSpec,
    start_utc: dt.datetime,
    days: int,
    step_minutes: int,
) -> pd.DataFrame:
    """Analitik (sentetik) görünürlük zaman serisi üretir.

    Amaç: K1/K2/K3 modülleri hazır olmadan arayüzü uçtan uca çalıştırmak.
    Üretilen tüm satırlar `quality_flag=test_fixture` ile işaretlenir; bu veri
    bilimsel sonuç olarak sunulmaz.
    """
    total_hours = days * 24
    step_hours = step_minutes / 60.0
    t_hours = np.arange(0.0, total_hours + 1e-9, step_hours)
    t_days = t_hours / 24.0

    # Sabit tohum: aynı bölge ve parametreler her çalıştırmada aynı veriyi üretir.
    rng = np.random.default_rng(zlib.crc32(site.site_id.encode("utf-8")))

    # Güneş: kutba yakın enlemde küçük genlikli mevsimsel yükseklik değişimi.
    sun_alt = site.sun_offset_deg + site.sun_amplitude_deg * np.sin(
        2.0 * np.pi * t_days / SOLAR_SYNODIC_DAYS + site.sun_phase
    )
    sun_az = np.mod(360.0 * (t_days / SOLAR_SYNODIC_DAYS) + 35.0, 360.0)

    # Dünya: librasyon kaynaklı küçük yükseklik salınımı, sabit azimut çevresi.
    earth_alt = 6.5 * np.sin(2.0 * np.pi * t_days / EARTH_LIBRATION_DAYS + site.earth_phase)
    earth_az = np.mod(
        site.earth_az_deg
        + 4.0 * np.sin(2.0 * np.pi * t_days / EARTH_LIBRATION_DAYS + site.earth_phase),
        360.0,
    )

    # Küçük ve deterministik gürültü: gerçek verideki ölçüm saçılımını taklit eder.
    sun_alt = sun_alt + rng.normal(0.0, TERRAIN_JITTER_DEG, size=t_hours.shape)
    earth_alt = earth_alt + rng.normal(0.0, TERRAIN_JITTER_DEG, size=t_hours.shape)

    horizon_sun = _terrain_horizon_deg(sun_az, site)
    horizon_earth = _terrain_horizon_deg(earth_az, site)

    sun_visible = sun_alt > horizon_sun
    earth_visible = earth_alt > horizon_earth
    joint_visible = sun_visible & earth_visible

    start_ts = pd.Timestamp(start_utc)
    start_ts = (
        start_ts.tz_localize("UTC") if start_ts.tzinfo is None else start_ts.tz_convert("UTC")
    )
    timestamps = start_ts + pd.to_timedelta(t_hours, unit="h")

    frame = pd.DataFrame(
        {
            "site_id": site.site_id,
            "latitude_deg": site.latitude_deg,
            "longitude_deg_east": site.longitude_deg_east,
            "timestamp_utc": timestamps,
            "sun_az_deg": sun_az,
            "sun_alt_deg": sun_alt,
            "earth_az_deg": earth_az,
            "earth_alt_deg": earth_alt,
            "terrain_horizon_sun_deg": horizon_sun,
            "terrain_horizon_earth_deg": horizon_earth,
            "sun_visible": np.where(sun_visible, VISIBLE, BLOCKED),
            "earth_visible": np.where(earth_visible, VISIBLE, BLOCKED),
            "joint_visible": np.where(joint_visible, VISIBLE, BLOCKED),
            "quality_flag": "test_fixture",
            "source_id": "synthetic-analytic",
            "source_version": "v0",
            "model_id": f"lunar-analytic-{site.site_id.lower()}",
            "parameters": json.dumps(
                {"days": days, "step_minutes": step_minutes, "model": "synthetic-v0"},
                ensure_ascii=False,
            ),
        }
    )
    return frame


def normalize_contract_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Dışarıdan gelen DataFrame'i veri sözleşmesine göre doğrular ve düzenler.

    K1/K2/K3 modüllerinden gelen çıktılar bu fonksiyondan geçirilerek
    arayüze bağlanır. Eksik alan varsa sessizce geçilmez, açık hata verilir.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Görünürlük verisi pandas.DataFrame olmalıdır.")

    missing = [column for column in DATA_CONTRACT_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError("Veri sözleşmesinde eksik alan(lar): " + ", ".join(missing))

    normalized = frame.loc[
        :,
        DATA_CONTRACT_COLUMNS + [c for c in OPTIONAL_DIAGNOSTIC_COLUMNS if c in frame.columns],
    ].copy()
    normalized["timestamp_utc"] = pd.to_datetime(
        normalized["timestamp_utc"], utc=True, errors="raise"
    )
    for column in NUMERIC_COLUMNS:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    for column in ("sun_visible", "earth_visible", "joint_visible"):
        normalized[column] = (
            normalized[column].astype(str).str.strip().str.lower().replace({"nan": UNCERTAIN})
        )

    normalized = normalized.sort_values("timestamp_utc").reset_index(drop=True)
    return normalized


def _import_optional(dotted_name: str):
    """Modülü içe aktarır; yoksa ya da içe aktarma hata verirse ``None`` döner."""
    try:
        return importlib.import_module(dotted_name)
    except Exception:  # noqa: BLE001 - isteğe bağlı bilimsel modül
        return None


def _callable_in(module, names: tuple[str, ...]):
    """Modülde ilk bulunan çağrılabilir niteliği döndürür."""
    if module is None:
        return None
    for name in names:
        candidate = getattr(module, name, None)
        if callable(candidate):
            return candidate
    return None


def _module_implemented(dotted_name: str) -> bool:
    """Modül gerçekten uygulanmış mı (boş klasörler namespace paketi sayılır)."""
    directory = SRC_DIR.joinpath(*dotted_name.split("."))
    if not any(directory.rglob("*.py")):
        return False
    return _import_optional(dotted_name) is not None


def _engine_available() -> bool:
    """K3 görünürlük motoru (``evaluate_series``) kullanılabilir mi."""
    module = _import_optional("luna_sight.visibility")
    return callable(getattr(module, "evaluate_series", None))


def _k1_series(
    site: SiteSpec,
    start_utc: dt.datetime,
    days: int,
    step_minutes: int,
) -> pd.DataFrame | None:
    """K1 efemerisi varsa veri sözleşmesi sütunlarını taşıyan çerçeve döndürür.

    Kabul edilen arayüz (K1 ile kararlaştırılacak):
        luna_sight.ephemeris.build_series(site_id, start_utc, days, step_minutes)
    Dönen çerçeve en az ``timestamp_utc``, ``sun_az_deg``, ``sun_alt_deg``,
    ``earth_az_deg``, ``earth_alt_deg`` alanlarını içermelidir. K1 yoksa ya da
    hata verirse ``None`` döner ve sentetik hatta düşülür.
    """
    module = _import_optional("luna_sight.ephemeris")
    builder = _callable_in(module, ("build_series", "build_site_series"))
    if builder is None:
        return None
    try:
        frame = builder(site.site_id, start_utc, days, step_minutes)
    except Exception:  # noqa: BLE001 - K1 hatasında sentetiğe düş
        return None
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    required = {
        "timestamp_utc",
        "sun_az_deg",
        "sun_alt_deg",
        "earth_az_deg",
        "earth_alt_deg",
    }
    if not required.issubset(frame.columns):
        return None
    return frame


def _load_horizon_csv(path: Path) -> tuple[np.ndarray, np.ndarray] | None:
    """K2 ufuk profil CSV'sini (``azimuth_deg``, ``horizon_deg``) okur."""
    try:
        table = pd.read_csv(path)
        azimuths = pd.to_numeric(table["azimuth_deg"], errors="coerce").to_numpy(dtype=float)
        horizons = pd.to_numeric(table["horizon_deg"], errors="coerce").to_numpy(dtype=float)
    except Exception:  # noqa: BLE001 - bozuk/eksik profil dosyası
        return None
    if azimuths.size < 2 or not np.isfinite(azimuths).all():
        return None
    return azimuths, horizons


def _horizon_arrays(site: SiteSpec) -> tuple[np.ndarray, np.ndarray, str]:
    """Ufuk profilini K2 çıktısından ya da analitik modelden üretir.

    Sıra: ``site.horizon_csv`` (gerçek K2 çıktısı) → ``$LUNA_SIGHT_HORIZON_DIR``
    → ``data/derived`` → analitik profil. Dönen etiket ``K2`` ya da
    ``synthetic`` olur ve çıktının ``parameters`` alanına yazılır.
    """
    if site.horizon_csv is not None:
        loaded = _load_horizon_csv(site.horizon_csv)
        if loaded is not None:
            return loaded[0], loaded[1], "K2"

    names = [f"horizon_{site.site_id.lower()}.csv", f"horizon_{site.site_id}.csv"]
    directories = [HORIZON_DIR]
    override = os.environ.get("LUNA_SIGHT_HORIZON_DIR")
    if override:
        directories.insert(0, Path(override))

    for directory in directories:
        for name in names:
            path = directory / name
            if not path.is_file():
                continue
            loaded = _load_horizon_csv(path)
            if loaded is not None:
                return loaded[0], loaded[1], "K2"

    azimuths = np.arange(0.0, 360.0, 1.0)
    return azimuths, _terrain_horizon_deg(azimuths, site), "synthetic"


def _site_horizon_profile(site: SiteSpec) -> tuple[np.ndarray, np.ndarray, str]:
    """Polar grafik için ufuk profili (gerçek K2 dosyası varsa ondan)."""
    return _horizon_arrays(site)


def _build_samples(frame: pd.DataFrame, module, sample_type):
    """Veri sözleşmesi çerçevesini K3 ``Sample`` listesine çevirir."""
    records: list[dict[str, object]] = []
    for row in frame.to_dict(orient="records"):
        record = dict(row)
        record["timestamp_utc"] = pd.Timestamp(record["timestamp_utc"]).to_pydatetime()
        records.append(record)

    sample_from_row = getattr(module, "sample_from_row", None)
    if callable(sample_from_row):
        return [sample_from_row(record) for record in records]

    allowed = {field.name for field in fields(sample_type)}
    return [
        sample_type(**{key: value for key, value in record.items() if key in allowed})
        for record in records
    ]


def _merge_parameters(raw: object, extra: dict[str, object]) -> str:
    """Mevcut ``parameters`` JSON'unu motor bilgisiyle birleştirir."""
    payload: object
    try:
        payload = json.loads(raw) if isinstance(raw, str) and raw.strip() else {}
    except json.JSONDecodeError:
        payload = {"raw": raw}
    if not isinstance(payload, dict):
        payload = {"raw": payload}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _evaluate_with_engine(frame: pd.DataFrame, site: SiteSpec) -> pd.DataFrame | None:
    """K3 motoru varsa çerçeveyi ``evaluate_series`` ile sınıflandırır.

    K3 API'si (``k3/visibility-engine``):
    ``Sample``, ``HorizonProfileLookup``, ``VisibilityConfig`` ve
    ``evaluate_series(samples, profile, config) -> list[SampleResult]``.
    Sonuçlar ``SampleResult.as_row()`` ile veri sözleşmesine çevrilir;
    ``uncertain`` durumu ve gerekçe kodları korunur. Motor yoksa ya da hata
    verirse ``None`` döner ve çağıran taraf sentetik sınıflandırmada kalır.
    """
    module = _import_optional("luna_sight.visibility")
    if module is None or not callable(getattr(module, "evaluate_series", None)):
        return None

    sample_type = getattr(module, "Sample", None)
    profile_type = getattr(module, "HorizonProfileLookup", None)
    config_type = getattr(module, "VisibilityConfig", None)
    if sample_type is None or profile_type is None or config_type is None:
        return None

    try:
        config = config_type()
        azimuths, horizons, horizon_source = _horizon_arrays(site)
        profile = profile_type(azimuths, horizons)
        samples = _build_samples(frame, module, sample_type)
        results = module.evaluate_series(samples, profile, config)
        rows = [result.as_row() for result in results]
    except Exception:  # noqa: BLE001 - entegrasyon hatasında sentetiğe düş
        return None

    if not rows:
        return None

    evaluated = pd.DataFrame(rows)
    engine_info = {
        "engine": "K3:evaluate_series",
        "engine_config": (config.as_dict() if callable(getattr(config, "as_dict", None)) else {}),
        "horizon_profile": horizon_source,
    }
    evaluated["parameters"] = evaluated["parameters"].map(
        lambda raw: _merge_parameters(raw, engine_info)
    )
    evaluated["source_id"] = evaluated["source_id"].astype(str) + "+K3"
    normalized = normalize_contract_frame(evaluated)
    return normalized


class RealDataError(RuntimeError):
    """Gerçek ekip çıktısı okunamadığında fırlatılır (mock moda düşülür)."""


@st.cache_data(show_spinner=False)
def load_real_site_data(site_id: str) -> pd.DataFrame:
    """``outputs/k3/<site_id>_visibility.csv`` dosyasını okur (önbellekli).

    Dosya yoksa, zorunlu sütunlar eksikse ya da zaman damgaları okunamıyorsa
    :class:`RealDataError` fırlatır; çağıran taraf güvenli mock moda düşer.
    """
    path = OUTPUT_K3_DIR / f"{site_id}_visibility.csv"
    if not path.is_file():
        raise RealDataError(f"Gerçek çıktı bulunamadı: {path}")

    try:
        frame = pd.read_csv(path)
    except Exception as exc:  # bozuk dosya
        raise RealDataError(f"{path} okunamadı: {exc}") from exc

    missing = [column for column in DATA_CONTRACT_COLUMNS if column not in frame.columns]
    if missing:
        raise RealDataError(f"{path}: eksik sütunlar: {', '.join(missing)}")

    try:
        frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True, errors="raise")
    except Exception as exc:  # bozuk zaman damgası
        raise RealDataError(f"{path}: zaman damgaları okunamadı: {exc}") from exc

    frame = frame.sort_values("timestamp_utc").reset_index(drop=True)
    frame.attrs["data_path"] = repo_relative(path)
    return frame


def _slice_real_frame(
    frame: pd.DataFrame,
    start_utc: dt.datetime,
    days: int,
    step_minutes: int,
) -> pd.DataFrame:
    """Gerçek seriyi istenen pencereye kırpar ve istenen adıma örnekler.

    İstenen başlangıç kullanılabilir pencerenin dışındaysa başlangıç verinin
    ilk anına çekilir; pencere veri sonunu aşarsa kırpılır. Bu durumlar
    ``attrs`` üzerinden arayüze bildirilir.
    """
    if frame.empty:
        raise RealDataError("Gerçek seri boş.")

    start = pd.Timestamp(start_utc)
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    start = start.tz_convert("UTC")

    available_start = frame["timestamp_utc"].iloc[0]
    available_end = frame["timestamp_utc"].iloc[-1]
    step = pd.Timedelta(minutes=step_minutes)

    clamped = start < available_start or start > available_end - step
    if clamped:
        start = available_start
    requested_end = start + pd.Timedelta(days=days)
    truncated = requested_end > available_end
    end = min(requested_end, available_end)

    window = frame.loc[(frame["timestamp_utc"] >= start) & (frame["timestamp_utc"] <= end)].copy()
    if len(window) < 2:
        raise RealDataError(f"Seçilen pencere için yeterli gerçek örnek yok ({len(window)} satır).")

    offsets_min = (
        (window["timestamp_utc"] - window["timestamp_utc"].iloc[0]).dt.total_seconds() / 60.0
    ).to_numpy()
    nearest = np.round(offsets_min / step_minutes) * step_minutes
    keep = np.isclose(offsets_min, nearest, atol=2.5)
    window = window.loc[keep].reset_index(drop=True)

    window.attrs["data_source"] = SOURCE_REAL
    window.attrs["data_path"] = frame.attrs.get("data_path", "")
    window.attrs["window_clamped"] = bool(clamped)
    window.attrs["window_truncated"] = bool(truncated)
    window.attrs["available_start"] = available_start.isoformat()
    window.attrs["available_end"] = available_end.isoformat()
    return window


@st.cache_data(show_spinner=False)
def load_site_series(
    site_id: str,
    start_iso: str,
    days: int,
    step_minutes: int,
    source_mode: str = SOURCE_REAL,
) -> pd.DataFrame:
    """Tek giriş noktası: gerçek ekip çıktısı → K1/K3 → sentetik yedek.

    ``source_mode=real`` iken ``outputs/k3/<site_id>_visibility.csv`` okunur.
    Dosya yoksa ya da bozuksa uygulama çökmez: ``attrs["fallback_reason"]``
    ile işaretlenmiş sentetik çerçeve döner (Güvenli Çevrimdışı Mod).
    ``source_mode=mock`` iken doğrudan analitik sentetik hat kullanılır.
    """
    start_utc = dt.datetime.fromisoformat(start_iso)
    catalog = _site_catalog(source_mode)
    site = catalog.get(site_id) or SITES[site_id]

    if source_mode == SOURCE_REAL:
        try:
            real = load_real_site_data(site.site_id)
            sliced = _slice_real_frame(real, start_utc, days, step_minutes)
            normalized = normalize_contract_frame(sliced)
            normalized.attrs.update(sliced.attrs)
            normalized.attrs["data_source"] = SOURCE_REAL
            return normalized
        except Exception as exc:  # noqa: BLE001 - her hata mock moda düşer
            reason = str(exc) or exc.__class__.__name__
            fallback_site = replace(site, **SYNTHETIC_FALLBACK_PARAMS)
            frame = generate_synthetic_series(fallback_site, start_utc, days, step_minutes)
            normalized = normalize_contract_frame(frame)
            normalized.attrs["data_source"] = SOURCE_MOCK
            normalized.attrs["fallback_reason"] = reason
            return normalized

    frame = _k1_series(site, start_utc, days, step_minutes)
    if frame is None:
        frame = generate_synthetic_series(site, start_utc, days, step_minutes)

    evaluated = _evaluate_with_engine(frame, site)
    if evaluated is not None:
        frame = evaluated
    normalized = normalize_contract_frame(frame)
    normalized.attrs["data_source"] = SOURCE_MOCK
    return normalized


# ---------------------------------------------------------------------------
# Hesaplama katmanı
# ---------------------------------------------------------------------------


@dataclass
class SiteMetrics:
    """Bir bölgenin özet görünürlük metrikleri."""

    total_hours: float
    sun_hours: float
    earth_hours: float
    joint_hours: float
    longest_earth_window: float
    longest_joint_window: float
    longest_earth_blackout: float
    optimal_landing_time: str
    sun_share: float
    earth_share: float
    joint_uncertain_share: float
    terrain_blocked_share: float
    horizon_mean: float
    horizon_max: float
    horizon_max_az: float


def _longest_run_hours(flags: pd.Series, step_hours: float) -> float:
    """True değerlerinin en uzun kesintisiz süresini saat cinsinden döndürür."""
    if flags.empty or not flags.any():
        return 0.0
    run_id = (flags != flags.shift()).cumsum()
    lengths = flags.groupby(run_id).sum() * step_hours
    return float(lengths.max())


def _find_optimal_landing_start(frame: pd.DataFrame, step_hours: float) -> str:
    """En uzun kesintisiz ortak görünürlük (Güneş+Dünya) penceresinin başlangıç zamanını bulur."""
    joint = frame["joint_visible"].eq(VISIBLE)
    if joint.empty or not joint.any():
        return "Pencere bulunamadı"
    run_id = (joint != joint.shift()).cumsum()
    lengths = joint.groupby(run_id).sum() * step_hours
    best_run_id = lengths.idxmax()
    if lengths[best_run_id] <= 0:
        return "Pencere bulunamadı"
    first_idx = frame[run_id == best_run_id].index[0]
    ts = pd.to_datetime(frame.loc[first_idx, "timestamp_utc"])
    return ts.strftime("%d %b %Y %H:%M UTC")


def compute_metrics(frame: pd.DataFrame, step_minutes: int) -> SiteMetrics:
    """Veri sözleşmesine uygun çerçeveden görünürlük metriklerini üretir."""
    step_hours = step_minutes / 60.0
    total_hours = len(frame) * step_hours
    if total_hours <= 0:
        raise ValueError("Metrik hesaplamak için en az bir zaman adımı gerekir.")

    sun = frame["sun_visible"].eq(VISIBLE)
    earth = frame["earth_visible"].eq(VISIBLE)
    joint = frame["joint_visible"].eq(VISIBLE)
    joint_uncertain = frame["joint_visible"].eq(UNCERTAIN)

    # İletişimsizlik kesintisi (Blackout): Dünya'nın engellenmiş olduğu kesintisiz en uzun süre
    earth_blocked = frame["earth_visible"].eq(BLOCKED)
    longest_earth_blackout = _longest_run_hours(earth_blocked, step_hours)
    optimal_landing = _find_optimal_landing_start(frame, step_hours)

    horizon = frame["terrain_horizon_sun_deg"]
    max_index = horizon.idxmax()

    # Güneş geometrik olarak ufkun üzerindeyken topoğrafya tarafından kesilen oran.
    # Belirsiz (uncertain) örnekler engellenmiş sayılmaz.
    above_geometric = frame["sun_alt_deg"] > 0.0
    blocked_by_terrain = above_geometric & frame["sun_visible"].eq(BLOCKED)

    return SiteMetrics(
        total_hours=total_hours,
        sun_hours=float(sun.sum() * step_hours),
        earth_hours=float(earth.sum() * step_hours),
        joint_hours=float(joint.sum() * step_hours),
        longest_earth_window=_longest_run_hours(earth, step_hours),
        longest_joint_window=_longest_run_hours(joint, step_hours),
        longest_earth_blackout=longest_earth_blackout,
        optimal_landing_time=optimal_landing,
        sun_share=float(sun.mean()),
        earth_share=float(earth.mean()),
        joint_uncertain_share=float(joint_uncertain.mean()),
        terrain_blocked_share=float(blocked_by_terrain.mean()),
        horizon_mean=float(horizon.mean()),
        horizon_max=float(horizon.max()),
        horizon_max_az=float(frame.loc[max_index, "sun_az_deg"]),
    )


# ---------------------------------------------------------------------------
# Görselleştirme katmanı
# ---------------------------------------------------------------------------


def build_horizon_figure(
    frame: pd.DataFrame,
    current_index: int,
    site: SiteSpec,
    horizon_profile: tuple[np.ndarray, np.ndarray] | None = None,
) -> go.Figure:
    """Güneş ve Dünya'nın azimut/yükseklik değişimini polar düzlemde çizer.

    Dönüşüm: r = 90 - yükseklik. Böylece ufuk (0°) dış çemberde, zenit (90°)
    merkezde yer alır. ``horizon_profile`` verilirse (K2 çıktısı) gerçek
    topoğrafik ufuk çizgisi, verilmezse analitik profil çizilir.
    """
    current = frame.iloc[current_index]

    def radius(altitude: pd.Series | float) -> pd.Series | float:
        return 90.0 - altitude

    figure = go.Figure()

    # Görünürlük yolu (görev penceresi boyunca)
    figure.add_trace(
        go.Scatterpolar(
            r=radius(frame["sun_alt_deg"]),
            theta=frame["sun_az_deg"],
            mode="lines",
            name="Güneş yolu (☀)",
            line={"color": "#f5b942", "width": 1.2},
            opacity=0.45,
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatterpolar(
            r=radius(frame["earth_alt_deg"]),
            theta=frame["earth_az_deg"],
            mode="lines",
            name="Dünya yolu (◆)",
            line={"color": "#5aa9ff", "width": 1.2},
            opacity=0.45,
            hoverinfo="skip",
        )
    )

    # Topoğrafik ufuk profili: gerçek K2 çıktısı varsa ondan.
    if horizon_profile is not None:
        horizon_theta, horizon_deg = horizon_profile
        horizon_source = "K2 ufuk profili"
    else:
        horizon_theta = np.linspace(0.0, 360.0, 361)
        horizon_deg = _terrain_horizon_deg(horizon_theta, site)
        horizon_source = "Analitik ufuk (mock)"
    horizon_radius = 90.0 - np.asarray(horizon_deg, dtype=float)
    figure.add_trace(
        go.Scatterpolar(
            r=horizon_radius,
            theta=np.asarray(horizon_theta, dtype=float),
            mode="lines",
            name=f"Topoğrafik ufuk · {horizon_source}",
            line={"color": "#9aa4bf", "width": 2.2, "dash": "dot"},
            hovertemplate=(
                "Azimut %{theta:.0f}°<br>Ufuk yüksekliği %{customdata:.1f}°<extra></extra>"
            ),
            customdata=90.0 - horizon_radius,
        )
    )

    # Seçilen andaki konumlar
    sun_state = current["sun_visible"]
    earth_state = current["earth_visible"]
    figure.add_trace(
        go.Scatterpolar(
            r=[radius(current["sun_alt_deg"])],
            theta=[current["sun_az_deg"]],
            mode="markers+text",
            name=f"Güneş (şu an: {STATE_LABELS.get(sun_state, sun_state)})",
            marker={
                "symbol": "circle",
                "size": 16,
                "color": STATE_COLORS.get(sun_state, "#f5b942"),
                "line": {"color": "#0b1020", "width": 2},
            },
            text=["☀"],
            textfont={"size": 13, "color": "#0b1020"},
            hovertemplate=(
                "Güneş<br>Azimut %{theta:.1f}°<br>Yükseklik %{customdata:.1f}°<extra></extra>"
            ),
            customdata=[current["sun_alt_deg"]],
        )
    )
    figure.add_trace(
        go.Scatterpolar(
            r=[radius(current["earth_alt_deg"])],
            theta=[current["earth_az_deg"]],
            mode="markers+text",
            name=f"Dünya (şu an: {STATE_LABELS.get(earth_state, earth_state)})",
            marker={
                "symbol": "diamond",
                "size": 15,
                "color": STATE_COLORS.get(earth_state, "#5aa9ff"),
                "line": {"color": "#0b1020", "width": 2},
            },
            text=["◆"],
            textfont={"size": 12, "color": "#0b1020"},
            hovertemplate=(
                "Dünya<br>Azimut %{theta:.1f}°<br>Yükseklik %{customdata:.1f}°<extra></extra>"
            ),
            customdata=[current["earth_alt_deg"]],
        )
    )

    figure.update_layout(
        height=520,
        margin={"l": 50, "r": 50, "t": 40, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#e8ecf8"},
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.12, "x": 0},
        polar={
            "bgcolor": "rgba(20,26,46,0.65)",
            "radialaxis": {
                "range": [0, 95],
                "angle": 90,
                "tickvals": [0, 30, 60, 90],
                "ticktext": ["90°", "60°", "30°", "0°"],
                "gridcolor": "rgba(154,164,191,0.25)",
                "title": {"text": "Yükseklik", "font": {"size": 11}},
            },
            "angularaxis": {
                "direction": "clockwise",
                "rotation": 90,
                "tickvals": [0, 90, 180, 270],
                "ticktext": ["K", "D", "G", "B"],
                "gridcolor": "rgba(154,164,191,0.25)",
            },
        },
    )
    return figure


def build_visibility_intervals(frame: pd.DataFrame, step_minutes: int) -> pd.DataFrame:
    """Ardışık durumları tek aralığa indirger (zaman çizelgesi için)."""
    step = pd.Timedelta(minutes=step_minutes)
    channels = [
        ("Güneş", "sun_visible"),
        ("Dünya", "earth_visible"),
        ("Ortak", "joint_visible"),
    ]
    records: list[dict[str, object]] = []

    for channel, column in channels:
        states = frame[column].tolist()
        times = frame["timestamp_utc"].tolist()
        run_start = 0
        for index in range(1, len(states) + 1):
            if index == len(states) or states[index] != states[run_start]:
                records.append(
                    {
                        "Kanal": channel,
                        "Durum": STATE_LABELS.get(states[run_start], states[run_start]),
                        "Başlangıç": times[run_start],
                        "Bitiş": times[index - 1] + step,
                    }
                )
                run_start = index
    return pd.DataFrame(records)


def build_timeline_figure(frame: pd.DataFrame, step_minutes: int, title: str) -> go.Figure:
    """Görünür / engellenmiş aralıkları renkli zaman çizelgesi olarak çizer."""
    intervals = build_visibility_intervals(frame, step_minutes)
    figure = px.timeline(
        intervals,
        x_start="Başlangıç",
        x_end="Bitiş",
        y="Kanal",
        color="Durum",
        color_discrete_map={
            "Görünür": STATE_COLORS[VISIBLE],
            "Engellenmiş": STATE_COLORS[BLOCKED],
            "Belirsiz": STATE_COLORS[UNCERTAIN],
        },
        category_orders={"Kanal": ["Güneş", "Dünya", "Ortak"]},
    )
    figure.update_yaxes(autorange="reversed", title=None)
    figure.update_layout(
        title={"text": title, "font": {"size": 14}},
        height=250,
        barmode="overlay",
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,26,46,0.5)",
        font={"color": "#e8ecf8"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        xaxis={"title": None, "gridcolor": "rgba(154,164,191,0.2)"},
    )
    return figure


def build_battery_figure(frame: pd.DataFrame, step_minutes: int, title: str) -> go.Figure:
    """Güneşlenme durumuna göre batarya seviyesini (% SoC) gösterim amaçlı çizer.

    Oranlar bir araç tasarımından türetilmemiştir; `BATTERY_ASSUMPTIONS`
    metninde açıkça beyan edilir ve grafiğin altında kullanıcıya gösterilir.
    Bu eğri güç bütçesi değildir.
    """
    step_hours = step_minutes / 60.0
    charge_rate_per_hr = BATTERY_CHARGE_PER_HOUR
    discharge_rate_per_hr = BATTERY_DISCHARGE_PER_HOUR

    soc_values = []
    current_soc = BATTERY_START_SOC

    for is_sun_vis in frame["sun_visible"].eq(VISIBLE):
        if is_sun_vis:
            current_soc = min(100.0, current_soc + charge_rate_per_hr * step_hours)
        else:
            current_soc = max(0.0, current_soc - discharge_rate_per_hr * step_hours)
        soc_values.append(current_soc)

    timestamps = pd.to_datetime(frame["timestamp_utc"])
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=soc_values,
            mode="lines",
            name="Batarya Seviyesi (% SoC)",
            line={"color": "#3ddc97", "width": 2.5},
            fill="tozeroy",
            fillcolor="rgba(61, 220, 151, 0.12)",
        )
    )
    # %20 Kritik rezerv çizgisi
    fig.add_hline(
        y=BATTERY_RESERVE_SOC,
        line_dash="dot",
        line_color="#ff5c5c",
        annotation_text=f"Kritik Rezerv (%{BATTERY_RESERVE_SOC:.0f})",
        annotation_position="bottom right",
    )
    fig.update_layout(
        title={"text": f"{title} · Batarya Enerji Simülasyonu", "font": {"size": 13}},
        height=200,
        margin={"l": 10, "r": 10, "t": 35, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,26,46,0.5)",
        font={"color": "#e8ecf8"},
        yaxis={"title": "Şarj (%)", "range": [0, 105], "gridcolor": "rgba(154,164,191,0.2)"},
        xaxis={"gridcolor": "rgba(154,164,191,0.2)"},
    )
    return fig


def lunar_surface_distance_km(
    lat1_deg: float, lon1_deg: float, lat2_deg: float, lon2_deg: float
) -> float:
    """İki Ay yüzeyi koordinatı arasındaki büyük daire mesafesini (km) hesaplar.

    Ay ortalama yarıçapı: R ≈ 1737.4 km.
    """
    r_moon_km = 1737.4
    phi1, phi2 = math.radians(lat1_deg), math.radians(lat2_deg)
    dphi = math.radians(lat2_deg - lat1_deg)
    dlam = math.radians(lon2_deg - lon1_deg)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return r_moon_km * c


def build_south_pole_map(spec_a: SiteSpec, spec_b: SiteSpec) -> go.Figure:
    """Ay Güney Kutbu (90°S) merkezli 2D radar / kutupsal harita üretir."""
    km_per_deg = (math.pi / 180.0) * 1737.4  # ~30.323 km/deg
    r_a = max(0.0, (90.0 + spec_a.latitude_deg) * km_per_deg)
    r_b = max(0.0, (90.0 + spec_b.latitude_deg) * km_per_deg)

    dist_km = lunar_surface_distance_km(
        spec_a.latitude_deg,
        spec_a.longitude_deg_east,
        spec_b.latitude_deg,
        spec_b.longitude_deg_east,
    )

    fig = go.Figure()

    # 1. Güney Kutbu (90°S) Merkez Noktası
    fig.add_trace(
        go.Scatterpolar(
            r=[0],
            theta=[0],
            mode="markers+text",
            name="Ay Güney Kutbu (90°S)",
            text=["Ay Güney Kutbu (90°S)"],
            textposition="top center",
            marker={"size": 13, "color": "#ffffff", "symbol": "cross"},
            hovertemplate="<b>Ay Güney Kutbu (90.00°S)</b><extra></extra>",
        )
    )

    # 2. Bölge A Noktası
    fig.add_trace(
        go.Scatterpolar(
            r=[r_a],
            theta=[spec_a.longitude_deg_east],
            mode="markers+text",
            name=f"Bölge A: {spec_a.site_id}",
            text=[f"A: {spec_a.site_id}"],
            textposition="bottom right",
            marker={"size": 15, "color": "#4FC3F7", "symbol": "circle"},
            hovertemplate=(
                f"<b>Bölge A: {spec_a.name}</b><br>"
                f"ID: {spec_a.site_id}<br>"
                f"Enlem: {spec_a.latitude_deg:.4f}°<br>"
                f"Boylam: {spec_a.longitude_deg_east:.4f}°<br>"
                f"Kutuptan Mesafe: {r_a:.1f} km<extra></extra>"
            ),
        )
    )

    # 3. Bölge B Noktası
    fig.add_trace(
        go.Scatterpolar(
            r=[r_b],
            theta=[spec_b.longitude_deg_east],
            mode="markers+text",
            name=f"Bölge B: {spec_b.site_id}",
            text=[f"B: {spec_b.site_id}"],
            textposition="bottom left",
            marker={"size": 15, "color": "#FFB74D", "symbol": "diamond"},
            hovertemplate=(
                f"<b>Bölge B: {spec_b.name}</b><br>"
                f"ID: {spec_b.site_id}<br>"
                f"Enlem: {spec_b.latitude_deg:.4f}°<br>"
                f"Boylam: {spec_b.longitude_deg_east:.4f}°<br>"
                f"Kutuptan Mesafe: {r_b:.1f} km<extra></extra>"
            ),
        )
    )

    # 4. A ile B arasındaki bağlantı çizgisi (inter-site mesafe)
    fig.add_trace(
        go.Scatterpolar(
            r=[r_a, r_b],
            theta=[spec_a.longitude_deg_east, spec_b.longitude_deg_east],
            mode="lines",
            name=f"A–B Mesafesi (~{dist_km:.1f} km)",
            line={"color": "#FF5252", "width": 2.5, "dash": "dash"},
            hovertemplate=f"Bölgeler Arası Mesafe: <b>{dist_km:.1f} km</b><extra></extra>",
        )
    )

    max_r = max(25.0, max(r_a, r_b) * 1.3)
    fig.update_layout(
        title={
            "text": f"Ay Güney Kutup Bölgesi Radar Haritası (A–B Mesafesi: ~{dist_km:.1f} km)",
            "font": {"size": 14},
        },
        polar={
            "radialaxis": {
                "visible": True,
                "range": [0, max_r],
                "gridcolor": "rgba(154,164,191,0.2)",
                "linecolor": "rgba(154,164,191,0.4)",
                "ticksuffix": " km",
                "tickfont": {"color": "#9aa4bf", "size": 10},
            },
            "angularaxis": {
                "gridcolor": "rgba(154,164,191,0.2)",
                "linecolor": "rgba(154,164,191,0.4)",
                "tickfont": {"color": "#9aa4bf", "size": 10},
                "direction": "counterclockwise",
                "rotation": 0,
            },
            "bgcolor": "rgba(20,26,46,0.5)",
        },
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#e8ecf8"},
        height=450,
        margin={"l": 30, "r": 30, "t": 50, "b": 30},
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.15, "x": 0.05},
    )
    return fig


def generate_flight_briefing_card(
    spec: SiteSpec,
    metrics: SiteMetrics,
    start_utc: dt.datetime,
    days: int,
    min_sun_req: int,
    max_blackout_tol: int,
) -> str:
    """Astronotlar ve görev kontrol için tek tıkla indirilebilir uçuş brifing kartı."""
    end_utc = start_utc + dt.timedelta(days=days)
    sun_pct = metrics.sun_share * 100.0
    sun_pass = sun_pct >= min_sun_req
    blackout_pass = metrics.longest_earth_blackout <= max_blackout_tol
    overall_status = (
        "GO (UÇUŞA UYGUN)" if (sun_pass and blackout_pass) else "NO-GO (KORUMA / İPTAL)"
    )

    pass_sun_str = "[PASS - SAĞLANDI]" if sun_pass else "[FAIL - YETERSİZ]"
    pass_blk_str = "[PASS - SAĞLANDI]" if blackout_pass else "[FAIL - TOLERANS AŞILDI]"
    badge_str = (
        "🟢 GO (Tüm Kriterler Karşılandı)"
        if (sun_pass and blackout_pass)
        else "🔴 NO-GO (Kritik Risk Tespit Edildi)"
    )

    t_start = start_utc.strftime("%Y-%m-%d %H:%M")
    t_end = end_utc.strftime("%Y-%m-%d %H:%M")
    blk = metrics.longest_earth_blackout
    coord = f"Enlem {spec.latitude_deg:.4f}°, Boylam {spec.longitude_deg_east:.4f}°"

    return f"""# 🌙 LUNA SIGHT · ASTRONOT UÇUŞ BRİFİNG KARTI (FLIGHT BRIEFING CARD)
**Görev ID:** ARTEMIS-LS-{spec.site_id}
**Zaman Penceresi:** {t_start} UTC → {t_end} UTC ({days} Gün)
**Nihai Değerlendirme:** {overall_status}

---

## 1. İNİŞ BÖLGESİ KİMLİK KARTI
- **Bölge Adı:** {spec.name} ({spec.site_id})
- **Koordinat:** {coord} (Doğu-Pozitif)
- **Topografya Veri Tabanı:** {spec.origin.upper()} (LOLA DEM)

## 2. GÖREV KISITLARI & DEĞERLENDİRME (SUHAIL STANDARDI)
- **Minimum Güneşlenme:** Hedef ≥ %{min_sun_req} | Gerçekleşen: %{sun_pct:.1f} → {pass_sun_str}
- **Maks. Kesinti:** Limit ≤ {max_blackout_tol} sa | Gerçekleşen: {blk:.1f} sa → {pass_blk_str}
- **Görev Durumu Rozeti:** {badge_str}

## 3. TAKTİK İNİŞ VE OPERASYON PENCERESİ
- **Önerilen Taktik İniş Anı (Optimal Landing):** {metrics.optimal_landing_time}
- **En Uzun Kesintisiz Şarj & Doğrudan İletişim:** {metrics.longest_joint_window:.1f} saat
- **Toplam Güneş Aydınlanma Süresi:** {metrics.sun_hours:.1f} saat
- **Toplam Dünya Doğrudan Görüş Süresi:** {metrics.earth_hours:.1f} saat
- **Eşzamanlı (Güneş + Dünya) Görüş Süresi:** {metrics.joint_hours:.1f} saat
- **Maksimum İletişimsizlik (Kör Nokta):** {metrics.longest_earth_blackout:.1f} saat

## 4. TOPOĞRAFİK RİSK & ENGEL ÖZETİ
- **Ortalama Ufuk Yüksekliği:** {metrics.horizon_mean:.1f}°
- **En Yüksek Tepe/Engel:** {metrics.horizon_max:.1f}° (Azimut: {metrics.horizon_max_az:.0f}°)
- **Krater/Dağ Gölgeleme Kaybı:** %{metrics.terrain_blocked_share * 100:.0f}

## 5. ASTRONOT PROSEDÜR VE EMNİYET TALİMATLARI
1. İniş anında batarya şarj seviyesini en az %80 SoC'de tutun.
2. {blk:.1f} saatlik kör nokta öncesinde Dünya'ya telemetri iletin.
3. Kör nokta sırasında otonom sistemleri batarya tasarruf moduna alın.

*Bu brifing kartı LUNA SIGHT K4 Navigasyon Sistemi tarafından otomatik olarak üretilmiştir.*
"""


# ---------------------------------------------------------------------------
# Arayüz katmanı
# ---------------------------------------------------------------------------


def inject_theme() -> None:
    """NASA temasına yakın koyu uzay görünümü için ince CSS katmanı."""
    st.markdown(
        """
        <style>
        /* Tasarım belirteçleri. Bileşenlerde ham hex yerine bunlar kullanılır;
           tek yerden değiştirilir ve açık/koyu ayrımı tutarlı kalır. */
        :root {
            --ls-space-900: #070a14;   /* en derin zemin */
            --ls-space-800: #0b1020;   /* sayfa zemini */
            --ls-space-700: #141a2e;   /* yüzey */
            --ls-nasa-blue: #0b3d91;   /* NASA mavisi: yüzey ve kenarlık */
            --ls-azure:     #5aa9ff;   /* etkileşim rengi (koyu zeminde okunur) */
            --ls-azure-dim: rgba(90,169,255,0.16);
            --ls-text:      #e8ecf8;
            --ls-text-dim:  #b9c3dc;
            --ls-ok:        #3ddc97;
            --ls-warn:      #f5b942;
            --ls-danger:    #fc3d21;   /* NASA kırmızısı: yalnızca engel/hata */
            --ls-radius:    12px;
        }
        /* Teknik/panel karakteri için Fira ailesi; yüklenemezse sistem yazı
           tipine düşer, metin görünmez kalmaz. */
        html, body, [class*="css"], [data-testid="stAppViewContainer"] {
            font-family: "Fira Sans", "Segoe UI", system-ui, sans-serif;
            -webkit-font-smoothing: antialiased;
        }
        code, pre, [data-testid="stMetricValue"] {
            font-family: "Fira Code", "Cascadia Mono", ui-monospace, monospace;
        }
        /* Sayı sütunları kaydıkça zıplamasın. */
        [data-testid="stMetricValue"], .ls-verdict-value {
            font-variant-numeric: tabular-nums;
        }
        /* Karar bandı: jürinin ilk saniyede okuması gereken tek cümle. */
        .ls-verdict {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.9rem 1.6rem;
            padding: 0.85rem 1.1rem;
            margin: 0 0 1rem 0;
            border-radius: var(--ls-radius);
            border: 1px solid var(--ls-azure-dim);
            border-left: 3px solid var(--ls-azure);
            background: linear-gradient(
                90deg, rgba(11,61,145,0.35) 0%, rgba(20,26,46,0.55) 60%
            );
        }
        .ls-verdict-kicker {
            font-size: 0.68rem;
            letter-spacing: 0.2em;
            text-transform: uppercase;
            color: var(--ls-azure);
        }
        .ls-verdict-text {font-size: 1.02rem; color: var(--ls-text); margin: 0.1rem 0 0 0;}
        .ls-verdict-text strong {color: #ffffff;}
        .ls-verdict-stats {display: flex; gap: 1.4rem; margin-left: auto;}
        .ls-verdict-stat {text-align: right;}
        .ls-verdict-label {
            display: block;
            font-size: 0.66rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--ls-text-dim);
        }
        .ls-verdict-value {font-size: 1.25rem; font-weight: 600; color: var(--ls-text);}
        .ls-verdict-value.is-blocked {color: var(--ls-danger);}
        @media (max-width: 900px) {
            .ls-verdict-stats {margin-left: 0; width: 100%; justify-content: space-between;}
        }
        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2rem;
            max-width: 1500px;
        }
        .ls-hero {
            background: radial-gradient(
                1200px 400px at 15% -20%, #1b2a5e 0%, #0b1020 55%, #070a14 100%
            );
            border: 1px solid rgba(90,169,255,0.25);
            border-radius: 16px;
            padding: 1.4rem 1.6rem 1.2rem 1.6rem;
            margin-bottom: 1.1rem;
        }
        .ls-kicker {
            font-size: 0.72rem;
            letter-spacing: 0.22em;
            text-transform: uppercase;
            color: #7fb4ff;
            margin-bottom: 0.35rem;
        }
        .ls-title {font-size: 2.05rem; line-height: 1.15; margin: 0 0 0.45rem 0; color: #f4f7ff;}
        .ls-sub {font-size: 0.95rem; color: #b9c3dc; margin: 0; max-width: 70ch;}
        .ls-chip {
            display: inline-block;
            padding: 0.15rem 0.6rem;
            margin: 0.55rem 0.35rem 0 0;
            border-radius: 999px;
            font-size: 0.72rem;
            letter-spacing: 0.04em;
            border: 1px solid rgba(90,169,255,0.35);
            color: #a9c8ff;
            background: rgba(90,169,255,0.08);
        }
        .ls-chip-warn {
            border-color: rgba(245,185,66,0.45);
            color: #f5c76a;
            background: rgba(245,185,66,0.08);
        }
        .ls-chip-ok {
            border-color: rgba(61,220,151,0.45);
            color: #7ff0bd;
            background: rgba(61,220,151,0.10);
        }
        .ls-step {
            display: inline-block;
            padding: 0.22rem 0.7rem;
            border-radius: 8px;
            background: rgba(90,169,255,0.12);
            border: 1px solid rgba(90,169,255,0.35);
            color: #a9c8ff;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.03em;
            margin: 0.2rem 0 0.7rem 0;
        }
        .ls-card {
            background: rgba(20,26,46,0.7);
            border: 1px solid rgba(90,169,255,0.16);
            border-radius: 10px;
            padding: 0.55rem 0.7rem;
            margin-bottom: 0.5rem;
        }
        .ls-card-title {font-size: 0.8rem; color: #e8ecf8; font-weight: 600;}
        .ls-card-path {
            font-size: 0.7rem;
            color: #7fb4ff;
            word-break: break-all;
            margin-top: 0.15rem;
        }
        .ls-card-detail {font-size: 0.7rem; color: #b9c3dc;}
        .ls-badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            margin: 0.25rem 0 0.65rem 0;
        }
        .ls-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            padding: 0.22rem 0.62rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.02em;
            border: 1px solid rgba(90,169,255,0.35);
            color: #a9c8ff;
            background: rgba(90,169,255,0.08);
        }
        .ls-badge-ok {
            border-color: rgba(61,220,151,0.45);
            color: #7ff0bd;
            background: rgba(61,220,151,0.10);
        }
        .ls-badge-warn {
            border-color: rgba(245,185,66,0.45);
            color: #f5c76a;
            background: rgba(245,185,66,0.08);
        }
        div[data-testid="stMetric"] {
            background: rgba(20,26,46,0.65);
            border: 1px solid rgba(90,169,255,0.16);
            border-radius: 12px;
            padding: 0.65rem 0.8rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(
    source_mode: str,
    engine_active: bool,
    fallback_reason: str | None = None,
) -> None:
    """Başlık ve durum rozetleri."""
    chips = []
    if source_mode == SOURCE_REAL:
        chips.append('<span class="ls-chip ls-chip-ok">K2/K3 ekip çıktısı · outputs/</span>')
    else:
        chips.append('<span class="ls-chip ls-chip-warn">Çevrimdışı mock · test_fixture</span>')
    chips.append('<span class="ls-chip">JPL Horizons · K1</span>')
    if engine_active:
        chips.append('<span class="ls-chip ls-chip-ok">Görünürlük motoru · K3 etkin</span>')
    else:
        chips.append('<span class="ls-chip">Görünürlük motoru · K3</span>')
    if fallback_reason:
        chips.append('<span class="ls-chip ls-chip-warn">Güvenli çevrimdışı mod</span>')
    st.markdown(
        f"""
        <div class="ls-hero">
            <div class="ls-kicker">NASA Space Apps Challenge · Artemis</div>
            <h1 class="ls-title">{APP_TITLE}</h1>
            <p class="ls-sub">{APP_SUBTITLE}</p>
            {"".join(chips)}
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def real_output_window() -> tuple[str, str] | None:
    """``outputs/k3`` özetlerinden gerçek çıktının zaman penceresini okur."""
    for path in sorted(OUTPUT_K3_DIR.glob("*_summary.json")):
        series = _read_json(path).get("series") or {}
        start = series.get("start_utc")
        end = series.get("end_utc")
        if start and end:
            return str(start), str(end)
    return None


def _file_card(title: str, path: Path, ok: bool, detail: str = "") -> str:
    """Bilimsel kaynak kartı için kısa HTML üretir."""
    icon = "✅" if ok else "⚠️"
    suffix = f"<br><span class='ls-card-detail'>{detail}</span>" if detail else ""
    return (
        f"<div class='ls-card'><div class='ls-card-title'>{icon} {title}</div>"
        f"<div class='ls-card-path'>{repo_relative(path)}</div>{suffix}</div>"
    )


def _integration_statuses() -> list[tuple[str, str, bool]]:
    """K1/K2/K3 modüllerinin gerçek entegrasyon durumunu döndürür.

    Durum, dosya sistemindeki gerçek modüllere bakılarak belirlenir; K1
    efemeris modülü depoya gelene kadar rozet yeşile dönmez.
    """
    return [
        ("K1", "JPL Horizons · Efemeris", _module_implemented("luna_sight.ephemeris")),
        ("K2", "LOLA DEM · Topoğrafya", _module_implemented("luna_sight.terrain")),
        ("K3", "Görünürlük ve Pencere Motoru", _engine_available()),
    ]


def _integration_badges_html() -> str:
    """K1/K2/K3 için yeşil/amber durum rozetlerini HTML olarak üretir."""
    items = []
    for code, name, ready in _integration_statuses():
        state = "Tam Entegre · Aktif" if ready else "Bekliyor · Sentetik"
        css = "ls-badge-ok" if ready else "ls-badge-warn"
        items.append(f"<span class='ls-badge {css}'>{code} · {name} · {state}</span>")
    return "<div class='ls-badge-row'>" + "".join(items) + "</div>"


def render_sidebar_controls() -> tuple[int, int, dt.datetime, str]:
    """Adım 2: veri kaynağı, görev süresi, örnekleme ve başlangıç zamanı."""
    st.sidebar.markdown(
        "<div class='ls-step'>2 · Görev parametreleri</div>", unsafe_allow_html=True
    )

    source_mode = st.sidebar.selectbox(
        "Veri Kaynağı",
        options=[SOURCE_REAL, SOURCE_MOCK],
        index=0 if REAL_AVAILABLE else 1,
        format_func=lambda key: SOURCE_LABELS[key],
        help=(
            "Gerçek ekip çıktısı: outputs/k3 altındaki K3 CSV'leri. "
            "Dosya yoksa uygulama çökmeden çevrimdışı mock moda düşer."
        ),
        key="source_mode",
    )
    if source_mode == SOURCE_REAL:
        st.sidebar.caption(f"Kaynak: `{repo_relative(OUTPUT_K3_DIR)}/<Site>_visibility.csv`")
        if not REAL_AVAILABLE:
            st.sidebar.warning("Gerçek çıktı bulunamadı; mock moda düşülecek.")
    else:
        st.sidebar.caption("Analitik sentetik hat · `quality_flag=test_fixture`")

    days = st.sidebar.slider(
        "Görev süresi (gün)",
        min_value=1,
        max_value=30,
        value=7,
        step=1,
        help="Varsayılan 7 gün. Gerçek çıktı 168 saatlik pencereyi kapsar.",
    )
    step_label = st.sidebar.selectbox(
        "Zaman örnekleme aralığı",
        options=list(SAMPLE_STEP_OPTIONS),
        index=2,
        help="Veri sözleşmesi varsayılanı 5 dakikadır; demo için 1 saat uygundur.",
    )
    step_minutes = SAMPLE_STEP_OPTIONS[step_label]

    default_start = dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0)
    if source_mode == SOURCE_REAL:
        window = real_output_window()
        if window is not None:
            default_start = dt.datetime.fromisoformat(window[0])

    start_utc = st.sidebar.datetime_input(
        "Görev başlangıcı (UTC)",
        value=default_start,
        step=dt.timedelta(hours=1),
        help="Tüm zamanlar UTC ve ISO 8601 biçimindedir.",
        key=f"start_{source_mode}",
    )
    # st.datetime_input saat dilimi bilgisi döndürmez; alan UTC olarak
    # etiketlendiği için naif değerler UTC kabul edilir.
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=dt.UTC)
    else:
        start_utc = start_utc.astimezone(dt.UTC)
    st.sidebar.caption(
        f"Pencere: {days} gün × {step_label} = {days * 24 * 60 // step_minutes} adım"
    )
    if source_mode == SOURCE_REAL:
        window = real_output_window()
        if window is not None:
            start_text = window[0][:16].replace("T", " ")
            end_text = window[1][:16].replace("T", " ")
            st.sidebar.caption(f"Gerçek çıktı aralığı: {start_text} → {end_text} UTC")
        st.sidebar.caption(
            "Pencere dışı seçimlerde başlangıç verinin ilk anına çekilir; "
            "veri sonu aşılırsa grafik kırpılır."
        )

    st.sidebar.divider()
    st.sidebar.subheader("Görev kısıtları (SUHAIL)")
    min_sun_req = st.sidebar.slider(
        "Min. Güneş İhtiyacı (%)",
        min_value=10,
        max_value=100,
        value=70,
        step=5,
        help="Aracın güneş panelleri için görev boyunca gereken minimum aydınlanma oranı.",
        key=f"min_sun_{source_mode}",
    )
    max_blackout_tol = st.sidebar.slider(
        "Maks. Telsiz Kesintisi Toleransı (saat)",
        min_value=0,
        max_value=72,
        value=24,
        step=2,
        help="Dünya ile kesintisiz kör nokta (blackout) süresinin izin verilen üst sınırı.",
        key=f"max_blackout_{source_mode}",
    )

    st.sidebar.divider()
    st.sidebar.subheader("Bilimsel kaynaklar")
    st.sidebar.markdown(_integration_badges_html(), unsafe_allow_html=True)
    k1_ready = _module_implemented("luna_sight.ephemeris")
    k2_ready = _module_implemented("luna_sight.terrain")
    k3_ready = _engine_available()
    st.sidebar.markdown(
        _file_card(
            "K1 · JPL Horizons efemerisi",
            SRC_DIR / "luna_sight" / "ephemeris",
            k1_ready,
            "Modül hazır. Görünürlük çıktıları bu modülün ürettiği "
            "Horizons serisiyle hesaplandı."
            if k1_ready
            else "Henüz yok; efemeris sentetik (test_fixture).",
        ),
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        _file_card(
            "K2 · LOLA DEM ufuk profili",
            OUTPUT_K2_DIR,
            k2_ready,
            "outputs/k2/*_horizon_4000m.csv (azimuth_deg, horizon_deg)",
        ),
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        _file_card(
            "K3 · Görünürlük motoru",
            OUTPUT_K3_DIR,
            k3_ready,
            "evaluate_series + outputs/k3/*_visibility.csv ve *_summary.json",
        ),
        unsafe_allow_html=True,
    )
    st.sidebar.caption("Veri sözleşmesi: `docs/DATA_CONTRACT.md` (UTC, doğu-pozitif, 3 durum)")

    with st.sidebar.expander("Yöntem ve sınırlar"):
        st.markdown(
            "**Gerçek çıktı modu:** K3 motorunun ürettiği `outputs/k3` CSV'leri "
            "(5 dk adım, 168 saat) okunur; topoğrafik ufuk `outputs/k2` "
            "profilinden gelir. Efemeris kaynağı, sürümü ve kalite bayrağı "
            'sabit metin değildir: her satırdan okunup "Veri ve kaynak" '
            "sekmesinde gösterilir.\n\n"
            "**Mock modu:** Güneş için 29,53 günlük sinodik dönem, Dünya için "
            "27,21 günlük librasyon salınımı ve azimuta bağlı analitik ufuk.\n\n"
            "Eksik veri görünür/engellenmiş sayılmaz; geçiş bandı `uncertain` "
            "olarak raporlanır. Bu ekran iniş güvenliği kararı vermez."
        )
    return days, step_minutes, start_utc, source_mode, min_sun_req, max_blackout_tol


def render_site_panel(
    column,
    label: str,
    spec: SiteSpec,
    metrics: SiteMetrics,
    compare: SiteMetrics,
    min_sun_req: int = 70,
    max_blackout_tol: int = 24,
    start_utc: dt.datetime | None = None,
    days: int = 7,
    source_mode: str = "mock",
) -> None:
    """Tek bir bölgenin metrik ve engel özetini sütuna çizer."""
    with column:
        source_note = "K2/LOLA ufuk profili" if spec.origin == "real" else "yaklaşık · mock"
        st.caption(f"Koordinat: {spec.coordinates} · {source_note}")

        # SUHAIL Kriter Uygunluk Rozeti
        sun_pct = metrics.sun_share * 100.0
        sun_pass = sun_pct >= min_sun_req
        blackout_pass = metrics.longest_earth_blackout <= max_blackout_tol
        if sun_pass and blackout_pass:
            st.success(
                f"🟢 **GÖREV İÇİN UYGUN (PASS)** · Güneş %{sun_pct:.0f} (Hedef ≥ %{min_sun_req}) · "
                f"Kesinti {metrics.longest_earth_blackout:.1f} sa (Limit ≤ {max_blackout_tol} sa)",
                icon="✅",
            )
        else:
            fails = []
            if not sun_pass:
                fails.append(f"Güneş %{sun_pct:.0f} < %{min_sun_req}")
            if not blackout_pass:
                fails.append(
                    f"Kesinti {metrics.longest_earth_blackout:.1f} sa > {max_blackout_tol} sa"
                )
            st.error(
                f"🔴 **GÖREV RİSKLİ (FAIL)** · Kriter İhlali: {', '.join(fails)}",
                icon="🚨",
            )

        sun_delta = metrics.sun_hours - compare.sun_hours
        earth_delta = metrics.earth_hours - compare.earth_hours
        joint_delta = metrics.joint_hours - compare.joint_hours
        joint_longest_delta = metrics.longest_joint_window - compare.longest_joint_window

        first, second = st.columns(2)
        first.metric(
            "Güneş görünürlük süresi",
            f"{metrics.sun_hours:.1f} sa",
            f"{sun_delta:+.1f} sa",
            help="Görev penceresinde Güneş'in topoğrafik ufkun üzerinde kaldığı toplam süre.",
            border=True,
        )
        second.metric(
            "Dünya doğrudan görüş penceresi",
            f"{metrics.earth_hours:.1f} sa",
            f"{earth_delta:+.1f} sa",
            help="Dünya'nın yerel ufka göre görüş hattında kaldığı toplam süre.",
            border=True,
        )

        third, fourth = st.columns(2)
        third.metric(
            "Ortak görünürlük",
            f"{metrics.joint_hours:.1f} sa",
            f"{joint_delta:+.1f} sa",
            help="Güneş ve Dünya'nın aynı anda görünür olduğu süre.",
            border=True,
        )
        fourth.metric(
            "En uzun Dünya penceresi",
            f"{metrics.longest_earth_window:.1f} sa",
            help="Kesintisiz en uzun Dünya görüş aralığı.",
            border=True,
        )

        # Artemis operasyonu için kritik: kesintisiz şarj + haberleşme penceresi ve blackout riski.
        fifth, sixth = st.columns(2)
        fifth.metric(
            "En Uzun Kesintisiz İletişim (Güneş+Dünya)",
            f"{metrics.longest_joint_window:.1f} sa",
            f"{joint_longest_delta:+.1f} sa",
            help=(
                "Güneş ve Dünya'nın aynı anda kesintisiz görünür kaldığı en uzun "
                "süre; Artemis için şarj ve doğrudan haberleşme penceresini belirler."
            ),
            border=True,
        )
        blackout_delta = metrics.longest_earth_blackout - compare.longest_earth_blackout
        sixth.metric(
            "Maksimum İletişimsizlik",
            f"{metrics.longest_earth_blackout:.1f} sa",
            f"{blackout_delta:+.1f} sa",
            delta_color="inverse",
            help="Dünya ile görüş hattının kesintisiz koptuğu en uzun kör nokta süresi.",
            border=True,
        )

        best_dur = metrics.longest_joint_window
        st.info(
            f"🎯 **Taktik İniş Önerisi:** {metrics.optimal_landing_time}\n\n"
            f"*(En uzun pencere: {best_dur:.1f} sa kesintisiz güç ve iletişim)*",
            icon="🚀",
        )

        if start_utc is not None:
            briefing_md = generate_flight_briefing_card(
                spec, metrics, start_utc, days, min_sun_req, max_blackout_tol
            )
            st.download_button(
                f"📋 {spec.site_id} Uçuş Kartını İndir (.md)",
                data=briefing_md.encode("utf-8"),
                file_name=f"flight_briefing_{spec.site_id.lower()}.md",
                mime="text/markdown",
                key=f"dl_flight_card_{spec.site_id}_{label}_{source_mode}",
                help="Astronotlar ve görev kontrol için taktik uçuş brifing kartı.",
            )

        with st.expander("Topoğrafik engel özeti", expanded=True):
            st.markdown(
                f"- Ortalama ufuk yüksekliği: **{metrics.horizon_mean:.1f}°**\n"
                f"- En yüksek engel: **{metrics.horizon_max:.1f}°** "
                f"(Güneş azimutu {metrics.horizon_max_az:.0f}°)\n"
                f"- Güneş geometrik olarak ufkun üzerindeyken topoğrafya "
                f"tarafından kesilen süre: **%{metrics.terrain_blocked_share * 100:.0f}**\n"
                f"- Geçiş bandı nedeniyle belirsiz ortak görünürlük: "
                f"**%{metrics.joint_uncertain_share * 100:.0f}**"
            )
            st.progress(
                min(max(metrics.sun_share, 0.0), 1.0),
                text=f"Güneş görünürlüğü: %{metrics.sun_share * 100:.0f}",
            )


def render_source_cards(spec_a: SiteSpec, spec_b: SiteSpec, frame_a: pd.DataFrame) -> None:
    """K1/K2/K3 kaynaklarını, dosya yollarını ve sözleşme durumunu gösterir."""
    k1_ready = _module_implemented("luna_sight.ephemeris")
    k2_ready = spec_a.horizon_csv is not None and spec_a.horizon_csv.is_file()
    k3_path = OUTPUT_K3_DIR / f"{spec_a.site_id}_visibility.csv"
    k3_ready = k3_path.is_file()
    contract_missing = [column for column in DATA_CONTRACT_COLUMNS if column not in frame_a.columns]

    st.markdown("**Entegrasyon durumu**")
    st.markdown(_integration_badges_html(), unsafe_allow_html=True)

    first, second, third = st.columns(3)
    with first:
        st.markdown(
            _file_card(
                "K1 · JPL Horizons",
                SRC_DIR / "luna_sight" / "ephemeris",
                k1_ready,
                "Görünürlük çıktıları bu modülün ürettiği Horizons serisiyle "
                "hesaplandı; köken her satırda taşınır."
                if k1_ready
                else "Modül yok: efemeris sentetik senaryo (test_fixture).",
            ),
            unsafe_allow_html=True,
        )
    with second:
        st.markdown(
            _file_card(
                "K2 · LOLA DEM ufuk profili",
                spec_a.horizon_csv or OUTPUT_K2_DIR,
                k2_ready,
                f"{spec_a.site_id}: {spec_a.name} · {spec_a.coordinates}",
            ),
            unsafe_allow_html=True,
        )
    with third:
        st.markdown(
            _file_card(
                "K3 · Görünürlük motoru",
                k3_path,
                k3_ready,
                f"A: `{spec_a.site_id}` · B: `{spec_b.site_id}` · 3 durum + gerekçe kodu",
            ),
            unsafe_allow_html=True,
        )

    status = "✅ tam" if not contract_missing else "⚠️ eksik"
    missing_text = (
        "tüm zorunlu alanlar mevcut"
        if not contract_missing
        else "eksik: " + ", ".join(contract_missing)
    )
    st.markdown(
        f"**Veri sözleşmesi** (`docs/DATA_CONTRACT.md`): {status} · "
        f"{len(DATA_CONTRACT_COLUMNS)} zorunlu alan · {missing_text}"
    )


#: 3B küre, derlenmiş bir React/three.js uygulamasıdır ve `static/moon/`
#: altından sunulur. Streamlit `enableStaticServing` ile bu klasörü
#: `/app/static/` yoluna açar, yani ayrı bir sunucu süreci gerekmez.
GLOBE_DIR = Path(__file__).resolve().parent / "static" / "moon"
GLOBE_URL = "/app/static/moon/index.html"
GLOBE_HEIGHT = 760


def render_verdict_band(
    spec_a: SiteSpec,
    metrics_a: SiteMetrics,
    spec_b: SiteSpec,
    metrics_b: SiteMetrics,
) -> None:
    """Karşılaştırmanın tek cümlelik sonucunu en üstte göster.

    Metin veriden türetilir, sabit yazılmaz: hangi bölgenin ortak görünürlük
    verdiği her koşuda yeniden hesaplanır. Böylece pencere veya bölge
    değiştiğinde cümle kendiliğinden doğru kalır.
    """
    pairs = [(spec_a, metrics_a), (spec_b, metrics_b)]
    best_spec, best = max(pairs, key=lambda item: item[1].joint_hours)
    other_spec, other = min(pairs, key=lambda item: item[1].joint_hours)

    if best.joint_hours <= 0:
        headline = (
            "Seçilen pencerede <strong>hiçbir aday</strong> Güneş ve Dünya'yı "
            "aynı anda görmüyor."
        )
    elif other.joint_hours <= 0:
        headline = (
            f"Doğrudan Dünya bağlantısı yalnızca <strong>{best_spec.label}</strong> "
            f"bölgesinde var: <strong>{best.joint_hours:.1f} saat</strong> ortak "
            f"görünürlük. {other_spec.label} bu pencerede hiç vermiyor."
        )
    else:
        headline = (
            f"<strong>{best_spec.label}</strong> ortak görünürlükte önde: "
            f"<strong>{best.joint_hours:.1f} saat</strong>, "
            f"{other_spec.label} {other.joint_hours:.1f} saat."
        )

    blocked = " is-blocked" if other.joint_hours <= 0 else ""
    verdict_html = textwrap.dedent(
        f"""
        <div class="ls-verdict notranslate" translate="no">
          <div>
            <span class="ls-verdict-kicker">Karşılaştırma sonucu</span>
            <p class="ls-verdict-text">{headline}</p>
          </div>
          <div class="ls-verdict-stats">
            <div class="ls-verdict-stat">
              <span class="ls-verdict-label">{best_spec.site_id} ortak</span>
              <span class="ls-verdict-value">{best.joint_hours:.1f} sa</span>
            </div>
            <div class="ls-verdict-stat">
              <span class="ls-verdict-label">{other_spec.site_id} ortak</span>
              <span class="ls-verdict-value{blocked}">{other.joint_hours:.1f} sa</span>
            </div>
          </div>
        </div>
        """
    ).strip()
    st.markdown(verdict_html, unsafe_allow_html=True)


def render_globe_tab() -> None:
    """Moon Trek dokulu 3B Ay küresini göm.

    Küre ile bu arayüz **aynı analizi** gösterir: her ikisi de JPL Horizons
    OBSERVER efemerisini (DE441, `coord@301`, AIRLESS) ve aynı iki aday
    bölgeyi kullanır; örnekleme 5 dakika, geçiş bandı 0.1 derece, gözlemci
    yüksekliği 2 metre. Sayılar bu yüzden birbirini tutar.
    """
    if not (GLOBE_DIR / "index.html").exists():
        st.warning(
            "3B küre varlıkları bulunamadı (`static/moon/`). Depo eksiksiz "
            "klonlanmadıysa bu sekme boş kalır; diğer sekmeler etkilenmez.",
            icon="⚠️",
        )
        return

    st.caption(
        "Taban harita: **NASA Moon Trek / LRO WAC** mozaiği. Kabartma ve normal "
        "haritaları **LRO LOLA** yükseklik modelinden türetilmiştir. Küre, bu "
        "arayüzle aynı efemeris ve aynı aday bölgeleri kullanır "
        "(JPL Horizons · DE441 · `coord@301` · AIRLESS)."
    )
    components.iframe(GLOBE_URL, height=GLOBE_HEIGHT, scrolling=False)
    st.caption(
        "Fare ile döndür, tekerlekle yakınlaş. Küre ayrı bir pencere gibi "
        "çalışır; kenar çubuğundaki seçimler bu görünümü değiştirmez."
    )


def render_data_tab(
    frame_a: pd.DataFrame,
    frame_b: pd.DataFrame,
    spec_a: SiteSpec,
    spec_b: SiteSpec,
) -> None:
    """Veri sözleşmesi çıktısını, kaynak kartlarını ve indirme seçeneğini gösterir."""
    st.subheader("Veri ve kaynak")
    render_source_cards(spec_a, spec_b, frame_a)
    st.divider()

    left, right = st.columns(2)
    for column, title, spec, frame in (
        (left, "Bölge A", spec_a, frame_a),
        (right, "Bölge B", spec_b, frame_b),
    ):
        with column:
            st.markdown(f"**{title}** · {spec.label} · {len(frame)} satır")
            st.dataframe(frame.head(50), height=260, hide_index=True)
            st.download_button(
                f"{title} CSV indir",
                data=frame.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"luna_sight_{spec.site_id.lower()}_{title.lower()}.csv",
                mime="text/csv",
                key=f"download_{title}",
            )

    meta = frame_a.iloc[0]
    st.divider()
    st.markdown("**Kaynak ve kalite bilgisi**")
    st.markdown(
        f"- Kaynak: `{meta['source_id']}` · sürüm `{meta['source_version']}`\n"
        f"- Model: `{meta['model_id']}`\n"
        f"- Kalite bayrağı: `{meta['quality_flag']}`\n"
        f"- Dosya: `{frame_a.attrs.get('data_path', '—')}`\n"
        f"- Parametreler: `{meta['parameters']}`"
    )
    if (frame_a["quality_flag"] == "test_fixture").any():
        st.warning(
            "Bu çıktı `test_fixture` etiketlidir: Güneş/Dünya efemerisi sentetik "
            "senaryodur, bilimsel sonuç olarak kullanılamaz.",
            icon="⚠️",
        )


def main() -> None:
    st.set_page_config(
        page_title="LUNA SIGHT · Ay İniş Alanı Navigatörü",
        page_icon="🌙",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_theme()

    days, step_minutes, start_utc, source_mode, min_sun_req, max_blackout_tol = (
        render_sidebar_controls()
    )
    start_iso = start_utc.astimezone(dt.UTC).isoformat()

    engine_active = _engine_available()
    catalog = _site_catalog(source_mode)
    default_a, default_b = _site_defaults(source_mode)

    # Başlıktaki mod bilgisi için ilk bölgeyi yükle (önbellekli).
    probe = load_site_series(default_a, start_iso, days, step_minutes, source_mode)
    fallback_reason = probe.attrs.get("fallback_reason")
    actual_source = probe.attrs.get("data_source", source_mode)

    render_header(actual_source, engine_active, fallback_reason)

    if fallback_reason:
        st.warning(
            "**Güvenli Çevrimdışı Mod (Test Verisi).** Gerçek ekip çıktısı "
            f"okunamadı: {fallback_reason}",
            icon="⚠️",
        )
    elif actual_source == SOURCE_REAL:
        # Köken sabit metin değil: yüklenen satırdan okunur, böylece çıktı
        # yeniden üretildiğinde arayüz metni eskimez.
        meta = probe.iloc[0] if len(probe) else None
        provenance = (
            f"Efemeris kaynağı: `{meta['source_id']}` · sürüm `{meta['source_version']}` · "
            f"model `{meta['model_id']}` · kalite bayrağı `{meta['quality_flag']}`."
            if meta is not None
            else "Köken bilgisi okunamadı."
        )
        st.caption(
            "Kaynak: `outputs/k3/*_visibility.csv` (K3 motoru) + "
            f"`outputs/k2/*_horizon_4000m.csv` (K2 ufuk profili). {provenance}"
        )
    else:
        st.info(
            "Çevrimdışı mock modu etkin: analitik sentetik hat kullanılıyor. "
            "Sonuçlar `test_fixture` etiketlidir.",
            icon="ℹ️",
        )

    # --- Adım 1: A/B aday bölge seçimi -----------------------------------
    st.markdown("<div class='ls-step notranslate'>1 · Aday bölge seçimi</div>", unsafe_allow_html=True)
    column_a, column_b = st.columns(2, gap="large")

    options = list(catalog)
    with column_a:
        selected_a = st.selectbox(
            "Bölge A — aday iniş bölgesi",
            options=options,
            format_func=lambda key: catalog[key].label,
            index=options.index(default_a) if default_a in options else 0,
            key=f"site_a_{source_mode}",
        )
    with column_b:
        selected_b = st.selectbox(
            "Bölge B — aday iniş bölgesi",
            options=options,
            format_func=lambda key: catalog[key].label,
            index=options.index(default_b) if default_b in options else 0,
            key=f"site_b_{source_mode}",
        )

    frame_a = load_site_series(selected_a, start_iso, days, step_minutes, source_mode)
    frame_b = load_site_series(selected_b, start_iso, days, step_minutes, source_mode)
    metrics_a = compute_metrics(frame_a, step_minutes)
    metrics_b = compute_metrics(frame_b, step_minutes)

    # Karşılaştırma karar bandı doğrudan doğal sırada render edilir (React DOM hatasını önler)
    render_verdict_band(
        catalog[selected_a], metrics_a, catalog[selected_b], metrics_b
    )

    if actual_source == SOURCE_REAL and frame_a.attrs.get("window_truncated"):
        st.warning(
            "Seçilen görev süresi gerçek çıktının sonunu aşıyor; grafikler "
            "mevcut 168 saatlik pencereyle sınırlandı.",
            icon="⚠️",
        )
    if actual_source == SOURCE_REAL and frame_a.attrs.get("window_clamped"):
        st.info(
            "Seçilen başlangıç gerçek çıktı aralığının dışında; başlangıç verinin "
            "ilk anına çekildi.",
            icon="ℹ️",
        )

    render_site_panel(
        column_a,
        "Bölge A",
        catalog[selected_a],
        metrics_a,
        metrics_b,
        min_sun_req,
        max_blackout_tol,
        start_utc,
        days,
        source_mode,
    )
    render_site_panel(
        column_b,
        "Bölge B",
        catalog[selected_b],
        metrics_b,
        metrics_a,
        min_sun_req,
        max_blackout_tol,
        start_utc,
        days,
        source_mode,
    )

    # --- Adım 3: görselleştirmeler ----------------------------------------
    st.markdown(
        "<div class='ls-step notranslate'>3 · Karşılaştırma ve ufuk grafikleri</div>",
        unsafe_allow_html=True,
    )
    globe_tab, horizon_tab, timeline_tab, map_tab, data_tab = st.tabs(
        [
            "3B Ay küresi",
            "Ufuk görünümü",
            "Zaman çizelgesi",
            "Güney Kutbu Haritası (2D)",
            "Veri ve kaynak",
        ]
    )

    with globe_tab:
        render_globe_tab()

    with horizon_tab:
        st.caption(
            "Polar düzlemde merkez zenit (90°), dış çember ufuktur (0°). "
            "☀ Güneş ve ◆ Dünya ayrı sembollerle gösterilir; kesikli çizgi "
            "topoğrafik ufku çizer. Nokta ufuk çizgisinin içinde kaldığında görünür."
        )
        control_left, control_right = st.columns([1, 2])
        with control_left:
            site_options = list(dict.fromkeys([selected_a, selected_b]))
            horizon_key = f"horizon_site_{source_mode}"
            if st.session_state.get(horizon_key) not in site_options:
                st.session_state.pop(horizon_key, None)
            horizon_site = st.radio(
                "Bölge",
                options=site_options,
                format_func=lambda key: catalog[key].label,
                horizontal=True,
                key=horizon_key,
            )
        frame = frame_a if horizon_site == selected_a else frame_b
        spec = catalog[horizon_site]

        max_index = len(frame) - 1
        with control_right:
            current_index = st.slider(
                "Zaman adımı (0 = görev başlangıcı)",
                min_value=0,
                max_value=max_index,
                value=0,
                step=1,
                help="Zaman seçimi ufuk görünümünü ve anlık durum rozetlerini günceller.",
            )
        current_index = min(max(current_index, 0), max_index)
        current = frame.iloc[current_index]
        st.caption(
            f"Seçilen an: **{current['timestamp_utc'].strftime('%Y-%m-%d %H:%M')} UTC** "
            f"(adım {current_index}/{max_index}, aralık {step_minutes} dk)"
        )

        profile_az, profile_hz, profile_source = _site_horizon_profile(spec)
        st.plotly_chart(
            build_horizon_figure(
                frame,
                current_index,
                spec,
                horizon_profile=(profile_az, profile_hz),
            )
        )
        st.caption(
            f"Ufuk profili kaynağı: **{profile_source}** · "
            f"{len(profile_az)} azimut örneği · semboller: ☀ Güneş, ◆ Dünya"
        )

        badge_a, badge_b, badge_c = st.columns(3)
        badge_a.metric(
            "Anlık Güneş yüksekliği",
            f"{current['sun_alt_deg']:.1f}°",
            STATE_LABELS.get(current["sun_visible"], current["sun_visible"]),
            delta_color="off",
            border=True,
        )
        badge_b.metric(
            "Anlık Dünya yüksekliği",
            f"{current['earth_alt_deg']:.1f}°",
            STATE_LABELS.get(current["earth_visible"], current["earth_visible"]),
            delta_color="off",
            border=True,
        )
        badge_c.metric(
            "Anlık zaman (UTC)",
            current["timestamp_utc"].strftime("%d %b %H:%M"),
            border=True,
        )

    with timeline_tab:
        st.caption(
            "Renkler: yeşil = görünür, gri = engellenmiş, sarı = belirsiz (geçiş bandı "
            "ya da eksik veri). Üç kanal Güneş, Dünya ve ortak görünürlüğü gösterir."
        )
        left, right = st.columns(2)
        with left:
            st.plotly_chart(
                build_timeline_figure(
                    frame_a, step_minutes, f"Bölge A · {catalog[selected_a].label}"
                )
            )
            st.plotly_chart(
                build_battery_figure(
                    frame_a, step_minutes, f"Bölge A · {catalog[selected_a].label}"
                )
            )
        with right:
            st.plotly_chart(
                build_timeline_figure(
                    frame_b, step_minutes, f"Bölge B · {catalog[selected_b].label}"
                )
            )
            st.plotly_chart(
                build_battery_figure(
                    frame_b, step_minutes, f"Bölge B · {catalog[selected_b].label}"
                )
            )
        st.caption(BATTERY_ASSUMPTIONS)

    with map_tab:
        st.caption(
            "Ay Güney Kutbu (90°S) merkezli 2D radar haritası. Aday iniş bölgelerinin "
            "konumlarını, kutba mesafelerini ve iki bölge arasındaki mesafeyi gösterir."
        )
        st.plotly_chart(
            build_south_pole_map(catalog[selected_a], catalog[selected_b]),
            use_container_width=True,
        )

    with data_tab:
        render_data_tab(frame_a, frame_b, catalog[selected_a], catalog[selected_b])

    st.divider()
    st.caption(
        "LUNA SIGHT · K4 ürün ve entegrasyon · Veri sözleşmesi: docs/DATA_CONTRACT.md · "
        "Bu prototip iniş güvenliği kararı vermez."
    )


if __name__ == "__main__":
    main()
