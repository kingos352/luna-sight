# LUNA SIGHT — 120 Saniyelik Demo Video Senaryosu

> **Durum:** Gerçek veri sürümü · `main` üzerinde doğrulandı
> **Hedef kitle:** sunum ekibi, jüri provası
> **Süre:** 120 saniye (±3 sn) · **Çözünürlük:** 1920×1080, 30 fps
> **Uygulama:** `app/app.py` · **Dal:** `main`
> **Son güncelleme:** 2026-11-14 19:30 UTC

> ### Bu sürümde ne değişti
>
> Senaryonun önceki hâli sentetik dönemde yazılmıştı ve **merkez iddiası tersti.**
> Eski metin "Site04 kırk beş saat kesintisiz ortak görünürlük veriyor; Site01
> yirmi beş saat" diyordu. Gerçek JPL Horizons verisiyle sonuç **tam tersi**:
> Site04'te ortak görünürlük **sıfır**, Site01'de **54 saat**. Ayrıca metin
> sunucuya "efemeris sentetik, çıktılar `test_fixture`" demesini söylüyordu; bu
> da artık doğru değil. Her iki hata düzeltildi, tüm sayılar `main` üzerinde
> uygulamadan okunarak yenilendi.

---

## 0. Tek cümlelik mesaj

> **LUNA SIGHT, Ay'ın güney kutbundaki aday iniş bölgelerini, Güneş ve Dünya'nın
> yerel topoğrafik ufka göre görünürlüğü üzerinden karşılaştıran bir görev
> planlama arayüzüdür.**

Videonun sonunda izleyicinin aklında kalması gereken üç kanıt:

1. **Gerçek ve izlenebilir veri:** Güneş/Dünya geometrisi JPL Horizons'tan
   (`jpl-horizons`, API 1.2, **DE441**), topoğrafik ufuk LRO/LOLA DEM'den.
   Her satır kaynak, sürüm, model ve parametre taşır; kalite bayrağı `valid`.
2. **Ölçülebilir A/B ayrımı:** iki aday da tam hafta Güneş görüyor, ama doğrudan
   Dünya bağlantısı yalnızca birinde var.
3. **Dürüst sınırlar:** belirsiz geçiş bandı ayrı sınıf, eksik veri görünür
   sayılmıyor, batarya eğrisi gösterim amaçlı olduğu ekranda yazıyor.

---

## 1. Çekim öncesi hazırlık (5 dakika)

### Uygulamayı başlat

```powershell
# Depo kökünde
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m streamlit run app\app.py
```

Tarayıcıda `http://localhost:8501` açılır. İlk açılış 5–10 sn sürebilir; grafik
gelmeden kayda başlamayın.

### Varsayılan ekran ayarları (kayıt öncesi kontrol)

| Ayar | Değer |
|---|---|
| Veri Kaynağı | **Gerçek Ekip Çıktısı (K2/K3)** |
| Bölge A | **Site01 · Connecting ridge** |
| Bölge B | **Site04 · Shackleton rim** |
| Görev süresi (gün) | **7** |
| Zaman örnekleme aralığı | **1 saat** |
| Zaman adımı kaydırıcısı | **0** |
| Açık sekme | **Ufuk görünümü** |
| "Yöntem ve sınırlar" açılır kutusu | **Kapalı** |

### Ekranda görünecek değerler

Bu tablo `main` üzerinde uygulamadan okundu (7 gün, 1 saat örnekleme, 169 örnek).
Kayıt sırasında birebir bu sayılar görünmeli.

| Metrik | Site01 · Connecting ridge | Site04 · Shackleton rim |
|---|---|---|
| Güneş görünürlük süresi | **169.0 sa** | **169.0 sa** |
| Dünya doğrudan görüş penceresi | **54.0 sa** | **0.0 sa** |
| Ortak görünürlük | **54.0 sa** | **0.0 sa** |
| En uzun Dünya penceresi | **54.0 sa** | **0.0 sa** |
| En Uzun Kesintisiz İletişim (Güneş+Dünya) | **54.0 sa** | **0.0 sa** |
| Maksimum İletişimsizlik | **111.0 sa** | **169.0 sa** |

