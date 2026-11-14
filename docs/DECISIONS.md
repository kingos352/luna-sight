# Karar kaydı

| ID | Zaman (UTC) | Karar | Gerekçe | Sahip | Etkilenen alan |
|---|---|---|---|---|---|
| ADR-001 |  | Python + Streamlit | 24 saatlik bilimsel prototip ve hızlı entegrasyon | K5 | Tümü |
| ADR-002 |  | UTC ve doğu-pozitif boylam | Ortak veri sözleşmesi | K1/K2 | Veri |
| ADR-003 | 2026-11-14T09:20Z | Ufuk profili, PGDA 5 m/piksel LOLA LDEM yüzeyi + LDEC kapsam maskesi ile üretilir; 2 km ve 4 km yarıçapları birlikte raporlanır | 5 m ızgarada gerçek LOLA dönüş oranı yalnızca %8–11; yüzeyi tümden dışlamak yerine kapsam oranı kalite bayrağına yazılır | K2 | `src/luna_sight/terrain/`, `outputs/k2/` |
| ADR-004 | 2026-11-14T18:00Z | K3'ün iki ayrı uygulaması tek dalda birleştirildi: uzaktaki çekirdek (durum/gerekçe, sınır inceltme, gövde analizi) + yerel entegrasyon katmanı (K1/K2 sağlayıcıları, sözleşme tablosu, ızgara, runner, CLI) | Çekirdek daha kapsamlı ve K2'ye bağlıydı; entegrasyon katmanı gerçek K2 profillerini ve site bazlı koşumu sağlıyordu. İki kopya bakım borcu üretiyordu | K3 | `src/luna_sight/visibility/`, `tests/`, `docs/K3_VISIBILITY.md` |

Yeni kararlar kısa tutulur. Önceki bir karar değişirse yeni satır açılır ve eski ID'ye bağlantı verilir.

