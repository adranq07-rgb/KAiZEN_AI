# Kaizen-1 alt sistemleri — 1 Ekim 2026

Kaizen-1 dışında yeni mimari yok. Muhasebe doğruluğunun otoritesi hâlâ kesin araçlar ve Evidence / Consensus / FactRegistry. Haricî servis cevapları bu otoriteye dönüşmez.

## Kullanım ve sınırlar

- Scrapling, mevcut Research Engine içindeki SafeFetcher güvenlik kontrollerinin arkasında HTTP taşıma ve metin çıkarımı yapar. Tarayıcı açmaz. Robots/401/403/429 engelleri aşılmaz; yönlendirmeler her adımda denetlenir; 5 MB üst sınırı, sınırlı süre ve bir taşıma denemesi vardır. Arızada mevcut okuyucu devreye girer. Trace: scrapling_attempted, scrapling_success, scrapling_latency_ms, scrapling_fallback_used.
- Invisible Playwright MCP, Codex eklentisidir: geliştirme/UAT için açıkça seçilir. Kaizen üretim otomatik tarayıcı yolu DISABLED. MCP el sıkışması, gerçek sayfa okuma, yapılandırılmış sonuç ve kapanış doğrulandı. Mevcut sohbetin araç listesi yeni eklentiyi henüz taşımıyor; Codex eklenti araçlarını yenilemek/yeni oturum gerekir.
- Manus ve Documenso mevcut ToolManager'a kayıtlıdır. Kurulumda ağ çağrısı yapılmaz. `durum` komutu bağımlılık durumlarını gösterir. Araçlar `engine.tool_manager.run_tool(...)` ile açıkça çağrılır; otomatik muhasebe yönlendirmesi yoktur.
- Manus: manus_health, manus_create_task, manus_status, manus_poll, manus_result, manus_follow_up. Oluşturma ve devam mesajı için `approved=True` şarttır. Kimlik: MANUS_API_KEY. Resmî v2 API; özel görev; en çok 60 saniye/12 sorgu polling; bekleyen kullanıcı onayı otomatik kabul edilmez. Arka plan iş durumu bilinmiyorsa tamamlandı sayılmaz. Sonuç ve işlem Trace'i çağırana döner; `tool_manager.last_trace` içerik veya anahtar saklamaz.
- Documenso: documenso_health, documenso_create_draft, documenso_status. DOCUMENSO_BASE_URL ve DOCUMENSO_API_KEY yalnız ortamdan okunur. Onaylanmış PDF en çok 10 MB; `approved=True` zorunlu. Yalnız taslak oluşturulur; alıcı ekleme, gönderme veya imza endpoint'i yoktur. Dönen metadata alıcı/imza tokenlarını içermez.
- Coolify sunucusu Windows'a kurulmadı; aşağıdaki taşınabilir Docker paketi hazırdır. Yerel masaüstü Coolify'dan bağımsızdır.
- codex-chatgpt-web 6.1.3: üçüncü taraf, OpenAI destekli değil. Resmî kurucu checksum doğrulandı. SAFE_TO_INSTALL kararı yalnız Browser-only başlatıcı içindir. Full Harness, Allow All, otomatik onay, tünel veya model yönlendirme değişikliği etkinleştirilmedi; tarayıcı oturumu kopyalanmadı. Başlatıcı ve CLI açılır. Doctor: `config / error / Configuration is invalid` — ilk hesap girişi ve Browser-only kurulum tamamlanmadığından gerçek ChatGPT smoke doğrulanmadı. Kullanıcı başlatıcıda giriş yaptıktan sonra bu kurulum tamamlanabilir.

## Coolify / Docker

Dockerfile ve compose.yaml kullanılır. `/health` model veya haricî servise gitmez. `/ask`, KAIZEN_API_TOKEN ile Bearer kimlik doğrulaması ister; token yoksa kapalıdır. Genel yönetim/dosya ve haricî işlem araçları HTTP üzerinden açılmaz. Coolify'da bu portu TLS proxy arkasına bağlayın; doğrudan internete açmayın.

