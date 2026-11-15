# K1 — JPL Horizons efemeris ürünü ve doğrulaması

Issue: [#1](https://github.com/kingos352/luna-sight/issues/1) ·
[#12](https://github.com/kingos352/luna-sight/issues/12) · Dal: `k1/*`

Bu belge, Ay güney kutbundaki aday bölgeler için üretilen Güneş ve Dünya
azimut/yükseklik zaman serisinin kaynağını, parametrelerini, doğrulama
kanıtını ve bilimsel sınırlarını kaydeder.

## 1. Veri ürünü kaydı

| Alan | Değer |
|---|---|
| Sağlayıcı | NASA/JPL, Solar System Dynamics |
| Ürün | Horizons `OBSERVER` efemeris tablosu |
| Arayüz | `https://ssd.jpl.nasa.gov/api/horizons.api` |
| API sürümü | `1.2` (yanıt imzasından okunur, satır başına kaydedilir) |
| Efemeris çekirdeği | **DE441** (yanıttaki `Target body name: ... {source: DE441}`) |
| Gözlemci | Ay yüzeyinde nokta: `CENTER='coord@301'`, `COORD_TYPE=GEODETIC` |
| Hedefler | Güneş `COMMAND='10'`, Dünya `COMMAND='399'` |
| Gövde yarıçapı | 1737.4 km küre (Horizons `Target radii`) |
| Köken kaydı | Ham yanıt `data/cache/`, satır `data/manifest.csv` (kaynak, sürüm, parametre, SHA-256) |

Ham yanıtlar Git'e eklenmez. Her gerçek veri dosyası için `manifest.csv`
satırı açılır ve `sha256` önbellek dosyasından yeniden hesaplanabilir.

## 2. Aday noktalar

Koordinatlar K2 kataloğundan gelir (`src/luna_sight/terrain/sites.py` ve
`docs/K2_HORIZON.md` bölüm 2); K1 kendi nokta tanımı üretmez. `site_id` yazımı
K2 ve K3 çıktılarıyla birebir aynıdır, yoksa bölge bazlı birleştirme hata
vermeden boş kalır.

K1 (`Site`, `build_site_timeseries`, `HorizonsEphemeris`) tüm **12 NASA
Artemis III aday bölgesini** (`Site01`–`Site09`, `Site11`–`Site13`) destekler;
`luna_sight.ephemeris.__main__.SITES` CLI varsayılanı tarihsel referans çifti
olan `Site01` ve `Site04`'ü içerir.

| Site | Bölge | Enlem (°) | Boylam doğu-pozitif (°) |
|---|---|---|---|
| Site01 | Connecting ridge | −89.463163 | −137.489553 |
| Site02 | Connecting ridge extension | −89.300000 | −150.000000 |
| Site03 | de Gerlache rim 1 | −88.500000 | −68.000000 |
| Site04 | Shackleton rim | −89.766811 | −171.869898 |
| Site05 | de Gerlache rim 2 | −88.710000 | −64.000000 |
| Site06 | de Gerlache-Kocher massif | −85.800000 | −116.300000 |
| Site07 | Haworth | −87.450000 | −5.000000 |
| Site08 | Malapert massif | −86.000000 | +2.700000 |
| Site09 | Leibnitz beta plateau | −85.200000 | +33.000000 |
| Site11 | Nobile rim 2 | −84.100000 | +59.700000 |
| Site12 | Amundsen rim | −84.500000 | +85.000000 |
| Site13 | Mons Mouton | −84.600000 | +31.000000 |

## 3. Birimler, çerçeve ve işaretler

`docs/GOVERNANCE.md` bölüm 5 ile aynıdır:

- Zaman: UTC, ISO 8601, zaman dilimi bilgisi zorunlu.
- Boylam: ondalık derece, doğu-pozitif, [−180, 180].
- Azimut: derece, kuzeyden **saat yönünde**, [0, 360).
- Yükseklik: derece, yerel ufuk düzlemine göre, [−90, 90].
- `APPARENT=AIRLESS`: Ay yüzeyinde atmosfer yok, kırılma düzeltmesi
  uygulanmaz.

Zaman damgası biçim dizgesiyle ayrıştırılır; ay adı İngilizce kısaltmadır ve
pandas biçim dizgesi yerel ayardan etkilenmediği için Türkçe Windows
kurulumunda da aynı sonucu verir.

## 4. Parametreler

| Parametre | Değer |
|---|---|
| `EPHEM_TYPE` | `OBSERVER` |
| `QUANTITIES` | `4` (azimut, yükseklik) |
| `ANG_FORMAT` | `DEG` |
| `CAL_FORMAT` | `CAL` |
| `CSV_FORMAT` | `YES` |
| Varsayılan tarama | 5 dakika |
| Varsayılan analiz | 168 saat |

Tam sorgu sözlüğü her satırın `parameters` alanında JSON nesnesi olarak
taşınır, böylece çıktı tek satırdan yeniden üretilebilir.

## 5. Üretilen kolonlar ve bilinçli sınır

K1, veri sözleşmesinin **astronomik alt kümesini** üretir: `site_id`,
`latitude_deg`, `longitude_deg_east`, `timestamp_utc`, `sun_az_deg`,
`sun_alt_deg`, `earth_az_deg`, `earth_alt_deg`, `quality_flag`, `source_id`,
`source_version`, `model_id`, `parameters`.

`terrain_horizon_sun_deg`, `terrain_horizon_earth_deg`, `sun_visible`,
`earth_visible` ve `joint_visible` **üretilmez**. Arazi ufku K2, görünürlük
kararı K3 sahipliğindedir; K1 bu değerleri tahmin etmez.

Kalite bayrağı: dört açının tamamı sayısalsa `valid`, bir kısmı eksikse
`partial`, hiçbiri yoksa `missing`. Horizons `n.a.` değeri `NaN` olarak
taşınır ve hiçbir durumda görünür ya da engelli sayılmaz.

## 6. Sonuçlar

2026-11-14 00:00Z → 2026-11-21 00:00Z, 5 dakika adım, bölge başına 2017
satır, tamamı `valid`, boş değer yok:

| Site | Güneş yüksekliği | Güneş azimutu | Dünya yüksekliği | Dünya azimutu |
|---|---|---|---|---|
| Site01 | +1.004° … +1.501° | 178.940° … 264.093° | −5.036° … +4.019° | 130.451° … 136.232° |
| Site04 | +1.346° … +1.668° | 213.317° … 298.482° | −4.878° … +4.143° | 164.812° … 170.640° |

Fiziksel tutarlılık:

- Güneş yüksekliği her iki bölgede 2 derecenin altında kalıyor; güney
  kutbunda beklenen sıyırma geometrisi.
- Güneş azimutu yedi günde ~85 derece kayıyor; Ay'ın ~13.2°/gün dönüşüyle
  uyumlu.
- Dünya azimutu ~6 derecelik bantta neredeyse sabit, yüksekliği ±5 derece
  salınıyor; senkron dönme ve librasyon beklentisiyle uyumlu.

K2'nin ortalama arazi ufkuyla büyüklük karşılaştırması (**görünürlük kararı
değildir**, azimut çözünürlüklü karar K3'e aittir):

| Site | K1 Güneş yüksekliği | K2 ortalama arazi ufku | Büyüklük ilişkisi |
|---|---|---|---|
| Site01 | +1.004° … +1.501° | −0.373° | Güneş ortalama ufkun üstünde |
| Site04 | +1.346° … +1.668° | +3.219° | Güneş ortalama ufkun altında |

### 6.1 Tüm 12 Artemis III Aday Bölgesi Özeti (`Site01`–`Site09`, `Site11`–`Site13`)

`2026-11-14 00:00Z → 2026-11-21 00:00Z`, 5 dakika adım, `jpl-horizons` (`v1.2`,
`DE441`, `APPARENT=AIRLESS`); `data/cache/ephemeris_{site_id}_20261114T0000_168h.csv`
altındaki 12 bölgenin tamamında **2017 satır**, **0 `NaN`** ve `quality_flag == "valid"`:

| Site | Bölge | Güneş yüksekliği (min … max) | Güneş azimutu | Dünya yüksekliği (min … max) | Dünya azimutu |
|---|---|---|---|---|---|
| Site01 | Connecting ridge | +1.0041° … +1.5014° | 178.9400° … 264.0928° | −5.0359° … +4.0195° | 130.2703° … 136.2323° |
| Site02 | Connecting ridge extension | +0.8548° … +1.6372° | 191.4473° … 276.5981° | −5.2465° … +3.8090° | 142.7808° … 148.7428° |
| Site03 | de Gerlache rim 1 | +0.0562° … +1.0409° | 109.4821° … 194.6120° | −4.0557° … +5.0955° | 60.8465° … 66.6737° |
| Site04 | Shackleton rim | +1.3460° … +1.6678° | 213.3169° … 298.4816° | −4.8783° … +4.1427° | 164.6299° … 170.6395° |
| Site05 | de Gerlache rim 2 | +0.2664° … +1.1969° | 105.4800° … 190.6136° | −4.0574° … +5.0710° | 56.8306° … 62.6903° |
| Site06 | de Gerlache-Kocher massif | −2.6525° … −0.3575° | 157.7391° … 242.8783° | −6.4163° … +2.9736° | 109.2512° … 114.7199° |
| Site07 | Haworth | −0.1375° … +3.2967° | 46.5284° … 131.6411° | −2.1044° … +6.9173° | 3.7635° → 357.9273° (0°/360° geçişli) |
| Site08 | Malapert massif | −0.6768° … +4.6579° | 38.8861° … 123.9430° | −0.6584° … +8.3115° | 349.9881° … 356.0842° |
| Site09 | Leibnitz beta plateau | +1.2487° … +6.2885° | 8.4987° … 93.7349° | −0.6769° … +8.0347° | 319.4546° … 325.8865° |
| Site11 | Nobile rim 2 | +3.8593° … +7.4464° | 67.1747° → 341.6093° (0°/360° geçişli) | −1.7681° … +6.6723° | 292.5881° … 299.3395° |
| Site12 | Amundsen rim | +5.5208° … +7.0524° | 41.8486° → 316.2157° (0°/360° geçişli) | −4.2668° … +4.1487° | 267.4049° … 274.1771° |
| Site13 | Mons Mouton | +1.0219° … +6.8508° | 10.5224° … 95.7386° | −0.0774° … +8.6113° | 321.4133° … 327.8791° |

## 7. Doğrulama

| Kanıt | Yöntem | Sonuç |
|---|---|---|
| Boylam yönü | Aynı enlemde doğu-pozitif 90° ve 270° canlı sorgu | Güneş azimutları 10°'den fazla ayrışıyor; yön doğru |
| Zaman ızgarası | 168 saat / 5 dakika | 2017 damga, tek adım değeri `[5.]` |
| Köken alanları | Yanıt imzası ve `{source: ...}` ayrıştırması | `1.2`, `DE441`; `sha256` önbellekten yeniden hesaplandı |
| Hata yolları | HTTP 503, kesik `$$SOE`, `n.a.`, eksik kolon, bozuk takvim | Hepsi hata ya da `NaN`; sessiz kabul yok |
| Ağsız tekrar | `pytest-recording` kaseti, `--record-mode=none` | 54 K1 testi (depo geneli 225 test), tamamı geçer |
| **Bağımsız yol** | Alt-nokta geometrisi, 5 damga × 2 bölge × 2 gövde | **Azimutta ≤ 0.0038°, yükseklikte ≤ 0.0004°** |

### 7.1 Bağımsız yol nasıl kurgulandı

Üretim hattı Horizons'tan azimut ve yüksekliği **hazır** alır
(`QUANTITIES=4`). Bu, hattın kendi içinde tutarlı olduğunu gösterir ama
Horizons çıktısını yanlış yorumlamış olma olasılığını dışlamaz.

İkinci yol başka bir niceliği kullanır: Horizons'ın bildirdiği alt-güneş
(`SunSub-LON/LAT`) ve alt-dünya (`ObsSub-LON/LAT`) noktası ile gövde
uzaklığı. Buradan azimut ve yükseklik, `luna_sight.ephemeris.verify`
içindeki vektör hesabıyla yerel ufuk çerçevesinde yeniden üretilir:

```
hedef  = d · (cosδ cosλ_alt, cosδ sinλ_alt, sinδ)
gözlem = R · (cosφ cosλ, cosφ sinλ, sinφ)
v      = hedef − gözlem

yukarı = gözlem/R,  doğu = (−sinλ, cosλ, 0),
kuzey  = (−sinφ cosλ, −sinφ sinλ, cosφ)

yükseklik = atan2(v·yukarı, |v_yatay|)
azimut    = atan2(v·doğu, v·kuzey) mod 360
```

Bu yol şu hataları yakalardı: boylamın ters yönde alınması, azimutun
güneyden ölçülmesi, enlem işareti hatası, paralaksın ihmali.

### 7.2 Beş damgada sonuç

`scripts/k1_independent_check.py`, 42 saat adımla iki uç dahil beş damga:

```text
=== Site01  lat=-89.463163  lon_e=-137.489553   model=DE441  surum=1.2
damga (UTC)          govde    A azimut   B azimut     d_az    A yuks    B yuks    d_alt
2026-11-14T00:00Z    sun      264.0928   264.0930   0.0002    1.5014    1.5014   0.0000
2026-11-14T00:00Z    earth    136.2323   136.2362   0.0038   -5.0359   -5.0356   0.0003
2026-11-15T18:00Z    sun      242.7731   242.7733   0.0002    1.3100    1.3100   0.0000
2026-11-15T18:00Z    earth    133.8255   133.8277   0.0022   -3.0048   -3.0046   0.0002
2026-11-17T12:00Z    sun      221.4740   221.4742   0.0002    1.1499    1.1499   0.0000
2026-11-17T12:00Z    earth    131.7301   131.7304   0.0003   -0.6273   -0.6273   0.0000
2026-11-19T06:00Z    sun      200.1965   200.1967   0.0002    1.0434    1.0434   0.0000
2026-11-19T06:00Z    earth    130.4507   130.4490   0.0017    1.8297    1.8295   0.0002
2026-11-21T00:00Z    sun      178.9400   178.9402   0.0002    1.0041    1.0041   0.0000
2026-11-21T00:00Z    earth    130.4583   130.4547   0.0036    4.0195    4.0192   0.0003

=== Site04  lat=-89.766811  lon_e=-171.869898   model=DE441  surum=1.2
2026-11-14T00:00Z    sun      298.4816   298.4818   0.0002    1.6678    1.6678   0.0000
2026-11-14T00:00Z    earth    170.6395   170.6434   0.0038   -4.8783   -4.8779   0.0004
2026-11-15T18:00Z    sun      277.1591   277.1593   0.0002    1.5846    1.5846   0.0000
2026-11-15T18:00Z    earth    168.2212   168.2234   0.0022   -2.8613   -2.8611   0.0002
2026-11-17T12:00Z    sun      255.8567   255.8569   0.0002    1.4952    1.4952   0.0000
2026-11-17T12:00Z    earth    166.1117   166.1120   0.0003   -0.4963   -0.4963   0.0000
2026-11-19T06:00Z    sun      234.5761   234.5763   0.0002    1.4121    1.4121   0.0000
2026-11-19T06:00Z    earth    164.8174   164.8157   0.0017    1.9529    1.9527   0.0002
2026-11-21T00:00Z    sun      213.3169   213.3171   0.0002    1.3460    1.3460   0.0000
2026-11-21T00:00Z    earth    164.8116   164.8080   0.0036    4.1427    4.1424   0.0003

=== ozet (20 karsilastirma: 2 bolge x 5 damga x 2 govde)
en buyuk azimut farki   : 0.0038 derece
en buyuk yukseklik farki: 0.0004 derece
```

Güneş için iki yol azimutta 0.0002, yükseklikte 0.0000 derece ayrışıyor.
Dünya için azimut artığı 0.0038 dereceye çıkıyor; büyüklük ~14 yay
saniyesidir ve ışık zamanı ile aberasyonun iki nicelikte farklı epokta
uygulanmasıyla uyumludur. Görünürlük kararı için anlamlı değildir.

### 7.3 Paralaksın gerekliliği ölçüldü

Gözlemci gövde merkezinde sayılırsa Dünya için (Site01, 2026-11-14 00:00Z):

| Hesap | Azimut | Yükseklik |
|---|---|---|
| `OBSERVER` tablosu (Yol A) | 136.2323° | −5.0359° |
| Alt-nokta + paralaks (Yol B) | 136.2362° | −5.0356° |
| Alt-nokta, paralaks ihmal | 136.2362° | **−4.7911°** |

Paralaks ihmal edilirse yükseklik hatası **0.2448 derece** olur; bizim
artığımızın ~600 katı. Güneş kutupta ufku sıyırdığı için bu mertebede bir
hata saatler mertebesinde görünürlük farkı üretir. Güneş uzaklığında aynı
düzeltme 0.001 derecenin altındadır.

## 8. Bilimsel sınırlar

- Bu modül **görünürlük kararı vermez**. Arazi ufkuyla karşılaştırma ve
  geçiş sınırı inceltme K3 motoruna aittir.
- Gözlemci 1737.4 km yarıçaplı küre üzerinde, yükseklik 0 km alınır. Yerel
  topoğrafik yükseklik hesaba katılmaz; aday nokta yüksekliği K2 DEM'inden
  gelirse `Site.elevation_km` ile verilebilir.
- Bağımsız yol Horizons'ın **kendi** alt-nokta niceliğini kullanır. Bu,
  Horizons çıktısının bizim tarafımızda doğru yorumlandığını kanıtlar;
  Horizons'ın kendi doğruluğunu bağımsız olarak kanıtlamaz. Tamamen harici
  bir kontrol SPICE çekirdekleri (`spiceypy`, DE440/DE441 + MOON_ME) ile
  yapılabilir; bu koşuda yapılmadı.
- `n.a.` dışındaki eksik veri biçimleri Horizons tarafından üretilirse
  ayrıştırıcı hata fırlatır; sessiz kabul yoktur.
- Işık zamanı ve aberasyon Horizons tarafından uygulanır, bizim tarafta
  yeniden hesaplanmaz. Dünya için 0.0038 derecelik azimut artığının kaynağı
  budur.

## 9. Yeniden üretme

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# Gerçek seri (168 saat, 5 dakika, iki bölge) + manifest satırları
.venv\Scripts\python.exe -m luna_sight.ephemeris --start "2026-11-14 00:00"

# Bağımsız doğrulama (beş damga, iki yol)
.venv\Scripts\python.exe scripts/k1_independent_check.py

# Ağsız testler
.venv\Scripts\python.exe -m pytest --record-mode=none
```

## 10. K3 entegrasyonu

Görünürlük motoru `EphemerisProvider` protokolünü bekler. Gerçek veriyle
karşılayan sağlayıcı `luna_sight.ephemeris.HorizonsEphemeris`:

```python
from luna_sight.ephemeris import HorizonsEphemeris
from luna_sight.visibility import build_site_series

frame = build_site_series(
    "Site01", "2026-11-14 00:00", days=7, step_minutes=5, ephemeris=HorizonsEphemeris()
)
```

Sorgu adımı istenen ızgaradan çıkarılır; düzensiz ızgara ve dakika altı adım
reddedilir. Horizons bir damga için değer vermezse hücre `NaN` kalır ve
doldurulmaz; o satırı `uncertain` olarak sınıflamak K3'ün işidir. `HorizonsEphemeris`
sınıfı kanonik köken özniteliklerini (`source_id="jpl-horizons"`, `source_version="1.2"`,
`model_id="DE441"`) taşır ve çağrı sonrasında yanıt değerleriyle günceller; böylece
`VisibilityRunner` gerçek efemerisle koşarken köken alanlarını korur. Ham
yanıtlar `provider.last_responses` içinde durur, köken kaydı oradan yazılır.
