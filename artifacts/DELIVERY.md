# Teslim kaydı

Issue: [#5](https://github.com/kingos352/luna-sight/issues/5) · Sahip: K5 ·
Kayıt tarihi: 2026-11-15

Bu belge, teslim edilen sürümün ne olduğunu, hangi kanıtla doğrulandığını ve
neyin **henüz tamamlanmadığını** kaydeder. Eksikler saklanmaz: jüri karşısında
bilinmeyen bir boşluk, bilinen bir boşluktan daha pahalıdır.

## 1. Teslim edilen sürüm

| Alan | Değer |
|---|---|
| Dal | `fix/k1-k5-full-sync` (`main` adayı) |
| Temel Commit | `3a37d78` + `v3.0.0` K1–K5 tam senkronizasyon, 5 kapatılan boşluk ve 5 uçuş fiziği modülü |
| Zaman | 2026-11-15 |
| Python | 3.12 (`.python-version`) |
| Giriş noktası | `app/app.py` (Streamlit — 6 sekme, 12 Artemis III aday bölgesi) |

Beş rolün tamamı bu sürümde: K1 efemeris, K2 arazi ve 3B/eğim riski, K3
görünürlük motoru, K4 arayüz, K5 entegrasyon/yönetişim/demo.

## 2. Doğrulama kanıtı

Hepsi `fix/k1-k5-full-sync` çalışma alanında güncel durumla koşturuldu.

| Kontrol | Komut | Sonuç |
|---|---|---|
| Bağımlılık ağacı | `.venv\Scripts\python.exe -m pip check` | `No broken requirements found.` |
| Biçimlendirme | `.venv\Scripts\ruff.exe format --check .` | `86 files already formatted` |
| Kod denetimi | `.venv\Scripts\ruff.exe check .` | `All checks passed!` |
| Testler | `.venv\Scripts\python.exe -m pytest -q --record-mode=none` | **248 passed** |
| Kanonik sözleşme | `.venv\Scripts\python.exe scripts/check_governance.py` | `Sonuc: gecti. 0 uyari.` |
| Uygulama ve uçuş fiziği testleri | `tests/test_app_smoke.py`, `tests/test_flight_physics.py`, `tests/test_surface_3d.py` (`pytest` içinde) | Geçti (canlı `/_stcore/health` bu koşuda ayrıca başlatılmadı; önceki `f6b361c` sürümünde `200 ok`) |

CI kapıları `main` üzerinde zorunlu (ADR-500): `structure`,
`Kanonik sözleşme`, `ubuntu-latest / Python 3.12`, `windows-latest / Python 3.12`.

### Bilimsel doğrulama

| Kanıt | Sonuç | Kayıt |
|---|---|---|
| K1 efemeris, bağımsız ikinci yol | azimutta ≤ **0.0038°**, yükseklikte ≤ **0.0004°** fark (20 karşılaştırma) | `docs/K1_EPHEMERIS.md` §7 |
| Boylam yönü, canlı sorgu | 90°E ve 270°E azimutları 10°'den fazla ayrışıyor | `docs/K1_EPHEMERIS.md` §7 |
| K2 koordinat dönüşümü | gidiş-dönüş Δ < 1e-3 m; GDAL/PROJ ile karşılaştırıldı | `docs/K2_HORIZON.md` §6 |
| K2 ufuk algoritması | sentetik düzlem/sırt vakalarında analitik açıyla eşleşiyor | `docs/K2_HORIZON.md` §6 |
| K3 motoru | geçiş bandı ayrı sınıf, eksik veri görünür sayılmıyor | `docs/K3_VISIBILITY.md` |
| Uçtan uca gerçek koşu | **12 Artemis III adayı** (`Site01`–`Site09`, `Site11`–`Site13`) × 2017 örnek, tamamı `valid` | `outputs/k3/*_summary.json`, `docs/K1_EPHEMERIS.md` §6.1, `docs/REAL_RUN.md` |
| 3B rölyef ve arazi riski | 12 aday bölgede eğim/krater riski ve 3B yüzey testleri | `tests/test_surface_3d.py`, `tests/test_terrain_sites.py` |

## 3. Bilimsel sonuç

### 3.1 Yüksek çözünürlüklü A/B referans çifti (5 m/piksel)

2026-11-14 00:00Z → 2026-11-21 00:00Z, 5 dakika adım, 5 m/piksel LOLA profili
(4 km yarıçap), marj 0.1°:

| Site | Bölge | Güneş | Dünya | Ortak | En uzun ortak pencere |
|---|---|---|---|---|---|
| Site01 | Connecting ridge | **%100** | %31.96 | **%31.96** | **53.68 saat** (1 kesintisiz görünür pencere; `window_count=3` durum koşusu) |
| Site04 | Shackleton rim | **%100** | **%0.00** | **%0.00** | yok |

Ayrım azimut bazında: Site04'te Dünya 164.6°–170.6° azimut aralığında kalıyor ve
oradaki arazi ufku +6.4°…+9.2°; Dünya librasyonunun en yükseği +4.14°, duvarı hiç
aşamıyor. Site01'de Dünya azimutunda ufuk +0.8°…+1.1°, librasyonun üst kısmı
açıkta.

**5 m/piksel yüksek çözünürlüklü A/B referans çiftinde doğrudan Dünya bağlantısı
gerektiren bir görev için aday Site01'dir.** Güneş tarafında iki bölge eşit.

### 3.2 Tüm 12 NASA Artemis III aday bölgesi özeti (20 km bölgesel DEM üst sınırı)

`Site02`, `Site03`, `Site05`–`Site09`, `Site11`–`Site13` bölgeleri 240 m/piksel
bölgesel DEM (`LDEM_60S_240MPP_ADJ`, 20 km yarıçap, `quality_flag="partial"`)
üzerinden hesaplanan K2 profilleri ve gerçek JPL Horizons DE441 efemerisi ile
K3 tarafından değerlendirilmiştir (`outputs/k3/*_summary.json`). 240 m/piksel
ızgara mikro-rölyefi düzleştirdiği için bu satırlar **görünürlüğün üst sınırı**
olarak okunmalıdır (`docs/REAL_RUN.md` §5):

| Site | Bölge | K2 Profili | Güneş | Dünya | Ortak | En uzun ortak pencere |
|---|---|---|---|---|---|---|
| Site01 | Connecting ridge | 4 km (5 m/px, `valid`) | %100.00 | %31.96 | %31.96 | 53.68 saat |
| Site02 | Connecting ridge extension | 20 km (240 m/px, `partial`) | %0.00 | %0.00 | %0.00 | yok |
| Site03 | de Gerlache rim 1 | 20 km (240 m/px, `partial`) | %24.30 | %65.39 | %24.30 | 40.82 saat |
| Site04 | Shackleton rim | 4 km (5 m/px, `valid`) | %100.00 | %0.00 | %0.00 | yok |
| Site05 | de Gerlache rim 2 | 20 km (240 m/px, `partial`) | %100.00 | %100.00 | %100.00 | 168.00 saat |
| Site06 | de Gerlache-Kocher massif | 20 km (240 m/px, `partial`) | %0.00 | %57.84 | %0.00 | yok |
| Site07 | Haworth | 20 km (240 m/px, `partial`) | %0.00 | %0.00 | %0.00 | yok |
| Site08 | Malapert massif | 20 km (240 m/px, `partial`) | %87.91 | %94.17 | %87.91 | 147.68 saat |
| Site09 | Leibnitz beta plateau | 20 km (240 m/px, `partial`) | %30.20 | %100.00 | %30.20 | 50.73 saat |
| Site11 | Nobile rim 2 | 20 km (240 m/px, `partial`) | %100.00 | %42.35 | %42.35 | 71.14 saat |
| Site12 | Amundsen rim | 20 km (240 m/px, `partial`) | %100.00 | %90.30 | %90.30 | 151.70 saat |
| Site13 | Mons Mouton | 20 km (240 m/px, `partial`) | %50.05 | %61.15 | %50.05 | 84.08 saat |

## 4. Köken zinciri

| Katman | Kaynak | Sürüm / model | Kayıt |
|---|---|---|---|
| Efemeris | JPL Horizons `OBSERVER` API | API `1.2`, **DE441** | `source_id=jpl-horizons`, satır başına `parameters` (JSON) |
| Arazi (yüksek çöz.) | NASA GSFC PGDA, LRO/LOLA LDEM + LDEC | Barker vd. 2021, 5 m/piksel | `source_id=pgda-lola-5mpp` |
| Bölgesel arazi | LDEM_60S_240MPP_ADJ | Barker vd. 2021, 240 m/piksel (`MOON_ME`, `DE421`) | `source_id=pgda-lola-240mpp` (`*_summary_20000m.json` `dem` alanı) |
| 3B küre dokuları | NASA Moon Trek / LRO WAC + LOLA | WAC mozaik 2K/4K, LOLA normal/bump | `app/static/moon/textures/` |

`data/manifest.csv` **13 veri satırı** (başlıkla 14 satır) taşıyor: 5 LOLA DEM
satırı, 4 JPL Horizons ham yanıt satırı, 4 Moon Trek doku satırı. Ham NASA
GeoTIFF ve Horizons önbellek dosyaları Git'e eklenmez (`data/cache/`,
`.gitignore`).

