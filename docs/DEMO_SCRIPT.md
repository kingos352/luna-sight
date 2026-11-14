# LUNA SIGHT — 120 Saniyelik Demo Video Senaryosu

> **Durum:** T+16 teslimi · Feature Freeze (yeni özellik eklenmiyor)
> **Hedef kitle:** K5 doğrulama ekibi, sunum ekibi, jüri provası
> **Süre:** 120 saniye (±3 sn) · **Çözünürlük:** 1920×1080, 30 fps
> **Uygulama:** `app/app.py` · **Dal:** `k4/dev-environment`
> **Son güncelleme:** 2026-11-14 14:35 UTC

---

## 0. Tek cümlelik mesaj

> **LUNA SIGHT, Ay'ın güney kutbundaki aday iniş bölgelerini, Güneş ve Dünya'nın
> yerel topoğrafik ufka göre görünürlüğü üzerinden karşılaştıran bir görev
> planlama arayüzüdür.**

Videonun sonunda izleyicinin aklında kalması gereken üç kanıt:

1. **Gerçek ekip çıktısı:** K2 LOLA DEM ufuk profilleri ve K3 görünürlük matrisleri
   `outputs/k2` ve `outputs/k3` altından doğrudan okunuyor.
2. **Üç adımlı akış:** bölge seçimi → görev süresi/tarih → A/B metrikleri ve polar ufuk.
3. **Güvenilirlik:** kaynak kartları, veri sözleşmesi ve dosya yoksa çökmeyen
   **güvenli çevrimdışı mod**.

---

## 1. Çekim öncesi hazırlık (5 dakika)

### Uygulamayı başlat

