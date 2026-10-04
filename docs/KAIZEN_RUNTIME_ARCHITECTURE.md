# KAIZEN RUNTIME ARCHITECTURE — Gerçek Koddan Çıkarılmış Mimari Harita

> **Kaynak:** Bu belge KAIZEN — BÜYÜK İŞ EMRİ #2, madde 2'nin gereğidir. Roadmap raporuna
> (`KAIZEN_HEDEF_VE_YOL_HARITASI.md`) körü körüne güvenilmeden, doğrudan repository'nin
> gerçek kod durumu okunarak (2026-09-23 tarihli tam denetim) üretilmiştir. Her iddia
> `dosya:satır` referansı taşır; referanssız hiçbir iddia yoktur.
>
> **Denetim yöntemi:** beş bağımsız, salt-okunur alt-denetim (Search, Core/Decision/
> Provider/Commands, Accounting, Memory/Learning, Providers/Hermes/Misc) + bu belgeyi
> yazan oturumun doğrudan `Read`/`Grep`/`Bash` kontrolleri. Baseline test koşumu
> (`python3 -m tests.run_all`) bu denetimle **aynı gün** çalıştırıldı: tüm testler
> BAŞARILI, 33 soruluk gerçek hayat sınavı 15/33 (18 bilinen darboğaz — önceki fazla
> birebir aynı), red-team (düzeltilmiş) 96.2% — hiçbiri bu denetimle çelişmiyor.

---

## 1. Üst Düzey Giriş Noktaları

| Giriş noktası | Ne yapar | Kanıt |
|---|---|---|
| `main.py` | CLI REPL: `KaizenEngine()`'i argümansız kurar, stdin'den okur, `"cikis"` yazılana kadar `Kaizen.cevap_ver(mesaj)` çağırır, hatayı `Kaizen.logger.error` ile loglar | `main.py:11,16-38` |
| `desktop_app.py` | tkinter masaüstü uygulaması; **aynı** `core.engine.KaizenEngine`'i doğrudan sarar, ayrı bir iş mantığı YOKTUR | `desktop_app.py` (Faz E-J, önceki denetim) |

Her iki giriş noktası da aynı tek gerçek motora (`core/engine.py::KaizenEngine`) bağlanır —
iki ayrı "beyin" yoktur.

---

## 2. `KaizenEngine.__init__` — Bileşenlerin Kuruluşu

`core/engine.py`'de (satır 1-107 civarı) kurulan bileşenler ve bağlantıları:

