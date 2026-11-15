# AI yüzey analizi

Bu katman K2/K3 ölçümlerini değiştirmez. Model yalnızca görüntüyü yorumlar;
modelin söylediği çap, eğim, yükseklik veya güvenlik sayıları ölçüm sayılmaz.

## Uç nokta bulguları (2026-11-15)

- NVIDIA `/v1/models` canlı listesinde Cosmos3 Nano Reasoner bulunmadı.
- Cosmos Reason2 8B listede bulundu, ancak aynı anahtarla hem görüntülü
  hem metin isteği HTTP 404 `Function not found for account` döndürdü.
- [NVIDIA resmi forum açıklaması](https://forums.developer.nvidia.com/t/function-not-found-for-account/357670)
  Reason2 API erişiminin kapatıldığını belirtiyor. Liste kontrolü, çıkarımın
  çalıştığı anlamına gelmez. Yeni anahtar üretmek çözüm olarak varsayılmaz.
- Cosmos3 kullanmak için erişilebilir bir NIM sunucusu ve uygun donanım gerekir.
  Bu bilgisayarda Docker PATH'te bulunmadı. Kurulum yapılmadı.

Katalog sayfasındaki “Free API” yazısı tek başına çalışan uç nokta kanıtı değildir.
Model kimliği her analiz kaydında tutulur; otomatik model değiştirme yoktur.

Kullanıcının alternatif model onayıyla `nvidia/nemotron-3.5-super-vl-120b-a12b`
seçildi. Aynı API anahtarıyla metin isteği ve Site01'in gerçek 801×801 DEM
görseli başarılı oldu: geçerli JSON, üç gözlem, durum `completed`.
Site04 de CLI üzerinden aynı modelle gerçek görüntülü çağrıda `completed`
durumuna ulaştı. İki kayıtta da `inferenceExecuted=true`; bilimsel ölçümler
K2/K3 kaynaklarından korundu. Başarısız Reason2 denemesi ayrı bir `failed`
oturumu olarak saklandı.
[NVIDIA model API sözleşmesi](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-super-vl-120b-a12b-infer).

## Yerel yapılandırma

`.env.example` dosyasını `.env` olarak kopyalayın. Anahtar yalnızca yerelde tutulur:

```dotenv
LUNA_SIGHT_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
LUNA_SIGHT_NIM_MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b
LUNA_SIGHT_NIM_REASONING_EFFORT=none
NVIDIA_API_KEY=
LUNA_SIGHT_DEM_DIR=./data/cache/lola
```

Harici Cosmos3 sunucusu için adresi ve model adını sunucunun `/v1/models`
yanıtına göre ayarlayın. Uzak bağlantılarda HTTPS zorunludur. Yerel NIM için
`http://127.0.0.1:8000/v1` kullanılabilir. Ortam değişkenleri `.env` değerlerinden
önceliklidir. `.env` anahtarı loglara veya analiz JSON dosyasına yazılmaz.
Çalışan uygulamada `.env` değişirse sunucuyu yeniden başlatın. Reasoning ayarı
Nemotron sözleşmesindeki `none/low/high` değerlerini kabul eder; başka bir
sunucu bu alanı desteklemiyorsa boş bırakın.

## Görüntü verisi

Manifestteki `Site01_final_adj_5mpp_surf.tif` ve
`Site04_final_adj_5mpp_surf.tif` dosyalarını `data/cache/lola/` altına koyun.
Bu çalışma sırasında LunaEk1'de bulunan iki dosyanın SHA-256 değerleri
`data/manifest.csv` ile doğrulandı ve dosyalar bu konuma kopyalandı.
Yeni kurulumda kaynak URL'ler ve doğrulama özetleri manifesttedir.

Hillshade, aday nokta çevresindeki 4 km kare pencereyi DEM'in Ay koordinat
sisteminde kırpar. Bu iki dosyada çıktı 801×801, 5 m/pikseldir. Daha geniş
pencereler en çok 1024 piksele indirilir ve gerçek gönderim ölçeği kaydedilir.
Enterpolasyonla doldurulmuş yükseklikler gerçek lazer dönüşü sayılmaz.

**Hillshade fotoğraf değildir:** aydınlatma azimutu 315°, yüksekliği 45°
olan yapay kabartmadır. Gerçek Güneş gölgesi, albedo, yüzey dokusu ve küçük
kaya blokları buradan doğrulanamaz. LDEC kapsamı ile görüntüdeki geçerli
yükseklik kapsamı farklıdır. WAC 4K seçeneği yalnızca bölgesel bağlam içindir.

## Çalıştırma

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m luna_sight.ai --probe
.venv\Scripts\python.exe -m luna_sight.ai --site Site01
.venv\Scripts\python.exe -m luna_sight.ai --site Site01 --infer
.venv\Scripts\python.exe -m streamlit run app\app.py
```

İlk komut yalnızca model listesini kontrol eder. İkincisi görüntü hazırlar;
modele istek göndermez. `--infer` gerçek çağrı yapar. Önizlemeler
`data/cache/ai_images/`, analizler `data/cache/ai_sessions/` altındadır.
Model başarısız olursa bilimsel sonuçlar korunur ve durum `failed` olur.
Yapısız veya eksik model yanıtı `partial` olur.

Streamlit'te **3B Ay küresi → LunarSight AI** düğmesi mevcut analiz
penceresini açar. Ayrı AI sekmesi yoktur. DEM, 3B sahne yakalama ve dosya
yükleme sunucuda doğrulanır. Açıklama/Tespit/Noktalama düğmeleri gerçek
model çağrısı yapar; Soru-Cevap aynı görüntüyle sunucuda tutulan son sohbet
turlarını kullanır. Açılış yalnızca DEM hazırlar, çıkarım yapmaz.

Sabit cevap, kutu, nokta ve güven yüzdeleri kaldırıldı. Model yalnızca
0–1 aralığında geçerli görüntü konumları verirse yaklaşık işaret çizilir;
vermezse boş konumlar doldurulmaz. Bu koordinatlar fiziksel ölçüm değildir.
Kutu/nokta için bağımsız doğruluk garantisi verilmez. İniş güvenliği önerilmez.

React kaynakları `frontend/` altındadır. `npm ci` ardından `npm run build`
derlenmiş dosyaları `app/components/lunar/` altına yazar. Ortak NASA dokuları
ve bilimsel JSON dosyaları `app/static/moon/` içinden okunur. Eski bağımsız
kürenin bu dizine yeniden kopyalanması AI köprüsünü ezmez. Görünüm Streamlit'in
resmi çift yönlü component protokolüyle `src/luna_sight/ai/component.py`
sunucu köprüsüne bağlıdır; ayrı API sunucusu ve tarayıcıda API anahtarı yoktur.
Tekrarlanan request id aynı oturumda tekrar model çağırmaz. Kapatılan veya
kaynağı değişen görüntünün eski cevabı yeni görüntüye uygulanmaz.

Nominal seçili UTC anı ve 0°/2 km/4 km senaryosu için model bağlamı
tarayıcının gönderdiği sayılardan değil sunucudaki `timeseries.json`
verisinden alınır. Sanal gösterim vakası nominal bilimsel ölçüm gibi
sunulmaz. Kayıtlı bölgesel K2/K3 özeti ayrı etiketlenir.

## Doğrulama sınırı

`tests/test_ai.py` çevrimdışı test_fixture verileriyle URL/anahtar güvenliğini,
hata durumlarını, model listesi kontrolünü, DEM kapsam/projeksiyonunu,
hillshade ölçeğini, şema normalizasyonunu ve bilimsel değerlerin korunmasını
denetler. Bunlar modelin bilimsel doğruluğunu veya iniş güvenliğini kanıtlamaz.

Son ölçüm (2026-11-15, `feat/nvidia-cosmos-ai`): 261 test geçti, ruff tüm
ağaçta temiz, yönetişim denetimi 0 uyarı, `tsc --noEmit` temiz,
`npm run build` tamamlandı.

Bu bölüm daha önce "Ruff temiz" ve "Vite derlemesi başarılı" diyordu;
ölçüm anında ikisi de doğru değildi (212 ruff hatası ve
`LunarGlobe.tsx` içinde sözdizimi hatası vardı). İkisi de o tarihten
sonra giderildi: sözdizimi hatası düzeltildi, ruff hatalarının kaynağı
olan `flight_physics/` depodan çıkarıldı.

Aşağıdaki tarayıcı doğrulamaları **daha eski bir ağaç durumuna** aittir.
O tarihten sonra uçuş simülasyonu paneli ve dayanaksız sayı gösteren
alanlar arayüzden kaldırıldı; bu akışlar güncel arayüzde yeniden
koşturulmadı.

Gerçek Edge tarayıcısında Playwright ile mevcut
LunarSight AI penceresinin DEM hazırlama, 3B sahne yakalama, dosya yükleme
ve Site04'e geçiş akışları doğrulandı. Ekran görüntüleri `data/cache/`
altında tutulur. Canlı test ayrıca `LUNA_LIVE_AI=1 npx playwright test`
ile açıkça etkinleştirilir; normal tarayıcı testi model çağırmaz.

Mevcut LunarSight AI penceresinden yapılan canlı analiz ve takip sorusu
gerçek Edge tarayıcısında uçtan uca geçti (32 saniye). Türkçe analiz,
K2/K3 ölçümleri ve takip cevabı aynı pencerede görüntülendi. Kanıtlar:
`data/cache/lunar_ai_live_result.png`, `data/cache/lunar_ai_followup.png`.

Telefon boyutunda (390×844) mevcut pencerenin açılması, DEM hazırlaması ve
kapanması da doğrulandı. Canlı NVIDIA hizmeti sonraki bir denemede geçici
bağlantı hatası verdi; bu durum kullanıcıya hata olarak döner, sonuç üretilmez.
Okuma zaman aşımında aynı POST otomatik tekrarlanmaz; yeniden deneme kullanıcı
düğmesiyle yeni bir istek olarak yapılır.

Son asıl site doğrulaması (`http://127.0.0.1:8501`): üç Playwright testi de
geçti. DEM/3B yakalama/yükleme/bölge değişimi, gerçek model analizi ve takip
sorusu, 390×844 mobil erişim doğrulandı. Canlı analiz ve takip sorusu testi
47 saniyede tamamlandı. AI bileşeninin derlemesi ortak statik küre paketinden
ayrıldı; derlenmiş dosyada gerçek Streamlit köprüsünün bulunması Python
testiyle de denetleniyor.