Topoğrafik engel özeti (Güneş azimut aralığına göre):

| Satır | Site01 | Site04 |
|---|---|---|
| Ortalama ufuk yüksekliği | −2.0° | −27.5° |
| En yüksek engel | 0.2° (Güneş azimutu 181°) | −19.0° (Güneş azimutu 213°) |
| Güneş ufkun üzerindeyken kesilen süre | %0 | %0 |
| Geçiş bandı nedeniyle belirsiz ortak görünürlük | %2 | %0 |

Anlık rozetler (kaydırıcı 0 konumunda): Güneş **+1.5° · Görünür**, Dünya
**−5.0° · Engellenmiş**, zaman **14 Nov 00:00**.

### Kaynak kayıtla tutarlılık

Arayüz 1 saatlik örnekleme gösteriyor; kaynak çıktılar 5 dakikalık. İkisi aynı
veri, farklı çözünürlük:

| | Arayüz (1 saat) | Kaynak kayıt (5 dakika) |
|---|---|---|
| Site01 ortak görünürlük | 54.0 sa, 1 pencere | %31.96 (53.68 sa), **3 pencere** |
| Site04 ortak görünürlük | 0.0 sa | %0.00 |
| Güneş (her iki bölge) | 169.0 sa | %100 (168.0 sa, 1 pencere) |

**Sunucuya not:** 1 saatlik örnekleme Site01'deki üç pencereyi tek pencere gibi
gösteriyor; kısa kesintiler bu çözünürlükte kayboluyor. Jüri sorarsa doğru cevap:
"Arayüz bir saatlik örneklemede özet veriyor; beş dakikalık kaynak çıktıda aynı
süre üç ayrı pencereye bölünüyor ve en uzunu 53.7 saat." Bunu gizlemek yerine
söylemek güvenilirliği artırır.

### Adlandırma notu (veri bütünlüğü)

- **Site01 = Connecting ridge** (−89.463163, doğu-pozitif −137.489553)
- **Site04 = Shackleton rim** (−89.766811, doğu-pozitif −171.869898)

Ekipte "Site01 = Shackleton" gibi bir kısaltma dolaşsa da **videoda verideki adlar
kullanılmalıdır.** Shackleton bölgesi bu veri setinde **Site04**'tür.

---

## 2. Zaman çizelgesi (kuş bakışı)

| Zaman | Bölüm | Ekranda | Ana mesaj |
|---|---|---|---|
| 00:00–00:30 | Giriş & Sorun | Başlık, rozetler, kenar çubuğu | Güneş + Dünya görünürlüğü neden kritik? |
| 00:30–01:00 | Aday Bölge Karşılaştırması | A/B paneli ve metrik kartları | Site01 vs Site04: keskin ve ölçülebilir fark |
| 01:00–01:30 | Polar Ufuk ve Zaman Çizelgesi | Ufuk görünümü, zaman kaydırıcısı | ☀ ve ◆ topoğrafik ufka göre hareket eder |
| 01:30–02:00 | Bilimsel Güvenilirlik & Kapanış | Veri ve kaynak sekmesi | Köken zinciri ve dürüst sınırlar |

---

## 3. Segment senaryoları

### 00:00–00:30 — Giriş & Sorun

**Ekran:** Ana sayfa, başlık ve rozetler. Fare kenar çubuğundaki **Veri Kaynağı**
kutusunun üzerinde dursun, sonra A/B alanına insin.

**Anlatım**

> Ay'ın güney kutbunda Güneş ufka çok yakın seyreder. Bir iniş alanı için iki şey
> aynı anda gerekir: enerji için Güneş, iletişim ve navigasyon için Dünya görüşü.
> Ama topoğrafya, ufkun hemen üzerindeki bu iki cismi kolayca kesebilir.
> LUNA SIGHT aday bölgeleri bu iki görünürlük üzerinden karşılaştırır. Veri
> gerçek: Güneş ve Dünya konumları JPL Horizons'tan, topoğrafik ufuk LRO LOLA
> yüksek çözünürlüklü DEM'inden geliyor.

