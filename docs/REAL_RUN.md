# Gerçek veriyle uçtan uca koşu kaydı

Bu belge, `outputs/k3/` altındaki görünürlük çıktılarının **sentetik senaryo
yerine gerçek JPL Horizons efemerisiyle** üretildiği koşuyu kaydeder.

Koşuyu entegrasyon otoritesi yürüttü (`docs/GOVERNANCE.md` bölüm 1), depo
sahibinin açık talimatıyla. K3'ün motor koduna **dokunulmadı**; yalnızca
`scripts/k3_visibility_report.py` ve `scripts/k3_sensitivity.py` betikleri
`--series` parametresiyle gerçek seri verilerek yeniden koşturuldu.

## 1. Neden gerekliydi

README'nin 24 saatlik hedefi "gerçek ve izlenebilir JPL Horizons verisi"
diyor. Önceki çıktılar doğru biçimde etiketlenmişti ama bilimsel sonuç
değildi:

| Alan | Önceki (sentetik) | Şimdi (gerçek) |
|---|---|---|
| `source_id` | `synthetic-scenario` | `jpl-horizons` |
| `source_version` | `v1` | `1.2` |
| `model_id` | `accelerated-azimuth-sweep` | `DE441` |
| `quality_flag` | `test_fixture` | `valid` |

## 2. Girdi zinciri

| Katman | Kaynak | Köken |
|---|---|---|
| Efemeris | `luna_sight.ephemeris` → JPL Horizons `OBSERVER` | API 1.2, DE441, `APPARENT=AIRLESS` |
| Arazi ufku | `outputs/k2/Site0X_horizon_4000m.csv` | PGDA LOLA LDEM 5 m/piksel (Barker vd. 2021) |
| Motor | `luna_sight.visibility` `evaluate_series` | `margin_deg = 0.1` |

Efemeris serisi: 2026-11-14 00:00Z → 2026-11-21 00:00Z, 5 dakika adım,
bölge başına **2017 örnek**, tamamı `valid`, boş değer yok.

Kullanılan ham Horizons yanıtlarının SHA-256 ön ekleri: Site01 Güneş
`50d51e46`, Site01 Dünya `c59f7878`, Site04 Güneş `24e39ce2`, Site04 Dünya
`ad9f115d`. Ham yanıtlar `data/cache/` altındadır ve Git tarafından
izlenmez; manifest satırları K1 dalında tutulur.

## 3. Sonuç: iki adayın karşılaştırması

4 km yarıçap, 5 m/piksel LOLA profili, marj 0.1°, 168 saat:

| Site | Bölge | Güneş görünür | Dünya görünür | Ortak görünür | Ortak en uzun pencere |
|---|---|---|---|---|---|
| **Site01** | Connecting ridge | **%100** (1 pencere, 168.00 sa) | %31.96 (3 pencere) | **%31.96** | **53.68 saat** |
| **Site04** | Shackleton rim | **%100** (1 pencere, 168.00 sa) | **%0.00** | **%0.00** | yok |

**Ayrım nereden geliyor.** Her iki bölgede Güneş bütün hafta görünür, ama
Dünya yalnızca Site01'de görünür:

| Site | Dünya azimutu | Dünya yüksekliği | O azimutlarda arazi ufku | Marj |
|---|---|---|---|---|
| Site01 | 130.27° … 136.23° | −5.036° … +4.019° | +0.821° … +1.061° | −5.86° … **+2.96°** |
| Site04 | 164.63° … 170.64° | −4.878° … +4.143° | +6.425° … +9.244° | −11.30° … **−5.01°** |

Site04'te Dünya librasyonunun en yüksek noktası (+4.14°) bile krater
duvarının altında kalıyor (+6.43°); marj hiçbir örnekte pozitife çıkmıyor.
Doğrudan Dünya bağlantısı gerektiren bir görev için **Site01 tek aday**.

