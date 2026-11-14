"""Ortak test düzenekleri.

Buradaki metin blokları `test_fixture` düzeneğidir: gerçek Horizons
yanıtının biçimini taklit eder, bilimsel sonuç olarak kullanılamaz.
Gerçek yanıtla çalışan tek test `test_horizons_api.py` içindedir ve
kasetten oynatılır.
"""

from __future__ import annotations

import pytest

from luna_sight.ephemeris import Site

#: Kasetsiz ve ağsız ayrıştırma testleri için düzenek. Değerler sahte değildir,
#: gerçek bir sorgudan alınmıştır; yine de `test_fixture` olarak işaretlenir.
FIXTURE_SUN = """*****
Target body name: Sun (10)                        {source: DE441}
Center body name: Moon (301)                      {source: DE441}
Date__(UT)__HR:MN, , ,Azi_(a-app), Elev_(a-app),
$$SOE
 2026-Nov-14 00:00,*, , 126.628204,     1.228504,
 2026-Nov-14 00:30,*, , 126.374313,     1.230469,
 2026-Nov-14 01:00,*, , 126.120424,     1.232440,
$$EOE
*****
"""

FIXTURE_EARTH = """*****
Target body name: Earth (399)                     {source: DE441}
Center body name: Moon (301)                      {source: DE441}
$$SOE
 2026-Nov-14 00:00,*, ,  11.552000,    -0.413000,
 2026-Nov-14 00:30,*, ,  11.549000,    -0.410000,
 2026-Nov-14 01:00,*, ,  11.546000,    -0.407000,
$$EOE
*****
"""

#: Horizons JSON yanıtının imza bloğu; `source_version` buradan okunur.
SIGNATURE = {"source": "NASA/JPL Horizons API", "version": "1.2"}

#: `FIXTURE_SUN` içindeki ikinci satır; eksik veri testlerinde değiştirilir.
SUN_SECOND_ROW = " 2026-Nov-14 00:30,*, , 126.374313,     1.230469,"

#: Horizons eksik değeri `n.a.` ile bildirir. Bu satır `partial` olmalıdır.
FIXTURE_SUN_WITH_GAP = FIXTURE_SUN.replace(
    SUN_SECOND_ROW,
    " 2026-Nov-14 00:30,*, , n.a., n.a.,",
)

#: `$$EOE` yok: kesik yanıt sessizce kabul edilmemeli.
FIXTURE_TRUNCATED = FIXTURE_SUN.split("$$EOE")[0]


@pytest.fixture
def site() -> Site:
    """Shackleton kenarına yakın referans nokta; boylam doğu-pozitif."""
    return Site(
        site_id="shackleton_rim_a",
        latitude_deg=-89.45,
        longitude_deg_east=0.0,
    )


@pytest.fixture(scope="module")
def vcr_config() -> dict[str, object]:
    """Kaset eşleştirmesi sorgu dizgesini de içerir.

    Horizons parametreleri sorgu dizgesinde taşındığı için `query` olmadan
    farklı sorgular aynı kasete düşerdi. Kimlik bilgisi gönderilmiyor;
    yine de `Authorization` başlığı temizlenir.
    """
    return {
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
        "filter_headers": ["authorization", "cookie"],
        "decode_compressed_response": True,
    }
