"""Senaryo (test_fixture) ephemeris üreteci.

K1 gerçek JPL Horizons serisini sağlayana kadar motoru uçtan uca denemek
için kullanılır. **Astronomik bir model değildir**: azimut taraması
hızlandırılmıştır ve yükseklik eğrisi senaryo gereği seçilmiştir. Üretilen
her örnek ``quality_flag="test_fixture"`` taşır ve çıktılarda da böyle
işaretlenir.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from luna_sight.visibility.series import Sample

SYNTHETIC_SOURCE_ID = "synthetic-scenario"
SYNTHETIC_SOURCE_VERSION = "v1"
SYNTHETIC_MODEL_ID = "accelerated-azimuth-sweep"
TEST_FIXTURE = "test_fixture"


def synthetic_series(
    *,
    start_utc: datetime | None = None,
    hours: float = 168.0,
    step_minutes: float = 5.0,
    site_id: str = "",
    latitude_deg: float | None = None,
    longitude_deg_east: float | None = None,
) -> list[Sample]:
    """Hızlandırılmış azimut taramasıyla senaryo serisi üretir.

    - Güneş azimutu 168 saatte tam tur atar (gerçekte ~27.3 gün).
    - Güneş yüksekliği −1.7°…+0.1° arasında salınır.
    - Dünya, Güneş'ten 55° ileride ve daha dar bir yükseklik aralığında.
    """
    start = start_utc or datetime(2026, 11, 15, tzinfo=timezone.utc)
    step = timedelta(minutes=step_minutes)
    count = int(round(hours * 60.0 / step_minutes)) + 1
    span_hours = max(hours, 1e-9)

    samples: list[Sample] = []
    for index in range(count):
        offset_hours = index * step_minutes / 60.0
        phase = 2.0 * math.pi * offset_hours / span_hours
        sun_az = (offset_hours / span_hours * 360.0) % 360.0
        sun_alt = -0.8 + 0.9 * math.sin(phase)
        earth_alt = -0.2 + 0.5 * math.sin(2.0 * phase + 1.0)
        samples.append(
            Sample(
                timestamp_utc=start + step * index,
                sun_az_deg=sun_az,
                sun_alt_deg=sun_alt,
                earth_az_deg=(sun_az + 55.0) % 360.0,
                earth_alt_deg=earth_alt,
                site_id=site_id,
                latitude_deg=latitude_deg,
                longitude_deg_east=longitude_deg_east,
                quality_flag=TEST_FIXTURE,
                source_id=SYNTHETIC_SOURCE_ID,
                source_version=SYNTHETIC_SOURCE_VERSION,
                model_id=SYNTHETIC_MODEL_ID,
                parameters=f"hours={hours};step_minutes={step_minutes};azimut_hizlandirilmis",
            )
        )
    return samples