Güneş tarafında durum terstir: Site04'te Güneş azimutlarında arazi ufku
−31.37° … −18.96°, yani krater içine bakıyor ve Güneş 20–33 derecelik
marjla açıkta kalıyor.

### Ortalama ufuk karşılaştırması neden yanıltıcı

K1 ürün kaydında "Site04'te Güneş yüksekliği (+1.35…+1.67°) K2'nin ortalama
arazi ufkunun (+3.22°) altında" denmişti ve bu bir **büyüklük kontrolü**
olarak işaretlenmişti, görünürlük kararı olarak değil. Azimut çözünürlüklü
hesap bunun neden yeterli olmadığını gösteriyor: Site04'ün ortalama ufku
+32° duvar ile −31° krater içinin ortalamasıdır. Güneş krater içine
baktığı için ortalama hiçbir şey anlatmıyor. Karar azimut bazında verilir.

## 4. Belirsiz örnekler

Site01'de 2017 örneğin **41'i** (%2.05) `uncertain`, gerekçe
`transition_band`: Dünya yüksekliği arazi ufkunun ±0.1° marj bandı içinde.
Bunlar görünür ya da engelli sayılmaz. Site04'te belirsiz örnek yok, çünkü
marj hiçbir yerde banda girmiyor.

## 5. Duyarlılık

`outputs/k3/sensitivity.csv`, 54 satır: 2 bölge × 3 profil × 3 marj × 3 gövde.

### Marj duyarlılığı (Site01, 4 km)

| Marj | Ortak görünür | Belirsiz |
|---|---|---|
| 0.05° | %32.47 | %1.02 |
| 0.10° | %31.96 | %2.05 |
| 0.20° | %30.93 | %4.10 |

Marj iki katına çıktığında belirsiz oran da iki katına çıkıyor, görünür oran
~1.5 puan düşüyor. Güneş tarafı marjdan etkilenmiyor (açıklık 20°'nin
üzerinde).

### Yarıçap duyarlılığı ve **önemli uyarı**

| Site | Profil | Ortak görünür | Ortak en uzun |
|---|---|---|---|
| Site01 | 2 km, 5 m/piksel | %31.96 | 53.68 sa |
| Site01 | 4 km, 5 m/piksel | %31.96 | 53.68 sa |
| Site01 | 20 km, **240 m/piksel** | %52.31 | 87.88 sa |
| Site04 | 2 / 4 / 20 km | %0.00 | yok |

