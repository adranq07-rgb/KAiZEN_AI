# KAIZEN RESEARCH ENGINE — Mimari Karar + Sözleşmeler

> İş Emri #2, madde 7-31'in gereği. Bu belge önce (Faz 7-8) mimari kararı ve modül
> iskeletini, sonra (çalışma ilerledikçe) her modülün sözleşmesini ve test sonuçlarını
> belgeler. `docs/KAIZEN_RUNTIME_ARCHITECTURE.md`'nin devamıdır — orada "bugün ne var"
> anlatıldı, burada "ne inşa ediliyor ve neden" anlatılıyor.

## 1. Sorun (madde 7, tek cümle)

`search/` paketi (SearXNG tabanlı `SearchProvider`) eksiksiz yazılmış ve test edilmiş ama
`KaizenBrain`'e HİÇ bağlı değil; bugünkü tek canlı internet erişimi Hermes'in kapalı-kutu
`web_search`/`web_extract` araçları. Bu iş emri bu boşluğu, `SearchProvider`'ı doğrudan
`KaizenBrain`'e YAPIŞTIRARAK DEĞİL (madde 7'nin açıkça yasakladığı gibi), aralarına yeni,
sorumlulukları ayrılmış bir **Research Engine** katmanı koyarak kapatır.

## 2. Mimari Karar (madde 8)

**Karar: `research/` adında yeni bir üst paket, madde 8'in önerdiği isimlere sadık
kalarak, TEK BİR DEV SINIF OLMADAN (madde 61) yedi dar-sorumluluklu modülden oluşur:**

| Modül | Tek sorumluluğu | Bağımlılığı |
|---|---|---|
| `research/models.py` | Sözleşmeler: `Evidence`, `Claim`, `ResearchResult`, durum sabitleri, `Subquestion`/`ResearchPlan` | Yok (saf veri) |
| `research/trigger.py` | "Bu soru araştırma gerektirir mi?" kararı (madde 32-33) | `models` |
| `research/planner.py` | Soru → alt-sorular → arama sorguları (madde 9-10) | `models` |
| `research/fetcher.py` | Güvenli URL getirme: robots/rate-limit/boyut/timeout/SSRF (madde 14-15) | Yok (saf urllib) |
| `research/extractor.py` | Ham HTML/PDF → başlık/tarih/domain/pasaj (madde 16) | `accounting/html_extract.py`, `accounting/crawler.py` (PDF/XLSX metin çıkarma, KOPYALANMADI, çağrıldı) |
| `research/evidence.py` | Arama sonucu + getirilen içerik → `Evidence` nesnesi; tazelik/dönem eşleşmesi (madde 17,20-21) | `models`, `accounting/source_registry.py` (KOPYALANMADI, çağrıldı) |
| `research/verifier.py` | Kanıtlardan iddia (claim) çıkarma + uzlaşı/çelişki (madde 18-19,22-25) | `models`, `accounting/consensus.py` (KOPYALANMADI, çağrıldı) |
| `research/engine.py` | Orkestratör: `trigger→planner→SearchProvider→fetcher→extractor→evidence→verifier→ResearchResult` (madde 26) | hepsi + `search.provider.SearchProvider` (Protocol, somut sınıfa değil) |

**Neden bu 8 dosya ve neden bu sınır çizgileri:** her dosya İş Emri #2'nin ayrı bir
maddesine karşılık geliyor (Search≠Evidence≠Fact≠Principle≠Experience zincirinin her
halkası kendi dosyasında) — böylece "Research Engine tek dev sınıf olmasın" (madde 61)
kuralı dosya düzeyinde de zorlanmış olur, ve her modül kendi başına (diğerleri
olmadan) test edilebilir.

## 3. Mevcut Altyapıyla İlişki — Neyi Kopyalamıyoruz, Neyi Çağırıyoruz

- **`accounting/source_registry.py`**: Research Engine kendi paralel bir "güvenilir
  kaynak" listesi YAZMAZ (madde 18 açık yasak) — `research/evidence.py`,
  `source_registry.trusted_source_for_url()`'i doğrudan çağırır. SGK/Resmî Gazete
  eksikliği (Faz 1 bulgusu) bu iş emrinin kapsamında `source_registry.py`'ye YENİ satır
  eklenerek düzeltilecek (kod değişikliği, çoğaltma değil).
