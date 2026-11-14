# Karar kaydı

| ID | Zaman (UTC) | Karar | Gerekçe | Sahip | Etkilenen alan |
|---|---|---|---|---|---|
| ADR-001 |  | Python + Streamlit | 24 saatlik bilimsel prototip ve hızlı entegrasyon | K5 | Tümü |
| ADR-002 |  | UTC ve doğu-pozitif boylam | Ortak veri sözleşmesi | K1/K2 | Veri |
| ADR-003 | 2026-11-14T09:20Z | Ufuk profili, PGDA 5 m/piksel LOLA LDEM yüzeyi + LDEC kapsam maskesi ile üretilir; 2 km ve 4 km yarıçapları birlikte raporlanır | 5 m ızgarada gerçek LOLA dönüş oranı yalnızca %8–11; yüzeyi tümden dışlamak yerine kapsam oranı kalite bayrağına yazılır | K2 | `src/luna_sight/terrain/`, `outputs/k2/` |
| ADR-004 | 2026-11-14T09:35Z | Görünürlük çıktısı boolean değil durum metni (`visible/blocked/uncertain`); `uncertain` için ±0.10° geçiş bandı ve gerekçe kodu; pencere sınırları bant kenarına göre inceltilir | Üçüncü durum boolean ile temsil edilemez; eksik veri görünür/engelli sınıfına çevrilemez; sabit örnekleme sınırı ±2.5 dk kuantalama bırakır | K3 | `src/luna_sight/visibility/`, `outputs/k3/` |

Yeni kararlar kısa tutulur. Önceki bir karar değişirse yeni satır açılır ve eski ID'ye bağlantı verilir.

