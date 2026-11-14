# Karar kaydı

| ID | Zaman (UTC) | Karar | Gerekçe | Sahip | Etkilenen alan |
|---|---|---|---|---|---|
| ADR-001 |  | Python + Streamlit | 24 saatlik bilimsel prototip ve hızlı entegrasyon | K5 | Tümü |
| ADR-002 |  | UTC ve doğu-pozitif boylam | Ortak veri sözleşmesi | K1/K2 | Veri |
| ADR-005 | 2026-11-14T09:11Z | Python 3.12 ve tek ortak `requirements.txt` | numpy/rasterio/pyproj 3.12+ ister; tüm doğrudan paketlerde Windows, Linux ve macOS için cp312 tekerleği var | K1 | Kurulum |
| ADR-006 | 2026-11-14T09:30Z | ÖNERİ: veri sözleşmesini pandera şemasıyla zorla | Zorunlu alanlar, enum ve açı aralıkları yalnızca belgede; kodda kontrol yok. Hata modül sınırında yakalanmazsa arayüzde görünür | K1 | Veri, Kurulum |
| ADR-500 | 2026-11-14T12:04Z | `main` dal korumasında dört kontrol zorunlu: `structure`, `Kanonik sözleşme`, `ubuntu-latest / Python 3.12`, `windows-latest / Python 3.12`; `strict` açık | Kapılar koşuyordu ama yalnızca `structure` zorunluydu; testler ve sözleşme kırmızıyken PR birleşebiliyordu | K5 | `.github/`, birleştirme |

Yeni kararlar kısa tutulur. Önceki bir karar değişirse yeni satır açılır ve eski ID'ye bağlantı verilir.

