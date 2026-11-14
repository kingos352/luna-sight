# Entegrasyon sözleşmesi ve karar otoritesi

Bu belge bağlayıcıdır. Çakışma durumunda `README.md`, dal içi belgeler ve
sohbet kayıtları yerine **bu belge ve `governance/registry.json` geçerlidir**.

Kurallar prosa olarak kalmaz: `scripts/check_governance.py` her Pull Request'te
koşar ve ihlalde kapıyı kapatır. Yani sözleşmeye uymak gönüllü değil, teknik
olarak zorunludur.

## 1. Otorite

| Konu | Karar sahibi |
|---|---|
| Kanonik kurulum dosyaları, kimlik sözlüğü, birleştirme sırası | **Entegrasyon otoritesi: `kingos352` (K5 şapkası)** |
| Bilimsel yöntem ve kendi modülünün iç tasarımı | İlgili rol sahibi (K1–K4) |
| Veri sözleşmesi şeması (`docs/DATA_CONTRACT.md`) | Entegrasyon otoritesi + ilgili rol birlikte |

Otorite, `.github/CODEOWNERS` ile teknik olarak da tanımlıdır: depodaki her yol
`@kingos352` incelemesinden geçer.

**Rol sahibi kendi alanında serbesttir.** Otorite, modüllerin *arasındaki*
sözleşmeye karışır: kimlikler, birimler, kolon adları, kurulum dosyaları,
birleştirme sırası. Bir rolün bilimsel yöntemine karışmaz.

### İtiraz yolu

Kurala itiraz, kuralı sessizce esnetmek değildir. Sıra şu:

1. İlgili Issue'ya gerekçeyi yaz (ölçüm, kaynak, kırılan senaryo).
2. `docs/DECISIONS.md` içine kendi ADR aralığından yeni satır aç.
3. Otorite onaylarsa `governance/registry.json` ve bu belge aynı PR'da güncellenir.

Kural değişmeden kodun kuralın dışına çıkması, `main`'e giremez.

## 2. Çalışma protokolü

