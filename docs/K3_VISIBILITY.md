# K3 — Görünürlük ve pencere motoru

Issue: [#3](https://github.com/kingos352/luna-sight/issues/3) · Dal: `k3/visibility-merged`
Bağımlılık: [#6](https://github.com/kingos352/luna-sight/pull/6) (K2 ufuk profili) — bu dal
`k2/lola-horizon` üzerine kuruludur.

Bu belge, Güneş/Dünya geometrisini K2 ufuk profiliyle birleştiren görünürlük
motorunu, durum modelini, geçiş sınırı inceltmesini, doğrulama kanıtını ve
bilimsel sınırları kaydeder.

## 0. Bu dal neyi birleştirir

Repoda iki ayrı K3 uygulaması gelişmişti. `k3/visibility-merged` bunları tek
pakette birleştirir:

| Katman | Kaynak | İçerik |
|---|---|---|
| Çekirdek | `k3/visibility-engine` | Durum modeli + gerekçe kodları, geçiş sınırı inceltmesi, gövde bazlı pencere/analiz, senaryo serisi |
| Entegrasyon | `k3/engine-skeleton` | K1/K2 sağlayıcı protokolleri, UTC ızgarası, sözleşme tablosu + teşhis sütunları, site bazlı özet, uçtan uca runner, CLI |

Çekirdek modüller (`states`, `series`, `profile`, `engine`, `analysis`,
`synthetic`) yol ve API olarak korunmuştur; böylece her iki dalın testleri de
çalışır.

**Modül haritası**

| Modül | Sorumluluk |
|---|---|
| `states.py` | `visible` / `blocked` / `uncertain`, gerekçe kodları, `VisibilityConfig` |
| `series.py` | `Sample`, CSV okuma, UTC normalizasyonu, seri doğrulaması |
| `profile.py` | `HorizonProfileLookup`: K2 profili üzerinde dairesel arama |
| `engine.py` | `classify`, `evaluate_series`, `build_windows`, sınır inceltmesi |
| `analysis.py` | Gövde bazlı süre/oran, duyarlılık satırları, marj farkı |
| `synthetic.py` | `test_fixture` senaryo serisi (astronomik model değil) |
| `providers.py` | `EphemerisProvider` / `HorizonProvider` protokolleri, `ConstantHorizon`, `SyntheticEphemeris`, `load_horizon_profile` |
| `grid.py` | Aralık-tam UTC analiz ızgarası (varsayılan 168 sa / 5 dk = 2016 örnek) |
| `table.py` | `docs/DATA_CONTRACT.md` tablosu + marj/gerekçe teşhis sütunları |
| `summary.py` | Site bazlı süre, oran, pencere ve en uzun görünürlük özeti |
| `runner.py` | `Site`, `RunnerConfig`, `VisibilityRunner`, `run_demo` |
| `__main__.py` | CLI: `python -m luna_sight.visibility` |

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
| `outputs/k3/sensitivity.csv` | Profil yarıçapı × marj taraması: durum oranları, pencere sayısı, en uzun görünür pencere |

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
| `start_utc` | `2026-11-14T00:00:00Z` | Analiz penceresinin UTC başlangıcı (saat dilimi zorunlu) |
| `hours` / `step_minutes` | `168` / `5` | Izgara; `hours`, adımın tam katı olmalı |

Yapılandırma özet JSON'unda `config` alanı olarak yazılır; çıktı tekrar
üretilebilir.

## 4. Yöntem

### 4.1 Ufuk araması

K2 profili 0–360° arasında **daireseldir**. `HorizonProfileLookup` profili
iki yönde birer tur genişletip doğrusal enterpolasyon yapar; böylece 359° ile
1° arasındaki geçiş yapay olarak 0°'ye sıçramaz. Profilde `NaN` olan bir
noktanın komşu aralıkları da `NaN` döner ve motor bunu `missing_horizon`
olarak raporlar. K2 CSV'leri BOM'lu (`utf-8-sig`) olabilir; okuyucu bunu
destekler.

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

### 4.4 Analiz ızgarası ve süreler

`grid.analysis_timestamps` 168 saat / 5 dakika için **2016 örnek** üretir; bu,
her örnek `[t, t + step)` aralığının başlangıcı sayıldığında 168 saatlik
kapsama demektir. Motor ise ilk ve son örnek arasındaki aralığı değerlendirir
(2015 × 5 dk = **167.92 saat**); `summary.py` süreleri aynı tanımla, yani
`(N − 1) × step` olarak hesaplar. Böylece özet ile pencere toplamları birebir
tutarlı kalır.

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
uydurulmaz. `table.validate_table` sütunları, durum değerlerini, gerekçe
kodlarını, UTC zaman damgalarını ve `(site_id, timestamp_utc)` tekilliğini
denetler.

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

## 7. Duyarlılık analizi

`scripts/k3_sensitivity.py`, aynı seri üzerinde **profil yarıçapı** (K2:
2 km / 4 km) ve **geçiş bandı** (`margin_deg`) seçimlerini tarar. Amaç, tek
bir marj değerinin ürettiği sayıyı "kesin" gibi sunmamaktır.

Yöntem:

1. `outputs/k2/*_horizon_*m.csv` profilleri otomatik bulunur.
2. Her bölge için seri **bir kez** üretilir; böylece fark yalnızca profil ve
   marjdan kaynaklanır.
3. Her kombinasyon için `visible` / `blocked` / `uncertain` süreleri ve
   oranları, pencere sayısı, en uzun görünür pencere ve inceltilmiş sınır
   sayısı `outputs/k3/sensitivity.csv` dosyasına yazılır.

Ortak (`joint_visible`) görünürlük oranı, 168 saatlik senaryo serisi:

| Bölge | Yarıçap | 0.02° | 0.05° | 0.10° | 0.20° |
|---|---|---|---|---|---|
| Site01 | 2 km | %15.5 | %15.3 | %15.1 | %14.6 |
| Site01 | 4 km | %15.5 | %15.3 | %15.1 | %14.6 |
| Site04 | 2 km | %30.6 | %30.6 | %30.5 | %30.4 |
| Site04 | 4 km | %26.8 | %26.8 | %26.7 | %26.6 |

En uzun kesintisiz ortak pencere (saat):

| Bölge | Yarıçap | 0.02° | 0.05° | 0.10° | 0.20° |
|---|---|---|---|---|---|
| Site01 | 2 km | 26.00 | 25.78 | 25.40 | 24.55 |
| Site01 | 4 km | 26.00 | 25.78 | 25.40 | 24.55 |
| Site04 | 2 km | 51.44 | 51.42 | 51.29 | 51.13 |
| Site04 | 4 km | 45.06 | 45.01 | 44.93 | 44.76 |

Okuma:

- **Yarıçap etkisi bölgeye bağlı.** Site01'de 2 km ve 4 km profilleri
  birebir aynı sonucu verir; ufuk, gözlemcinin 210 m yakınındaki mikro-rölyef
  tarafından belirleniyor (K2 bulgusu). Site04'te 4 km profil, 2 km'ye göre
  ortak görünürlüğü **3.8 yüzde puan** düşürür ve en uzun pencereyi ~0.5 saat
  kısaltır. Bu yüzden tek bir yarıçap seçmek Site04 için yanıltıcıdır.
- **Marj etkisi senaryoda küçük görünür, gerçekte değildir.** Senaryo Güneş'i
  168 saatte tam tur attırır; gerçekte bu ~27.3 gün sürer. Yükseklik değişim
  hızı yaklaşık 10 kat fazla olduğu için 0.2°'lik bant senaryoda yalnızca
  %0.4–3.8 belirsizlik üretir. Gerçek K1 serisinde aynı bant 15–40 saate
  karşılık gelir; bu tablodaki **oranlar gerçek göreve taşınmamalıdır**.
- Marj büyüdükçe görünür oran ve en uzun pencere **monoton** azalır; bu,
  sınıflandırma ve pencere mantığının tutarlı olduğunu gösteren bir sanity
  kontrolüdür.

## 8. Doğrulama

`python -m pytest` → **116 test, hepsi geçiyor** (2 K2-profili testi dahil;
K2 çıktıları bu dalda mevcut olduğu için atlanmıyor).

| Dosya | Kapsam |
|---|---|
| `tests/test_visibility_classify.py` | Normal, geçiş bandı (sınır dahil), eksik yükseklik/ufuk, `missing` kalite, yapılandırma doğrulaması |
| `tests/test_visibility_profile.py` | Nokta ve ara değer, 359°–0° dairesel geçiş, `NaN` bölgesi, gerçek K2 profili, hatalı CSV |
| `tests/test_visibility_series.py` | UTC normalizasyonu, `Z`/`+03:00`, boş/`NaN` hücre → `None`, azalan zaman reddi, eksik sütun |
| `tests/test_visibility_engine.py` | Ortak durum tablosu, eksik veri önceliği, marj, doğrudan ve bant kenarı inceltmesi, gövde bazlı pencereler, özet |
| `tests/test_visibility_analysis.py` | Süre/oran toplamı, marj→belirsizlik geçişi, eksik ufuk oranı, pencere sayısı, üç gövdelik tablo satırı, marj farkı |
| `tests/test_grid.py` | Aralık-tam ızgara, 168 sa/5 dk = 2016 örnek, UTC zorunluluğu, geçersiz adım/süre |
| `tests/test_runner.py` | Site/yapılandırma doğrulaması, sağlayıcı sözleşmesi, sözleşme + teşhis sütunları, site bazlı ufuk, BOM'lu profil, `NaN` boşluğu → `uncertain`, demo |
| `tests/test_summary.py` | Süre/oran toplamı, pencere sayısı/en uzun pencere, tek örnek, ortak durum, tablo doğrulaması |

Kabul ölçütleri karşılığı:

- **`visible/blocked/uncertain` destekleniyor** → sınıflandırma ve ortak durum testleri
- **Eksik veri açık durum üretiyor** → `missing_ephemeris`, `missing_horizon`, `quality_missing`
- **Geçiş sınırı inceltildi** → `refine_crossing_time` birim testleri + rapor çıktısında `*_refined: true`
- **Normal / sınır / hata vakaları test edildi** → yukarıdaki dosyalar

## 9. Bilimsel sınırlar

1. **`margin_deg = 0.1°` kutupta uzun bir zamana karşılık gelir.** Güney
   kutbunda Güneş yüksekliği saatte yaklaşık 0.005–0.015° değişir; 0.2°'lik
   bant 15–40 saatlik bir belirsizlik penceresi demektir. 168 saatlik bir
   görev penceresinde bu, görünürlük kararının büyük bölümünü `uncertain`
   yapabilir. Bu yüzden `scripts/k3_sensitivity.py` ile marj taraması
   yayımlanır (bkz. bölüm 7); tek bir marj değeri "kesin" sunulmaz.
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

## 10. Yeniden üretme

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest        # 116 passed

# K2 profili + senaryo serisi (test_fixture):
.venv/Scripts/python scripts/k3_visibility_report.py \
  --profile outputs/k2/Site04_horizon_4000m.csv

# Yarıçap × marj duyarlılık taraması:
.venv/Scripts/python scripts/k3_sensitivity.py \
  --margins 0.02,0.05,0.10,0.20

# Motorun kendi CLI'sı (168 sa, aralık-tam ızgara):
$env:PYTHONPATH = "src"
.venv/Scripts/python -m luna_sight.visibility \
  --profile outputs/k2/Site04_horizon_4000m.csv \
  --site-id Site04 --latitude -89.766811 --longitude -171.869898 \
  --hours 168 --csv outputs/k3/Site04_rover_visibility.csv

# K1 gerçek serisi geldiğinde:
.venv/Scripts/python -m luna_sight.visibility \
  --profile outputs/k2/Site04_horizon_4000m.csv \
  --series data/processed/k1_horizons_Site04.csv \
  --csv outputs/k3/Site04_visibility.csv \
  --windows-json outputs/k3/Site04_windows.json \
  --summary-json outputs/k3/Site04_summary.json
```

**Bağımlılık dosyaları:** kurulum için doğrulanmış sürümleri taşıyan
`requirements.txt` kullanılır. `pyproject.toml` paketleme/CI içindir ve aynı
alt sınırları taşır. İki dosya birlikte güncellenmelidir; tek kaynağa indirme
kararı K5'te bekliyor.

## 11. Sonraki adım

- **K1 entegrasyonu:** `--series` ile gerçek Horizons serisi; `latitude_deg`
  ve `longitude_deg_east` alanları K1 çıktısında dolu olmalı.
- **Gerçek seriyle duyarlılık:** `k3_sensitivity.py --series ...`; senaryo
  yerine K1 serisi kullanıldığında marj→saat dönüşümü gerçek hızıyla görülür.
- **K4:** `joint_visible` pencereleri zaman çizelgesinde; `uncertain` bantlar
  ayrı renkte ve gerekçe etiketiyle gösterilmeli; duyarlılık tablosu
  "belirsizlik" göstergesi olarak sunulmalı.
- **İsteğe bağlı:** `*_toterr.tif` ile ufuk belirsizliğini metre→derece
  dönüştürüp `margin_deg`'i azimuta göre değişken yapmak.
