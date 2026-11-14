# K2 — LOLA tabanlı topoğrafik ufuk profili

Issue: [#2](https://github.com/kingos352/luna-sight/issues/2) · Dal: `k2/lola-horizon`

Bu belge, Ay güney kutbundaki iki aday bölge için LRO/LOLA verisinden üretilen
ufuk profilini, kullanılan ürün sürümünü, parametreleri, doğrulama kanıtını ve
bilimsel sınırları kaydeder.

## 1. Veri ürünü kaydı

| Alan | Değer |
|---|---|
| Ürün | LRO/LOLA bölgesel DEM (LDEM) + LDEC dönüş sayısı haritası |
| Sağlayıcı | NASA GSFC PGDA (LOLA Data Node) |
| Sürüm | Barker vd. 2021, düzeltilmiş 5 m/piksel (PSS 203:105119) |
| Datum / çerçeve | MOON_ME, JPL DE421 yörünge çözümü |
| Projeksiyon | Güney kutup stereografik, küresel R = 1 737 400 m, kutupta gerçek ölçek |
| Piksel | 5 m × 5 m, GMT piksel-merkezli (X/Y piksel merkezini verir) |
| Kapsam | Her karo 3 200 × 3 200 piksel = 16 km × 16 km |
| Kaynak | `https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/<Site>/` |
| Atıf | Barker vd. 2021; Mazarico vd. 2011 (bölge numaralandırması) |

Dosya özetleri (SHA-256), indirme zamanı ve parametreler `data/manifest.csv`
içinde `K2` sahibiyle kayıtlıdır. Ham GeoTIFF'ler depoya eklenmez
(`data/cache/`), yalnızca küçük türetilmiş çıktılar `outputs/k2/` altında tutulur.

## 2. Aday noktalar

Aday koordinatı, ilgili PGDA karosunun merkezinden ters stereografik dönüşümle
hesaplanır (`DemGrid.center_lonlat`). Bu, bölge karoları aday alanlara
ortalandığı için tekrarlanabilir bir tanımdır; iniş elipsi seçimi bu görevin
kapsamı dışındadır.

| Site | Bölge | Enlem (°) | Boylam doğu-pozitif (°) | Karonun X/Y merkezi (m) |
|---|---|---|---|---|
| Site01 | Connecting ridge | −89.463163 | −137.489553 | −11 000, −12 000 |
| Site04 | Shackleton rim | −89.766811 | −171.869898 | −1 000, −7 000 |

## 3. Yöntem

Her azimut θ için ışın boyunca 10 m aralıkla yüzey yüksekliği örneklenir
(bilineer) ve ufuk açısı ışın üzerindeki en büyük yükseklik açısı olarak alınır:

```
h(θ) = max_r  atan2( z(r·û(θ)) − (z_gözlemci + h_göz) , r )
```

- Azimut kuzeyden saat yönünde; doğu 90° (`docs/DATA_CONTRACT.md`).
- Yerel kuzey/doğu birim vektörleri stereografik düzlemde analitik türetilir
  (`azimuth_unit_vector`), ayrı bir projeksiyon kütüphanesi gerekmez.
- Yüzey yüksekliği geçersizse (gerçek boşluk/kapsam dışı) örnek ufka katkı
  vermez ve `gap_fraction` olarak raporlanır; boşluk asla "görünür" sayılmaz.
- LDEC ≥ 1 olan pikseller "gerçek LOLA dönüşü" sayılır. 5 m/piksel ızgarada bu
  oran yalnızca **%8–11** düzeyindedir; yüzeyin geri kalanı enterpolasyonludur.
  Yerel kapsam eşiğin (varsayılan %5) altına düşerse profil `partial` işaretlenir.
- İki analiz yarıçapı (2 km ve 4 km) aynı noktada karşılaştırılır.

## 4. Parametreler

| Parametre | Değer |
|---|---|
| Azimut adımı | 1° (360 azimut) |
| Radyal adım | 10 m |
| Analiz yarıçapları | 2 000 m ve 4 000 m |
| Gözlemci yüksekliği | 2 m |
| Boşluk toleransı | 0.02 |
| Kapsam eşiği | 0.05 |

## 5. Sonuçlar

`outputs/k2/` altındaki CSV/JSON dosyalarından:

| Site | Yarıçap | Ufuk min | Ufuk ortalama | Ufuk max | Yerel kapsam | Kalite |
|---|---|---|---|---|---|---|
| Site01 | 2 km | −4.615° | −0.373° | +2.215° | %9.3 | valid |
| Site01 | 4 km | −4.615° | −0.373° | +2.215° | %10.3 | valid |
| Site04 | 2 km | −31.370° | +1.876° | +32.060° | %8.8 | valid |
| Site04 | 4 km | −31.370° | +3.219° | +32.060° | %8.4 | valid |

**Yarıçap karşılaştırması**

- **Site01 (Connecting ridge):** ufuk, gözlemciden medyan **210 m** uzaklıktaki
  mikro-rölyef tarafından belirleniyor; 2 km ile 4 km profilleri tüm azimutlarda
  aynı (en büyük fark 0.000°). Yani 4 km'lik halka mevcut ufku yükseltmiyor.
- **Site04 (Shackleton rim):** 4 km yarıçap, medyan engel mesafesini 150 m'den
  3 015 m'ye taşıyor; ortalama ufuk 1.876° → 3.219°, en büyük azimut farkı
  **6.224°**. Krater içi (GB yönü) −31°, krater dışı duvar (D yönü) +32° ile
  Shackleton kenarı topoğrafyasıyla tutarlı.

Bu fark, ufuk profilinin yarıçapa duyarlı olduğunu ve tek bir yarıçapın bilimsel
olarak yeterli olmadığını gösterir.

## 6. Doğrulama

| Kanıt | Yöntem | Sonuç |
|---|---|---|
| Koordinat dönüşümü | Altı noktada gidiş-dönüş; GDAL/PROJ ile karşılaştırma | Δ < 1e-3 m |
| Projeksiyon ölçeği | Kutup çevresinde 1 km ve 2 km yerdeğiştirme | Göreli sapma < %0.5 |
| Ufuk algoritması | Sentetik düzlem, 100 m sırt, uzak sırt | Analitik açıyla eşleşiyor |
| Boşluk davranışı | Sentetik boşluk ve gözlemci-boşluk vakaları | `partial` / `missing` |
| Gerçek veri | 8 azimutta bağımsız kaba kuvvet hesabı | Birebir aynı (3 ondalık) |
| Yarıçap etkisi | Site04, 2 km vs 4 km | 6.224° fark |

Testler: `tests/test_terrain_polar.py`, `tests/test_terrain_horizon.py`,
`tests/test_terrain_dem.py` (toplam 25 test, hepsi sentetik `test_fixture`
verisiyle, ağ erişimi gerektirmez).

## 7. Bilimsel sınırlar

- Profil **görünürlük kararı değildir**; Güneş/Dünya azimut-yükseklik serisiyle
  birleştirilmesi K3 motorunun işidir.
- Gözlemci noktası DEM karo merkezidir, optimize edilmiş iniş elipsi değildir.
  Site01'de nokta yerel bir yamaçta; yakın mikro-rölyef ufku belirliyor.
- 5 m/piksel yüzeyin büyük bölümü enterpolasyonludur (yerel dönüş oranı %8–11).
  Bu, ufuk açısında sistematik bir belirsizlik yaratır; Barker vd. 2021'in
  `*_toterr.tif` ürünü desteklenmektedir ama bu koşuda indirilmemiştir.
- Stereografik ölçek distorsiyonu 4 km yarıçapta %0.001 mertebesindedir; ihmal
  edilebilir.
- Güneş kutupta ufka çok yakın seyrettiği için 0.1°'lik ufuk hatası saatler
  mertebesinde görünürlük farkı üretebilir; duyarlılık analizi K3'te yapılmalıdır.

## 8. Yeniden üretme

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt

# Ağ erişimi varsa (≈160 MB indirir):
python scripts/k2_horizon_profile.py --radii 2000,4000

# Veri zaten data/cache/lola altındaysa:
python scripts/k2_horizon_profile.py --offline --radii 2000,4000
```

## 9. Çıktılar

| Dosya | İçerik |
|---|---|
| `outputs/k2/Site0X_horizon_2000m.csv` | 360 satır: azimut, ufuk açısı, engel mesafesi, boşluk, kapsam |
| `outputs/k2/Site0X_horizon_4000m.csv` | Aynı şema, 4 km yarıçap |
| `outputs/k2/Site0X_summary.json` | Koordinat, DEM meta verisi, boşluk taraması, yarıçap karşılaştırması |
| `outputs/k2/k2_comparison.json` | İki bölgenin birleşik özeti |
| `outputs/k2/manifest_rows.csv` | `data/manifest.csv`'ye eklenen satırlar |

## 10. Sonraki adım

K3 görünürlük motoru bu profili `terrain_horizon_sun_deg` /
`terrain_horizon_earth_deg` olarak tüketir; azimut enterpolasyonu ve geçiş
sınırı inceltme K3 kapsamındadır.
