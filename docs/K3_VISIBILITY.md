# K3 — Görünürlük ve pencere motoru

Issue: [#3](https://github.com/kingos352/luna-sight/issues/3) · Dal: `k3/visibility-engine`
Bağımlılık: [#6](https://github.com/kingos352/luna-sight/pull/6) (K2 ufuk profili) — bu dal
`k2/lola-horizon` üzerine kuruludur.

Bu belge, Güneş/Dünya geometrisini K2 ufuk profiliyle birleştiren görünürlük
motorunu, durum modelini, geçiş sınırı inceltmesini, doğrulama kanıtını ve
bilimsel sınırları kaydeder.

## 1. Kapsam

**Girdi**

| Girdi | Kaynak | Not |
|---|---|---|
| Ufuk profili | `outputs/k2/<Site>_horizon_<r>m.csv` | 360 satır: `azimuth_deg`, `horizon_deg`, `gap_fraction`, `native_coverage_fraction` |
| Ephemeris serisi | K1 (JPL Horizons) CSV veya `synthetic.py` senaryosu | `timestamp_utc`, `sun_az_deg`, `sun_alt_deg`, `earth_az_deg`, `earth_alt_deg` |

**Çıktı**

| Dosya | İçerik |
|---|---|
| `outputs/k3/<Site>_visibility.csv` | Örnek başına durum, gerekçe, ufuk, marj ve sözleşme alanları |
| `outputs/k3/<Site>_windows.json` | Güneş, Dünya ve ortak görünürlük için kesintisiz pencereler |
| `outputs/k3/<Site>_summary.json` | Yapılandırma, seri bilgisi, durum süreleri, en uzun pencere |

## 2. Durum modeli

Sözleşmedeki üç durum (`docs/DATA_CONTRACT.md`) korunur; durumlar **boolean
değil metindir**, çünkü `uncertain` üçüncü bir değerdir ve `false` ile
karıştırılmamalıdır.

| Durum | Anlam | Gerekçe kodları |
|---|---|---|
| `visible` | Hedef, yerel ufkun en az `margin_deg` üzerinde | `clear` |
| `blocked` | Hedef, yerel ufkun en az `margin_deg` altında | `occluded` |
| `uncertain` | Karar verilemez: geçiş bandı veya eksik veri | `transition_band`, `missing_ephemeris`, `missing_horizon`, `quality_missing` |

Kurallar:

1. `alt_deg` yoksa → `uncertain / missing_ephemeris`
2. Ufuk profili o azimutta yoksa (`NaN`) → `uncertain / missing_horizon`
3. Kalite bayrağı `missing` ise → `uncertain / quality_missing`
   (yükseklik ufkun üzerinde olsa bile karar verilmez)
4. `|alt − ufuk| ≤ margin_deg` → `uncertain / transition_band`
5. `alt − ufuk > margin_deg` → `visible`, aksi halde `blocked`

**Ortak görünürlük (`joint_visible`)**

| Güneş | Dünya | Ortak | Gerekçe |
|---|---|---|---|
| `visible` | `visible` | `visible` | `clear` |
| herhangi biri `blocked` | — | `blocked` | `occluded` |
| aksi halde | — | `uncertain` | belirsizliğin gerekçesi |

Kesin engel, diğer cisim belirsiz olsa da ortak kararı belirler: iki cisimden
biri kesin olarak ufkun altındaysa ortak görünürlük sağlanamaz. Ortak marj,
iki cismin marjlarından küçüğüdür; cisimlerden birinin marjı bilinmiyorsa
ortak marj da `None` (boş) bırakılır.

## 3. Yapılandırma

| Parametre | Varsayılan | Açıklama |
|---|---|---|
| `margin_deg` | `0.10` | Geçiş bandının yarı genişliği; `0` verilirse band kapanır |
| `refine_boundaries` | `true` | Pencere sınırlarını enterpolasyonla incelt |
| `quality_flag_missing` | `"missing"` | Bu bayrağı taşıyan örnek doğrudan `uncertain` |

Yapılandırma özet JSON'unda `config` alanı olarak yazılır; çıktı tekrar
üretilebilir.

## 4. Yöntem

### 4.1 Ufuk araması

K2 profili 0–360° arasında **daireseldir**. `HorizonProfileLookup` profili
iki yönde birer tur genişletip doğrusal enterpolasyon yapar; böylece 359° ile
1° arasındaki geçiş yapay olarak 0°'ye sıçramaz. Profilde `NaN` olan bir
noktanın komşu aralıkları da `NaN` döner ve motor bunu `missing_horizon`
olarak raporlar.

### 4.2 Sınıflandırma

```
marj = alt_deg − ufuk_deg
|marj| ≤ margin  → uncertain (transition_band)
marj  > margin  → visible   (clear)
marj  < −margin → blocked   (occluded)
```

### 4.3 Pencereler ve sınır inceltmesi

Durum serisi kesintisiz koşulara bölünür. İki komşu koşu arasındaki sınır,
marjın zaman içinde doğrusal değiştiği varsayımıyla inceltilir:

```
t_sınır = t0 + (t1 − t0) · (−(m0 − L)) / ((m1 − L) − (m0 − L))
```

- `L = 0` → `visible ↔ blocked` doğrudan geçişi (ufuk çizgisi)
- `L = +margin_deg` → `visible ↔ uncertain` sınırı (bandın üst kenarı)
- `L = −margin_deg` → `uncertain ↔ blocked` sınırı (bandın alt kenarı)

Marjı bilinmeyen belirsizliklerde (eksik ephemeris, eksik ufuk) inceltme
yapılmaz; pencere sınırı örnek zamanında kalır ve `*_refined = false` olur.
5 dakikalık örneklemede inceltme, ±2.5 dakikalık kuantalamayı kaldırır.

## 5. Veri sözleşmesi eşlemesi

Çıktı CSV'si sözleşmedeki zorunlu alanların tamamını taşır:

`site_id`, `latitude_deg`, `longitude_deg_east`, `timestamp_utc`,
`sun_az_deg`, `sun_alt_deg`, `earth_az_deg`, `earth_alt_deg`,
`terrain_horizon_sun_deg`, `terrain_horizon_earth_deg`, `sun_visible`,
`earth_visible`, `joint_visible`, `quality_flag`, `source_id`,
`source_version`, `model_id`, `parameters`

Ek alanlar: `sun_margin_deg`, `earth_margin_deg`, `joint_margin_deg`,
`sun_reason`, `earth_reason`, `joint_reason`.

`latitude_deg` / `longitude_deg_east`, seride yoksa K2 özet dosyasındaki
karo merkezi koordinatından doldurulur; o da yoksa alan boş bırakılır —
uydurulmaz.

## 6. Örnek çıktılar (senaryo verisi — bilimsel değil)

`--series` verilmediğinde motor, 168 saatlik **hızlandırılmış azimut
taraması** senaryosu üretir. Her satır `quality_flag=test_fixture`,
`source_id=synthetic-scenario`, `model_id=accelerated-azimuth-sweep` taşır
ve özet dosyasında `synthetic_test_fixture: true` yazar.

| Bölge | Gövde | Görünür oranı | Pencere | En uzun görünür | İnceltilmiş sınır |
|---|---|---|---|---|---|
| Site01 (4 km), 168 sa | Güneş | %28.7 | 5 | 48.20 sa | 5 |
| Site01 | Dünya | %36.1 | 5 | 60.66 sa | 5 |
| Site01 | Ortak | %15.1 | 5 | 25.40 sa | 5 |
| Site04 (4 km), 168 sa | Güneş | %41.8 | 5 | 70.14 sa | 5 |
| Site04 | Dünya | %42.1 | 5 | 70.80 sa | 5 |
| Site04 | Ortak | %26.7 | 5 | 44.93 sa | 5 |

Örnek pencere (Site04, Güneş):

```text
blocked    2026-11-15T00:00:00Z → 2026-11-18T13:20:18Z   (85.34 sa)
uncertain  2026-11-18T13:20:18Z → 2026-11-18T13:29:12Z   (0.15 sa, bant)
visible    2026-11-18T13:29:12Z → 2026-11-21T11:37:46Z   (70.14 sa)
uncertain  2026-11-21T11:37:46Z → 2026-11-21T11:48:36Z   (0.18 sa, bant)
blocked    2026-11-21T11:48:36Z → 2026-11-22T00:00:00Z   (12.19 sa)
```

Bu sayılar yalnızca motorun uçtan uca çalıştığını gösterir. Gerçek görev
analizi için K1'in JPL Horizons serisi (`--series`) kullanılmalıdır.

## 7. Doğrulama

`pytest --override-ini addopts=` → **80 test, hepsi geçiyor**. K3 ile ilgili
dosyalar:

| Dosya | Kapsam |
|---|---|
| `tests/test_visibility_classify.py` | Normal, geçiş bandı (sınır dahil), eksik yükseklik/ufuk, `missing` kalite, yapılandırma doğrulaması |
| `tests/test_visibility_profile.py` | Nokta ve ara değer, 359°–0° dairesel geçiş, `NaN` bölgesi, gerçek K2 profili, hatalı CSV |
| `tests/test_visibility_series.py` | UTC normalizasyonu, `Z`/`+03:00`, boş/`NaN` hücre → `None`, azalan zaman reddi, eksik sütun |
| `tests/test_visibility_engine.py` | Ortak durum tablosu, eksik veri önceliği, marj, doğrudan ve bant kenarı inceltmesi, gövde bazlı pencereler, özet |

Kabul ölçütleri karşılığı:

- **`visible/blocked/uncertain` destekleniyor** → sınıflandırma ve ortak durum testleri
- **Eksik veri açık durum üretiyor** → `missing_ephemeris`, `missing_horizon`, `quality_missing`
- **Geçiş sınırı inceltildi** → `refine_crossing_time` birim testleri + rapor çıktısında `*_refined: true`
- **Normal / sınır / hata vakaları test edildi** → yukarıdaki dört dosya

## 8. Bilimsel sınırlar

1. **`margin_deg = 0.1°` kutupta uzun bir zamana karşılık gelir.** Güney
   kutbunda Güneş yüksekliği saatte yaklaşık 0.005–0.015° değişir; 0.2°'lik
   bant 15–40 saatlik bir belirsizlik penceresi demektir. 168 saatlik bir
   görev penceresinde bu, görünürlük kararının büyük bölümünü `uncertain`
   yapabilir. Duyarlılık analizi (`--margin 0.05 / 0.1 / 0.2`) zorunludur.
2. **Ufuk profili belirsizliği sayısallaştırılmadı.** K2 çıktısı `partial`
   kalite bayrağı ve yerel kapsam oranı taşır; `*_toterr.tif` ürünü
   indirilmedi. Bant genişliği bu nedenle sabit varsayıldı.
3. **Gözlemci noktası DEM karo merkezidir** (K2 sınırı). İniş elipsi seçimi
   ve yerel en iyi nokta taraması bu görevin dışındadır.
4. **Senaryo serisi astronomik model değildir.** Azimut taraması
   hızlandırılmıştır; çıktılar yalnızca `test_fixture` olarak kullanılmalıdır.
5. **Doğrusal zaman enterpolasyonu** 5 dakikalık örnekleme için yeterlidir;
   çok daha seyrek örneklemede geçiş zamanı hatası büyür.
6. **Kırılma/atmosfer yok.** Ay'da atmosfer olmadığı için yükseklik tanımı
   geometriktir; bu bir varsayım değil, fiziksel gerçektir.

## 9. Yeniden üretme

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest --override-ini addopts= -q   # 80 passed

# K2 profili + senaryo serisi (test_fixture):
.venv/Scripts/python scripts/k3_visibility_report.py \
  --profile outputs/k2/Site04_horizon_4000m.csv

# K1 gerçek serisi geldiğinde:
.venv/Scripts/python scripts/k3_visibility_report.py \
  --profile outputs/k2/Site04_horizon_4000m.csv \
  --series data/processed/k1_horizons_Site04.csv \
  --margin 0.10
```

## 10. Sonraki adım

- **K1 entegrasyonu:** `--series` ile gerçek Horizons serisi; `latitude_deg`
  ve `longitude_deg_east` alanları K1 çıktısında dolu olmalı.
- **Duyarlılık analizi:** `margin` ve ufuk yarıçapı (2 km / 4 km) için
  görünürlük oranı taraması; K4'te "belirsizlik" olarak gösterilmeli.
- **K4:** `joint_visible` pencereleri zaman çizelgesinde; `uncertain` bantlar
  ayrı renkte ve gerekçe etiketiyle gösterilmeli.
- **İsteğe bağlı:** `*_toterr.tif` ile ufuk belirsizliğini metre→derece
  dönüştürüp `margin_deg`'i azimuta göre değişken yapmak.