Protokol Issue [#11](https://github.com/kingos352/luna-sight/issues/11) içinde
kararlaştırıldı. O Issue kapandı; kalıcı metin burasıdır.

1. **Başlamadan:** `git fetch --all --prune`, `git status`, `git log --oneline -5`.
2. **Sahiplen:** açık koordinasyon Issue'suna tek satır:
   `SAHIPLEN | <rol> | <dal> | <dosyalar> | <UTC>`
3. **Çakışmadan çalış:** aynı dosyada başka dalın commit'i varsa düzenleme,
   önce koordine et.
4. **Bitir:** test → `git add <dosya>` (asla `git add -A`) → commit → push →
   `BITTI | <rol> | <dal> | <commit>`
5. **Yasak:** `git push --force` (paylaşılan dala), `main`'e doğrudan commit,
   başka rolün dizininde izinsiz değişiklik.

`data/manifest.csv` ve `docs/DECISIONS.md` **yalnızca satır eklenerek**
değiştirilir. Başkasının satırı düzenlenmez, silinmez, yeniden numaralanmaz.

## 3. Kanonik kurulum dosyaları

Tek doğru yer kuralı. Dört dalda dört farklı bağımlılık dosyası, 24 saatlik bir
operasyonda en pahalı hatadır.

| Rol | Dosya | Kural |
|---|---|---|
| Çalışma zamanı bağımlılıkları | `requirements.txt` | Sabit sürüm (`==`). Test/lint paketi giremez. |
| Geliştirme bağımlılıkları | `requirements-dev.txt` | İlk satır `-r requirements.txt`. |
| Araç ayarı | `pyproject.toml` | Yalnızca `[tool.*]`. Paketleme ve bağımlılık listesi yok. |
| Python sürümü | `.python-version` | `3.12` |

**Yasak dosyalar:** `pytest.ini`, `setup.cfg`, `tox.ini`, `Pipfile`,
`poetry.lock`, `environment.yml`, `requirements-<rol>.txt`.

`pytest.ini` özellikle tehlikeli: pytest onu `pyproject.toml` içindeki
`[tool.pytest.ini_options]` bölümünün **önüne** alır, yani kanonik ayar sessizce
devre dışı kalır. Hata vermez, sadece yanlış çalışır.

**Kodlama:** kanonik dosyalar UTF-8. UTF-16 bir bağımlılık dosyası pip
tarafından okunsa bile git diff'inde, kabukta ve denetleyicide satır olarak
görünmez.

### Python 3.12 neden

`numpy`, `rasterio` ve `pyproj` güncel sürümleri `requires-python >= 3.12`
ilan ediyor. Daha eski bir taban bu üçünü eski sürümlere düşürür. Daha yeni bir
taban (3.13+) ise jeo-uzamsal tekerlek kapsamını riske atar. Beyan tek yerde
tutulur: `.python-version`.

## 4. Kimlik sözlüğü

Kayıt: `governance/registry.json`.

- `source_id` ve `model_id`: **küçük harf, kebab-case**. Kayıtlı değer dışında
  bir şey yazılamaz; yeni kaynak kayıt güncellemesiyle eklenir.
- Sentetik kaynaklar `synthetic-` ön ekiyle başlar.
- `quality_flag`, `*_visible` ve `*_reason` değerleri `docs/DATA_CONTRACT.md` ve
  K3 `states.py` sözlüğünden **birebir** alınır (`test_fixture` alt çizgilidir,
  bu kasıtlıdır).

Neden önemli: `jpl_horizons` ile `jpl-horizons` arayüzde iki ayrı kaynak gibi
görünür ve `source_id` üzerinden yapılan her filtre sessizce boş döner.

## 5. Geometri ve zaman

| Alan | Kanonik |
|---|---|
| Zaman | UTC, ISO 8601, zaman dilimi bilgisi zorunlu |
| Açı birimi | derece |
| Boylam | doğu-pozitif, **[-180, 180]** |
| Enlem | [-90, 90] |
| Azimut | kuzeyden saat yönünde, [0, 360] |
| Yükseklik | [-90, 90] |

Boylam aralığı neden [-180, 180]: K2'nin özet JSON'ları, K3'ün ürettiği
`outputs/k3/*_visibility.csv` dosyaları ve K1'in efemeris çıktısı bu aralığı
kullanıyor. Yalnızca `src/luna_sight/terrain/sites.py` kataloğu 0–360 yazıyor.
Hattın tamamını tek dosyaya uydurmak, tek dosyayı hatta uydurmaktan pahalıdır.
Yön değişmiyor, yalnızca sarma noktası sabitleniyor.

## 6. Veri sözleşmesi tablosu

`governance/registry.json → data_contract.required_columns` listesindeki 18
kolon, `site_id` **ve** `timestamp_utc` içeren her CSV çıktısında bulunmalıdır.

- Teşhis kolonları serbesttir: `sun_margin_deg`, `earth_margin_deg`,
  `joint_margin_deg`, `sun_reason`, `earth_reason`, `joint_reason`.
- Ufuk profili (`outputs/k2/*_horizon_*.csv`) ve duyarlılık taraması
  (`outputs/k3/sensitivity.csv`) zaman serisi değildir, bu kurala tabi değildir.
- `parameters` alanı **kompakt JSON nesnesi** olur. K3'ün mevcut
  `key=value;...` çıktıları yeniden üretilene kadar uyarı olarak raporlanır,
  kapıyı kapatmaz.

## 7. ADR numaralandırma

Aynı numaranın iki farklı kararı göstermesi yaşandı: ADR-003 hem K1'in Python
kararı hem K2'nin ufuk kararıydı; ADR-004 hem K3'ün iki farklı kararı hem de
K1'in pandera önerisi olarak anıldı. Numara çakışması artık yapısal olarak
engellenir.

| Rol | Aralık |
|---|---|
| Ortak / devralınan | ADR-001 … ADR-099 |
| K1 | ADR-100 … ADR-199 |
| K2 | ADR-200 … ADR-299 |
| K3 | ADR-300 … ADR-399 |
| K4 | ADR-400 … ADR-499 |
| K5 | ADR-500 … ADR-599 |

Mevcut ADR-001 … ADR-006 devralınmıştır, olduğu gibi kalır:

| ID | Karar | Sahip |
|---|---|---|
| ADR-001 | Python + Streamlit | K5 |
| ADR-002 | UTC ve doğu-pozitif boylam | K1/K2 |
| ADR-003 | LOLA ufuk profili yöntemi | K2 |
| ADR-004 | Görünürlük durumu metin, boolean değil | K3 |
| ADR-005 | Python 3.12 ve tek ortak `requirements.txt` | K1 |
| ADR-006 | ÖNERİ: veri sözleşmesini pandera ile zorla | K1 |

ADR-006 **onaylanmadı**. Onaylanana kadar `pandera` kanonik
`requirements.txt` içinde etkin satır olarak bulunamaz.

## 8. Birleştirme treni

#10 (`k1/dev-environment`) `main`'e alındı: kanonik kurulum dosyaları, CI test
kapısı ve K1 efemeris modülü artık `main` üzerinde. Kalan sıra bağlayıcıdır:

1. **#20 `k1/dev-environment`** → `main` — #10 birleştikten sonra gelen iki K1
   commit'i: onaysız `pandera` satırının çıkarılması ve K3 efemeris sağlayıcısı.
   **Önce bu girer:** `main` şu an `DEP-04` ihlali taşıyor ve bu düzelmeden
   denetleyici hiçbir dalda yeşile dönemez.
2. **#19 `k5/integration-contract`** → `main` — sözleşme, kayıt defteri ve
   denetleyici. Yalnızca yeni dosya ekler, hiçbir dalla çakışmaz.
3. **#6 `k2/lola-horizon`** → `main` — K2 arazi + K3 görünürlük.
4. **#8 `k4/dev-environment`** → `main` — arayüz.

Her adımda bir sonraki dal `main` ile güncellenir ve denetleyici yeşile dönene
kadar birleşmez. Sıra dışına çıkmak isteyen rol, koordinasyon Issue'sunda
gerekçe yazar.

Sıranın gerekçesi: #6 ve #8 ile `main` arasındaki çakışma yüzeyi büyük
(`requirements.txt`, `requirements-dev.txt`, `pytest.ini`,
`src/luna_sight/__init__.py`, `data/manifest.csv`, `docs/DECISIONS.md`,
`README.md`). Kapı önce ayağa kalkmazsa bu çakışmalar elle ve her seferinde
yeniden çözülür.

#7 (`k3/visibility-engine`) kapatılır: #16 onun tam üst kümesidir ve
`k2/lola-horizon` içine birleşti. Aynı kodu ikinci kez incelemek zaman kaybıdır.

## 9. Denetleyici

```bash
.venv\Scripts\python.exe scripts/check_governance.py
```

Çıkış kodu 0 = sözleşme korunuyor. Kural kodları: `PY-01/02` sürüm,
`ENC-01` kodlama, `DEP-01…04` kurulum dosyaları, `ADR-01/02` karar kaydı,
`ID-01/02` kimlik sözlüğü, `GEO-01` kaynak kodda boylam aralığı,
`GEO-02` çıktı JSON'larında boylam aralığı, `OUT-01/02` çıktı şeması,
`OUT-03` bozuk JSON.

`GEO-01` yalnızca `.py` dosyalarını tarar. Boylam üretilmiş özet
dosyalarına da yazılır; kaynak kod düzeltilip çıktı yeniden üretilmezse
tutarsızlık görünmez kalır. `GEO-02` bu boşluğu kapatır ve `outputs/**/*.json`
içindeki `lon_deg_east` / `longitude_deg_east` değerlerini doğrular.

Denetleyici standart kütüphaneyle çalışır; bağımlılık kurulmadan da koşar.
Kurulum dosyası bulunmayan bir dalda ilgili kurallar atlanır, böylece boş
`main` üzerinde de geçer.

## 10. Dal koruması

Kapının bağlayıcı olması, iş akışının koşmasına değil **zorunlu kontrol**
listesine bağlıdır. Koşan ama zorunlu olmayan bir kontrol, kırmızıyken
birleşmeyi engellemez; yalnızca kırmızı bir ikon gösterir.

`main` üzerinde zorunlu dört kontrol (ADR-500):

| Kontrol | Ne doğrular |
|---|---|
| `structure` | Zorunlu işbirliği dosyaları, gizli dosya ve 20 MB üstü dosya taraması |
| `Kanonik sözleşme` | Bu belgedeki kurallar (`scripts/check_governance.py`) |
| `ubuntu-latest / Python 3.12` | `pip check`, `ruff`, `pytest`, kapsam — Linux |
| `windows-latest / Python 3.12` | Aynı adımlar — Windows |

Diğer ayarlar:

- `strict: true` — dal `main` ile güncel değilse birleşmez. Bu yüzden
  birleştirme treninde her vagon sırası gelince `git merge origin/main` yapar.
- 1 onay + CODEOWNERS incelemesi zorunlu, eski onaylar yeni push'ta düşer.
- `allow_force_pushes: false`, `allow_deletions: false`.
- `enforce_admins: false` — entegrasyon otoritesi kendi PR'ını onaylayamadığı
  için birleştirme yönetici atlamasıyla yapılır. Atlama **kontrolleri
  atlamak değildir**: dört kontrol yeşil olmadan hiçbir dal birleştirilmez,
  bu kural otorite için de geçerlidir.

Zorunlu kontrol listesi değişirse bu bölüm ve `docs/DECISIONS.md` aynı PR'da
güncellenir.
