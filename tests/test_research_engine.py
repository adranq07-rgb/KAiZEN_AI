"""KAIZEN — BÜYÜK İŞ EMRİ #2, Faz 11-12/26: Research Engine orkestratörü (`research/
engine.py`) testleri. GERÇEK AĞ YOK -- `SearchProvider` ve fetcher, sabit sonuçlar
döndüren test double'larıdır (bkz. tests/test_search_provider.py, tests/
test_research_fetcher.py ile AYNI disiplin). Sayılar tamamı test uydurmasıdır."""
from research.engine import run_research
from research.fetcher import FetchOutcome
from research.models import (
    CONFLICTED,
    FETCH_BLOCKED_ROBOTS,
    FETCH_OK,
    INSUFFICIENT,
    PARTIAL,
    SEARCH_DEGRADED,
    SEARCH_UNAVAILABLE,
    SUPPORTED,
)
from search.provider import (
    SearchOptions,
    SearchOutcome,
    SearchResult,
    SearchUnavailableError,
    STATUS_EMPTY,
    STATUS_OK,
)


def _sr(url, query, engine="fake"):
    domain = url.split("/")[2]
    return SearchResult(
        title="Test Sonucu", url=url, snippet="...", engine=engine, engines=(engine,),
        category="general", score=1.0, published_date=None, domain=domain, is_pdf=False,
        query=query,
    )


def _html(sentence, published="2026-01-05T10:00:00+03:00"):
    return (
        f"<html><head><title>Test</title>"
        f"<meta property=\"article:published_time\" content=\"{published}\"></head>"
        f"<body><article><p>{sentence}</p></article></body></html>"
    ).encode("utf-8")


class _FakeProvider:
    """madde 12: `SearchProvider` Protocol'üne uyan, ağa hiç çıkmayan test double'ı."""

    def __init__(self, results_by_query=None, status_by_query=None, raise_for=None):
        self.results_by_query = results_by_query or {}
        self.status_by_query = status_by_query or {}
        self.raise_for = raise_for or {}
        self.calls = []

    def search(self, query, options=None):
        self.calls.append(query)
        if query in self.raise_for:
            raise self.raise_for[query]
        results = tuple(self.results_by_query.get(query, ()))
        status = self.status_by_query.get(query, STATUS_OK if results else STATUS_EMPTY)
        return SearchOutcome(results=results, query=query, status=status)


class _FakeFetcher:
    def __init__(self, outcomes_by_url):
        self.outcomes_by_url = outcomes_by_url

    def fetch(self, url):
        return self.outcomes_by_url.get(
            url, FetchOutcome(status=FETCH_BLOCKED_ROBOTS, url=url, final_url=url)
        )


def test_run_research_never_raises_returns_search_unavailable_on_total_failure():
    """madde 26: SearchProvider tamamen kullanılamaz olsa bile run_research ASLA
    exception fırlatmaz, geçerli bir ResearchResult döner."""
    question = "Bugün hava nasıl olacak"
    provider = _FakeProvider(raise_for={question: SearchUnavailableError("kapali")})
    fetcher = _FakeFetcher({})
    result = run_research(question, provider, fetcher)
    assert result.status == SEARCH_UNAVAILABLE
    assert result.evidence == () and result.claims == ()
    assert result.question == question
    print("KAIZEN ENGINE TOPLAM ARAMA HATASINDA COKMEZ, SEARCH_UNAVAILABLE DONER TESTI: BASARILI")