**Sunucu ipucu:** "İniş güvenliği" demeyin; "ön değerlendirme" deyin.

---

### 00:30–01:00 — Aday Bölge Karşılaştırması

**Ekran:** Adım 1 ve Adım 2. A/B sütunlarındaki metrik kartları ve "Topoğrafik
engel özeti" açılır kutusu.

**Çekim adımları**

1. 00:30–00:38: Bölge seçim kutuları; etiketler okunur: **Site01 · Connecting
   ridge**, **Site04 · Shackleton rim**.
2. 00:38–00:46: Her iki sütunda **Güneş görünürlük süresi 169.0 sa** kartı
   gösterilir — iki aday burada eşit.
3. 00:46–00:54: **Ortak görünürlük** kartları yan yana: Site01 **54.0 sa**,
   Site04 **0.0 sa**. Delta göstergesi −54.0 sa okunur.
4. 00:54–01:00: "Topoğrafik engel özeti" açılır; Site04'ün ortalama ufku −27.5°
   satırı gösterilir.

**Anlatım**

> Solda Site01, Connecting ridge; sağda Site04, Shackleton rim. Pencere yedi gün.
> Güneş tarafında iki aday eşit: her ikisi de yüz altmış dokuz saat boyunca Güneş
> görüyor. Fark Dünya'da ortaya çıkıyor. Site01 elli dört saat doğrudan Dünya
> görüşü sağlıyor; Site04 **hiç** sağlamıyor. Sebebi topoğrafya: Site04'te Dünya,
> yüz altmış beş ile yüz yetmiş bir derece azimut aralığında kalıyor ve orada
> krater duvarı altı ile dokuz derece yükseklikte. Dünya librasyonunun en yükseği
> dört nokta bir derece; duvarı hiç aşamıyor. Yani doğrudan Dünya bağlantısı
> gereken bir görev için bu veri setinde tek aday Site01.

**Sunucu ipucu:** Bu, videonun en güçlü cümlesi. Yavaş söyleyin. "Sıfır" rakamını
atlamayın; jüri için ikna edici olan tam da keskinliği.

**Jüri sorusu beklentisi.** "Site04 kötü bir bölge mi?" Doğru cevap: "Bu veri
setinde ve bu pencerede doğrudan Dünya görüşü vermiyor. Güneş tarafında Site01
kadar iyi; krater içine baktığı için Güneş yirmi-otuz derecelik marjla açıkta.
Bir yörünge röle bağlantısıyla değerlendirilirse tablo değişir — bu araç röleyi
modellemiyor."

---

### 01:00–01:30 — Polar Ufuk ve Zaman Çizelgesi

**Ekran:** **Ufuk görünümü** sekmesi. Polar grafik, zaman kaydırıcısı.

**Çekim adımları**

1. 01:00–01:06: Merkez = zenit, dış çember = ufuk; gri kesikli çizgi = K2/LOLA
   topoğrafik ufku.
2. 01:06–01:16: Zaman kaydırıcısını 6–8 kademede 0 → sona sürükleyin. Sarı ☀ ve
   mavi ◆ izlerinin ufka göre hareketi görünür.
3. 01:16–01:24: Alttaki rozetler okunur: Güneş yüksekliği, Dünya yüksekliği,
   durum etiketi (Görünür / Engellenmiş / Belirsiz).
4. 01:24–01:30: **Zaman çizelgesi** sekmesine geçin; üç kanalın renkleri
   (yeşil/gri/sarı) bir saniye gösterilir.

**Anlatım**

