# Teslim kaydı

Issue: [#5](https://github.com/kingos352/luna-sight/issues/5) · Sahip: K5 ·
Kayıt tarihi: 2026-11-14

Bu belge, teslim edilen sürümün ne olduğunu, hangi kanıtla doğrulandığını ve
neyin **henüz tamamlanmadığını** kaydeder. Eksikler saklanmaz: jüri karşısında
bilinmeyen bir boşluk, bilinen bir boşluktan daha pahalıdır.

## 1. Teslim edilen sürüm

| Alan | Değer |
|---|---|
| Dal | `main` |
| Commit | `f6b361c` |
| Zaman | 2026-11-14T22:16:05+03:00 |
| Python | 3.12 (`.python-version`) |
| Giriş noktası | `app/app.py` (Streamlit) |

Dört rolün tamamı bu sürümde: K1 efemeris, K2 arazi, K3 görünürlük motoru,
K4 arayüz.

## 2. Doğrulama kanıtı

Hepsi `main` üzerinde, bu commit ile koşturuldu.

| Kontrol | Komut | Sonuç |
|---|---|---|
| Bağımlılık ağacı | `python -m pip check` | `No broken requirements found.` |
| Kod denetimi | `python -m ruff check .` | `All checks passed!` |
| Testler | `python -m pytest --record-mode=none -q` | **209 passed** |
| Kanonik sözleşme | `python scripts/check_governance.py` | `Sonuc: gecti. 0 uyari.` |
| Uygulama | `streamlit run app/app.py` | `/_stcore/health` → `200 ok` |

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
| Uçtan uca gerçek koşu | iki bölge × 2017 örnek, tamamı `valid` | `docs/REAL_RUN.md` |

## 3. Bilimsel sonuç

2026-11-14 00:00Z → 2026-11-21 00:00Z, 5 dakika adım, 5 m/piksel LOLA profili
(4 km yarıçap), marj 0.1°:

| Site | Bölge | Güneş | Dünya | Ortak | En uzun ortak pencere |
|---|---|---|---|---|---|
| Site01 | Connecting ridge | **%100** | %31.96 | **%31.96** | **53.68 saat** (3 pencere) |
| Site04 | Shackleton rim | **%100** | **%0.00** | **%0.00** | yok |

Ayrım azimut bazında: Site04'te Dünya 164.6°–170.6° azimut aralığında kalıyor ve
orada arazi ufku +6.4°…+9.2°; Dünya librasyonunun en yükseği +4.14°, duvarı hiç
aşamıyor. Site01'de Dünya azimutunda ufuk +0.8°…+1.1°, librasyonun üst kısmı
açıkta.

**Doğrudan Dünya bağlantısı gerektiren bir görev için bu veri setinde tek aday
Site01.** Güneş tarafında iki bölge eşit.

## 4. Köken zinciri

| Katman | Kaynak | Sürüm / model | Kayıt |
|---|---|---|---|
| Efemeris | JPL Horizons `OBSERVER` API | API `1.2`, **DE441** | `source_id=jpl-horizons`, satır başına `parameters` (JSON) |
| Arazi | NASA GSFC PGDA, LRO/LOLA LDEM + LDEC | Barker vd. 2021, 5 m/piksel | `source_id=pgda-lola-5mpp` |
| Bölgesel arazi | LDEM_60S_240MPP_ADJ | 240 m/piksel | yalnızca duyarlılık üst sınırı için |

`data/manifest.csv` **9 satır** taşıyor: her ham veri dosyası için kaynak
adresi, sürüm, parametreler, SHA-256 ve sahip. Ham NASA dosyaları ve önbellek
Git'e eklenmez (`data/cache/`, `.gitignore`).

## 5. Teslim varlıkları

| Varlık | Yer | Durum |
|---|---|---|
| Çalışan uygulama | `app/app.py`, `main` | **hazır** |
| Bilimsel modüller | `src/luna_sight/{ephemeris,terrain,visibility}` | **hazır** |
| Görünürlük çıktıları | `outputs/k3/Site0X_{visibility.csv,windows.json,summary.json}` | **hazır**, gerçek veri |
| Ufuk profilleri | `outputs/k2/Site0X_horizon_{2000,4000,20000}m.csv` | **hazır** |
| Duyarlılık taraması | `outputs/k3/sensitivity.csv` (54 satır) | **hazır** |
| Ürün kayıtları | `docs/K1_EPHEMERIS.md`, `K2_HORIZON.md`, `K3_VISIBILITY.md`, `REAL_RUN.md` | **hazır** |
| Entegrasyon sözleşmesi | `docs/GOVERNANCE.md`, `governance/registry.json` | **hazır** |
| Demo senaryosu | `docs/DEMO_SCRIPT.md` | **hazır**, gerçek sayılarla yenilendi |
| Demo videosu | `build/luna_sight_demo_120s_v2.mp4` | **üretildi** — 121.81 sn, 1920×1080, 30 fps, H.264+AAC, 4.47 MB. Drive yüklemesi bekliyor |
| Altyazı dosyası | `artifacts/luna_sight_demo_120s_v2.en.srt` | **hazır** — 17 girdi, anlatımın tamamı |
| Anlatım kaynağı | `docs/demo_narration_en.json` | **hazır** — ses, gömülü altyazı ve `.srt` tek kaynaktan |
| Sunum destesi | Drive | **EKSİK** |

### Demo videosu nasıl üretildi

Video elle kaydedilmedi; üç betikle **yeniden üretilebilir** biçimde kuruldu:

| Betik | İş |
|---|---|
| `scripts/k5_record_demo.py` | Kurulu Chrome'u DevTools Protokolü ile sürer, gerçek arayüzden 1920×900 kare yakalar (28 kare, 18'i zaman kaydırıcısı animasyonu) |
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

