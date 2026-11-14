# LUNA SIGHT

Ay'ın güney kutbundaki aday iniş bölgelerini ve görev tarihlerini; Güneş ile Dünya'nın yerel ufka göre konumları üzerinden karşılaştıran NASA Space Apps prototipi.

## 24 saatlik çalışma hedefi

- Gerçek ve izlenebilir JPL Horizons verisi
- En az iki aday bölgenin karşılaştırılması
- Güneş ve Dünya için azimut, yükseklik ve görünürlük zaman çizelgesi
- En az bir referans noktada LRO/LOLA tabanlı topoğrafik ufuk
- Kaynak, varsayım, kalite durumu ve bilimsel sınırların görünür sunumu

## Hızlı başlangıç

1. `docs/TEAM_PLAYBOOK.md` içindeki rolünüzü ve ilk tesliminizi okuyun.
2. `docs/DATA_CONTRACT.md` veri sözleşmesini değiştirmeden kullanın.
3. Görevinizi GitHub Issue olarak açın veya atanmış Issue'yu alın.
4. `k1/...`, `k2/...`, `k3/...`, `k4/...`, `k5/...` biçiminde kısa bir dal açın.
5. Küçük ve çalışan bir değişiklik gönderin; Pull Request şablonunu doldurun.

## K3 görünürlük motoru

K2 ufuk profili + K1 efemeris serisinden `visible` / `blocked` / `uncertain`
durumları, gerekçe kodları ve kesintisiz pencereler üretir. Yöntem ve bilimsel
sınırlar: `docs/K3_VISIBILITY.md`.

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m luna_sight.visibility `
  --profile outputs\k2\Site04_horizon_4000m.csv `
  --site-id Site04 --latitude -89.766811 --longitude -171.869898 `
  --hours 168 --csv outputs\k3\Site04_rover_visibility.csv
```

## Depo haritası

```text
app/                 Kullanıcı arayüzü
src/luna_sight/      Bilimsel ve teknik modüller
tests/               Otomatik doğrulamalar
data/                Yalnızca küçük manifestler ve örnek şemalar
docs/                Yöntem, kararlar, çalışma kuralları
artifacts/           Demo ve teslim manifestleri
outputs/             Ekip uygulama planı ve K2 ufuk profilleri
```

NASA veri dosyaları, DEM parçaları, videolar ve önbellekler Git deposuna eklenmez. Kaynak adresi, sürüm, parametre ve dosya özeti `data/manifest.csv` içinde tutulur.