Ortam değişkenleri:
- KAIZEN_API_TOKEN: dağıtım platformunun gizli değişkeni; örnek değer koda yazılmaz.
- KAIZEN_PROVIDER: varsayılan offline; mevcut Ollama için local.
- KAIZEN_OLLAMA_URL: varsayılan http://host.docker.internal:11434.
- KAIZEN_HYBRID: varsayılan false; BGE hazırsa true.
- KAIZEN_SEARXNG_URL: varsayılan http://host.docker.internal:8890.
- KAIZEN_DATA_DIR / KAIZEN_LOG_DIR: konteynerde /var/lib/kaizen/data ve /var/lib/kaizen/logs.

Compose iki kalıcı volume kullanır. Eski göreli data/logs yolları aynı kalıcı dizinlere bağlanır. İmaj allowlist ile oluşturulur; veritabanları, .env, loglar, artifacts ve kullanıcı tarayıcı profilleri dahil edilmez. OCR sistem motorları bu hafif imajda kurulu değildir; yerel Kaizen OCR kurulumu değişmez. Docker Desktop özel host gateway'si yerel model adresi olarak kabul edilir; diğer uzak modeller bulut kapalıyken engellenmeye devam eder.

Gerçek yerel Docker build, health, iki muhasebe sorusu, Ollama /api/tags ve SearXNG HTTP bağlantısı geçti. Test konteyneri durduruldu; yalnız test verisi içeren kaizen-subsystems-smoke-data volume korunur. Dış Coolify hostu verilmediği için uzak dağıtım yapılmadı.

## Kanıt ve sınırlar

Ham çalışma kayıtları: artifacts/subsystems_20261001/. Anahtarlar kayıtlara yazılmaz.

- research_smoke.json: gerçek SearXNG -> 7 başarılı sayfa -> Evidence -> karar. Arama kısmen bozulmuş ve uzlaşma yok: Kaizen güncel oran vermeyi reddetti. Bu başarılı doğrulanmış mevzuat cevabı olarak raporlanmaz.
- scrapling_fallback.json: Scrapling taşıması kontrollü bozuldu, eski okuyucu gerçek sayfayı aldı.
- browser_smoke.json: gerçek MCP tarayıcı akışı; kapandıktan sonra browser_list boş.
- gpu_smoke.json: yeni donanımdaki tek generation, tek soğuk ve önbellekli sıcak BGE sorgusu; nvidia-smi örnekleri, Ollama size_vram, sıralama ve aşağı akış tüketicisi.
- core_integrated.json: normal Kaizen girişinde muhasebe sonuçları, gecikme ve Trace; core_baseline.json yalnız yeni araç kaydı olmadan tek başlangıç gözlemi. İki ölçüm istatistiksel hız iddiası değildir.
- docker_smoke.json: yerel dağıtım sağlık ve çalışma kanıtları.
- final_regression.json: önceki kabul edilmiş aktif ana test manifesti + yeni tests.run_all modülü; kullanıcının isteğiyle adı Cognee içeren dört test atlanır. Gerçek Cognee veya önceki pahalı BGE testi tekrarlanmaz.

Manus/Documenso testleri kimliksiz güvenli dönüş ve resmî API sözleşmesi testleridir; canlı görev veya imza iş akışı PASS iddiası değildir.

Resmî kaynaklar: https://open.manus.im/docs/v2/task.detail ; https://app.documenso.com/api/v2/openapi.json ; https://github.com/feder-cr/invisible_playwright_mcp ; https://github.com/miuuyy/codex-chatgpt-web/blob/main/docs/security-model.md

Son ana regresyon: 342 PASS / 0 FAIL / 4 SKIPPED; 117,754 saniye. graphify update . denendi fakat araç -1073741819 (0xC0000005) ile kapandı; grafik güncellemesi doğrulanamadı. Bu görevde araç onarımı yapılmadı.