1. **Demo videosu üretildi ama Drive'a yüklenmedi.** Dosya yerelde
   (`build/`, Git tarafından izlenmez), SHA-256 manifestte. Sunum destesi hâlâ
   eksik. Videonun anlatımı sentezlenmiş İngilizce sestir; insan seslendirmesi
   istenirse aynı `.srt` zamanlamasıyla değiştirilebilir.
2. **Gözlemci noktası DEM karo merkezidir**, optimize edilmiş iniş elipsi değil.
3. **5 m/piksel yüzeyde gerçek LOLA dönüş oranı %8–11**; gerisi
   enterpolasyonlu. Ufuk açısında sistematik belirsizlik yaratır.
4. **20 km profili bir yarıçap sonucu değildir**: 240 m/piksel bölgesel DEM'den
   gelir ve mikro-rölyefi düzleştirir. Ortak görünürlüğü +20.4 puan yükseltmesi
   çözünürlük kaybının işaretidir; **görünürlüğün üst sınırı** olarak okunmalıdır
   (`docs/REAL_RUN.md` §5).
5. **Bağımsız doğrulama Horizons'ın kendi alt-nokta niceliğini kullanır.**
   Kanıtladığı şey: Horizons çıktısı bizim tarafımızda doğru yorumlanıyor.
   Horizons'ın mutlak doğruluğunu kanıtlamaz; o SPICE çekirdeğiyle yapılır ve bu
   koşuda yapılmadı (ADR-100).
6. **Tek hafta penceresi** incelendi; yıllık mevsimsel değişim kapsam dışı.
7. **Batarya eğrisi gösterim amaçlıdır**, güç bütçesi değildir. Oranlar bir araç
   tasarımından türetilmemiştir ve bu beyan arayüzde grafiğin altında görünür.
8. **Yörünge röle bağlantısı modellenmemiştir.** "Doğrudan Dünya görüşü yok"
   ifadesi "iletişim yok" anlamına gelmez.
9. **Araç iniş güvenliği kararı vermez.** Ön değerlendirme sunar.

## 7. Açık iş

| Konu | Sahip |
|---|---|
| Demo videosunun Drive'a yüklenmesi ve bağlantının manifeste yazılması | K5 |
| Sunum destesi | K5 |
| `app/app.py` içinde `source_id` değerine `"+K3"` eklenmesi; kanonik sözlükte olmayan değer indirilen CSV'ye geçiyor | K4 |
| `outputs/k2/*_summary_20000m.json` dosyalarında `dem` köken bölümünün eksikliği | K2 |
| `scripts/k3_sensitivity.py` çok bölgeli `--series` kabul etmiyor | K3 |
| ADR-006 (pandera ile sözleşme doğrulaması) kararı | ekip |
