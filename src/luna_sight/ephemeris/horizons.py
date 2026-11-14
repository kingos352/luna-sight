"""JPL Horizons OBSERVER sorguları ve yanıt ayrıştırma.

Birimler ve yönler, `docs/DATA_CONTRACT.md` ile aynıdır:

- Zaman: UTC, zaman dilimi bilgisi taşıyan damga.
- Boylam: ondalık derece, **doğu-pozitif** (Horizons `SITE_COORD` ile aynı yön).
- Azimut: derece, kuzeyden doğuya artan (0 = kuzey, 90 = doğu).
- Yükseklik: derece, yerel ufuk düzlemine göre.

Ay yüzeyinde atmosfer yoktur; `APPARENT=AIRLESS` ile kırılma düzeltmesi kapatılır.
Bu modül yalnızca astronomik geometriyi verir. Arazi ufku ve görünürlük kararı
K2 ve K3 modüllerine aittir.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass, field

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
SOURCE_ID = "jpl_horizons"
PROVIDER = "NASA/JPL"
PRODUCT = "horizons_observer_ephemeris"

#: Horizons gövde kodları. Gözlemci Ay yüzeyinde olduğu için Ay hedef değildir.
BODIES = {"sun": "10", "earth": "399"}
MOON_SITE_CENTER = "coord@301"

_SOE = "$$SOE"
_EOE = "$$EOE"
_MODEL_RE = re.compile(r"Target body name:[^{]*\{source:\s*([A-Za-z0-9_.-]+)\s*\}")
_TS_FORMATS = ("%Y-%b-%d %H:%M", "%Y-%b-%d %H:%M:%S")
_RETRY_STATUS = (429, 500, 502, 503, 504)


class HorizonsError(RuntimeError):
    """Horizons kaynaklı taban hata."""


class HorizonsFormatError(HorizonsError):
    """Yanıt beklenen efemeris bloğunu içermiyor."""


@dataclass(frozen=True)
class Site:
    """Ay yüzeyinde bir gözlem noktası."""

    site_id: str
    latitude_deg: float
    longitude_deg_east: float
    elevation_km: float = 0.0

    def __post_init__(self) -> None:
        if not self.site_id:
            raise ValueError("site_id boş olamaz")
        if not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError(f"latitude_deg aralık dışı: {self.latitude_deg}")
        if not -180.0 <= self.longitude_deg_east <= 360.0:
            raise ValueError(f"longitude_deg_east aralık dışı: {self.longitude_deg_east}")

    @property
    def site_coord(self) -> str:
        """Horizons `SITE_COORD` dizgesi: doğu-pozitif boylam, enlem, yükseklik (km)."""
        return f"{self.longitude_deg_east},{self.latitude_deg},{self.elevation_km}"


@dataclass(frozen=True)
class HorizonsResponse:
    """Tek bir Horizons sorgusunun ham yanıtı ve kökeni."""

    body: str
    site: Site
    params: dict[str, str]
    raw_text: str
    source_version: str
    model_id: str
    retrieved_utc: str
    url: str = API_URL
    _digest: list[str] = field(default_factory=list, repr=False, compare=False)

    @property
    def sha256(self) -> str:
        """Ham yanıtın özeti. `data/manifest.csv` satırına bu değer yazılır."""
        if not self._digest:
            self._digest.append(hashlib.sha256(self.raw_text.encode("utf-8")).hexdigest())
        return self._digest[0]

    @property
    def parameters_json(self) -> str:
        return json.dumps(self.params, sort_keys=True, separators=(",", ":"))


def build_session(total_retries: int = 4, backoff_factor: float = 0.8) -> requests.Session:
    """Hız sınırı ve geçici sunucu hatalarında geri çekilerek yeniden deneyen oturum.

    Ek paket almak yerine `requests` içindeki `urllib3.Retry` kullanılır.
    """
    retry = Retry(
        total=total_retries,
        connect=total_retries,
        read=total_retries,
        status=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=_RETRY_STATUS,
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "luna-sight/0.1 (NASA Space Apps prototype)"
    return session


def build_params(
    body: str,
    site: Site,
    start_utc: str,
    stop_utc: str,
    step: str = "5 m",
) -> dict[str, str]:
    """Horizons sorgu parametrelerini üret. Köken kaydına bu sözlük yazılır."""
    try:
        command = BODIES[body]
    except KeyError:
        raise ValueError(f"bilinmeyen gövde: {body!r}; beklenen {sorted(BODIES)}") from None
    return {
        "format": "json",
        "COMMAND": f"'{command}'",
        "EPHEM_TYPE": "OBSERVER",
        "CENTER": f"'{MOON_SITE_CENTER}'",
        "COORD_TYPE": "GEODETIC",
        "SITE_COORD": f"'{site.site_coord}'",
        "START_TIME": f"'{start_utc}'",
        "STOP_TIME": f"'{stop_utc}'",
        "STEP_SIZE": f"'{step}'",
        "QUANTITIES": "'4'",
        "ANG_FORMAT": "DEG",
        "CSV_FORMAT": "YES",
        "CAL_FORMAT": "CAL",
        "APPARENT": "AIRLESS",
        "OBJ_DATA": "'NO'",
    }


def fetch(
    body: str,
    site: Site,
    start_utc: str,
    stop_utc: str,
    step: str = "5 m",
    session: requests.Session | None = None,
    timeout: float = 60.0,
) -> HorizonsResponse:
    """Tek gövde için Horizons sorgusu çalıştır ve kökenle birlikte döndür."""
    params = build_params(body, site, start_utc, stop_utc, step)
    http = session or build_session()
    response = http.get(API_URL, params=params, timeout=timeout)
    if response.status_code != 200:
        raise HorizonsError(f"Horizons HTTP {response.status_code}: {response.text[:200]!r}")
    try:
        payload = response.json()
        raw_text = payload["result"]
        source_version = str(payload.get("signature", {}).get("version", "unknown"))
    except (ValueError, KeyError, TypeError) as exc:
        raise HorizonsFormatError(f"beklenmeyen Horizons JSON yükü: {exc}") from exc
    match = _MODEL_RE.search(raw_text)
    return HorizonsResponse(
        body=body,
        site=site,
        params=params,
        raw_text=raw_text,
        source_version=source_version,
        model_id=match.group(1) if match else "unknown",
        retrieved_utc=dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def _parse_timestamps(values: pd.Series) -> pd.Series:
    """`2026-Nov-14 00:00` biçimini UTC damgasına çevir.

    Ay adı İngilizce kısaltmadır. pandas biçim dizgesi yerel ayardan
    etkilenmediği için Türkçe Windows kurulumunda da aynı sonucu verir.
    """
    cleaned = values.str.strip()
    for fmt in _TS_FORMATS:
        parsed = pd.to_datetime(cleaned, format=fmt, utc=True, errors="coerce")
        if parsed.notna().all():
            return parsed
    raise HorizonsFormatError(f"zaman damgası ayrıştırılamadı: {cleaned.iloc[0]!r}")


def parse_observer_table(raw_text: str) -> pd.DataFrame:
    """`$$SOE` ve `$$EOE` arasındaki CSV bloğunu tabloya çevir.

    Dönen kolonlar: `timestamp_utc`, `az_deg`, `alt_deg`.

    Horizons `n.a.` değerleri `NaN` olur. Eksik veri burada görünür ya da
    engelli sınıfına çevrilmez; kalite kararı `series` katmanına aittir.
    """
    if _SOE not in raw_text or _EOE not in raw_text:
        raise HorizonsFormatError("yanıtta $$SOE/$$EOE efemeris bloğu yok")
    block = raw_text.split(_SOE, 1)[1].split(_EOE, 1)[0].strip()
    if not block:
        raise HorizonsFormatError("efemeris bloğu boş")

    rows: list[tuple[str, str, str]] = []
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        fields = [value.strip() for value in line.split(",")]
        if len(fields) < 5:
            raise HorizonsFormatError(f"eksik kolonlu efemeris satırı: {line!r}")
        # Kolon düzeni: tarih, güneş varlığı, engelleyen gövde, azimut, yükseklik
        rows.append((fields[0], fields[3], fields[4]))
    # `block` boş değilse en az bir dolu satır vardır; boş blok yukarıda reddedilir.

    frame = pd.DataFrame(rows, columns=["timestamp_utc", "az_deg", "alt_deg"])
    frame["timestamp_utc"] = _parse_timestamps(frame["timestamp_utc"])
    for column in ("az_deg", "alt_deg"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values("timestamp_utc", ignore_index=True)