## 5. Teslim varlıkları

| Varlık | Yer | Durum |
|---|---|---|
| Çalışan uygulama | `app/app.py`, `fix/k1-k5-full-sync` | **hazır** — 6 sekme, 12 Artemis III adayı, Moon Trek `?siteA=...&siteB=...` URL senkronu, Gateway NRHO / Penumbra / ITU-R P.526 / A* / `3σ` BHI |
| Bilimsel modüller | `src/luna_sight/{ephemeris,terrain,visibility}` | **hazır** — 3B rölyef (`surface_3d.py`), 3 kademeli eğim riski (`risk.py`), `horizon.py` (`merge_hybrid_profiles`), `hazard.py`, `pathfinder.py`, `gateway.py`, `penumbra.py`, `comms.py` |
| Görünürlük çıktıları | `outputs/k3/SiteXX_{visibility.csv,windows.json,summary.json}` | **hazır** (12 bölge × 3 = 36 dosya + `sensitivity.csv`; 12 bölgenin tamamı `CANDIDATE_SITES` ile `0.0°` hizalı ve Git'e hazır) |
| Ufuk ve eğim profilleri | `outputs/k2/` | **hazır** — 12 bölge, 45 dosya (`regional_20000m_comparison.json`, `*_summary_20000m.json` ve 12 adet çevrimdışı `Site*_slope_summary.json` dahil) |
| Duyarlılık taraması | `outputs/k3/sensitivity.csv` (144 satır = 16 profil × 3 marj × 3 gövde) | **hazır** (`scripts/k3_sensitivity.py --series-dir`, gerçek `jpl-horizons` `DE441`) |
| Ürün kayıtları | `docs/K1_EPHEMERIS.md`, `K2_HORIZON.md`, `K3_VISIBILITY.md`, `REAL_RUN.md` | **hazır** (`K1_EPHEMERIS.md` 12 bölge özetiyle güncellendi) |
| Master proje raporu | `docs/MASTER_PROJECT_REPORT_TR.md`, `docs/LUNA_SIGHT_MASTER_PROJE_RAPORU.pdf` | **hazır** — Sürüm `3.0.0` (`200568` bayt) |
| Entegrasyon sözleşmesi | `docs/GOVERNANCE.md`, `governance/registry.json` | **hazır** |
| Demo senaryosu | `docs/DEMO_SCRIPT.md` | **hazır**, 12 bölge + `.en.srt` + `228 passed` sürümünden güncellendi |
| Demo videosu | `build/luna_sight_demo_120s_v2.mp4` | **yerelde mevcut değil / Drive veya yerel derleme** — >20 MB CI sınırı nedeniyle Git dışındadır (`build/` `.gitignore` altındadır); `k5_record_demo.py` ile yeniden üretilebilir |
| Altyazı dosyası | `artifacts/luna_sight_demo_120s_v2.en.srt` | **hazır** — 17 girdi, LF satır sonlu SHA-256 manifestte güncellendi |
| Anlatım kaynağı | `docs/demo_narration_en.json` | **hazır** — ses, gömülü altyazı ve `.srt` tek kaynaktan |
| Sunum destesi | `artifacts/luna_sight_sunum.pdf` (`scripts/generate_presentation_pdf.py`) | **hazır** — 12 slayt (`297mm × 167mm` 16:9 yatay), `158062` bayt, Türkçe vektörel PDF |

### Demo videosu nasıl üretildi

Video elle kaydedilmedi; üç betikle **yeniden üretilebilir** biçimde kuruldu:

| Betik | İş |
|---|---|
| `scripts/k5_record_demo.py` | Kurulu Chrome'u DevTools Protokolü ile sürer, gerçek arayüzden 1920×900 kare yakalar (28 kare, 18'i zaman kaydırıcısı animasyonu). `center_element()` görünür (`offsetWidth > 0 && offsetHeight > 0`) Plotly ögesini seçerek `globe_tab`'daki kapalı 3B rölyef açılır kutusunu atlar |
| `scripts/k5_synthesize_narration.py` | Anlatımı Windows SAPI ile seslendirir ve her segmentin süresini `ffprobe` ile **ölçer** |
| `scripts/k5_build_video.py` | Kare ve altyazı sınırlarını birleştirip ffmpeg ile 1080p30 H.264 kurar, sesi bindirir, `.srt` yazar |