> Ufuk görünümünde merkez zenit, dış çember ufuk. Sarı iz Güneş, mavi iz Dünya,
> gri kesikli çizgi LOLA DEM'den gelen gerçek topoğrafik ufuk. Kaydırıcıyı
> oynattığımızda Dünya'nın librasyonla salındığını görüyoruz. Sarı kanal bütün
> hafta yeşil; mavi kanal Site01'de açılıp kapanıyor. Sarı renkli örnekler
> belirsiz: Dünya, ufkun onda bir derecelik geçiş bandı içinde. Bunları görünür
> saymıyoruz, ayrı sınıfta tutuyoruz.

**Teknik not:** Polar grafikte yarıçap `r = 90 − yükseklik`. Kaydırıcıyı tek
karede sona atlamayın.

---

### 01:30–02:00 — Bilimsel Güvenilirlik & Kapanış

**Ekran:** **Veri ve kaynak** sekmesi.

**Çekim adımları**

1. 01:30–01:38: Entegrasyon rozetleri okunur: **K1 · JPL Horizons · Efemeris ·
   Tam Entegre · Aktif**, **K2 · LOLA DEM**, **K3 · Görünürlük motoru**.
2. 01:38–01:48: "Kaynak ve kalite bilgisi" bloğu gösterilir:
   `jpl-horizons` · sürüm `1.2` · model `DE441` · kalite bayrağı `valid`, dosya
   yolu ve parametre sözlüğü.
3. 01:48–01:54: "Bölge A CSV indir" düğmesi gösterilir — çıktı sözleşmeli.
4. 01:54–02:00: Kapanış kartı; "karar destek aracı" vurgusu.

**Anlatım**

> Güvenilirlik için her sayının kaynağı görünür. Kaynak kaydında efemerisin
> geldiği servis, sürümü, kullanılan efemeris çekirdeği DE441 ve sorgu
> parametreleri yazıyor; kalite bayrağı `valid`. Bu değerler arayüze sabit metin
> olarak yazılmadı, her satırdan okunuyor. Ufuk profilinin kendi kaydı da var:
> beş metre çözünürlüklü LOLA DEM, dosya özetleri manifestte. Tabloyu olduğu gibi
> indirebilirsiniz. LUNA SIGHT bir ön değerlendirme aracıdır; iniş güvenliği
> kararını vermez.

**Sunucu ipucu:** Batarya grafiğini gösterirseniz altındaki beyanı da okuyun:
eğri gösterim amaçlı, güç bütçesi değil, oranlar bir araç tasarımından
türetilmemiş. Bunu söylemeden geçmek tek gerçek risk.

---

## 4. Riskli ifadeler ve doğru alternatifleri

| Söylenmemesi gereken | Bunun yerine |
|---|---|
| "Site01 Shackleton'dır." | "Site01 · Connecting ridge; Shackleton rim Site04'te." |
| "Efemeris sentetik, çıktılar `test_fixture`." | **Artık yanlış.** "Efemeris gerçek: `jpl-horizons`, DE441, kalite bayrağı `valid`." |
| "Bu bölge iniş için güvenli." | "Bu bölge ön değerlendirmede daha uzun ortak görünürlük veriyor." |
| "Site04 kullanılamaz." | "Site04 bu pencerede doğrudan Dünya görüşü vermiyor; Güneş tarafında Site01 kadar iyi." |
| "Batarya grafiği güç bütçemiz." | "Batarya eğrisi gösterim amaçlı; oranlar bir araç tasarımından türetilmedi." |
| "NASA onaylı." | "NASA Space Apps Challenge kapsamında geliştirilen prototip." |
| "Kesin iniş tarihi." | "Seçilen görev penceresinde karşılaştırma." |

---

## 5. Çekim sonrası kontrol listesi