- **`accounting/consensus.py`**: Research Engine kendi bağımsızlık/uzlaşı mantığını
  YENİDEN YAZMAZ — `research/verifier.py`, mevcut `AccountingConsensus`'u (zaten
  domain-bazlı dedup yapan, madde 24'ün istediği bağımsızlık kontrolünü sağlayan
  sınıf) ÇAĞIRIR.
- **`accounting/crawler.py`**: Bu dosyanın robots.txt/rate-limit/boyut/timeout mantığı
  SAĞLAM ama kasıtlı olarak dar bir amaç için yazılmış — yalnız ÖNCEDEN KAYITLI
  `source_registry` domain'lerini (`accept()` metodu domain allowlist'i zorunlu kılıyor)
  çeker. Research Engine'in fetcher'ı ise arama motorunun bulduğu, ÖNCEDEN BİLİNMEYEN
  herhangi bir domain'i güvenli şekilde çekmek ZORUNDA — bu YENİ bir güvenlik yüzeyi
  (SSRF: private-IP/localhost/`file://`/yönlendirme-sonrası-doğrulama), `crawler.py`'de
  HİÇ YOK (Faz 1 denetimi bunu açıkça tespit etti). Bu yüzden `research/fetcher.py`
  KOPYALAMAZ, aynı disiplini (robots.txt zorunlu, 403/429 asla aşılmaz, rate-limit,
  boyut/timeout sınırı) YENİDEN ama GENİŞLETİLMİŞ bir SSRF sınırıyla uygular — kod
  çoğaltması değil, farklı bir tehdit modeli için amaca uygun yeni bir modül (bu karar
  gerekçesiyle birlikte burada belgeleniyor, madde 61'in "büyük yeniden yazım yok"
  kuralını ihlal etmiyor çünkü `crawler.py`'ye HİÇ dokunulmuyor, yanına yeni bir dosya
  ekleniyor).
- **`search/provider.py::SearchProvider`**: `research/engine.py` YALNIZ bu Protocol'e
  bağlanır, `SearXNGProvider`'a doğrudan değil (madde 11) — böylece gelecekte başka bir
  arama backend'i (veya birden fazlası) `SearchProvider`'ı uyguladığı sürece Research
  Engine'de değişiklik gerekmez.