2 km ile 4 km arasında **hiç fark yok**; K2'nin bulgusuyla tutarlı
(Site01'de ufku medyan 210 m uzaklıktaki mikro-rölyef belirliyor).

20 km profili ortak görünürlüğü +20.4 puan yükseltiyor. **Bu bir yarıçap
etkisi değildir.** 20 km profili farklı bir üründen geliyor:
`LDEM_60S_240MPP_ADJ`, yani 240 m/piksel bölgesel DEM ve 240 m radyal adım.
Ufuk, ışın üzerindeki en büyük yükseklik açısıdır; yarıçap büyüdükçe ufuk
yalnızca yükselebilir, düşemez. Burada düşmesinin tek açıklaması
çözünürlüktür: 240 m ızgara, 5 m ızgaranın gördüğü mikro-rölyefi
düzleştiriyor.

Sayılar bunu doğruluyor — aynı bölgenin ufuk istatistikleri:

| Profil | Ufuk min | Ufuk ortalama | Ufuk max | Kalite |
|---|---|---|---|---|
| 4 km, 5 m/piksel | −4.615° | −0.373° | +2.215° | `valid` |
| 20 km, 240 m/piksel | −5.512° | −1.276° | +1.305° | `partial` |

Yani 20 km sonucu **görünürlüğün üst sınırı** olarak okunmalıdır, daha iyi
bir tahmin olarak değil. Manşet sonuç 5 m/piksel profilden alınmıştır.

## 6. Bilimsel sınırlar

- Gözlemci noktası DEM karo merkezidir, optimize edilmiş iniş elipsi
  değildir (K2 kaydı bölüm 7).
- 5 m/piksel yüzeyde gerçek LOLA dönüş oranı %8–11; geri kalan
  enterpolasyonludur. Ufuk açısında sistematik belirsizlik yaratır.
- Güneş kutupta ufku sıyırdığı için 0.1°'lik ufuk hatası saatler
  mertebesinde görünürlük farkı üretebilir. Marj taraması bu duyarlılığı
  ölçer ama ufuk hatasının kendisini ortadan kaldırmaz.
- Dünya için paralaks K1 tarafında hesaba katılmıştır; ihmal edilse
  yükseklikte 0.24° hata olurdu (`docs/K1_EPHEMERIS.md` bölüm 7.3).
- Tek hafta penceresi (168 saat) incelenmiştir. Yıllık mevsimsel değişim bu
  koşunun kapsamı dışındadır.

## 7. Yeniden üretme

```powershell
# 1) Gerçek efemeris serisi (data/cache altına, izlenmez)
.venv\Scripts\python.exe -m luna_sight.ephemeris --start "2026-11-14 00:00"

# 2) Görünürlük ve pencereler
.venv\Scripts\python.exe scripts/k3_visibility_report.py `
  --profile outputs/k2/Site01_horizon_4000m.csv --site-id Site01 `
  --series data/cache/ephemeris_Site01_20261114T0000_168h.csv
.venv\Scripts\python.exe scripts/k3_visibility_report.py `
  --profile outputs/k2/Site04_horizon_4000m.csv --site-id Site04 `
  --series data/cache/ephemeris_Site04_20261114T0000_168h.csv

# 3) Duyarlılık taraması (bölge bölge, bkz. bölüm 8)
.venv\Scripts\python.exe scripts/k3_sensitivity.py `
  --series data/cache/ephemeris_Site01_20261114T0000_168h.csv `
  --profiles outputs/k2/Site01_horizon_2000m.csv outputs/k2/Site01_horizon_4000m.csv `
             outputs/k2/Site01_horizon_20000m.csv `
  --out outputs/k3/_sens_Site01.csv
```

## 8. Koşu sırasında bulunan iki sorun

Her ikisi de ilgili sahibe bildirildi; bu koşu bunlara rağmen tamamlandı.

**K3 — `scripts/k3_sensitivity.py` çok bölgeli `--series` kabul etmiyor.**
`load_series_csv` damgaların kesin artan olmasını istiyor. İki bölgenin
serisi tek dosyada birleştirildiğinde damgalar tekrar ettiği için doğrulama
hata veriyor:

```
ValueError: Zaman damgaları kesin artan olmalı:
  2026-11-21T00:00:00+00:00 → 2026-11-14T00:00:00+00:00
```

Betik profilleri `outputs/k2/*` üzerinden otomatik keşfettiği için birden
çok bölgeyi aynı koşuda tarıyor; bu yol yalnızca sentetik seriyle çalışıyor.
Geçici çözüm: bölge bölge koşturup çıktıları birleştirmek (bu koşuda böyle
yapıldı).

**K2 — `outputs/k2/Site0X_summary_20000m.json` eski boylamı taşıyor.**
`lon_deg_east = 222.510447`, yani kanonik [−180, 180] aralığı dışında.
`sites.py` düzeltildi ama bu özet dosyası güncellenmedi. Denetleyici bunu
yakalamıyor: `GEO-01` kuralı yalnızca `.py` dosyalarını tarıyor. Ayrıca bu
özet dosyalarında `dem` bölümü yok, yani 20 km profilinin hangi üründen
geldiği (240 m/piksel) çıktıdan okunamıyor; ürün ancak
`data/manifest.csv` satırından (`lola_south_pole_240mpp_adj`) çıkarılabildi.
Bölüm 5'teki uyarı bu yüzden gereklidir.