- [ ] Süre 120 ±3 saniye; ses ve görüntü senkron.
- [ ] Varsayılan veri kaynağı **Gerçek Ekip Çıktısı**; A = Site01, B = Site04.
- [ ] Güneş kartları her iki bölgede **169.0 sa** okunuyor.
- [ ] Ortak görünürlük **Site01 54.0 sa**, **Site04 0.0 sa** okunuyor.
- [ ] Polar grafikte gri kesikli K2 ufku ve ☀/◆ izleri net görünüyor.
- [ ] "Veri ve kaynak" sekmesinde `jpl-horizons` · `1.2` · `DE441` · `valid`
      satırı okunuyor.
- [ ] Ekranda **mutlak dosya yolu görünmüyor** (yollar depo köküne göre).
- [ ] Batarya grafiği gösterildiyse varsayım beyanı da okundu.
- [ ] Dosya adı: `luna_sight_demo_120s_v2.mp4`; 1080p, H.264.
- [ ] Altyazı dosyası: `luna_sight_demo_120s_v2.tr.srt` (Türkçe).

---

## 6. Yeniden üretme ve doğrulama

```powershell
# Uygulama
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m streamlit run app\app.py

# Statik kontroller, testler, sözleşme denetimi
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest --record-mode=none -q
.\.venv\Scripts\python.exe scripts\check_governance.py

# Sağlık kontrolü (uygulama açıkken)
Invoke-WebRequest http://localhost:8501/_stcore/health
```

Beklenen: `ruff` temiz, **209 test** geçer, sözleşme denetimi `Sonuc: gecti`,
health yanıtı `ok`.

Veriyi sıfırdan üretmek için `docs/REAL_RUN.md` bölüm 7.

### Videoyu yeniden üret

Bu senaryo elle de çekilebilir, ama teslim edilen video üç betikle
**yeniden üretilebilir** biçimde kurulmuştur:

```powershell
# 1) Uygulamayı kayıt için ayağa kaldır
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m streamlit run app\app.py --server.port 8502 `
  --server.headless true --client.toolbarMode minimal

# 2) Gerçek arayüzden kareleri yakala (28 kare, 1920x900)
.\.venv\Scripts\python.exe scripts\k5_record_demo.py --out build\frames

# 3) Anlatımı seslendir ve sürelerini ölç
.\.venv\Scripts\python.exe scripts\k5_synthesize_narration.py

# 4) Videoyu kur (1080p30, H.264+AAC) ve .srt yaz
.\.venv\Scripts\python.exe scripts\k5_build_video.py
```

Anlatım metninin tek kaynağı `docs/demo_narration_en.json`; ses, gömülü
altyazı ve `.srt` dosyası aynı dosyadan türer, bu yüzden ayrışamazlar.
Segment süreleri tahmin edilmez, seslendirmeden ölçülür.

Anlatım **İngilizce**: NASA Space Apps değerlendirmesi İngilizce yürütülür ve
bu makinede Türkçe TTS sesi yoktur. İnsan seslendirmesi tercih edilirse aynı
`.srt` zamanlamasıyla ses değiştirilebilir; bu durumda yukarıdaki 3. adım
atlanır ve kendi ses dosyanız `k5_build_video.py` çıktısına bindirilir.

---

## 7. Sunum ekibi için tek paragraflık özet

> LUNA SIGHT, Ay'ın güney kutbundaki aday iniş bölgelerini Güneş ve Dünya
> görünürlüğü açısından karşılaştırır. Güneş ve Dünya konumları JPL Horizons'tan
> gelir (DE441 efemeris çekirdeği, atmosfersiz görünür konum), topoğrafik ufuk
> LRO/LOLA beş metre çözünürlüklü DEM'den hesaplanır, görünürlük sınıflandırması
> geçiş bandını ayrı tutan bir motorla yapılır. Yedi günlük pencerede iki aday da
> kesintisiz Güneş görüyor; ama doğrudan Dünya görüşü yalnızca Connecting
> ridge'de var — elli dört saat. Shackleton rim'de Dünya krater duvarını hiç
> aşmıyor. Her satır kaynak, sürüm, model ve parametre taşır; eksik veri görünür
> sayılmaz. Araç bir ön değerlendirme sunar, iniş güvenliği kararı vermez.