- **Hermes**: `research/engine.py` Hermes'i HİÇ çağırmaz — Hermes'in rolü (madde 29-30)
  yalnızca (a) `core/ai/*`'daki genel model sağlayıcı olarak metin üretmek, (b)
  SearXNG TAMAMEN kullanılamaz olduğunda dar bir FALLBACK olarak kalmak (madde 30,
  Faz 24'te ele alınacak — bu fazda henüz bağlanmadı).

## 4. `ResearchResult` Durum Sözleşmesi (madde 26-27) — özet (tam kod: `research/models.py`)

`SUPPORTED / PARTIAL / CONFLICTED / INSUFFICIENT / SEARCH_DEGRADED / SEARCH_UNAVAILABLE`
— hiçbiri "VERIFIED" değildir (o etiket yalnız `core/trace.py`'nin kendi kesin-araç/fact
rotasına aittir; Research Engine bir cevabı EN FAZLA `SUPPORTED` güvenine taşıyabilir,
tıpkı bugünkü `memory_grounded` rotası gibi — bkz. §5).

## 5. `KaizenBrain`'e Bağlantı Noktası (madde 28-31 — UYGULANDI, 2026-09-24)

Bugünkü zincir (`docs/KAIZEN_RUNTIME_ARCHITECTURE.md` §3): kesin araçlar → facts →
memory_grounded → araştırma (Hermes) → ofis red → provider fallback. Research Engine
**tam olarak bugünkü "araştırma" adımının YERİNE** (`accounting_agent.ask()`'ın, yani
Hermes'in, ÖNÜNE) bağlandı — tek dokunulan nokta `core/kaizen_brain.py::_research_once`
(iki farklı çağrı yerinden -- `_from_memory` ve `_answer_core` -- de kullanılan TEK
choke point, madde 61: "iki yerde aynı mantık yok"):

```
kesin araçlar → facts → memory_grounded (yerel kanıt yeterliyse)
  → RESEARCH ENGINE (research/engine.py::run_research, SearchProvider ile)
    → SUPPORTED (>=1 verified_claim) ise: bu sonuç kullanılır, Hermes HİÇ ÇAĞRILMAZ
    → PARTIAL/CONFLICTED/INSUFFICIENT/SEARCH_DEGRADED/SEARCH_UNAVAILABLE ise: None
  → (yukarıdaki None ise) Hermes araştırma FALLBACK (accounting_agent.ask, DEĞİŞMEDEN)
  → ofis red → provider fallback
```

**Güvenlik katmanları (hepsi birden, `core/kaizen_brain.py::_research_engine_once`)**:
1. `research_engine_enabled` bayrağı (`config/Kaizen.json` → `research.
   research_engine_enabled`, varsayılan `false`) — `learning_brain_enabled` ile BİREBİR
   aynı disiplin, tek satırlık geri dönüş.
2. `search_provider is None` ise (yanlış yapılandırma) yine sessizce Hermes'e düşer.
3. `research/engine.py::run_research` kendi içinde zaten hiçbir zaman raise etmez (madde
   26) ama entegrasyon noktasında YİNE DE geniş bir `try/except Exception` var (savunma
   katmanı, bir hatayı örtbas etmek için değil — Research Engine'in Kaizen'in ANA cevap
   zincirini asla çökertmemesi gerektiği için).
4. `_format_research_result` yalnız `status == SUPPORTED` VE `verified_claims` doluysa
   bir metin döner — PARTIAL/CONFLICTED/INSUFFICIENT dahil HER ŞEY `None` döner, çağıran
   Hermes'e düşer. Yani Research Engine'in Hermes'in YERİNİ alması yalnız en yüksek güven
   düzeyinde (`docs/RESEARCH_ENGINE.md` §4: SUPPORTED, "memory_grounded ile aynı tavan")
   olur — asla "belki" bir sonucu Hermes'in üstüne koymaz.

**Hermes'in rolü artık gerçekten madde 29-30'un öngördüğü gibi**: (a) `core/ai/*`'daki
genel model sağlayıcı, (b) Research Engine SUPPORTED bulamadığında (veya bayrak kapalıyken
— bugünkü varsayılan durum) dar bir FALLBACK. `core/engine.py`, `SearXNGProvider()`'ı HER
ZAMAN kurar (kurulumun kendisi ağa hiç çıkmaz, `principle_retriever` ile AYNI desen) ama
`KaizenBrain`'de gerçekten kullanılıp kullanılmayacağı tek başına bayrağa bağlı.

Test kanıtı: `tests/test_kaizen_brain_research_engine.py` (6 test) — varsayılan-kapalı
davranışın birebir korunduğu, sağlayıcısız/exception durumlarında çökmeden Hermes'e
düşüldüğü, ve SUPPORTED sonucun Hermes'i gerçekten atladığı uçtan uca kanıtlanır. Tüm
mevcut regresyon (`tests/run_all.py`, `test_kaizen_brain.py`/`test_core.py` dahil)
DEĞİŞMEDEN yeşil.

## 6. İlerleme Günlüğü

- 2026-09-23: §1-5 (bu belge) yazıldı. `research/` paketi henüz kod içermiyor — sıradaki
  adım `research/models.py` (madde 62 adım 8).
- 2026-09-24: `research/` paketinin TAMAMI (8 modül) yazıldı, test edildi (yeniden
  üretilebilir, izole fixture'larla, gerçek ağ/veri yok) ve `tests/run_all.py`'ye
  bağlandı — her regresyon çalıştırmasında `data/`/`knowledge/`/`memory/`/`logs/`
  SHA256 ile değişmedi doğrulandı:
  - `research/models.py` (9 test) — sözleşmeler.
  - `research/trigger.py` (32 vaka + 2 invariant) — `KaizenBrain.classify`/
    `.needs_current_research` ÇAĞRILARAK (kopyalanmadan).
  - `research/planner.py` (20 vaka + 5 invariant) — LLM'siz, kural tabanlı.
  - `research/fetcher.py` (`SafeFetcher`, 17 adversarial test) — SSRF/robots/rate-limit/
    yönlendirme-yeniden-doğrulama.
  - `research/extractor.py` (6 test) — `accounting/html_extract.py` + `accounting/
    crawler.py::extract_pdf_text` + `accounting/retriever.py::Retriever.coverage`
    ÇAĞRILARAK.
  - `research/evidence.py` (11 test) — `accounting/source_registry.py::
    trusted_source_for_url` ÇAĞRILARAK; kaynak otoritesi + tazelik/dönem eşleşmesi;
    `build_evidence` artık gerçek `fetch_status`'u (blocked/timeout/vb.) taşıyabiliyor
    (küçük, geriye-uyumlu ek: `fetch_status=None` varsayılanı eski davranışı korur).
  - `research/verifier.py` (10 test) — `accounting/consensus.py::AccountingConsensus`
    ve `accounting/facts.py::FactExtractor` ÇAĞRILARAK (kopyalanmadan); soru->konu
    eşleştirmesi için `accounting/facts.py::FactRegistry.find_topics`'ten SAF bir
    `match_topics()` fonksiyonuna küçük, davranış-koruyan bir çıkarma yapıldı (sqlite'a
    hiç dokunmadan yeniden kullanılabilsin diye) — `tests/test_facts.py` hâlâ yeşil.
    Sayısal/konu-çapalı alt-sorular için gerçek çok-kaynak uzlaşı/çelişki kararı;
    nitel (konu-dışı) alt-sorular için YALNIZ erişilebilirlik/otorite kontrolü (İÇERİK
    uyuşması kontrol EDİLMEZ — bu sınır dürüstçe modül docstring'inde belgelendi).
  - `research/engine.py` (6 test, uçtan uca) — orkestratör: `trigger→planner→
    SearchProvider(Protocol)→fetcher→extractor→evidence→verifier→ResearchResult`.
    `SearchProvider` TAMAMEN başarısız olsa bile (`SearchUnavailableError` vb.) ASLA
    exception fırlatmaz, her zaman geçerli bir `ResearchResult` döner (madde 26). Genel
    `status` kararı: bir Claim CONFLICTED ise her zaman CONFLICTED; plandaki HER
    alt-soru SUPPORTED olmadıkça SUPPORTED denmez (yalnızca üretilen Claim'lere bakan
    ilk tasarımdaki bir hata, regresyon testiyle sabitlendi — bkz.
    `test_run_research_partial_when_only_some_subquestions_supported`).
  - Ayrıca: `accounting/source_registry.py`'ye SGK/Resmî Gazete/Mevzuat Bilgi Sistemi
    resmî kaynak olarak eklendi (Faz 1 bulgusu, kendi testiyle).
  - Aynı gün (devam): `KaizenBrain`'e bağlantı TAMAMLANDI (madde 28-31, bkz. §5 —
    `core/kaizen_brain.py::_research_once`/`_research_engine_once`/
    `_format_research_result`, `core/engine.py::SearXNGProvider` kurulumu,
    `config/Kaizen.json::research.research_engine_enabled` bayrağı, varsayılan KAPALI).
    6 yeni test (`tests/test_kaizen_brain_research_engine.py`) + TÜM mevcut regresyon
    (`test_kaizen_brain.py`, `test_core.py` dahil) değişmeden yeşil, SHA256 ile veri
    bütünlüğü doğrulandı. Research Engine artık üretimde MEVCUT (bayrak varsayılan
    kapalı olduğu için bugün hâlâ hiçbir kullanıcı davranışını değiştirmiyor) ama tek
    satırlık bir config değişikliğiyle açılabilir durumda.
  - **HENÜZ YAPILMAYAN**: gerçek SearXNG'ye karşı canlı smoke test (madde 38 — bu ortamda
    localhost:8890'a erişilemiyor, kullanıcının kendi bilgisayarında yapılacak), bayrağın
    GERÇEKTEN açılıp doğrulanması (Shadow/UAT fazı), ve Faz 32-39'un geri kalanı.
