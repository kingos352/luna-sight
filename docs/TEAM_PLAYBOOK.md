# Ekip çalışma kitabı

## Roller

| Rol | Sahiplik | İlk teslim |
|---|---|---|
| K1 | JPL Horizons, astronomik çerçeve | Gerçek Güneş/Dünya zaman serisi |
| K2 | LRO/LOLA, koordinat ve ufuk | Adaylar ve doğrulanmış ufuk profili |
| K3 | Görünürlük ve pencere motoru | Test edilmiş karşılaştırma metrikleri |
| K4 | Streamlit ve görselleştirme | A/B kullanıcı akışı |
| K5 | Entegrasyon, QA, demo ve teslim | Çalışan ana sürüm ve teslim paketi |

## İletişim ritmi

- Her iki saatte en çok 10 dakikalık kapı toplantısı.
- Her kişi: çalışan çıktı, güncel engel, sonraki teslim.
- Kararlar GitHub Issue veya `docs/DECISIONS.md` içine yazılır.
- Hızlı mesajlaşma yalnızca koordinasyon içindir; karar ve kaynak bağlantısı depoya taşınır.
- Kritik engel etiketi: `blocker`; bilimsel inceleme etiketi: `science-review`.

## Dosya sahipliği

| Alan | Birincil | İnceleyen |
|---|---|---|
| `src/luna_sight/ephemeris/` | K1 | K3 |
| `src/luna_sight/terrain/` | K2 | K3 |
| `src/luna_sight/visibility/` | K3 | K1 veya K2 |
| `app/` | K4 | K5 |
| `tests/`, `.github/`, teslim | K5 | İlgili modül sahibi |

## Çakışma önleme

- Aynı dosyada paralel çalışma başlamadan Issue yorumunda sahiplik yazılır.
- Ortak şema yalnızca `docs/DATA_CONTRACT.md` üzerinden değiştirilir.
- Uzun yaşayan dallar kullanılmaz; değişiklikler sık aralıklarla `main` ile güncellenir.
- İkili dosyalar ve büyük veriler Git dışında tutulur.

## Araçların görevi

- GitHub: kod, Issue, karar, inceleme ve sürüm kaydı için ana kaynak.
- Google Drive: demo videosu, sunum, yüksek boyutlu teslim kopyaları ve harici yedek için.
- Mesajlaşma uygulaması: kısa durum ve toplantı bağlantısı için.

