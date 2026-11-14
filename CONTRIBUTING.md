# Katkı kuralları

## Tek iş, tek dal

- Dal biçimi: `k1/horizons-parser`, `k2/lola-horizon`, `k3/visibility-engine`, `k4/compare-ui`, `k5/integration`.
- Her dal tek bir somut Issue'yu çözer.
- `main` dalına doğrudan geliştirme yapılmaz.
- Değişiklikler küçük tutulur; mümkünse 300 satırın altında kalır.

## Pull Request kabul kapısı

- İlgili Issue bağlantısı bulunur.
- Veri sözleşmesi korunur veya sözleşme değişikliği ayrıca açıklanır.
- Bilimsel sonuç için kaynak, parametre ve doğrulama kanıtı eklenir.
- Test verisi `test_fixture` olarak etiketlenir.
- Birim, koordinat yönü ve UTC standardı kontrol edilir.
- En az bir ekip üyesi inceleme yapar; bilimsel çekirdekte K1-K3 içinden ilgili sahip inceler.
- Ana akış yerelde çalıştırılır.

## Birleştirme

K5, kontroller tamamlandığında squash merge uygular. Başlık kısa ve sonuç odaklı yazılır. Acil demo düzeltmesi de Pull Request üzerinden ilerler; gerekçe açıklamaya eklenir.

## Commit biçimi

`tür(alan): kısa açıklama`

Örnekler:

- `feat(ephemeris): Horizons zaman serisini ayrıştır`
- `fix(horizon): doğu-pozitif boylam dönüşümünü düzelt`
- `test(visibility): eksik veri durumunu doğrula`
- `docs(method): LOLA ürün kaydını ekle`

