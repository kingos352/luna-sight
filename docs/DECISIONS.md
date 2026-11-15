# Karar kaydı

| ID | Zaman (UTC) | Karar | Gerekçe | Sahip | Etkilenen alan |
|---|---|---|---|---|---|
| ADR-001 |  | Python + Streamlit | 24 saatlik bilimsel prototip ve hızlı entegrasyon | K5 | Tümü |
| ADR-002 |  | UTC ve doğu-pozitif boylam | Ortak veri sözleşmesi | K1/K2 | Veri |
| ADR-003 | 2026-11-14T09:20Z | Ufuk profili, PGDA 5 m/piksel LOLA LDEM yüzeyi + LDEC kapsam maskesi ile üretilir; 2 km ve 4 km yarıçapları birlikte raporlanır | 5 m ızgarada gerçek LOLA dönüş oranı yalnızca %8–11; yüzeyi tümden dışlamak yerine kapsam oranı kalite bayrağına yazılır | K2 | `src/luna_sight/terrain/`, `outputs/k2/` |
| ADR-004 | 2026-11-14T09:35Z | Görünürlük çıktısı boolean değil durum metni (`visible/blocked/uncertain`); `uncertain` için ±0.10° geçiş bandı ve gerekçe kodu; pencere sınırları bant kenarına göre inceltilir | Üçüncü durum boolean ile temsil edilemez; eksik veri görünür/engelli sınıfına çevrilemez; sabit örnekleme sınırı ±2.5 dk kuantalama bırakır | K3 | `src/luna_sight/visibility/`, `outputs/k3/` |
| ADR-005 | 2026-11-14T09:11Z | Python 3.12 ve tek ortak `requirements.txt` | numpy/rasterio/pyproj 3.12+ ister; tüm doğrudan paketlerde Windows, Linux ve macOS için cp312 tekerleği var | K1 | Kurulum |
| ADR-006 | 2026-11-14T09:30Z | ÖNERİ: veri sözleşmesini pandera şemasıyla zorla | Zorunlu alanlar, enum ve açı aralıkları yalnızca belgede; kodda kontrol yok. Hata modül sınırında yakalanmazsa arayüzde görünür | K1 | Veri, Kurulum |
| ADR-100 | 2026-11-14T12:13Z | K1 bağımsız doğrulaması, Horizons alt-güneş/alt-dünya noktasından paralaks dahil vektör hesabıyla yapılır; SPICE çekirdeği bu koşuda kullanılmaz | `OBSERVER` tablosu azimut/yüksekliği hazır verdiği için hattın kendi tutarlılığı yorum hatasını dışlamıyor; alt-nokta farklı bir nicelik ve farklı kod yolu | K1 | `src/luna_sight/ephemeris/`, doğrulama |
| ADR-500 | 2026-11-14T12:04Z | `main` dal korumasında dört kontrol zorunlu: `structure`, `Kanonik sözleşme`, `ubuntu-latest / Python 3.12`, `windows-latest / Python 3.12`; `strict` açık | Kapılar koşuyordu ama yalnızca `structure` zorunluydu; testler ve sözleşme kırmızıyken PR birleşebiliyordu | K5 | `.github/`, birleştirme |
| ADR-501 | 2026-11-15T11:21Z | `frontend/` kaynağı için TypeScript tip denetimi kapısı (`Frontend checks / TypeScript tip denetimi`) eklenir; kapı **şimdilik zorunlu değildir**, `frontend/src/components/scene/LunarGlobe.tsx` derlenir hale geldikten sonra dal korumasında zorunlu listeye alınır ve GOVERNANCE bölüm 10 güncellenir | 3B küre derlenmiş paket olarak depoya giriyor, kaynağı hiçbir kapıdan geçmiyordu; sözdizimi hatası olan bir .tsx fark edilmedi. Kırmızı bir kontrolü hemen zorunlu yapmak tüm PR'ları kilitler | K5 | `.github/`, `frontend/` |

Yeni kararlar kısa tutulur. Önceki bir karar değişirse yeni satır açılır ve eski ID'ye bağlantı verilir.

## AI yüzey analizi (2026-11-15)

- Görsel yorum bilimsel ölçümlerden ayrıdır; K2/K3 çıktıları korunur.
- DEM hillshade topoğrafya içindir; fotoğraf, gerçek Güneş gölgesi veya küçük kaya kanıtı değildir.
- `.env` okuma için python-dotenv çalışma zamanı bağımlılığına taşındı;
  görüntü hazırlama için kullanılan Pillow doğrudan bağımlılık olarak sabitlendi.
- Kullanıcı, kapalı Cosmos Reason2 API'si yerine erişilebilir bir NVIDIA görsel
  modelinin araştırılmasını ve denenmesini onayladı. Model seçimi yapılandırmada
  açıktır ve analiz kaydında saklanır. Ayrıntılar: `AI_SURFACE_ANALYSIS.md`.

