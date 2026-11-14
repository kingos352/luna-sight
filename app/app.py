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
import os
import sys
import zlib
from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

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


@dataclass(frozen=True)
class SiteSpec:
    """Aday iniş bölgesi tanımı."""

    site_id: str
    name: str
    latitude_deg: float
    longitude_deg_east: float
    sun_offset_deg: float
    sun_amplitude_deg: float
    sun_phase: float
    earth_phase: float
    earth_az_deg: float
    horizon_base_deg: float
    horizon_amp1_deg: float
    horizon_phase1_deg: float
    horizon_amp2_deg: float
    horizon_phase2_deg: float

    @property
    def coordinates(self) -> str:
        return (
            f"{self.latitude_deg:.2f}°, {self.longitude_deg_east:+.2f}° (doğu-pozitif)"
        )


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

# Sentetik model sabitleri (gerçek efemeris yerine kullanılan analitik yaklaşım)
SOLAR_SYNODIC_DAYS = 29.53059
EARTH_LIBRATION_DAYS = 27.21222
TERRAIN_JITTER_DEG = 0.12


# ---------------------------------------------------------------------------
# Veri katmanı
# ---------------------------------------------------------------------------


def _terrain_horizon_deg(azimuth_deg: np.ndarray, site: SiteSpec) -> np.ndarray:
    """Azimuta bağlı topoğrafik ufuk yüksekliği (derece, >= 0)."""
    az = np.deg2rad(azimuth_deg)
    horizon = (
        site.horizon_base_deg
        + site.horizon_amp1_deg * np.cos(az - np.deg2rad(site.horizon_phase1_deg))
        + site.horizon_amp2_deg
        * np.cos(2.0 * (az - np.deg2rad(site.horizon_phase2_deg)))
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
    earth_alt = 6.5 * np.sin(
        2.0 * np.pi * t_days / EARTH_LIBRATION_DAYS + site.earth_phase
    )
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
        start_ts.tz_localize("UTC")
        if start_ts.tzinfo is None
        else start_ts.tz_convert("UTC")
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
            "source_id": "SYNTHETIC-ANALYTIC",
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

    missing = [
        column for column in DATA_CONTRACT_COLUMNS if column not in frame.columns
    ]
    if missing:
        raise ValueError("Veri sözleşmesinde eksik alan(lar): " + ", ".join(missing))

    normalized = frame.loc[
        :,
        DATA_CONTRACT_COLUMNS
        + [c for c in OPTIONAL_DIAGNOSTIC_COLUMNS if c in frame.columns],
    ].copy()
    normalized["timestamp_utc"] = pd.to_datetime(
        normalized["timestamp_utc"], utc=True, errors="raise"
    )
    for column in NUMERIC_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    for column in ("sun_visible", "earth_visible", "joint_visible"):
        normalized[column] = (
            normalized[column]
            .astype(str)
            .str.strip()
            .str.lower()
            .replace({"nan": UNCERTAIN})
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


def _horizon_arrays(site: SiteSpec) -> tuple[np.ndarray, np.ndarray, str]:
    """Ufuk profilini K2 çıktısından ya da analitik modelden üretir.

    K2 dosyası şu sırayla aranır:
        ``$LUNA_SIGHT_HORIZON_DIR/horizon_<site_id>.csv``
        ``data/derived/horizon_<site_id>.csv``
    Beklenen sütunlar: ``azimuth_deg``, ``horizon_deg``. Dosya yoksa analitik
    profil kullanılır ve dönen kaynak etiketi ``synthetic`` olur.
    """
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
            try:
                table = pd.read_csv(path)
                azimuths = pd.to_numeric(
                    table["azimuth_deg"], errors="coerce"
                ).to_numpy(dtype=float)
                horizons = pd.to_numeric(
                    table["horizon_deg"], errors="coerce"
                ).to_numpy(dtype=float)
            except Exception:  # noqa: BLE001, S112 - bozuk profil dosyası
                continue
            if azimuths.size >= 2 and np.isfinite(azimuths).all():
                return azimuths, horizons, "K2"

    azimuths = np.arange(0.0, 360.0, 1.0)
    return azimuths, _terrain_horizon_deg(azimuths, site), "synthetic"


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
        "engine_config": (
            config.as_dict() if callable(getattr(config, "as_dict", None)) else {}
        ),
        "horizon_profile": horizon_source,
    }
    evaluated["parameters"] = evaluated["parameters"].map(
        lambda raw: _merge_parameters(raw, engine_info)
    )
    evaluated["source_id"] = evaluated["source_id"].astype(str) + "+K3"
    return evaluated


@st.cache_data(show_spinner=False)
def load_site_series(
    site_id: str,
    start_iso: str,
    days: int,
    step_minutes: int,
) -> pd.DataFrame:
    """Tek giriş noktası: K1 → K3 → sentetik yedek.

    Dönen çerçeve her zaman ``docs/DATA_CONTRACT.md`` şemasına uyar. Gerçek
    efemeris yoksa ``quality_flag=test_fixture`` olarak kalır; K3 motoru varsa
    sınıflandırma yine gerçek motorla yapılır ve ``uncertain`` korunur.
    """
    site = SITES[site_id]
    start_utc = dt.datetime.fromisoformat(start_iso)

    frame = _k1_series(site, start_utc, days, step_minutes)
    if frame is None:
        frame = generate_synthetic_series(site, start_utc, days, step_minutes)

    evaluated = _evaluate_with_engine(frame, site)
    if evaluated is not None:
        frame = evaluated
    return normalize_contract_frame(frame)


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
    frame: pd.DataFrame, current_index: int, site: SiteSpec
) -> go.Figure:
    """Güneş ve Dünya'nın azimut/yükseklik değişimini polar düzlemde çizer.

    Dönüşüm: r = 90 - yükseklik. Böylece ufuk (0°) dış çemberde, zenit (90°)
    merkezde yer alır. Topoğrafik ufuk çizgisinin içinde kalan noktalar görünür.
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

    # Topoğrafik ufuk profili
    horizon_theta = np.linspace(0.0, 360.0, 181)
    horizon_radius = 90.0 - _terrain_horizon_deg(horizon_theta, site)
    figure.add_trace(
        go.Scatterpolar(
            r=horizon_radius,
            theta=horizon_theta,
            mode="lines",
            name="Topoğrafik ufuk",
            line={"color": "#9aa4bf", "width": 2, "dash": "dot"},
            hovertemplate="Azimut %{theta:.0f}°<br>Ufuk yüksekliği %{customdata:.1f}°<extra></extra>",
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
                "Güneş<br>Azimut %{theta:.1f}°<br>Yükseklik %{customdata:.1f}°"
                "<extra></extra>"
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
                "Dünya<br>Azimut %{theta:.1f}°<br>Yükseklik %{customdata:.1f}°"
                "<extra></extra>"
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


def build_timeline_figure(
    frame: pd.DataFrame, step_minutes: int, title: str
) -> go.Figure:
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


# ---------------------------------------------------------------------------
# Arayüz katmanı
# ---------------------------------------------------------------------------


def inject_theme() -> None:
    """NASA temasına yakın koyu uzay görünümü için ince CSS katmanı."""
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1500px;}
        .ls-hero {
            background: radial-gradient(1200px 400px at 15% -20%, #1b2a5e 0%, #0b1020 55%, #070a14 100%);
            border: 1px solid rgba(90,169,255,0.25);
            border-radius: 16px;
            padding: 1.4rem 1.6rem 1.2rem 1.6rem;
            margin-bottom: 1.1rem;
        }
        .ls-kicker {
            font-size: 0.72rem; letter-spacing: 0.22em; text-transform: uppercase;
            color: #7fb4ff; margin-bottom: 0.35rem;
        }
        .ls-title {font-size: 2.05rem; line-height: 1.15; margin: 0 0 0.45rem 0; color: #f4f7ff;}
        .ls-sub {font-size: 0.95rem; color: #b9c3dc; margin: 0; max-width: 70ch;}
        .ls-chip {
            display: inline-block; padding: 0.15rem 0.6rem; margin: 0.55rem 0.35rem 0 0;
            border-radius: 999px; font-size: 0.72rem; letter-spacing: 0.04em;
            border: 1px solid rgba(90,169,255,0.35); color: #a9c8ff; background: rgba(90,169,255,0.08);
        }
        .ls-chip-warn {border-color: rgba(245,185,66,0.45); color: #f5c76a; background: rgba(245,185,66,0.08);}
        .ls-chip-ok {border-color: rgba(61,220,151,0.45); color: #7ff0bd; background: rgba(61,220,151,0.10);}
        div[data-testid="stMetric"] {background: rgba(20,26,46,0.65); border: 1px solid rgba(90,169,255,0.16);
            border-radius: 12px; padding: 0.65rem 0.8rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(synthetic: bool, engine_active: bool = False) -> None:
    """Başlık ve durum rozetleri."""
    chips = ['<span class="ls-chip">JPL Horizons · K1</span>']
    if synthetic:
        chips.append(
            '<span class="ls-chip ls-chip-warn">Sentetik efemeris · test_fixture</span>'
        )
    chips.append('<span class="ls-chip">LOLA DEM · K2</span>')
    if engine_active:
        chips.append(
            '<span class="ls-chip ls-chip-ok">Görünürlük motoru · K3 etkin</span>'
        )
    else:
        chips.append('<span class="ls-chip">Görünürlük motoru · K3</span>')
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


def render_sidebar_controls() -> tuple[int, int, dt.datetime]:
    """Görev parametreleri: süre, örnekleme aralığı, başlangıç zamanı."""
    st.sidebar.header("Görev parametreleri")

    days = st.sidebar.slider(
        "Görev süresi (gün)",
        min_value=1,
        max_value=30,
        value=7,
        step=1,
        help="Varsayılan 7 gün. Simülasyon penceresi bu süreye göre üretilir.",
    )
    step_label = st.sidebar.selectbox(
        "Zaman örnekleme aralığı",
        options=list(SAMPLE_STEP_OPTIONS),
        index=2,
        help="Veri sözleşmesi varsayılanı 5 dakikadır; demo için 1 saat uygundur.",
    )
    step_minutes = SAMPLE_STEP_OPTIONS[step_label]

    start_utc = st.sidebar.datetime_input(
        "Görev başlangıcı (UTC)",
        value=dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0),
        step=dt.timedelta(hours=1),
        help="Tüm zamanlar UTC ve ISO 8601 biçimindedir.",
    )
    st.sidebar.caption(
        f"Pencere: {days} gün × {step_label} = {days * 24 * 60 // step_minutes} adım"
    )

    st.sidebar.divider()
    st.sidebar.subheader("Veri kaynağı durumu")
    k1_ready = _module_implemented("luna_sight.ephemeris")
    k2_ready = _module_implemented("luna_sight.terrain")
    k3_ready = _engine_available()
    if k1_ready and k3_ready:
        st.sidebar.success("JPL Horizons & LOLA DEM Entegrasyonu: Aktif")
    elif k3_ready:
        st.sidebar.warning("K3 motoru etkin · sentetik efemeris (test_fixture)")
        st.sidebar.caption(
            "Sınıflandırmayı gerçek K3 motoru yapıyor; Güneş/Dünya efemerisi "
            "K1 bağlanana kadar sentetik."
        )
    else:
        st.sidebar.warning("Sentetik veri hattı (test_fixture) etkin")
        st.sidebar.caption(
            "K1 efemeris ve K3 görünürlük modülleri bağlanınca bu uyarı kaybolur."
        )
    marks = {True: "hazır", False: "bekliyor"}
    st.sidebar.markdown(
        f"- JPL Horizons (K1): **{marks[k1_ready]}**\n"
        f"- LOLA DEM / ufuk (K2): **{marks[k2_ready]}**\n"
        f"- Görünürlük motoru (K3): **{marks[k3_ready]}**"
    )

    st.sidebar.divider()
    with st.sidebar.expander("Yöntem ve sınırlar"):
        st.markdown(
            "Veriler analitik bir modelle üretilir: Güneş için 29,53 günlük sinodik "
            "dönem, Dünya için 27,21 günlük librasyon salınımı ve azimuta bağlı "
            "topoğrafik ufuk profili.\n\n"
            "Bu ekran iniş güvenliği kararı vermez; yalnızca bölgeleri "
            "karşılaştırmalı olarak ön değerlendirmeye sunar."
        )
    return days, step_minutes, start_utc


def render_site_panel(
    column,
    label: str,
    spec: SiteSpec,
    metrics: SiteMetrics,
    compare: SiteMetrics,
) -> None:
    """Tek bir bölgenin metrik ve engel özetini sütuna çizer."""
    with column:
        st.caption(
            f"Koordinat: {spec.coordinates} · yaklaşık (K2 doğrulaması bekliyor)"
        )

        sun_delta = metrics.sun_hours - compare.sun_hours
        earth_delta = metrics.earth_hours - compare.earth_hours
        joint_delta = metrics.joint_hours - compare.joint_hours

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


def render_data_tab(frame_a: pd.DataFrame, frame_b: pd.DataFrame) -> None:
    """Veri sözleşmesi çıktısını ve indirme seçeneğini gösterir."""
    st.subheader("Veri sözleşmesi çıktısı")
    st.caption(
        "Aşağıdaki tablolar `docs/DATA_CONTRACT.md` alanlarıyla birebir uyumludur; "
        "K1/K2/K3 modülleri bağlandığında aynı şema korunur."
    )

    left, right = st.columns(2)
    for column, title, frame in (
        (left, "Bölge A", frame_a),
        (right, "Bölge B", frame_b),
    ):
        with column:
            st.markdown(f"**{title}** · {len(frame)} satır")
            st.dataframe(frame.head(50), height=260, hide_index=True)
            st.download_button(
                f"{title} CSV indir",
                data=frame.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"luna_sight_{title.replace(' ', '_').lower()}.csv",
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
        f"- Parametreler: `{meta['parameters']}`"
    )
    if (frame_a["quality_flag"] == "test_fixture").any():
        st.warning(
            "Bu çıktı `test_fixture` etiketlidir: sentetik veridir, bilimsel sonuç "
            "olarak kullanılamaz.",
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

    days, step_minutes, start_utc = render_sidebar_controls()
    start_iso = start_utc.astimezone(dt.UTC).isoformat()

    k1_ready = _module_implemented("luna_sight.ephemeris")
    engine_active = _engine_available()
    synthetic = not k1_ready
    render_header(synthetic=synthetic, engine_active=engine_active)

    if synthetic:
        if engine_active:
            st.info(
                "Sınıflandırma **K3 görünürlük motoruyla** (`evaluate_series`) yapılıyor. "
                "Güneş/Dünya efemerisi K1 bağlanana kadar sentetiktir; çıktılar "
                "`test_fixture` etiketlidir ve bilimsel sonuç olarak kullanılamaz.",
                icon="ℹ️",
            )
        else:
            st.info(
                "Bilimsel modüller (K1/K2/K3) henüz bağlı değil. Arayüz, veri sözleşmesine "
                "uygun **sentetik** veriyle çalışıyor; sonuçlar `test_fixture` etiketlidir.",
                icon="ℹ️",
            )

    # --- A/B karşılaştırma panelleri -------------------------------------
    st.subheader("A/B aday iniş bölgesi karşılaştırması")
    column_a, column_b = st.columns(2, gap="large")

    with column_a:
        selected_a = st.selectbox(
            "Bölge A — aday iniş bölgesi",
            options=list(SITES),
            format_func=lambda key: SITES[key].name,
            index=list(SITES).index(DEFAULT_SITE_A),
            key="site_a",
        )
    with column_b:
        selected_b = st.selectbox(
            "Bölge B — aday iniş bölgesi",
            options=list(SITES),
            format_func=lambda key: SITES[key].name,
            index=list(SITES).index(DEFAULT_SITE_B),
            key="site_b",
        )

    frame_a = load_site_series(selected_a, start_iso, days, step_minutes)
    frame_b = load_site_series(selected_b, start_iso, days, step_minutes)
    metrics_a = compute_metrics(frame_a, step_minutes)
    metrics_b = compute_metrics(frame_b, step_minutes)

    render_site_panel(column_a, "Bölge A", SITES[selected_a], metrics_a, metrics_b)
    render_site_panel(column_b, "Bölge B", SITES[selected_b], metrics_b, metrics_a)

    # --- Görselleştirmeler ------------------------------------------------
    horizon_tab, timeline_tab, data_tab = st.tabs(
        ["Ufuk görünümü", "Zaman çizelgesi", "Veri ve kaynak"]
    )

    with horizon_tab:
        st.caption(
            "Polar düzlemde merkez zenit (90°), dış çember ufuktur (0°). "
            "Noktalar topoğrafik ufuk çizgisinin içinde kaldığında görünür."
        )
        control_left, control_right = st.columns([1, 2])
        with control_left:
            site_options = list(dict.fromkeys([selected_a, selected_b]))
            if st.session_state.get("horizon_site") not in site_options:
                st.session_state.pop("horizon_site", None)
            horizon_site = st.radio(
                "Bölge",
                options=site_options,
                format_func=lambda key: SITES[key].name,
                horizontal=True,
                key="horizon_site",
            )
        frame = frame_a if horizon_site == selected_a else frame_b
        spec = SITES[horizon_site]

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

        st.plotly_chart(build_horizon_figure(frame, current_index, spec))

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
                    frame_a, step_minutes, f"Bölge A · {SITES[selected_a].name}"
                )
            )
        with right:
            st.plotly_chart(
                build_timeline_figure(
                    frame_b, step_minutes, f"Bölge B · {SITES[selected_b].name}"
                )
            )

    with data_tab:
        render_data_tab(frame_a, frame_b)

    st.divider()
    st.caption(
        "LUNA SIGHT · K4 ürün ve entegrasyon · Veri sözleşmesi: docs/DATA_CONTRACT.md · "
        "Bu prototip iniş güvenliği kararı vermez."
    )


if __name__ == "__main__":
    main()
