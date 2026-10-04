"""KAIZEN Research Engine — Orkestratör (İş Emri #2 madde 11-12, 26).

`trigger -> planner -> SearchProvider -> fetcher -> extractor -> evidence -> verifier`
zincirini TEK BİR YERDE birleştirir. TEKRAR KULLANIM (madde 61, KESİN kural): bu dosyanın
KENDİSİ hiçbir arama/getirme/çıkarma/uzlaşı mantığını YENİDEN YAZMAZ, yalnızca her
`research/*` modülünü ve `search.provider.SearchProvider` sözleşmesini (Protocol,
SOMUT bir sınıfa değil -- madde 12) ÇAĞIRIR.

HENÜZ `KaizenBrain`'e bağlı DEĞİLDİR (bu Faz 28'in, madde 28-31'in işi) -- bu dosya
yalnızca bağımsız, kendi başına test edilebilir bir katmandır (`research/trigger.py`,
`research/planner.py` ile aynı ilke).

KRİTİK KURAL (madde 26): bu orkestratör çağırana HİÇBİR ZAMAN ham arama sonucu, ham
sayfa metni ya da bir exception SIZDIRMAZ -- `SearchProvider` TAMAMEN kullanılamaz olsa
bile (madde 26: "arama sistemi çökse bile Research Engine çökmemeli") her koşulda
geçerli bir `research.models.ResearchResult` DÖNER."""
import itertools
import time

from research.evidence import build_evidence
from research.extractor import extract
from research.models import (
    CONFLICTED,
    FETCH_HTTP_ERROR,
    FETCH_OK,
    INSUFFICIENT,
    PARTIAL,
    ResearchResult,
    SEARCH_DEGRADED,
    SEARCH_UNAVAILABLE,
    SUPPORTED,
)
from research.planner import build_plan
from research.verifier import build_claims
from search.provider import (
    SearchOptions,
    SearchProviderError,
    STATUS_DEGRADED,
    STATUS_EMPTY,
    STATUS_OK,
)

DEFAULT_MAX_RESULTS_PER_SUBQUESTION = 3


def _search_subquestion(provider, subquestion, max_results):
    """Tek bir alt-soru için `SearchProvider.search()` çağırır (madde 12: somut bir
    sınıfa DEĞİL, yalnızca Protocol'e bağımlı). madde 26: bir alt-sorudaki arama HATASI
    bütün araştırmayı ÇÖKERTMEZ -- `SearchProviderError` (ve alt sınıfları) burada
    YAKALANIR, bu alt-sorunun sonuç listesi boş sayılır, ama HANGİ hata olduğu
    (`.status`/`.fallback_reason`) çağırana döner ki genel `search_health` GİZLENMESİN."""
    options = SearchOptions(limit=max_results)
    try:
        outcome = provider.search(subquestion.search_query, options)
        return list(outcome.results)[:max_results], outcome.status
    except SearchProviderError as exc:
        return [], exc.status


def _fetch_and_build_evidence(fetcher, result, subquestion, requested_period, evidence_id):
    """Bir arama sonucunu güvenle getirir (`research/fetcher.py::SafeFetcher`), içerik
    çıkarır (`research/extractor.py`) ve bir `Evidence` inşa eder (`research/
    evidence.py`). Getirme BAŞARISIZ olursa (robots/SSRF/timeout/vb.) Evidence yine de
    üretilir ama GERÇEK `fetch_status`'uyla (madde 13: 'hiç denenmedi' ile 'denendi ama
    engellendi' KARIŞTIRILMAZ) -- hiçbir zaman uydurma içerik EKLENMEZ.

    SAĞLAMLIK (2026-09-25, gerçek PC UAT bulgusu -- 3. çalıştırma, madde 26): `fetcher.fetch()`
    kendi sözleşmesi gereği raise ETMEMELİ (bkz. `research/fetcher.py::SafeFetcher.fetch()` --
    gövde-okuma zaman aşımı ORADA da ayrıca düzeltildi), ama bu fonksiyon YİNE DE geniş bir
    savunma katmanına sahiptir -- `_search_subquestion`'daki `SearchProviderError` yakalama
    ile AYNI ilke (`run_research`'ün KENDİSİ 'ASLA raise etmez' sözleşmesini -- modülün en
    üstündeki docstring -- tek bir URL'deki BEKLENMEYEN bir istisna yüzünden ihlal etmemesi
    için): `fetcher`/`extract` katmanından beklenmeyen bir istisna sızarsa, bu tek kanıt
    FETCH_HTTP_ERROR olarak (mevcut 'ağ katmanında bir şeyler ters gitti' kovası, madde 13)
    işaretlenir -- İÇERİK UYDURULMAZ, yalnızca bu bir alt-sorunun/URL'nin diğerlerini
    ÇÖKERTMESİ engellenir."""
    try:
        outcome = fetcher.fetch(result.url)
        extracted = extract(outcome) if outcome.status == FETCH_OK else None
    except Exception:  # noqa: BLE001 -- madde 26: tek bir URL bütün araştırmayı çökertmez
        return build_evidence(
            evidence_id=evidence_id, subquestion=subquestion.text, query=result.query or subquestion.search_query,
            url=result.url, extracted=None, requested_period=requested_period,
            search_provider=result.engine, fetch_status=FETCH_HTTP_ERROR,
        )
    return build_evidence(
        evidence_id=evidence_id, subquestion=subquestion.text, query=result.query or subquestion.search_query,
        url=outcome.final_url or result.url, extracted=extracted, requested_period=requested_period,
        search_provider=result.engine, fetch_status=None if extracted else outcome.status,
    )