Zamanlama tahmin edilmez: segment süreleri seslendirmeden ölçülür, kareler ve
altyazı parçaları o ölçülen süre içine dağıtılır. Altyazı arayüzün üzerine
binmez — arayüz 900 piksel yüksekliğinde yakalanır, kalan 180 piksel altyazı
şeridine ayrılır.

Videoda görünen her sayı `outputs/k3` dosyalarından gelir; ayrı bir sunum
verisi yoktur.

**Anlatım dili İngilizce.** Gerekçe: NASA Space Apps değerlendirmesi İngilizce
yürütülür ve bu makinede Türkçe TTS sesi yok (`Microsoft Zira`, en-US).
Türkçe metni İngilizce sesle okutmak jüri videosunda kabul edilemezdi. Arayüz
Türkçe kalır; karar `docs/demo_narration_en.json` içinde kayıtlı.

Dosya adı, Drive bağlantısı, sürüm, sahip ve doğrulama durumu
`artifacts/manifest.csv` içinde tutulur.

## 6. Bilinen eksikler ve sınırlar

Teslimle birlikte açıkça beyan edilir.

1. **Demo videosu >20 MB CI sınırı nedeniyle Git dışındadır.** `build/`
   klasörü Git tarafından izlenmediği için `.mp4` çıktısı çalışma alanında
   depo dışındadır ve gerektiğinde `k5_record_demo.py` ile yeniden üretilebilir
   (önceki SHA-256 kaydı manifestte referans olarak korunur). Sunum destesi
   (`artifacts/luna_sight_sunum.pdf`) ise **v3.0.0 sürümünde üretilmiş ve
   reponun `artifacts/` dizinine eklenmiştir**. Videonun anlatımı sentezlenmiş
   İngilizce sestir; insan seslendirmesi istenirse aynı `.srt` zamanlamasıyla
   değiştirilebilir.