1. `ConfigManager` (`config/config_manager.py`) — `config/Kaizen.json`'ı okur.
2. `KaizenLogger` — `logs/kaizen.log`.
3. **Provider zinciri**: `build_provider(self.config)` (`core/ai/provider_factory.py:23-33`)
   çağrılır — `model.provider` (varsayılan `"hermes"`) + `model.fallback`
   (varsayılan `["offline"]`) okunur, `FallbackProvider(chain)` ile sarılır. **Bugünkü
   gerçek üretim zinciri: `HermesProvider → OfflineProvider`.** (`core/engine.py:14,81`;
   `config/Kaizen.json`'da `model.provider="hermes"`, `model.fallback=["offline"]`).
4. `LearningStore` (`memory/learning_store.py`) — kalıcı SQLite hafıza
   (`data/kaizen_learning.sqlite3`) — `core/engine.py:5,50`.
5. `SiteStore`, `FactRegistry` (`accounting/facts.py`), `KnowledgeCardStore`
   (`memory/knowledge_cards.py`, aynı sqlite dosyası farklı tablolar) — `core/engine.py:7,62`.
6. `AccountingAgent` — muhasebe alanı yönlendiricisi (araçlar + araştırmacı).
7. `ToolManager` + `SecurityManager` — dosya/araç işlemleri için onay kapısı
   (`tools/tool_manager.py:1-58`, `security/security_manager.py:1-21`).
8. `MemoryManager` (`memory/memory_manager.py`, basit JSON key-value) — kurulur
   (`core/engine.py:4,43`) **ama `BrainManager`'a hiç geçirilmez** — yalnız kısmen/marjinal
   kullanımda, üretim cevap zincirinin parçası değil.
9. `PrincipleRegistry` + `PrincipleRetriever` (`memory/principle_registry.py`,
   `learning/principle_retriever.py`) — Faz C (önceki iş emri) ile kuruldu, config
   bayrağı (`config_manager.learning_brain_enabled()`, varsayılan `False`) ile
   `KaizenBrain`'e geçirilir (`core/engine.py:96`).
10. `KaizenBrain` — yukarıdaki tüm parçalar + `learning_brain_enabled` bayrağı ile kurulur;
    kendi içinde `BrainManager`'ı da (dışarıdan verilmezse) kurar
    (`core/kaizen_brain.py:45,85`).

**`core/decision.py::DecisionEngine` bu kuruluşun hiçbir yerinde YOKTUR** — `engine.py`'nin
tam import listesinde `core.decision` geçmez, `__init__` içinde hiçbir yerde
`DecisionEngine(...)` çağrısı yoktur. (Bkz. §5.)

**`search/` paketinden HİÇBİR ŞEY bu kuruluşta YOKTUR** — `engine.py` `search` paketini
hiç import etmez. (Bkz. §6.)

---

## 3. Cevap Zinciri — `KaizenBrain.answer()` / `_answer_core()`

Metin komutları (`durum`, `kaynaklar`, `onayla:` vb.) `core/commands.py::CommandHandler`
tarafından `KaizenBrain`'e hiç uğramadan doğrudan işlenir (bkz. §7). Aşağıdaki zincir,
komut olmayan asıl "soru" mesajları içindir.

```
KULLANICI MESAJI
   │
   ├─ 1. düzeltme (correction) tespiti ─────────────────────────► VERIFIED (kullanıcı düzeltmesi)
   │
   ├─ 2. aritmetik/matematik ────────────────────────────────────► VERIFIED (hesap motoru)
   │
   ├─ 3. kesin araçlar (chart_of_accounts / journal / calculators) ► VERIFIED
   │        kaynak: accounting/chart_of_accounts.py, journal.py, calculators.py
   │        internet/model KULLANILMAZ — saf deterministik kod
   │
   ├─ 4. verified_fact_answer() ──────────────────────────────────► VERIFIED (facts.answer status=="verified")
   │        kaynak: accounting/facts.py::FactRegistry + accounting/consensus.py::AccountingConsensus
   │        kural: tek kaynak yeter YALNIZ priority==1 (resmî) ise; aksi halde ≥2 FARKLI
   │        kayıtlı source.name gerekir (aynı domain'den 2 sonuç TEK sayılır — bağımsızlık
   │        kontrolü VAR, consensus.py satır 79-111)
   │        internet KULLANILMAZ — yalnız önceden toplanmış/süzülmüş facts_registry okunur
   │
   ├─ 5. classify() alan yönlendirmesi
   │     │
   │     ├─ GENEL alan → provider.ask() doğrudan ─────────────────► FOUND/UNKNOWN (model serbest, doğrulamasız)
   │     │
   │     ├─ MUHASEBE/SGK alanı
   │     │     │
   │     │     ├─ 5a. _from_memory() — BrainManager.gather_evidence + Retriever ─► SUPPORTED
   │     │     │        kaynak: accounting/retriever.py (yerel öğrenilmiş bilgi/knowledge_store)
   │     │     │        eşik: 0.6 coverage; learning_brain_enabled=true ise
   │     │     │        _maybe_augment_with_principle() (yalnız HIGH/MEDIUM principle
   │     │     │        confidence'ta, "ilke ipucu" olarak prompt'a eklenir — ASLA VERIFIED
   │     │     │        üretmez, ASLA kesin araç/fact/correction rotasına dokunmaz)
   │     │     │        internet KULLANILMAZ
   │     │     │
   │     │     └─ 5b. yetersiz kanıt → accounting_agent araştırma
   │     │              kaynak: accounting/researcher.py::AccountingResearcher.research()
   │     │              1) önce AccountingKnowledgeStore önbelleği (yerel, internet yok)
   │     │              2) yoksa provider.research_packet(prompt) çağrılır
   │     │                 → HermesProvider → core/hermes_bridge.py → subprocess
   │     │                   ["hermes","chat","-q",...,"-t","web","--format","stream-json"]
   │     │                 → _parse_research_packet() web_extract tool-call sonuçlarını
   │     │                   "kaynak" (URL+domain) olarak çıkarır, derin araştırmada
   │     │                   (trusted_only=False) FARKLI HOSTNAME sayısı ≥2 bağımsızlık
   │     │                   kontrolü yapar (hermes_bridge.py:184)
   │     │              **BURASI BUGÜN KAIZEN'İN TEK CANLI İNTERNET ERİŞİM YOLU** —
   │     │              `search/` paketi (SearXNG) BU ZİNCİRDE HİÇ YOK.
   │     │              `accounting/crawler.py`'nin kendi güvenli fetcher'ı da BU CANLI
   │     │              yolda YOK — yalnız offline `güncelle` toplu işinde kullanılıyor.
   │     │              sonuç: SUPPORTED (kanıt yeterliyse) veya bulunamadı
   │     │
   │     └─ OFİS alanı → refuse ────────────────────────────────────► REFUSAL
   │              _refusal_with_experience(): BrainManager.recall_experience() ile
   │              Cognee'den geçmiş deneyim ipucu aranır (8sn timeout, bloklamaz),
   │              bulunursa YANITA HER ZAMAN "NOT (doğrulanmamış, ... deneyim hafızasından)"
   │              etiketiyle eklenir — ASLA doğrudan cevap gibi sunulmaz
   │              (kaizen_brain.py:465-479)
   │
   └─ 6. provider fallback (son çare) ──────────────────────────────► FOUND/UNKNOWN
```

**Her başarılı (boş/refusal olmayan) cevaptan SONRA:**
`self.brain.remember_experience(soru, cevap)` çağrılır (`kaizen_brain.py:359-360`) —
arka planda, sınırlı kuyruklu (maxsize 20, 2 worker), Cognee'ye yazar. Bu YALNIZCA
deneyim/tekrar-çağırma hafızasıdır; hiçbir zaman FACT/VERIFIED seviyesine çıkmaz
(`memory/brain_manager.py:332-333` docstring'i bunu açıkça söylüyor).

### Güven modeli (`core/trace.py::KaizenTrace`)

`FOUND / SUPPORTED / VERIFIED / PENDING / CONFLICTED / UNKNOWN` + `ROUTE_CONFIDENCE`
eşlemesi + `REFUSAL_*` sabitleri + (önceki fazdan) `principle_*` alanları. **Araştırma/
kanıt/consensus/reflection/experience alanları YOKTUR** — İş Emri #2 madde 47'nin
istediği "Trace v2" henüz yazılmadı, bu denetimle doğrulandı.

---

## 4. Bağlı/Bağlı Değil Matrisi (İş Emri #2 madde 3)

| Bileşen | Var mı | Testli mi | KaizenBrain'e bağlı mı | Production'da aktif mi | Kanıt |
|---|---|---|---|---|---|
| `search/provider.py::SearchProvider` (Protocol) | ✅ | ✅ (mock, 19 test) | ❌ | ❌ | `search/provider.py:242-254`; repo genelinde `from search`/`import search` sıfır üretim hit'i |
| `search/searxng_provider.py::SearXNGProvider` | ✅ | ✅ (mock, 29 test, 613 satır) | ❌ | ❌ | kendi docstring'i: "HENÜZ KaizenBrain'e bağlı DEĞİLDİR" (searxng_provider.py:3-6) |
| Search Resilience (retry/backoff/cooldown/health) | ✅ (gerçek: max_attempts=3, cooldown=30s, unavailable@3 fail) | ✅ | ❌ | ❌ | searxng_provider.py:189-336 |
| Gerçek SearXNG smoke test (repo içi) | ❌ | — | — | — | yalnız manuel/panel-tabanlı, repo'da otomatik test yok |
| `accounting/crawler.py` (Safe Fetcher — robots/rate-limit/size/timeout) | ✅ | ✅ | ⚠️ yalnız offline `güncelle` batch job'ı üzerinden | ⚠️ kısmi (canlı soru yolunda DEĞİL) | crawler.py; `researcher.py`'de import edilmiyor |
| `accounting/researcher.py` (canlı araştırma) | ✅ | ✅ | ✅ | ✅ | kaizen_brain.py araştırma dalı |
| Hermes `web_search`/`web_extract` (canlı internet erişimi) | ✅ | ✅ | ✅ (researcher.py üzerinden) | ✅ | hermes_bridge.py:282-346 |
| `accounting/source_registry.py` (kaynak otoritesi) | ✅ (16 domain, resmî: yalnız 3) | ✅ | ✅ | ✅ | consensus.py + crawler.py tarafından kullanılıyor; **SGK/Resmî Gazete/mevzuat.gov.tr eksik** |
| `accounting/consensus.py` (uzlaşı + bağımsızlık kontrolü) | ✅ | ✅ | ✅ | ✅ | consensus.py:79-111, domain-bazlı dedup VAR |
| `accounting/facts.py::FactRegistry` | ✅ | ✅ | ✅ | ✅ | kesin araçlardan sonra ikinci VERIFIED kaynağı |
| `accounting/document_verifier.py` | ✅ (deterministik, LLM yok) | ✅ | ✅ (`doğrula:` komutu) | ✅ | document_verifier.py:23-60 |
| `core/decision.py::DecisionEngine` | ✅ | ✅ (kontrat testleri) | ❌ | ❌ | sıfır üretim çağrısı; kendi docstring'i itiraf ediyor |
| `core/provider_factory.py` | ✅ | ✅ | ✅ | ✅ | engine.py:14,81 |
| `core/commands.py` | ✅ | ✅ | N/A (KaizenBrain'i çevreler) | ✅ | 12 komut, hepsi gerçek backend'e bağlı |
| `memory/brain_manager.py::BrainManager` | ✅ | ✅ | ✅ | ✅ | kaizen_brain.py:45,85 |
| `memory/learning_store.py::LearningStore` | ✅ | ✅ | ✅ | ✅ | engine.py:5,50 |
| `memory/knowledge_cards.py::KnowledgeCardStore` | ✅ | ✅ | ✅ | ✅ | engine.py:7,62 |
| `memory/cognee_memory.py::CogneeMemory` | ✅ | ✅ | ✅ (her cevaptan sonra + refusal'da) | ✅ (config `memory.cognee.enabled=true`) | kaizen_brain.py:359-360,465-479; asla VERIFIED sunulmuyor |
| `memory/memory_manager.py::MemoryManager` | ✅ | ⚠️ | ❌ (BrainManager'a geçirilmiyor) | ⚠️ marjinal | engine.py:4,43 |
| `memory/experience_store.py::ExperienceStore` | ✅ | ✅ (test-only) | ❌ | ❌ | sıfır üretim çağrısı (yeni bulgu — iş emrinde adı geçmiyordu) |
| `learning/principle_registry.py`, `principle_retriever.py`, `trace_bridge.py`, `problem_structure.py` | ✅ | ✅ | ✅ **ama config bayrağı arkasında** | ⚠️ varsayılan KAPALI (`learning.learning_brain_enabled=false`) | kaizen_brain.py `_maybe_augment_with_principle()` |
| `learning/experience_model.py::Experience` | ✅ | ✅ (9 test) | ❌ | ❌ | AST-guard testle kendi kendini doğruluyor (D4) |
| `learning/reflection_store.py::ReflectionStore` | ✅ | ✅ | ❌ | ❌ | aynı |
| `learning/decision_bridge.py` | ✅ | ✅ (test-only) | ❌ | ❌ | kendi docstring'i: "_answer_core'a HİÇ bağlanmaz" |
| Cognee (dış paket, timeout/queue/stats) | ✅ | ✅ | ✅ | ✅ | maxsize=20 kuyruk, 2 worker, 8s recall timeout — 2026-09-23 tarihli düzeltmeyle sağlamlaştırıldı |
| `models/model_manager.py`, `models/base_model.py` | ✅ | ❌ (görünür test yok) | ❌ | ❌ | `core/ai/provider_factory.py` gerçek zinciri kuruyor, bu ikisi kullanılmıyor — **muhtemel eski/yinelenen kod, ayrı temizlik gerektirir** |
| `security/security_manager.py::SecurityManager` | ✅ | ✅ | N/A (ToolManager üzerinden) | ✅ | sabit 5 eylemlik onay listesi; genel SSRF/URL-güvenliği YOK |
| `temp_ddgs_check.py` | ✅ (dosya var) | ❌ | ❌ | ❌ | tek seferlik `ddgs` pip kontrolü, tamamen ölü/öksüz kod |

---

## 5. `core/decision.py` — Gerçek mi, Gözlemsel mi? (madde 32'nin cevabı)

**Sonuç: ne gerçek planlayıcı ne de gözlemsel — tamamen izole/ölü.** `DecisionEngine.decide()`
`Decision` nesnesi üretir ama bu nesne hiçbir üretim dosyasında (`engine.py`,
`kaizen_brain.py`, `commands.py`, `main.py`) okunmaz, atanmaz, loglanmaz bile. Tek
tüketicileri kendi kontrat testleri ve — yalnızca alan uyumluluğu kanıtlamak için var olan,
kendisi de üretime bağlı olmayan — `learning/decision_bridge.py`'dir. Modülün kendi
docstring'i (`decision.py:4-9`) bunu zaten itiraf ediyor: "HENÜZ `KaizenBrain`'e
bağlanmadı." Bu, gelecekteki `needs_research`/`needs_exact_tool`/`needs_fact`/
`needs_memory` bayrakları için (madde 32) sıfırdan başlanacağı anlamına gelir — repo'da
bu dört isim hiç geçmiyor (grep doğrulandı).

---

## 6. Search ≠ Evidence ≠ Fact — Bugünkü Durumun Netliği

İş Emri #2'nin madde 13'ü şunu vurguluyor: "Arama sonucu (title/URL/snippet) henüz kanıt
değildir." Bugünkü kod bu ayrımı **kısmen** zaten yapıyor ama tutarsız iki yoldan:

1. **`accounting/facts.py` + `consensus.py`** — sıkı: yalnız kayıtlı `TrustedSource`'lardan
   gelen, ≥2 bağımsız (farklı domain) veya 1 resmî kaynaktan gelen değerleri "verified"
   sayıyor. Search sonucu asla doğrudan fact olmuyor.
2. **`accounting/researcher.py` → Hermes `web_extract`** — burada "arama" ve "içerik
   çıkarma" ikisi de Hermes'in kendi iç araçlarına devredilmiş; Kaizen'in kendi
   `search/` paketi veya `accounting/crawler.py`'si bu yolda YOK. `hermes_bridge.py`'nin
   kendi ayrıştırıcısı (`_parse_research_packet`) yine de kaynak/URL/hostname bazlı bir
   bağımsızlık kontrolü yapıyor (`hermes_bridge.py:184`) — yani sıfır disiplin değil, ama
   bu disiplin Kaizen'in kendi search/fetch/evidence katmanında değil, Hermes'in kapalı
   kutusunun İÇİNDE uygulanıyor. Bu, İş Emri #2'nin ana boşluğudur (madde 7): "SearchProvider
   KaizenBrain'e bağlı değil" + "Hermes internet YERİNE geçmemeli" ikisi birden geçerli.

---

## 7. `core/commands.py` — Metin Komutları (özet)

| Komut | Backend |
|---|---|
| `durum` | `learning_store.stats()`, `site_store.stats()`, `facts.rows()`, `cards.stats()`, `brain_manager.experience_stats()` |
| `kaynaklar` | `site_store.count()` |
| `parametreler` / `parametre <konu>` | `facts.rows()`, `facts.find_topic()`, `facts.history()` |
| `yetenekler` | statik JSON okuma |
| `güncelle [sayfa]` | `accounting.refresh.run_refresh()` — **`accounting/crawler.py` yalnız burada canlı çalışıyor** |
| `öğrendiklerim` | `cards.all_cards()`, `cards.contradictions()` |
| `onayla: soru` | `brain.confirm_card()` |
| `oku: dosya` | `tool_manager.run_tool()` |
| `doğrula: dosya` | `tool_manager.run_tool()` + `accounting_agent.verify_document()` |
| `düzelt: soru => cevap` | `accounting_agent.learn()` |

---

## 8. Providers (Hermes / Local / Offline)

`core/ai/base_provider.py::BaseAIProvider` (soyut, `.ask()`), somut sınıflar:
`hermes_provider.py` (subprocess `hermes chat ...` sarmalayıcı — `core/hermes_bridge.py`
üzerinden), `local_provider.py` (yerel Ollama uyumlu HTTP, `localhost`/`127.0.0.1`/`::1`
dışına yalnız `cloud_allowed=true` ise izin verir), `offline_provider.py` (sabit
"çevrimdışı" string'i), `fallback_provider.py` (zincir + `__getattr__` proxy —
`.research()` gibi ekstra metodları ilk uygun provider'a yönlendirir). `provider_factory.
build_provider()` bunları `config/Kaizen.json`'a göre kurar.

`models/model_manager.py` + `models/base_model.py` — **ayrı, kullanılmayan bir eski/
yinelenen soyutlama** (`ModelManager.model_bagla()`) — `core/engine.py`'nin gerçek
zincirinde hiç referans edilmiyor. Bu iş emrinin kapsamı dışında bırakılmıştır (KESİNLİKLE
YAPILMAYACAKLAR: "büyük yeniden yazım yok") ama gelecekte kafa karışıklığına yol
açabileceği için burada not edilmiştir.

---

## 9. Güvenlik Altyapısı — Safe Fetcher için Ne Var, Ne Yok

- `accounting/crawler.py`: gerçek robots.txt (`RobotFileParser`), 401/403/429'u asla
  aşmıyor, `http`/`https` şema kısıtı + **sabit domain allowlist'i** (`source_registry`
  üzerinden — yani zaten dar bir SSRF yüzeyi), rate limit, boyut/timeout sınırı, ETag
  önbellek. **Eksik**: yönlendirme (redirect) sonrası `final_url` domain/robots'a karşı
  tekrar doğrulanmıyor (`crawler.py` — redirect sonrası accept() tekrar çağrılmıyor).
- `core/ai/local_provider.py` ve `memory/cognee_memory.py`: yalnız "localhost mu değil
  mi" kontrolü — genel private-IP-aralığı/DNS-rebinding koruması YOK.
- `security/security_manager.py`: dosya/sistem eylemleri için onay kapısı — URL/ağ
  güvenliğiyle ilgisi yok.
- **Sonuç**: yeni Safe Fetcher (madde 14) SIFIRDAN private-IP/localhost/`file://`/
  kimlik-bilgisi-URL'de reddi kendi yazmalı; ama domain-allowlist + robots.txt +
  rate-limit + boyut/timeout mantığı `accounting/crawler.py`'den **yeniden kullanılabilir**
  (kopyalanmamalı — mümkünse ortak bir yardımcı modüle çıkarılmalı).

---

## 10. Bu Denetimin Doğrulanmış Baseline'ı (madde 4/5, aynı oturumda ölçüldü)

- `python3 -m tests.run_all` → **TÜM KAIZEN TESTLERİ: BAŞARILI** (search provider +
  resilience mock testleri dahil, hepsi izole/mock).
- 33 soruluk gerçek hayat sınavı: **15/33 başarılı, 18 bilinen darboğaz** (kategori:
  matematik 8, muhasebe 12, sgk 7, güncel 6; darboğaz dağılımı: other 6, research 7,
  retrieval 4, classification 1) — önceki fazla birebir aynı, regresyon yok.
- Red-team (düzeltilmiş, standalone `tests.test_learning_transfer_redteam`): Positive
  93.8%, Negative 100%, Ambiguous 90%, Fact Safety Violations 0/63, Overall 96.2% —
  önceki fazla birebir aynı.
- `data/`, `knowledge/`, `memory/`, `logs/` SHA256: test koşumundan ÖNCE ve SONRA
  birebir aynı (byte-level) — izolasyon disiplini bozulmadı.

---

## 11. En Önemli Boşluk (Bu Belgenin Tek Cümlelik Özeti)

**Kaizen bugün, güncel/internet gerektiren bir soruda kendi `SearchProvider`/SearXNG
altyapısını KULLANMIYOR.** Tek canlı internet erişim yolu, Hermes'in kendi kapalı-kutu
`web_search`/`web_extract` araçlarıdır (`accounting/researcher.py` üzerinden). `search/`
paketi (Protocol + SearXNG implementasyonu + resilience) eksiksiz yazılmış ve test edilmiş
ama sıfır üretim bağlantısına sahip. Bu, İş Emri #2'nin tüm sonraki fazlarının (7'den
itibaren) çözmesi gereken tam olarak o boşluktur.