def _overall_status(claims, search_statuses, total_subquestions):
    """madde 27: ResearchResult.status GENEL kararı. Kural (en güvenli/en dürüst
    öncelik sırası -- bir çelişki VARSA asla gizlenip 'destekli' denemez):
      1) hiçbir alt-soru için arama BİLE çalışmadıysa (tüm aramalar hata verdiyse) ->
         SEARCH_UNAVAILABLE (araştırmanın kendisi hiç başlayamadı).
      2) herhangi bir Claim CONFLICTED ise -> CONFLICTED (en güvenli varsayım: bir
         çelişki varken 'kısmen destekli' denip gizlenmez).
      3) PLANDAKİ HER alt-soru (yalnızca claim üretenler değil -- hiç kanıt getirilemeyip
         Claim'i bile olmayan bir alt-soru da 'eksik' sayılır, madde 25) SUPPORTED bir
         Claim ürettiyse -> SUPPORTED.
      4) en az bir SUPPORTED Claim varsa (ama hepsi değil) -> PARTIAL.
      5) hiç SUPPORTED yoksa ama en az bir PARTIAL claim VAR (value dolu = partially_verified,
         veya value None = single_source) -> PARTIAL (kısmi doğrulama).
      6) hiç SUPPORTED/PARTIAL yoksa ama en az bir arama DEGRADED/EMPTY ile sonuçlandıysa ->
         SEARCH_DEGRADED.
      7) aksi halde (claim'ler var ama hepsi INSUFFICIENT, arama sağlıklıydı) ->
         INSUFFICIENT."""
    if search_statuses and all(s not in (STATUS_OK, STATUS_EMPTY, STATUS_DEGRADED) for s in search_statuses):
        return SEARCH_UNAVAILABLE
    if any(c.status == CONFLICTED for c in claims):
        return CONFLICTED
    supported_subquestions = {c.text for c in claims if c.status == SUPPORTED}
    if supported_subquestions and len(supported_subquestions) == total_subquestions:
        return SUPPORTED
    if supported_subquestions:
        return PARTIAL
    # PARTIAL claims (partially_verified with value, or single_source without value)
    partial_subquestions = {c.text for c in claims if c.status == PARTIAL}
    if partial_subquestions:
        return PARTIAL
    if any(s in (STATUS_DEGRADED, STATUS_EMPTY) for s in search_statuses):
        return SEARCH_DEGRADED
    return INSUFFICIENT


def run_research(
    question, provider, fetcher, today=None,
    max_results_per_subquestion=DEFAULT_MAX_RESULTS_PER_SUBQUESTION,
):
    """madde 11-12, 26: tam araştırma turu. `provider`: `search.provider.SearchProvider`
    Protocol'üne uyan HERHANGİ bir nesne (madde 12: somut sınıfa bağlanmaz). `fetcher`:
    `research.fetcher.SafeFetcher` (ya da aynı `.fetch(url) -> FetchOutcome` arayüzüne
    uyan başka bir nesne -- test double dahil). ASLA raise ETMEZ (madde 26); her koşulda
    geçerli bir `ResearchResult` döner."""
    started = time.monotonic()
    plan = build_plan(question, today=today)
    evidence_id_counter = itertools.count(1)

    evidence_by_subquestion = {}
    all_evidence = []
    search_statuses = []
    all_queries = []

    for subquestion in plan.subquestions:
        all_queries.append(subquestion.search_query)
        results, status = _search_subquestion(provider, subquestion, max_results_per_subquestion)
        search_statuses.append(status)
        subquestion_evidence = []
        for result in results:
            evidence = _fetch_and_build_evidence(
                fetcher, result, subquestion, plan.requested_period,
                evidence_id=f"ev{next(evidence_id_counter)}",
            )
            subquestion_evidence.append(evidence)
            all_evidence.append(evidence)
        if subquestion_evidence:
            evidence_by_subquestion[subquestion.text] = subquestion_evidence

    claims = build_claims(plan, evidence_by_subquestion)
    claimed_subquestions = {c.text for c in claims}
    missing_information = tuple(
        sq.text for sq in plan.subquestions if sq.text not in claimed_subquestions
    )
    conflicts = tuple(c.text for c in claims if c.status == CONFLICTED)
    verified_claims = tuple(c for c in claims if c.status == SUPPORTED)
    sources = tuple(sorted({e.url for e in all_evidence if e.has_real_content()}))
    status = _overall_status(claims, search_statuses, total_subquestions=len(plan.subquestions))

    # search_health (madde 27): en kotu gozlemlenen arama durumu, KaizenBrain'in kendi
    # STATUS_* sozlesmesiyle (search/provider.py) uyumlu -- burada UYDURULMAZ.
    if not search_statuses:
        search_health = STATUS_EMPTY
    elif all(s not in (STATUS_OK, STATUS_EMPTY, STATUS_DEGRADED) for s in search_statuses):
        search_health = search_statuses[0]
    elif any(s == STATUS_DEGRADED for s in search_statuses):
        search_health = STATUS_DEGRADED
    elif all(s == STATUS_EMPTY for s in search_statuses):
        search_health = STATUS_EMPTY
    else:
        search_health = STATUS_OK

    return ResearchResult(
        status=status, question=question, subquestions=tuple(sq.text for sq in plan.subquestions),
        queries=tuple(all_queries), search_health=search_health, evidence=tuple(all_evidence),
        claims=claims, verified_claims=verified_claims, conflicts=conflicts,
        missing_information=missing_information, sources=sources,
        elapsed_time=time.monotonic() - started,
    )