2. **Gözlemci noktası DEM karo merkezidir**, optimize edilmiş iniş elipsi değil.
3. **5 m/piksel yüzeyde gerçek LOLA dönüş oranı %8–11**; gerisi
   enterpolasyonlu. Ufuk açısında sistematik belirsizlik yaratır.
4. **20 km profili bir yarıçap sonucu değildir**: 240 m/piksel bölgesel DEM'den
   gelir (`Site02`, `Site03`, `Site05`–`Site09`, `Site11`–`Site13` için yalnızca bu
   çözünürlük mevcuttur) ve mikro-rölyefi düzleştirir. `Site01`'de ortak
   görünürlüğü +20.4 puan yükseltmesi çözünürlük kaybının işaretidir;
   **görünürlüğün üst sınırı** olarak okunmalıdır (`docs/REAL_RUN.md` §5).
5. **Bağımsız doğrulama Horizons'ın kendi alt-nokta niceliğini kullanır.**
   Kanıtladığı şey: Horizons çıktısı bizim tarafımızda doğru yorumlanıyor.
   Horizons'ın mutlak doğruluğunu kanıtlamaz; o SPICE çekirdeğiyle yapılır ve bu
   koşuda yapılmadı (ADR-100).
6. **Tek hafta penceresi** incelendi; yıllık mevsimsel değişim kapsam dışı.
7. **Temel zaman çizelgesi sekmesindeki `% SoC` batarya eğrisi gösterim amaçlıdır.** Oranlar bir araç
   tasarımından türetilmemiştir ve bu beyan arayüzde grafiğin altında görünür;
   ayrıca `0.533°` Güneş diski penumbra modeli (`penumbra.py`) açılır panelde
   Wh kıyaslaması sunar.
