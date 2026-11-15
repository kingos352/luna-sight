# LUNA SIGHT 3B görünüm ve LunarSight AI

Bu kaynaklar ana Streamlit uygulamasındaki mevcut 3B küreyi ve LunarSight AI
penceresini üretir. Python sunucusu, görüntü hazırlama ve gerçek model
çağrıları için `luna_sight.ai.component` köprüsünü kullanır.

```powershell
cd frontend
npm ci
npm run build
cd ..
.venv\Scripts\python.exe -m streamlit run app\app.py
```

Derleme `app/components/lunar/` altına yazılır. `app/static/moon/` içindeki
ortak `data/` ve `textures/` dosyaları okunur ve değiştirilmez. Böylece eski
bağımsız küre paketinin kopyalanması AI köprüsünü ezmez. Yalnızca artık
kullanılmayan bu bileşene ait derlenmiş index varlıkları
temizlenir. Anahtar yalnızca proje kökündeki `.env` dosyasındadır; Vite
ortam değişkenlerine veya tarayıcıya eklenmez.

Ana uygulama açıkken `frontend/` içinde:

```powershell
npx playwright test
$env:LUNA_LIVE_AI = "1"
npx playwright test -g "live model"
```

Normal tarayıcı testleri çıkarım yapmaz. İkinci komut gerçek API çağrısı
yapar. Varsayılan test adresi `http://127.0.0.1:8511`; farklı adres için
`LUNA_APP_URL` kullanın. Testler kurulu Microsoft Edge ile çalışır.

Tespit ve noktalama, modelin verdiği yaklaşık görüntü konumlarını gösterir.
Model konum vermezse işaret oluşturulmaz. Bunlar fiziksel ölçüm veya
iniş güvenliği değerlendirmesi değildir. Ayrıntılar: `docs/AI_SURFACE_ANALYSIS.md`.