def test_run_research_supported_single_official_source():
    """YENİ KURAL: Tek resmi kaynak SUPPORTED vermez, single_source (PARTIAL) verir.
    3 kaynak gerekir SUPPORTED (verified) için."""
    question = "SGK prim tavanı nedir"
    url = "https://www.sgk.gov.tr/duyuru/2026"
    provider = _FakeProvider(results_by_query={question: [_sr(url, question)]})
    fetcher = _FakeFetcher({
        url: FetchOutcome(
            status=FETCH_OK, url=url, final_url=url, content_type="text/html; charset=utf-8",
            body=_html("2026 yılı için SGK prim tavanı 750.000 TL'dir."),
        ),
    })
    result = run_research(question, provider, fetcher)
    # Tek kaynak -> single_source -> PARTIAL status, claim value None
    assert result.status == PARTIAL
    assert len(result.claims) >= 1
    # Value None çünkü tek kaynakla kesin doğrulama yok
    assert result.claims[0].value is None
    assert result.search_health == STATUS_OK
    assert url in result.sources
    print("KAIZEN ENGINE TEK RESMI KAYNAK -> PARTIAL (single_source) TESTI: BASARILI")


def test_run_research_conflicted_when_two_independent_sources_disagree():
    question = "Fatura düzenleme sınırı ne kadar"
    url1 = "https://www.muhasebetr.com/a"
    url2 = "https://www.alomaliye.com/b"
    provider = _FakeProvider(results_by_query={question: [_sr(url1, question), _sr(url2, question)]})
    fetcher = _FakeFetcher({
        url1: FetchOutcome(
            status=FETCH_OK, url=url1, final_url=url1, content_type="text/html; charset=utf-8",
            body=_html("Fatura düzenleme sınırı 2026 yılında 11.111 TL olarak uygulanacaktır."),
        ),
        url2: FetchOutcome(
            status=FETCH_OK, url=url2, final_url=url2, content_type="text/html; charset=utf-8",
            body=_html("2026 yılında fatura düzenleme sınırı 12.222 TL oldu."),
        ),
    })
    result = run_research(question, provider, fetcher)
    assert result.status == CONFLICTED
    assert result.conflicts == (question,)
    assert result.verified_claims == ()
    print("KAIZEN ENGINE IKI BAGIMSIZ KAYNAK CELISKISI -> CONFLICTED (UCTAN UCA) TESTI: BASARILI")


def test_run_research_search_degraded_and_missing_information_when_no_results():
    """madde 25: arama çalıştı ama hiçbir sonuç bulunamadıysa -- bu durum GİZLENMEZ,
    hem search_health hem missing_information'a yansır."""
    question = "Bugün hava nasıl olacak"
    provider = _FakeProvider(status_by_query={question: STATUS_EMPTY})
    fetcher = _FakeFetcher({})
    result = run_research(question, provider, fetcher)
    assert result.status == SEARCH_DEGRADED
    assert result.missing_information == (question,)
    assert result.claims == ()
    print("KAIZEN ENGINE SONUCSUZ ARAMA -> SEARCH_DEGRADED + EKSIK BILGI RAPORU TESTI: BASARILI")


def test_run_research_partial_when_only_some_subquestions_supported():
    """madde 27: plan BİRDEN FAZLA alt-soru ürettiğinde (yıl+konu tetiklemesi), yalnız
    BİR TANESİ desteklenip diğerleri boş kalırsa -- genel durum SUPPORTED'a
    YÜKSELTİLMEZ, PARTIAL kalır (bir önceki tasarımdaki, yalnız üretilen Claim'lere
    bakan hatanın regresyon testi)."""
    question = "2026 SGK prim tavanı nedir"
    main_url = "https://www.sgk.gov.tr/duyuru/2026"
    provider = _FakeProvider(results_by_query={question: [_sr(main_url, question)]})
    fetcher = _FakeFetcher({
        main_url: FetchOutcome(
            status=FETCH_OK, url=main_url, final_url=main_url, content_type="text/html; charset=utf-8",
            body=_html("2026 yılı için SGK prim tavanı 750.000 TL'dir."),
        ),
    })
    result = run_research(question, provider, fetcher)
    assert len(result.subquestions) >= 2  # planner yil+konu icin ek alt-sorular uretti
    assert result.status == PARTIAL
    assert question in {c.text for c in result.claims}
    assert len(result.missing_information) >= 1
    print("KAIZEN ENGINE COK-ALT-SORULU PLANDA KISMI DESTEK -> PARTIAL (SUPPORTED DEGIL) TESTI: BASARILI")


