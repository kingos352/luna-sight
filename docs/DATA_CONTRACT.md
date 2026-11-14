# Ortak veri sözleşmesi

## Temel standartlar

- Zaman: UTC, ISO 8601
- Enlem ve boylam: ondalık derece; boylam doğu-pozitif
- Açılar: derece
- Varsayılan tarama: 5 dakika
- Varsayılan analiz: 168 saat
- Görünürlük: `visible`, `blocked`, `uncertain`
- Kalite: `valid`, `partial`, `missing`, `test_fixture`

## Zorunlu alanlar

```text
site_id
latitude_deg
longitude_deg_east
timestamp_utc
sun_az_deg
sun_alt_deg
earth_az_deg
earth_alt_deg
terrain_horizon_sun_deg
terrain_horizon_earth_deg
sun_visible
earth_visible
joint_visible
quality_flag
source_id
source_version
model_id
parameters
```

Eksik veri görünür veya engelli sınıfına çevrilmez. Test verileri kullanıcı arayüzünde ve çıktılarda açıkça işaretlenir.

