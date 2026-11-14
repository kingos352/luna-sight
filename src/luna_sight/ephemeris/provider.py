"""K3 görünürlük motoru için efemeris sağlayıcı adaptörü.

K3, `luna_sight.visibility.providers.EphemerisProvider` protokolünü tanımlar:

    def positions(self, site, timestamps: pd.DatetimeIndex) -> pd.DataFrame

Dönen tablo `timestamp_utc` ile birlikte `sun_az_deg`, `sun_alt_deg`,
`earth_az_deg`, `earth_alt_deg` kolonlarını taşır. `HorizonsEphemeris` bu
protokolü gerçek JPL Horizons verisiyle karşılar; motor böylece sentetik
sağlayıcı yerine ölçülmüş geometriyle koşabilir.

Bu modül **K3 paketini içe aktarmaz**. `site` nesnesi ördek tiplemesiyle
okunur (`site_id`, `latitude_deg`, `longitude_deg_east`), böylece K1 ile K3
arasında derleme zamanı bağımlılığı oluşmaz ve iki modül ayrı dallarda
geliştirilmeye devam edebilir.

Eksik veri doldurulmaz. Horizons bir damga için değer vermezse hücre `NaN`
kalır; enterpolasyon görünürlük kararını sessizce değiştirirdi ve veri
sözleşmesi bunu yasaklar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import requests

from luna_sight.ephemeris.horizons import Site, build_session
from luna_sight.ephemeris.series import build_site_timeseries

#: K3 protokolünün beklediği kolonlar.
POSITION_COLUMNS = ("sun_az_deg", "sun_alt_deg", "earth_az_deg", "earth_alt_deg")

_HORIZONS_TIME = "%Y-%m-%d %H:%M"


def _as_site(site: Any) -> Site:
    """K3 tarafından verilen bölge nesnesini K1 `Site` nesnesine çevir."""
    if isinstance(site, Site):
        return site
    try:
        return Site(
            site_id=str(site.site_id),
            latitude_deg=float(site.latitude_deg),
            longitude_deg_east=float(site.longitude_deg_east),
            elevation_km=float(getattr(site, "elevation_km", 0.0) or 0.0),
        )
    except AttributeError as exc:
        raise TypeError(
            "site nesnesi site_id, latitude_deg ve longitude_deg_east alanlarını taşımalı; "
            f"alınan tip: {type(site).__name__}"
        ) from exc


def _step_minutes(timestamps: pd.DatetimeIndex) -> int:
    """Izgara adımını tam dakika olarak döndür.

    Horizons `STEP_SIZE` tam dakika bekler. Düzensiz ızgara reddedilir:
    tek sorguyla karşılanamaz ve sessizce yanlış damgalar üretirdi.
    """
    if len(timestamps) < 2:
        return 5
    deltas = timestamps.to_series().diff().dropna().unique()
    if len(deltas) != 1:
        raise ValueError(
            "timestamps düzenli aralıklı olmalı; Horizons tek sorguda yalnızca sabit "
            f"adım üretir. Bulunan farklı adım sayısı: {len(deltas)}"
        )
    seconds = pd.Timedelta(deltas[0]).total_seconds()
    if seconds <= 0 or seconds % 60:
        raise ValueError(f"adım tam dakika olmalı; bulunan: {seconds} saniye")
    return int(seconds // 60)


@dataclass
class HorizonsEphemeris:
    """Gerçek Horizons verisiyle K3 `EphemerisProvider` protokolü.

    `session` verilmezse yeniden deneme yapan ortak oturum kurulur. Aynı
    örnek birden fazla bölge için kullanılabilir; her çağrı iki Horizons
    sorgusu yapar (Güneş ve Dünya) ve ham yanıtları `last_responses`
    içinde bırakır, böylece çağıran köken kaydını yazabilir.
    """

    session: requests.Session | None = None
    timeout: float = 60.0
    last_responses: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = build_session()

    def positions(self, site: Any, timestamps: pd.DatetimeIndex) -> pd.DataFrame:
        """İstenen damgalar için Güneş ve Dünya azimut/yükseklik değerleri."""
        index = pd.DatetimeIndex(timestamps)
        if len(index) == 0:
            raise ValueError("timestamps boş olamaz")
        if index.tz is None:
            raise ValueError("timestamps UTC bilgisi taşımalı; naive ızgara kabul edilmez")
        index = index.tz_convert("UTC")
        if not index.is_monotonic_increasing:
            index = index.sort_values()

        step = _step_minutes(index)
        resolved = _as_site(site)
        frame, responses = build_site_timeseries(
            resolved,
            index[0].strftime(_HORIZONS_TIME),
            index[-1].strftime(_HORIZONS_TIME),
            step=f"{step} m",
            session=self.session,
        )
        self.last_responses = dict(responses)

        # Horizons ızgarası istenen damgalarla birebir eşleşmezse eksik hücre
        # NaN kalır. Doldurma yapılmaz: K3 bunu uncertain olarak sınıflar.
        positions = frame.set_index("timestamp_utc")[list(POSITION_COLUMNS)]
        positions = positions[~positions.index.duplicated(keep="first")]
        aligned = positions.reindex(index)
        aligned.index.name = "timestamp_utc"
        return aligned.reset_index()
