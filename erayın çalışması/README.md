# Yerel Ay İniş Sahası Navigasyon ve Yörünge Simülasyon Sistemi
*(Lunar Landing Site Navigator & Orbit Simulation System)*

NASA Artemis ve profesyonel görev mühendisliği standartlarında, **hiçbir dış web API'sine veya çevrim içi harita karosuna (Moon Trek vb.) bağımlı olmadan**, **%100 yerel (offline)** çalışan bir Ay iniş sahası navigasyon, arazi analizi ve gök mekaniği simülasyon sistemidir.

---

## 🚀 Temel Özellikler ve Mimari

```
lunar-landing-navigator/
├── data/
│   ├── kernels/           # SPICE çekirdekleri (de440s.bsp, naif0012.tls, pck00011.tpc, moon_pa, tf)
│   └── dem/               # Ham LRO LOLA GeoTIFF yükseklik verileri
│       ├── shackleton_rim_dem.tif      # 512x512 yüksek çözünürlüklü Shackleton Krateri DEM
│       └── shackleton_candidates.json  # Artemis 4 aday iniş sahası telemetrisi
├── scripts/
│   ├── download_kernels.py        # Tek seferlik NAIF SPICE çekirdek indirici
│   ├── generate_synthetic_dem.py  # Standart krater DEM üretici
│   └── generate_shackleton_dem.py # MoonTrek LRO LOLA Shackleton kalibre DEM üretici
├── backend/
│   ├── config.py          # Ay fiziksel sabitleri ve görev sınır değerleri
│   ├── orbital_engine.py  # MOON_ME çerçevesi, ENU dönüşümleri, güneş akısı & efemeris
│   ├── terrain_engine.py  # Horn eğim, TRI pürüzlülük, 360° ufuk ray-casting, iniş skoru
│   └── main.py            # FastAPI REST API & SPA sunumu
├── frontend/              # 100% Yerel Three.js 3B Arayüzü (Harici CDN yok)
│   ├── index.html
│   ├── styles.css
│   ├── terrain_viewer.js  # BufferGeometry displacement, dinamik güneş gölgeleri, raycaster
│   ├── app.js             # Zaman kaydırıcısı, katman yöneticisi, telemetri paneli
│   └── vendor/            # three.min.js & OrbitControls.js
├── tests/                 # Kapsamlı pytest test paketi (14 birim & entegrasyon testi)
├── requirements.txt
├── run.py                 # Tek komutla başlatıcı
└── README.md
```

---

## 🛰️ 1. Yörünge ve Eksen Motoru (`orbital_engine.py`)

- **Yüksek Hassasiyetli Referans Çerçevesi**: Düşük hassasiyetli `IAU_MOON` yerine, NASA JPL/NAIF standardı olan **`MOON_ME`** (*Mean Earth / Polar Axis*) çerçevesi kullanılır. (İkincil olarak `MOON_PA` desteklenir).
- **Yerel Ufuk Düzlemi (ENU - East-North-Up)**:
  - $\mathbf{u}_{up} = [\cos(\phi)\cos(\lambda), \cos(\phi)\sin(\lambda), \sin(\phi)]^T$ (Yüzey normali)
  - $\mathbf{u}_{east} = [-\sin(\lambda), \cos(\lambda), 0]^T$ (Doğu birim vektörü)
  - $\mathbf{u}_{north} = \mathbf{u}_{up} \times \mathbf{u}_{east}$ (Kuzey kutup birim vektörü)
- **Toposentrik Efemeris & Güneş Akısı**:
  - Ay yüzeyindeki gözlemcinin ENU koordinatlarında Güneş ve Dünya'nın anlık azimut ve yükseklik (elevation) açıları.
  - Güneş mesafesi ve ışınım akısı: $S = S_0 \cdot (1\text{ AU} / d)^2 \cdot \max(0, \sin(\text{elevation}))$.
- **Kesintisiz Çevrimdışı Çalışma (Analytical Fallback)**: SPICE çekirdekleri henüz indirilmemiş olsa dahi yüksek hassasiyetli analitik efemeris motoru devreye girer.

---

## 🏔️ 2. Kendi Haritalandırma ve Arazi Analiz Motorumuz (`terrain_engine.py`)

Hazır risk haritaları yerine, ham LRO LOLA yükseklik matrisinden matematiksel olarak türetilen katmanlar:

1. **Eğim (Slope, derece)**:
   - Horn (1981) $3 \times 3$ ağırlıklı türev filtreleri ile piksel bazında kesin eğim gradyanı:
     $$\text{Slope} = \arctan\left(\sqrt{(\partial z / \partial x)^2 + (\partial z / \partial y)^2}\right)$$
2. **Yüzey Pürüzlülüğü (TRI - Terrain Ruggedness Index)**:
   - Riley et al. standardı ile pikselin 8 komşusu arasındaki karesel ortalama kot farkı:
     $$\text{TRI} = \sqrt{\frac{1}{8}\sum_{i=1}^{8} (z_i - z_0)^2}$$
3. **360° Ufuk Yükselme Maskesi (Horizon Ray-Casting)**:
   - Her pikselden 36 farklı azimut yönünde (her $10^\circ$) dışa doğru ışın atarak çevre tepe ve krater sırtlarının oluşturduğu maksimum engel yükselme açısı önbelleğe alınır.