8. **Yörünge röle bağlantısı v3.0.0 ile modellenmiştir (`gateway.py`).** "Doğrudan
   Dünya görüşü yok" (`Site04 = %0.00`) ifadesi "iletişim yok" anlamına gelmez;
   Lunar Gateway 9:2 NRHO katmanı `Site04`'te `%97.72` röle penceresi gösterir.
9. **Araç uçuş sertifikalı iniş emri vermez.** `hazard.py` (`3σ` iniş ayak izi
   skoru ve BHI) ve `pathfinder.py` (`A*` PSR güvenli koridoru) ile birlikte ön
   değerlendirme karar desteği sunar.

## 7. Açık iş

| Konu | Sahip | Durum |
|---|---|---|
| Demo videosunun (`k5_record_demo.py` düzeltmesi sonrası) yeniden üretilmesi, Drive'a yüklenmesi ve bağlantının manifeste yazılması | K5 | **Açık (isteğe bağlı dış medya — `build/` >20 MB CI dışı)** |
| Sunum destesi (`artifacts/luna_sight_sunum.pdf`, 12 slayt) | K5 | **Kapatıldı (`v3.0.0`, `scripts/generate_presentation_pdf.py`)** |
| `scripts/k3_sensitivity.py` çok bölgeli `--series-dir` ve 144 satırlı `sensitivity.csv` | K3 | **Kapatıldı (`v3.0.0`)** |
| Çevrimdışı LOLA eğim özetleri (`outputs/k2/Site*_slope_summary.json` + 3 kademeli `risk.py`) | K2 | **Kapatıldı (`v3.0.0`)** |
| Hibrit ufuk (`merge_hybrid_profiles`) + `outputs/k3/Site*_summary.json` `0.0°` koordinat hizalaması | K2/K3 | **Kapatıldı (`v3.0.0`)** |
| Moon Trek 3B küresinin 12 bölge verisi ve `?siteA=...&siteB=...` sorgusuyla senkronizasyonu | K4 | **Kapatıldı (`v3.0.0`)** |
| 5 ileri uçuş fiziği modülü (`gateway.py`, `penumbra.py`, `comms.py`, `pathfinder.py`, `hazard.py`) ve kokpit entegrasyonu | K2/K3/K4 | **Kapatıldı (`v3.0.0`, `tests/test_flight_physics.py`)** |
| `outputs/k3/Site{02,03,05..13}_*` dosyalarının LF normalizasyonu ile Git'e eklenmesi | K3/K5 | **Kapatıldı (`v3.0.0`)** |
| ADR-006 (pandera ile sözleşme doğrulaması) kararı | ekip | **Açık (`proposed`)** |
| `app/app.py` içinde `source_id` değerine `"+K3"` eklenmesi | K4 | **Kapatıldı (`fix/k1-k5-full-sync` içinde kaldırıldı)** |
| `outputs/k2/*_summary_20000m.json` dosyalarında `dem` köken bölümünün eksikliği | K2 | **Kapatıldı (`coordinate` ve `dem` 12 bölgeye eklendi)** |