class _RaisingFetcher:
    """GERÇEK PC BULGUSU (2026-09-25, 3. gerçek UAT çalışması): `fetcher.fetch(url)`
    beklenmedik bir istisna fırlattığında (ör. `SafeFetcher` içinde daha önce hiç
    yakalanmamış bir zaman aşımı türü) `run_research`'ün YİNE DE çökmediğini doğrular --
    `fetcher.fetch()`'in kendisi ASLA raise etmemesi gerekse de (bkz. tests/
    test_research_fetcher.py -- gövde-okuma zaman aşımı orada AYRICA düzeltildi), bu
    çift-katmanlı bir savunmadır (madde 26)."""

    def __init__(self, raise_for_url, ok_outcome_by_url=None):
        self.raise_for_url = raise_for_url
        self.ok_outcome_by_url = ok_outcome_by_url or {}

    def fetch(self, url):
        if url == self.raise_for_url:
            raise TimeoutError("govde okunurken zaman asimi (yavas/damla-damla sunucu)")
        return self.ok_outcome_by_url.get(
            url, FetchOutcome(status=FETCH_BLOCKED_ROBOTS, url=url, final_url=url)
        )


def test_run_research_survives_unexpected_fetcher_exception_for_one_url():
    """REGRESYON (2026-09-25, gerçek PC'deki 'A'/'B' sorularının UNEXPECTED_EXCEPTION ile
    çökmesinin kök nedeni): ESKİ kodda `fetcher.fetch()`'ten sızan bir istisna doğrudan
    `run_research()`'ten dışarı sızardı (modülün 'ASLA raise etmez' sözleşmesini ihlal
    ederdi). Bu test ESKİ kodda `TimeoutError` ile BAŞARISIZ olur."""
    question = "SGK prim tavanı nedir"
    url = "https://www.sgk.gov.tr/yavas-sunucu"
    provider = _FakeProvider(results_by_query={question: [_sr(url, question)]})
    fetcher = _RaisingFetcher(raise_for_url=url)
    result = run_research(question, provider, fetcher)  # ESKİ kodda burada raise eder
    assert len(result.evidence) == 1
    assert result.evidence[0].has_real_content() is False
    assert result.claims == ()
    assert result.verified_claims == ()
    print("KAIZEN ENGINE FETCHER BEKLENMEYEN ISTISNA FIRLATSA BILE COKMEZ TESTI: BASARILI")


def test_run_research_blocked_fetch_is_never_silently_treated_as_content():
    """madde 13/36: fetch robots.txt tarafından engellenirse (asla getirilmedi), bu
    ASLA gerçek içerik gibi bir Claim'e dönüşmez."""
    question = "SGK prim tavanı nedir"
    url = "https://www.sgk.gov.tr/duyuru/2026"
    provider = _FakeProvider(results_by_query={question: [_sr(url, question)]})
    fetcher = _FakeFetcher({url: FetchOutcome(status=FETCH_BLOCKED_ROBOTS, url=url, final_url=url)})
    result = run_research(question, provider, fetcher)
    assert result.claims == ()
    assert result.verified_claims == ()
    assert result.evidence[0].fetch_status == FETCH_BLOCKED_ROBOTS
    assert result.evidence[0].has_real_content() is False
    print("KAIZEN ENGINE ROBOTS-ENGELLI FETCH ICERIK GIBI GOSTERILMEZ TESTI: BASARILI")


if __name__ == "__main__":
    test_run_research_never_raises_returns_search_unavailable_on_total_failure()
    test_run_research_supported_single_official_source()
    test_run_research_conflicted_when_two_independent_sources_disagree()
    test_run_research_search_degraded_and_missing_information_when_no_results()
    test_run_research_partial_when_only_some_subquestions_supported()
    test_run_research_survives_unexpected_fetcher_exception_for_one_url()
    test_run_research_blocked_fetch_is_never_silently_treated_as_content()