```powershell
Set-Location C:\Users\Reyhan\Desktop\luna-sight
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
| Görev başlangıcı (UTC) | **2026-11-15 00:00** |
| Açık sekme | **Ufuk görünümü** |
| “Yöntem ve sınırlar” açılır kutusu | **Kapalı** |

### Beklenen değerler (7 gün / 1 saat, 169 satır)

Bu değerler `19d6b2e` commit'inde gerçek çıktılardan hesaplandı; kayıt sırasında
küçük yuvarlama farkları görülebilir.

| Metrik | Site01 · Connecting ridge | Site04 · Shackleton rim |
|---|---|---|
| Güneş görünürlüğü | ≈ %28 | ≈ %41 |
| Dünya görünürlüğü | ≈ %36 | ≈ %42 |
| Ortak görünürlük | ≈ 25 sa | ≈ 45 sa |
| En uzun kesintisiz ortak iletişim | ≈ 25 sa | ≈ 45 sa |
| En uzun Dünya penceresi | ≈ 61 sa | ≈ 71 sa |
| Ortalama ufuk yüksekliği | ≈ −0,4° | ≈ 3,3° |
| En yüksek ufuk engeli | ≈ 2,2° (azimut 54°) | ≈ 32,1° (azimut 86°) |

### ⚠️ Adlandırma notu (veri bütünlüğü)

K2 çıktıları bölgeleri şöyle adlandırıyor:

- **Site01 = Connecting ridge** (-89.463, -137.490)
- **Site04 = Shackleton rim** (-89.767, -171.870)

Ekipte “Site01 = Shackleton” gibi bir kısaltma dolaşsa da **videoda verideki adlar
kullanılmalıdır**. “Site01 Shackleton'dır” demek K2/K3 çıktılarıyla çelişir;
Shackleton bölgesi bu veri setinde **Site04**'te temsil edilir. Sunucu, ekranda
gördüğü etiketi söylemeli.

---

## 2. Zaman çizelgesi (kuş bakışı)

| Zaman | Bölüm | Ekranda | Ana mesaj |
|---|---|---|---|
| 00:00–00:30 | Giriş & Sorun | Başlık, rozetler, kenar çubuğu | Güneş + Dünya görünürlüğü neden kritik? |
| 00:30–01:00 | Aday Bölge Karşılaştırması | A/B paneli ve metrik kartları | Site01 vs Site04: ölçülebilir fark |
| 01:00–01:30 | Polar Ufuk ve Zaman Çizelgesi | Ufuk görünümü, zaman kaydırıcısı | ☀ ve ◆ topoğrafik ufka göre hareket eder |
| 01:30–02:00 | Bilimsel Güvenilirlik & Kapanış | Veri ve kaynak sekmesi, fallback | Kaynak şeffaflığı ve çökmeyen yedek |

---

## 3. Segment senaryoları

### 00:00–00:30 — Giriş & Sorun

**Ekran:** Ana sayfa, en üstte başlık ve rozetler. Fare kenar çubuğundaki
**Veri Kaynağı** kutusunun üzerinde dursun, sonra A/B alanına doğru insin.

**Çekim adımları**

1. 00:00–00:08: Başlık ve “Ay İniş Alanı Navigatörü” alt başlığı görünür.
2. 00:08–00:18: Rozetler gösterilir: `K2/K3 ekip çıktısı · outputs/`,
   `JPL Horizons · K1`, `Görünürlük motoru · K3 etkin`.
3. 00:18–00:30: Kenar çubuğunda **Veri Kaynağı** ve **Görev parametreleri**
   adımlarına kısa bir bakış; kamera A/B paneline döner.

**Anlatım (voice-over)**

> Ay'ın güney kutbunda Güneş ufka çok yakın seyreder. Bir iniş alanı için iki şey
> aynı anda gerekir: enerji için Güneş, iletişim ve navigasyon için Dünya görüşü.
> Ama topoğrafya, ufkun hemen üzerindeki bu iki cismi kolayca kesebilir.
> LUNA SIGHT, aday bölgeleri bu iki görünürlük üzerinden karşılaştıran bir görev
> planlama arayüzü. Şimdi üç adımda göreceğiz: bölge seçimi, zaman penceresi ve
> görünürlük.

**Sunucu ipucu:** “İniş güvenliği” demeyin; “ön değerlendirme” deyin.

---

### 00:30–01:00 — Aday Bölge Karşılaştırması

**Ekran:** Adım 1 ve Adım 2 görünür. A/B sütunlarındaki beş metrik kartı ve
“Topoğrafik engel özeti” açılır kutusu.

**Çekim adımları**

1. 00:30–00:38: Bölge A ve B seçim kutuları gösterilir; etiketler okunur:
   **Site01 · Connecting ridge**, **Site04 · Shackleton rim**.
2. 00:38–00:48: Sol sütunda Güneş/Dünya/ortak görünürlük metrikleri; sağ sütunda
   aynı metriklerin daha yüksek değerleri.
3. 00:48–00:54: Her iki sütunda **“En Uzun Kesintisiz İletişim (Güneş+Dünya)”**
   kartı vurgulanır; bu, Artemis için şarj ve haberleşmenin aynı anda sağlandığı
   en uzun aralıktır.
4. 00:54–01:00: “En uzun Dünya penceresi” ve “Topoğrafik engel özeti” satırları;
   imleç iki sütun arasında karşılaştırma yapar.

**Anlatım (voice-over)**

> Burada iki adayı yan yana görüyoruz: solda Site01, Connecting ridge; sağda
> Site04, Shackleton rim. Varsayılan pencere yedi gün, bir saatlik örnekleme.
> Her kartta beş metrik var: Güneş süresi, Dünya süresi, ortak görünürlük, en
> uzun Dünya penceresi ve Artemis için en kritik olan **en uzun kesintisiz ortak
> iletişim penceresi**. Bu pencerede Site04 kırk beş saat kesintisiz ortak
> görünürlük veriyor; Site01 yirmi beş saat. Fark, topoğrafik ufkun yüksekliğinden
> geliyor.

**Sunucu ipucu:** Rakamları yuvarlayın; “yaklaşık” demek güvenilirliği artırır.
Tek bir metriğin tek başına karar olmadığını belirtin.

---

### 01:00–01:30 — Polar Ufuk ve Zaman Çizelgesi

**Ekran:** **Ufuk görünümü** sekmesi. Polar grafik, sol üstte bölge radyosu,
sağda **Zaman adımı (0 = görev başlangıcı)** kaydırıcısı.

**Çekim adımları**

1. 01:00–01:06: Grafikte merkez = zenit, dış çember = ufuk; gri kesikli çizgi =
   K2/LOLA topoğrafik ufku.
2. 01:06–01:16: Zaman kaydırıcısını yumuşak biçimde 0 → ~1/3 → sonuna sürükleyin.
   Sarı ☀ ve mavi ◆ izlerinin ufuk çizgisine göre hareketi görünür.
3. 01:16–01:24: Alttaki üç rozet: anlık Güneş yüksekliği, Dünya yüksekliği ve
   zaman; durum etiketleri (Görünür / Engellenmiş / Belirsiz) okunur.
4. 01:24–01:30: **Zaman çizelgesi** sekmesine geçin; üç kanalın renkleri
   (yeşil/gri/sarı) bir saniye gösterilir, sonra geri dönün.

**Anlatım (voice-over)**

> Ufuk görünümünde merkez zenit, dış çember ufuk. Sarı iz Güneş, mavi iz Dünya.
> Gri kesikli çizgi, LOLA DEM'den gelen gerçek topoğrafik ufuk. Zaman
> kaydırıcısını oynattığımızda iki cismin azimut ve yükseklikleri değişiyor;
> izler ufuk çizgisinin içine girdiğinde görünür oluyorlar. Alttaki rozetler
> seçili anın yüksekliğini ve durumunu gösteriyor. Zaman çizelgesi de aynı üç
> kanalı yeşil, gri ve sarı olarak özetliyor.

**Teknik not:** Polar grafikte yarıçap `r = 90 − yükseklik`; yani bir cisim ufkun
üzerindeyse nokta dış çemberin içinde kalır. Kaydırıcıyı tek karede sona
atlamayın; 6–8 kademeli sürükleme hareketi videoda okunur olur.

---

### 01:30–02:00 — Bilimsel Güvenilirlik & Kapanış

**Ekran:** **Veri ve kaynak** sekmesi; ardından 2–3 saniyelik fallback gösterimi.

**Çekim adımları**

1. 01:30–01:40: Entegrasyon rozetleri okunur: **K2 · LOLA DEM · Tam Entegre ·
   Aktif**, **K3 · Görünürlük ve Pencere Motoru · Tam Entegre · Aktif**; K1
   rozeti amber renkte **“Bekliyor · Sentetik”** durumunu gösterir. Ardından üç
   kaynak kartı: **K1 · JPL Horizons**, **K2 · LOLA DEM ufuk profili**,
   **K3 · Görünürlük motoru**.
2. 01:40–01:47: “Veri sözleşmesi (`docs/DATA_CONTRACT.md`): ✅ tam · 18 zorunlu
   alan” satırı ve kalite bayrağı `test_fixture` uyarısı gösterilir.
3. 01:47–01:53: Kenar çubuğunda **Veri Kaynağı → Çevrimdışı Mock Modu (Test
   Verisi)** seçilir; **“Güvenli Çevrimdışı Mod (Test Verisi)”** uyarısı 2–3 sn
   görünür, sonra **Gerçek Ekip Çıktısı**'na geri dönülür.
4. 01:53–02:00: Başlık ve kapanış kartı; ekip adı ve “karar destek aracı” vurgusu.

**Anlatım (voice-over)**

> Güvenilirlik için her sayının kaynağı görünür. Veri ve kaynak sekmesinde
> entegrasyon rozetleri ve üç kart var: JPL Horizons efemerisi, LOLA DEM ufuk
> profili ve görünürlük motoru; dosya yolları ve veri sözleşmesinin on sekiz
> zorunlu alanı burada. K2 ve K3 tam entegre ve aktif; K1 efemerisi ise şu an
> sentetik senaryoyla çalışıyor ve bu rozette açıkça görünüyor. Şeffaf olalım:
> çıktılar `test_fixture` etiketli; gerçek Horizons verisi bağlandığında aynı
> arayüz çalışacak. Üstelik dosyalar okunamazsa uygulama çökmez, güvenli
> çevrimdışı moda düşer. LUNA SIGHT bir ön değerlendirme aracıdır; iniş
> güvenliği kararını vermez.

**Sunucu ipucu:** Fallback'i gösterirken “veri uyduruyoruz” demeyin; “çevrimdışı
test verisiyle çalışmaya devam ediyor” deyin.

---

## 4. Riskli ifadeler ve doğru alternatifleri

| Söylenmemesi gereken | Bunun yerine |
|---|---|
| “Site01 Shackleton'dır.” | “Site01 · Connecting ridge; Shackleton rim Site04'te.” |
| “Gerçek Güneş/Dünya efemerisi kullanıyoruz.” | “Efemeris şu an sentetik senaryo; çıktılar `test_fixture`.” |
| “Bu bölge iniş için güvenli.” | “Bu bölge ön değerlendirmede daha uzun görünürlük veriyor.” |
| “NASA onaylı.” | “NASA Space Apps Challenge kapsamında geliştirilen prototip.” |
| “Kesin iniş tarihi.” | “Seçilen görev penceresinde karşılaştırma.” |

---

## 5. Çekim sonrası kontrol listesi

- [ ] Süre 120 ±3 saniye; ses ve görüntü senkron.
- [ ] Varsayılan veri kaynağı **Gerçek Ekip Çıktısı**; A = Site01, B = Site04.
- [ ] Polar grafikte gri kesikli K2 ufku ve ☀/◆ izleri net görünüyor.
- [ ] “Veri ve kaynak” sekmesinde üç kart ve sözleşme satırı okunuyor.
- [ ] Fallback uyarısı en az 2 saniye ekranda kaldı.
- [ ] `test_fixture` uyarısı kesilmedi veya gizlenmedi.
- [ ] Dosya adı: `luna_sight_demo_120s_v1.mp4`; 1080p, H.264.
- [ ] Altyazı dosyası: `luna_sight_demo_120s_v1.tr.srt` (Türkçe).

---

## 6. Yeniden üretme ve doğrulama

```powershell
# Uygulama
.\.venv\Scripts\python.exe -m streamlit run app\app.py

# Statik kontroller ve testler
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\python.exe -m pytest -q

# Sağlık kontrolü (uygulama açıkken)
Invoke-WebRequest http://localhost:8501/_stcore/health
```

Beklenen: `ruff` temiz, `pytest` 95 test geçer, health yanıtı `ok`.

---

## 7. Sunum ekibi için tek paragraflık özet

> LUNA SIGHT, Ay'ın güney kutbundaki aday iniş bölgelerini Güneş ve Dünya
> görünürlüğü açısından karşılaştırır. Topoğrafik ufku LOLA DEM'den (K2), Güneş
> ve Dünya konumlarını efemeristen (K1), görünürlük sınıflandırmasını K3
> motorundan alır. Üç adımda bölge, zaman penceresi ve A/B metrikleri seçilir;
> polar ufuk görünümü ve zaman çizelgesi sonucu görselleştirir. Kaynak kartları
> ve veri sözleşmesi şeffaflık sağlar; gerçek dosyalar okunamazsa uygulama
> çökmeden çevrimdışı test moduna düşer.