4. **Zaman Serisi Simülasyonu**:
   - **Güneşlenme Süresi (Solar Illumination %)**: Güneş'in ufuk engel açısını aştığı anların toplam simülasyona oranı.
   - **Dünya Doğrudan Görüş Hattı (DTE Line-of-Sight %)**: Dünya iletişim hattının topoğrafik engellere takılmadığı süre yüzdesi.
   - **Çok Kriterli İniş Uygunluk Skoru (0 - 100)**:
     - Eğim $> 12^\circ$ ise **Skor = 0** (Kritik güvenlik vetosu).
     - Güvenli bölgede: $\%35 \text{ Eğim} + \%25 \text{ Pürüzlülük} + \%20 \text{ Güneşlenme} + \%20 \text{ DTE}$.

---

## 🎮 3. Kendi 3B Harita Arayüzümüz (`frontend/`)

- **Three.js Özel BufferGeometry**: Dış harita tile sunucusu kullanılmaz. Ham yükseklik matrisi `PlaneGeometry` üzerinde kot abartısıyla doğrudan tepe noktası (vertex) seviyesinde yerelleştirilir.
- **Gerçek Zamanlı Güneş Gölgeleri**:
  - `DirectionalLight` Güneş'in anlık azimut ve yükseklik açılarına göre uzayda konumlandırılır.
  - PCF Soft Shadow Map ile krater sırtlarının oluşturduğu gerçekçi dinamik gölgeler arazi üzerine düşer.
- **Katman Değiştirici (Layer Switcher)**:
  - 🗺️ **Yükseklik (DEM)**: Ay hipsometrik tonlaması.
  - 📐 **Eğim (Slope)**: Yeşil ($<8^\circ$ güvenli), Sarı ($8-12^\circ$ riskli), Kırmızı ($>12^\circ$ tehlikeli).
  - 🪨 **Pürüzlülük (TRI)**: Regolit pürüzlülük haritası.
  - ☀️ **Güneşlenme %**: Kalıcı karanlık kraterlerden (PSR) zirvelere aydınlanma.
  - 📡 **DTE %**: Dünya ile doğrudan telemetri görüş hattı.
  - 🎯 **İniş Skoru**: Ağırlıklı iniş uygunluk ısı haritası.
- **Zaman Kaydırıcısı (Time Scrubber & Oynatıcı)**:
  - 24 saatlik döngüyü kaydırıcı ile ileri-geri alabilir veya otomatik oynatabilirsiniz.
  - HUD üzerinde anlık Güneş Akısı ($W/m^2$), Dünya-Ay Mesafesi ve koordinat açıları güncellenir.
- **İnteraktif Nokta İnceleme (Inspector Panel & Grafikler)**:
  - Haritada herhangi bir noktaya tıklandığında Three.js Raycaster ile nokta yakalanır, 3B hedef halkası yerleştirilir.
  - Yan panelde o koordinatın eğimi, pürüzlülüğü, güneşlenme süresi, DTE yüzdesi ve iniş uygunluk rozeti gösterilir.
  - HTML5 Canvas üzerinde **24 saatlik Güneş/Dünya/Ufuk engel çizgileri grafiği** anında çizilir.

---

## 🛠️ Kurulum ve Çalıştırma

### 1. Gereksinimlerin Kurulması
```bash
pip install -r requirements.txt
```

### 2. (Opsiyonel) NASA SPICE Çekirdeklerinin İndirilmesi
Uygulama yerel çekirdekler olmadan da yüksek hassasiyetli analitik efemerisle kusursuz çalışır. Tam JPL DE440 çekirdeklerini indirmek için:
```bash
python scripts/download_kernels.py
```

### 3. Uygulamayı Başlatma
```bash
python run.py
```
Veya doğrudan Uvicorn ile:
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Tarayıcınızda açın:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

API Dokümantasyonu (Swagger):
👉 **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**

---

## 🧪 Birim ve Entegrasyon Testleri

Tüm gök mekaniği, koordinat dönüşümleri, Horn eğim matrisi, ray-casting ufuk maskesi ve API uç noktaları `pytest` ile doğrulanmıştır:

```bash
pytest -v
```

**Test Kapsamı:**
1. `test_moon_me_cartesian_transformations`: Ay ekvatoru, kutupları ve irtifa dönüşümlerinin doğrulanması.
2. `test_enu_basis_orthonormality`: ENU baz vektörlerinin dikliği, sağ-el kuralı ve normlarının 1.0 olması.
3. `test_enu_to_azimuth_elevation`: 0-360° Azimut ve $\pm 90^\circ$ Elevation açı dönüşümleri.
4. `test_solar_flux_physics`: Başucu, eğik ve gece koşullarında $1361\text{ W/m}^2$ güneş sabiti fiziği.
5. `test_compute_ephemeris_range`: 24 saatlik Güneş ve Dünya efemeris üretimi.
6. `test_horn_slope_calculation_known_geometry`: 0°, 8° ve 45° analitik eğimli test düzlemlerinde Horn doğrulaması.
7. `test_tri_roughness_calculation`: Pürüzsüz ve engebeli zeminlerde TRI indeksi.
8. `test_horizon_ray_casting_algorithm`: Sentetik krater tabanında ve dış düzlükte 360° ray-casting açıları.
9. `test_landing_suitability_scoring_rules`: Eğim vetosu ($>12^\circ \to 0$) ve Artemis ağırlıklandırma kuralları.
10. `test_api_status`, `test_api_terrain_mesh`, `test_api_terrain_layers`, `test_api_simulate`, `test_api_terrain_inspect`: REST API uç noktalarının uçtan uca doğrulanması.
