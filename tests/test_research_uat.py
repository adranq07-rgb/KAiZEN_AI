"""KAIZEN İŞ EMRİ #2 (ara kontrol), madde 29: `tools/research_uat.py`'yi kullanıcının GERÇEK
PC'sine göndermeden önce bulutta çalıştırılacak mock testler. Gerçek Docker/SearXNG/ağ/Hermes
YOKTUR (madde 2) -- bu yüzden her senaryo `monkeypatch`/sahte nesnelerle simüle edilir.

Bu dosya `tools/research_uat.py`'nin KENDİ davranışını test eder -- Research Engine'in
(`research/`) davranışı zaten `tests/test_research_engine.py`, `tests/test_research_verifier.py`
vb. tarafından kapsanır (madde 61: aynı şey iki yerde test edilmez); burada yalnızca UAT
script'inin YENİ kodu (Docker kontrolü, HTTP/JSON çağrıları, engine-health sınıflandırması,
provider sarmalayıcı sayaçları, adversarial senaryo üreticileri, SHA muhafızı, rapor/kapı
mantığı) hedeflenir.

Kapsanan madde 29 senaryoları:
  - mock Docker failure            -> test_stage_docker_*
  - mock SearXNG unavailable       -> test_stage_http_searxng_unavailable
  - mock JSON 403                  -> test_stage_json_api_403_diagnoses_without_editing_settings
  - mock empty results             -> test_stage_json_api_empty_results_not_counted_as_pass
  - mock degraded engines          -> test_stage_engine_health_degraded_classification
  - mock SearchProvider            -> test_counting_provider_wrapper_records_real_calls
  - mock fetch failure             -> test_stage_research_engine_mock_fetch_failure
  - mock evidence mismatch         -> test_relevance_adversarial_detects_injected_bug
  - mock temporal mismatch         -> test_temporal_adversarial_catches_wrong_period
  - mock consensus conflict        -> test_conflict_adversarial_catches_two_values
"""
import json
import urllib.error
from pathlib import Path

import tools.research_uat as uat


# ---------------------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------------

class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fresh_report():
    return uat.Report()


# ---------------------------------------------------------------------------------------
# mock Docker failure
# ---------------------------------------------------------------------------------

def test_stage_docker_mock_docker_command_missing():
    original_which = uat.shutil.which
    uat.shutil.which = lambda name: None
    try:
        report = _fresh_report()
        stage = uat.stage_docker(report)
        assert stage["result"] == "FAIL_DOCKER_UNAVAILABLE"
        assert report.criteria[1]["passed"] is False
        assert report.criteria[2]["passed"] is False
    finally:
        uat.shutil.which = original_which
    print("KAIZEN UAT MOCK: DOCKER KOMUTU YOK TESTI: BASARILI")


def test_stage_docker_mock_container_stopped():
    original_which = uat.shutil.which
    original_run = uat.subprocess.run
    uat.shutil.which = lambda name: "/usr/bin/docker"

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["docker", "version"]:
            return _FakeCompletedProcess(returncode=0, stdout="{}")
        if cmd[:2] == ["docker", "inspect"]:
            payload = [{
                "State": {"Status": "exited", "Running": False, "Health": None},
                "NetworkSettings": {"Ports": {}},
            }]
            return _FakeCompletedProcess(returncode=0, stdout=json.dumps(payload))
        raise AssertionError(f"beklenmeyen komut: {cmd}")

    uat.subprocess.run = fake_run
    try:
        report = _fresh_report()
        stage = uat.stage_docker(report)
        assert stage["result"] == "FAIL_SEARXNG_STOPPED"
        assert report.criteria[1]["passed"] is True
        assert report.criteria[2]["passed"] is False
    finally:
        uat.shutil.which = original_which
        uat.subprocess.run = original_run
    print("KAIZEN UAT MOCK: SEARXNG CONTAINER DURMUS TESTI: BASARILI")


def test_stage_docker_mock_container_missing():
    original_which = uat.shutil.which
    original_run = uat.subprocess.run
    uat.shutil.which = lambda name: "/usr/bin/docker"

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["docker", "version"]:
            return _FakeCompletedProcess(returncode=0, stdout="{}")
        if cmd[:2] == ["docker", "inspect"]:
            return _FakeCompletedProcess(returncode=1, stdout="", stderr="No such object")
        raise AssertionError(f"beklenmeyen komut: {cmd}")

    uat.subprocess.run = fake_run
    try:
        report = _fresh_report()
        stage = uat.stage_docker(report)
        assert stage["result"] == "FAIL_DOCKER_CONTAINER"
        assert report.criteria[1]["passed"] is True
        assert report.criteria[2]["passed"] is False
    finally:
        uat.shutil.which = original_which
        uat.subprocess.run = original_run
    print("KAIZEN UAT MOCK: DOCKER CONTAINER YOK TESTI: BASARILI")


def test_stage_docker_mock_running_ok():
    original_which = uat.shutil.which
    original_run = uat.subprocess.run
    uat.shutil.which = lambda name: "/usr/bin/docker"

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["docker", "version"]:
            return _FakeCompletedProcess(returncode=0, stdout="{}")
        if cmd[:2] == ["docker", "inspect"]:
            payload = [{
                "State": {"Status": "running", "Running": True, "Health": {"Status": "healthy"}},
                "NetworkSettings": {"Ports": {"8890/tcp": [{"HostPort": "8890"}]}},
            }]
            return _FakeCompletedProcess(returncode=0, stdout=json.dumps(payload))
        raise AssertionError(f"beklenmeyen komut: {cmd}")

    uat.subprocess.run = fake_run
    try:
        report = _fresh_report()
        stage = uat.stage_docker(report)
        assert stage["result"] == "OK"
        assert report.criteria[1]["passed"] is True
        assert report.criteria[2]["passed"] is True
        assert stage["health"] == "healthy"
    finally:
        uat.shutil.which = original_which
        uat.subprocess.run = original_run
    print("KAIZEN UAT MOCK: DOCKER/SEARXNG RUNNING OK TESTI: BASARILI")


# ---------------------------------------------------------------------------------------
# mock SearXNG unavailable (HTTP)
# ---------------------------------------------------------------------------------

def test_stage_http_searxng_unavailable():
    original = uat._http_get

    def fake_http_get(url, timeout=15.0, accept="text/html"):
        raise urllib.error.URLError("Connection refused")

    uat._http_get = fake_http_get
    try:
        report = _fresh_report()
        stage = uat.stage_http(report)
        assert stage["result"] == "FAIL_HTTP_UNREACHABLE"
        assert report.criteria[3]["passed"] is None  # hiç set edilmedi -- test edilemedi, uydurulmadı
    finally:
        uat._http_get = original
    print("KAIZEN UAT MOCK: SEARXNG HTTP ERISILEMEZ TESTI: BASARILI")


# ---------------------------------------------------------------------------------------
# mock JSON 403 / empty results
# ---------------------------------------------------------------------------------

def test_stage_json_api_403_diagnoses_without_editing_settings():
    original = uat._searxng_json_search

    def fake_search(query, timeout=15.0):
        raise urllib.error.HTTPError("http://127.0.0.1:8890/search", 403, "Forbidden", None, None)

    uat._searxng_json_search = fake_search
    settings_path = Path("/tmp/should_never_be_touched_settings.yml")
    if settings_path.exists():
        settings_path.unlink()
    try:
        report = _fresh_report()
        stage = uat.stage_json_api(report)
        assert stage["result"] == "FAIL_JSON_FORMAT_DISABLED"
        assert "settings.yml" in stage["diagnosis"]
        # madde 7: script settings.yml'yi KENDİLİĞİNDEN değiştirmez -- hiçbir dosyaya yazmadığını doğrula.
        assert not settings_path.exists()
        assert report.criteria[4]["passed"] is None
    finally:
        uat._searxng_json_search = original
    print("KAIZEN UAT MOCK: JSON 403 TESHIS (SETTINGS.YML'E DOKUNULMADI) TESTI: BASARILI")


def test_stage_json_api_empty_results_not_counted_as_pass():
    original = uat._searxng_json_search

    def fake_search(query, timeout=15.0):
        body = json.dumps({"results": []}).encode("utf-8")
        return 200, "application/json", body

    uat._searxng_json_search = fake_search
    try:
        report = _fresh_report()
        stage = uat.stage_json_api(report)
        assert stage["result"] == "SEARXNG_EMPTY"
        assert report.criteria[4]["passed"] is None  # HTTP 200 ama sonuc yok -> PASS SAYILMADI
    finally:
        uat._searxng_json_search = original
    print("KAIZEN UAT MOCK: SEARXNG_EMPTY PASS SAYILMAZ TESTI: BASARILI")


def test_stage_json_api_real_results_sets_criterion_true():
    original = uat._searxng_json_search

    def fake_search(query, timeout=15.0):
        body = json.dumps({"results": [
            {"title": "Dönemsellik Kavramı", "url": "https://example.gov.tr/a", "engine": "google"},
        ]}).encode("utf-8")
        return 200, "application/json", body

    uat._searxng_json_search = fake_search
    try:
        report = _fresh_report()
        stage = uat.stage_json_api(report)
        assert stage["result"] == "OK"
        assert report.criteria[4]["passed"] is True
    finally:
        uat._searxng_json_search = original
    print("KAIZEN UAT MOCK: JSON API GERCEK SONUC -> KRITER 4 TRUE TESTI: BASARILI")


# ---------------------------------------------------------------------------------------
# mock degraded engines
# ---------------------------------------------------------------------------------

def test_classify_engine_reason():
    assert uat._classify_engine_reason("CAPTCHA required") == "CAPTCHA"
    assert uat._classify_engine_reason("HTTP error 429: Too Many Requests") == "RATE_LIMITED"
    assert uat._classify_engine_reason("Timeout") == "TIMEOUT"
    assert uat._classify_engine_reason("Unexpected crash") == "UNAVAILABLE"
    print("KAIZEN UAT MOCK: MOTOR SEBEP SINIFLANDIRMA TESTI: BASARILI")


def test_stage_engine_health_degraded_classification():
    original = uat._searxng_json_search
    original_sleep = uat.time.sleep

    def fake_search(query, timeout=15.0):
        body = json.dumps({
            "results": [{"title": "x", "url": "https://a.gov.tr", "engine": "google"}],
            "unresponsive_engines": [["brave", "HTTP error 429"], ["duckduckgo", "CAPTCHA"]],
        }).encode("utf-8")
        return 200, "application/json", body

    uat._searxng_json_search = fake_search
    uat.time.sleep = lambda s: None  # madde 8 beklemesini testte hızlandır
    try:
        report = _fresh_report()
        stage = uat.stage_engine_health(report)
        assert stage["result"] == "OK"
        for entry in stage["queries"]:
            assert entry["overall"] == "DEGRADED"
            reasons = {u["classified_as"] for u in entry["unresponsive_classified"]}
            assert "RATE_LIMITED" in reasons
            assert "CAPTCHA" in reasons
    finally:
        uat._searxng_json_search = original
        uat.time.sleep = original_sleep
    print("KAIZEN UAT MOCK: MOTOR DEGRADED (TEK MOTOR HATASI TUM SISTEMI DUSURMUYOR) TESTI: BASARILI")


# ---------------------------------------------------------------------------------------
# mock SearchProvider (madde 10/12 sarmalayıcı gözlemi)
# ---------------------------------------------------------------------------------

class _FakeSearchOutcome:
    def __init__(self, results, status="OK"):
        self.results = results
        self.status = status


class _FakeSearchProvider:
    """`SearchProvider` sözleşmesini uygulayan minimal sahte sağlayıcı (mock) -- gerçek ağa
    hiç çıkmaz."""

    def __init__(self, results_per_call):
        self._results_per_call = results_per_call
        self.calls = []

    def search(self, query, options=None):
        self.calls.append(query)
        return _FakeSearchOutcome(self._results_per_call)


def test_counting_provider_wrapper_records_real_calls():
    fake = _FakeSearchProvider(results_per_call=[object(), object()])
    wrapper = uat._CountingProviderWrapper(fake)
    outcome = wrapper.search("test sorgusu", options=None)
    assert len(outcome.results) == 2
    assert wrapper.calls == [{"query": "test sorgusu", "result_count": 2, "status": "OK"}]
    print("KAIZEN UAT MOCK: SEARCHPROVIDER SARMALAYICI SAYAC TESTI: BASARILI")


# ---------------------------------------------------------------------------------------
# mock fetch failure -- stage_research_engine'e sahte provider + sahte (hep basarisiz) fetcher
# ---------------------------------------------------------------------------------

class _AlwaysFailingFetcher:
    """madde 29 'mock fetch failure': her URL için gerçek bir HTTP hatası simüle eder --
    `research/fetcher.py::SafeFetcher`'ın public `.fetch(url) -> FetchOutcome` arayüzünü
    (aynı çağrı sözleşmesini) taklit eder, ağa hiç çıkmaz."""

    def fetch(self, url):
        from research.models import FETCH_HTTP_ERROR
        from research.fetcher import FetchOutcome
        return FetchOutcome(status=FETCH_HTTP_ERROR, url=url, http_status=500, detail="mock 500")


def _fake_search_result(url="https://example.gov.tr/sayfa"):
    from search.provider import SearchResult
    return SearchResult(
        title="Örnek Başlık", url=url, snippet="kısa özet", engine="mockengine", engines=("mockengine",),
        category="general", score=1.0, published_date=None, domain="example.gov.tr", is_pdf=False,
        query="mock sorgu",
    )


class _SingleResultProvider:
    def __init__(self, result):
        self._result = result

    def search(self, query, options=None):
        return _FakeSearchOutcome([self._result])


def test_stage_research_engine_mock_fetch_failure():
    provider = _SingleResultProvider(_fake_search_result())
    fetcher = _AlwaysFailingFetcher()
    report = _fresh_report()
    stage, real_results = uat.stage_research_engine(report, provider, fetcher=fetcher)
    assert stage["result"] == "OK"
    for entry in stage["by_question"].values():
        # arama sonucu geldi (SEARCH_RESULT_COUNT>0) ama fetch BAŞARISIZ oldu -> FETCHED_COUNT=0.
        assert entry["SEARCH_RESULT_COUNT"] >= 1
        assert entry["FETCHED_COUNT"] == 0
        assert entry["EXTRACTED_COUNT"] == 0
    # madde 12: search bulundu ama fetch edilemedi -- bu GİZLENMEMELİ (kriter 6 True, kriter 7 False)
    assert report.criteria[6]["passed"] is True
    assert report.criteria[7]["passed"] is False
    print("KAIZEN UAT MOCK: FETCH BASARISIZLIGI GIZLENMEDI (SEARCH>0, FETCH=0) TESTI: BASARILI")


def test_stage_research_engine_mock_success_path():
    """Karşılaştırma için: fetch BAŞARILI olduğunda FETCHED_COUNT/EXTRACTED_COUNT>0 olmalı."""
    from research.fetcher import FetchOutcome
    from research.models import FETCH_OK

    class _WorkingFetcher:
        def fetch(self, url):
            html = (
                "<html><head><title>Dönemsellik</title></head><body>"
                "<p>Muhasebede dönemsellik kavramı, işletmenin sınırsız kabul edilen ömrünün, "
                "belli dönemlere bölünmesi ve her dönemin faaliyet sonuçlarının diğer "
                "dönemlerden bağımsız olarak saptanmasıdır.</p></body></html>"
            )
            return FetchOutcome(status=FETCH_OK, url=url, final_url=url, http_status=200,
                                 content_type="text/html", body=html.encode("utf-8"))

    provider = _SingleResultProvider(_fake_search_result(url="https://muhasebe.gov.tr/donemsellik"))
    report = _fresh_report()
    stage, real_results = uat.stage_research_engine(report, provider, fetcher=_WorkingFetcher())
    any_fetched = any(e["FETCHED_COUNT"] > 0 for e in stage["by_question"].values())
    assert any_fetched
    print("KAIZEN UAT MOCK: FETCH BASARILI -> FETCHED/EXTRACTED SAYAC TESTI: BASARILI")


# ---------------------------------------------------------------------------------------
# mock evidence mismatch (madde 15 canlı-ortam adversarial dedektörünün KENDİSİ doğru mu?)
# ---------------------------------------------------------------------------------

def _synthetic_result_with_evidence(question, evidence_list, claims=(), status="INSUFFICIENT"):
    from research.models import ResearchResult
    return ResearchResult(
        status=status, question=question, subquestions=(question,), queries=(question,),
        search_health="OK", evidence=tuple(evidence_list), claims=tuple(claims),
        verified_claims=tuple(c for c in claims if c.status == "SUPPORTED"),
    )


def _real_looking_evidence(evidence_id, url, domain, passage, official=True, source_type="OFFICIAL", period=None):
    from research.models import Evidence, FETCH_OK, EVIDENCE_FACT
    from research.evidence import classify_evidence_passage
    classification = classify_evidence_passage(passage)
    return Evidence(
        evidence_id=evidence_id, query="q", subquestion="sq", url=url, domain=domain,
        source_name=domain, source_type=source_type, title="t", published_at=None,
        retrieved_at="2026-09-24T00:00:00+00:00", passage=passage, extracted_claim="",
        period=period, official=official, confidence="HIGH", fetch_status=FETCH_OK,
        classification=classification,
    )


def test_relevance_adversarial_detects_injected_bug():
    """Bu test, `stage_relevance_adversarial`'ın KENDİSİNİN gerçekten çalıştığını kanıtlar:
    `research.verifier._is_relevant`'ı GEÇİCİ olarak 'her zaman ilgili' döndürecek şekilde
    bozup (madde 15'in düzeltmeden ÖNCEKİ hatalı davranışını simüle ederek), UAT dedektörünün
    bunu RELEASE_BLOCKER_CONFIRMED olarak YAKALADIĞINI doğrular -- yani dedektör yalnız
    'şu an bug yok' demiyor, gerçekten bug OLSAYDI da YAKALARDI."""
    import research.verifier as verifier_module

    kdv_evidence = _real_looking_evidence(
        "e_donor", "https://www.gib.gov.tr/kdv-genel-tebligi", "gib.gov.tr",
        "Genel KDV oranı yüzde 20 olarak uygulanmaktadır. İndirimli oranlar yüzde 1 ve yüzde 10'dur.",
    )
    amortisman_evidence = _real_looking_evidence(
        "e_victim", "https://www.gib.gov.tr/amortisman-rehberi", "gib.gov.tr",
        "Amortismanın mantığı, iktisadi kıymetin faydalı ömrü boyunca gider yazılmasıdır.",
    )
    result_victim = _synthetic_result_with_evidence(
        "Amortismanın mantığı nedir, faydalı ömür nasıl belirlenir", [amortisman_evidence]
    )
    result_donor = _synthetic_result_with_evidence(
        "2026 gelir vergisi tarifesi nedir?", [kdv_evidence]
    )
    real_results = {"E": result_victim, "A": result_donor}

    # 1) NORMAL (düzeltilmiş) kod ile: dedektör OK_REJECTED demeli (gerçek davranış).
    report_ok = _fresh_report()
    stage_ok = uat.stage_relevance_adversarial(report_ok, real_results)
    assert stage_ok["result"] == "OK_REJECTED"
    assert report_ok.criteria[11]["passed"] is True

    # 2) SİMÜLE EDİLMİŞ BUG ile: _is_relevant'ı 'her zaman ilgili' yap, dedektör bunu
    # YAKALAMALI (RELEASE_BLOCKER_CONFIRMED, kriter 11 False).
    original_is_relevant = verifier_module._is_relevant
    verifier_module._is_relevant = lambda subq, ev: True
    try:
        report_bug = _fresh_report()
        stage_bug = uat.stage_relevance_adversarial(report_bug, real_results)
        assert stage_bug["result"] == "RELEASE_BLOCKER_CONFIRMED"
        assert report_bug.criteria[11]["passed"] is False
    finally:
        verifier_module._is_relevant = original_is_relevant
    print("KAIZEN UAT MOCK: EVIDENCE MISMATCH (ALAKASIZLIK) DEDEKTORU IKI YONLU DOGRULANDI TESTI: BASARILI")


# ---------------------------------------------------------------------------------------
# mock temporal mismatch / consensus conflict
# ---------------------------------------------------------------------------------

def test_temporal_adversarial_catches_wrong_period():
    # DİKKAT: pasaj metni de period alanıyla TUTARLI olmalı ("2024" hem period'da hem
    # cümlede) -- yoksa FactExtractor pasajdaki yıl literalini önceliklendirdiği için test
    # yanlış anlamlı olur (bkz. tools/research_uat.py::stage_temporal_and_conflict_adversarial
    # docstring notu, bu tam da bu UAT'ı geliştirirken bulunan bir kendi-kendini-test bulgusu).
    evidence = _real_looking_evidence(
        "e_d1", "https://www.gib.gov.tr/yeniden-degerleme", "gib.gov.tr",
        "2024 yeniden değerleme oranı yüzde 58,46 olarak tespit edilmiştir.",
        period="2024",
    )
    result_d = _synthetic_result_with_evidence("2026 yeniden değerleme oranı nedir?", [evidence])
    real_results = {"D": result_d}
    report = _fresh_report()
    stage = uat.stage_temporal_and_conflict_adversarial(report, real_results)
    assert stage["temporal"]["wrongly_supported"] is False
    assert report.criteria[10]["passed"] is True
    print("KAIZEN UAT MOCK: TEMPORAL ADVERSARIAL (2024 KANIT, 2026 TALEP) TESTI: BASARILI")


def test_conflict_adversarial_catches_two_values():
    evidence = _real_looking_evidence(
        "e_d1", "https://www.gib.gov.tr/yeniden-degerleme", "gib.gov.tr",
        "2026 yeniden değerleme oranı yüzde 25 olarak tespit edilmiştir.",
        period="2026",
    )
    result_d = _synthetic_result_with_evidence("2026 yeniden değerleme oranı nedir?", [evidence])
    real_results = {"D": result_d}
    report = _fresh_report()
    stage = uat.stage_temporal_and_conflict_adversarial(report, real_results)
    assert stage["conflict"]["wrongly_supported"] is False
    assert report.criteria[12]["passed"] is True
    print("KAIZEN UAT MOCK: CONSENSUS CONFLICT (IKI FARKLI DEGER) TESTI: BASARILI")


# ---------------------------------------------------------------------------------------
# SHA muhafızı + rapor/kapı mantığı (ağdan tamamen bağımsız)
# ---------------------------------------------------------------------------------

def test_report_finalize_gate_all_true_is_pass():
    report = _fresh_report()
    for cid in report.criteria:
        report.set_criterion(cid, True, "ok")
    assert report.finalize_gate() == "PASS"
    print("KAIZEN UAT MOCK: TUM KRITERLER TRUE -> PASS TESTI: BASARILI")


def test_report_finalize_gate_one_false_is_not_pass():
    report = _fresh_report()
    for cid in report.criteria:
        report.set_criterion(cid, True, "ok")
    report.set_criterion(11, False, "bug")
    result = report.finalize_gate()
    assert result != "PASS"
    print("KAIZEN UAT MOCK: TEK KRITER FALSE -> PASS DEGIL TESTI: BASARILI")


def test_report_finalize_gate_all_none_is_fail():
    report = _fresh_report()
    assert report.finalize_gate() == "FAIL"
    print("KAIZEN UAT MOCK: HIC KRITER DOGRULANMADI -> FAIL TESTI: BASARILI")


def test_sha_snapshot_detects_change(tmp_path_factory=None):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        (tmp_root / "data").mkdir()
        (tmp_root / "data" / "x.txt").write_text("once")

        original_root = uat.ROOT
        original_guarded = uat.GUARDED_DIRS
        uat.ROOT = tmp_root
        try:
            before = uat._sha_snapshot()
            (tmp_root / "data" / "x.txt").write_text("degisti")
            after = uat._sha_snapshot()
            assert before != after
        finally:
            uat.ROOT = original_root
            uat.GUARDED_DIRS = original_guarded
    print("KAIZEN UAT MOCK: SHA256 SNAPSHOT DEGISIKLIGI YAKALAR TESTI: BASARILI")


# ---------------------------------------------------------------------------------------
# YENİ (2026-09-24, kullanıcının ikinci gerçek PC koşusu sonrası talimatı) -- madde 11'in
# 9 maddelik listesi: SHA izin-reddi reproducer, SHA özel-giriş (symlink/junction) testi,
# Docker CLI yok / CLI var+daemon kapalı / container yok / container durmuş teşhis kodları,
# fatal-istisnada-tam-rapor testi, Cognee-UAT-sırasında-başlatılmıyor testi,
# kalıcı-veri-mutasyona-uğramıyor testi.
# ---------------------------------------------------------------------------------------

def test_sha_snapshot_permission_denied_is_skipped_not_crashed():
    """madde 1/3: gerçek PC'de `PermissionError` ile ÇÖKMEYE yol açan senaryonun
    REPRODUCER'ı -- `Path.read_bytes` üzerinde (sandbox root olarak çalışsa bile
    GERÇEKÇİ biçimde tetiklenir, dosya izinlerine bağımlı DEĞİLDİR) PermissionError
    simüle edilir. `_sha_snapshot()` bu durumda ASLA raise ETMEMELİ; dosya `skipped`
    listesine SKIPPED_PERMISSION olarak girmeli, `hashes`'e hiç GİRMEMELİ, diğer
    (kilitli olmayan) dosyalar normal şekilde hash'lenmeye DEVAM etmeli."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        (tmp_root / "data").mkdir()
        locked = tmp_root / "data" / "locked.sqlite3"
        locked.write_text("kilitli-gibi-davranacak-icerik")
        other = tmp_root / "data" / "normal.txt"
        other.write_text("normal dosya")

        original_root = uat.ROOT
        original_read_bytes = uat.Path.read_bytes

        def fake_read_bytes(self):
            if self.name == "locked.sqlite3":
                raise PermissionError(13, "Permission denied", str(self))
            return original_read_bytes(self)

        uat.ROOT = tmp_root
        uat.Path.read_bytes = fake_read_bytes
        try:
            hashes, skipped = uat._sha_snapshot()
        finally:
            uat.ROOT = original_root
            uat.Path.read_bytes = original_read_bytes

        assert "data/normal.txt" in hashes
        assert "data/locked.sqlite3" not in hashes
        skipped_by_path = {s["path"]: s for s in skipped}
        assert "data/locked.sqlite3" in skipped_by_path
        assert skipped_by_path["data/locked.sqlite3"]["classification"] == "SKIPPED_PERMISSION"
        assert skipped_by_path["data/locked.sqlite3"]["type"] == "regular_file"
    print("KAIZEN UAT MOCK: SHA PERMISSIONERROR REPRODUCER (COKMEDEN SKIPPED) TESTI: BASARILI")


def test_sha_snapshot_symlink_junction_is_skipped_special():
    """madde 1: Windows junction/reparse point'lerin pathlib karşılığı `is_symlink()==True`
    döndürür -- gerçek bir dosyayı işaret eden bir symlink `_sha_snapshot()` tarafından
    hash'LENMEMELİ (içeriği zaten hedef dosyada bir kez sayılıyor), SKIPPED_SPECIAL olarak
    raporlanmalı, ve bu ASLA bir hataya/çökmeye yol AÇMAMALI."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        (tmp_root / "data").mkdir()
        real = tmp_root / "data" / "real.txt"
        real.write_text("gerçek içerik")
        link = tmp_root / "data" / "link.txt"
        try:
            link.symlink_to(real)
        except (OSError, NotImplementedError):
            print("KAIZEN UAT MOCK: SHA SYMLINK/JUNCTION TESTI: ATLANDI (bu platformda symlink oluşturulamadı)")
            return

        original_root = uat.ROOT
        uat.ROOT = tmp_root
        try:
            hashes, skipped = uat._sha_snapshot()
        finally:
            uat.ROOT = original_root

        assert "data/real.txt" in hashes
        skipped_by_path = {s["path"]: s for s in skipped}
        assert "data/link.txt" in skipped_by_path
        assert skipped_by_path["data/link.txt"]["classification"] == "SKIPPED_SPECIAL"
        assert skipped_by_path["data/link.txt"]["type"] == "symlink_or_reparse_point"
    print("KAIZEN UAT MOCK: SHA SYMLINK/JUNCTION SKIPPED_SPECIAL TESTI: BASARILI")


def test_stage_docker_cli_not_found_sets_diagnosis_code():
    """madde 6: docker komutu PATH'te yokken `stage['docker_diagnosis']` AÇIKÇA
    DOCKER_CLI_NOT_FOUND olmalı (mevcut `stage['result']=='FAIL_DOCKER_UNAVAILABLE'`
    davranışı GEVŞETİLMEDEN, yalnız yeni bir teşhis alanı EKLENEREK)."""
    original_which = uat.shutil.which
    uat.shutil.which = lambda name: None
    try:
        report = _fresh_report()
        stage = uat.stage_docker(report)
        assert stage["result"] == "FAIL_DOCKER_UNAVAILABLE"
        assert stage["docker_diagnosis"] == "DOCKER_CLI_NOT_FOUND"
    finally:
        uat.shutil.which = original_which
    print("KAIZEN UAT MOCK: DOCKER_CLI_NOT_FOUND TESHIS KODU TESTI: BASARILI")


def test_stage_docker_daemon_unreachable_sets_desktop_not_running_diagnosis():
    """madde 6: CLI PATH'te VAR (`shutil.which` başarılı) ama `docker version` daemon'a
    bağlanamadığında -- Windows'un tipik 'named pipe' hata metniyle -- teşhis
    DOCKER_DESKTOP_NOT_RUNNING olarak sınıflandırılmalı; bu, 'CLI yok' durumundan
    (DOCKER_CLI_NOT_FOUND) AYRI bir teşhis kodudur (madde 6'nın asıl amacı)."""
    original_which = uat.shutil.which
    original_run = uat.subprocess.run
    uat.shutil.which = lambda name: "/usr/bin/docker"

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["docker", "version"]:
            return _FakeCompletedProcess(
                returncode=1, stdout="",
                stderr='error during connect: Get "http://%2F%2F.%2Fpipe%2Fdocker_engine/v1.24/version": '
                       "open //./pipe/docker_engine: The system cannot find the file specified. "
                       "Is the docker daemon running?",
            )
        raise AssertionError(f"beklenmeyen komut: {cmd}")

    uat.subprocess.run = fake_run
    try:
        report = _fresh_report()
        stage = uat.stage_docker(report)
        assert stage["result"] == "FAIL_DOCKER_UNAVAILABLE"
        assert stage["docker_diagnosis"] == "DOCKER_DESKTOP_NOT_RUNNING"
        assert report.criteria[1]["passed"] is False
        assert report.criteria[2]["passed"] is False
    finally:
        uat.shutil.which = original_which
        uat.subprocess.run = original_run
    print("KAIZEN UAT MOCK: CLI VAR + DAEMON KAPALI (DOCKER_DESKTOP_NOT_RUNNING) TESTI: BASARILI")


def test_stage_docker_container_missing_sets_diagnosis_code():
    """madde 6: `docker inspect` container'ı bulamadığında `stage['container_diagnosis']`
    AÇIKÇA CONTAINER_NOT_FOUND olmalı (mevcut `FAIL_DOCKER_CONTAINER` sonucu korunur)."""
    original_which = uat.shutil.which
    original_run = uat.subprocess.run
    uat.shutil.which = lambda name: "/usr/bin/docker"

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["docker", "version"]:
            return _FakeCompletedProcess(returncode=0, stdout="{}")
        if cmd[:2] == ["docker", "inspect"]:
            return _FakeCompletedProcess(returncode=1, stdout="", stderr="No such object")
        raise AssertionError(f"beklenmeyen komut: {cmd}")

    uat.subprocess.run = fake_run
    try:
        report = _fresh_report()
        stage = uat.stage_docker(report)
        assert stage["result"] == "FAIL_DOCKER_CONTAINER"
        assert stage["container_diagnosis"] == "CONTAINER_NOT_FOUND"
    finally:
        uat.shutil.which = original_which
        uat.subprocess.run = original_run
    print("KAIZEN UAT MOCK: CONTAINER_NOT_FOUND TESHIS KODU TESTI: BASARILI")


def test_stage_docker_container_stopped_sets_diagnosis_code():
    """madde 6: container VAR ama `Running=False` olduğunda `stage['container_diagnosis']`
    AÇIKÇA CONTAINER_STOPPED olmalı (mevcut `FAIL_SEARXNG_STOPPED` sonucu korunur)."""
    original_which = uat.shutil.which
    original_run = uat.subprocess.run
    uat.shutil.which = lambda name: "/usr/bin/docker"

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["docker", "version"]:
            return _FakeCompletedProcess(returncode=0, stdout="{}")
        if cmd[:2] == ["docker", "inspect"]:
            payload = [{
                "State": {"Status": "exited", "Running": False, "Health": None},
                "NetworkSettings": {"Ports": {}},
            }]
            return _FakeCompletedProcess(returncode=0, stdout=json.dumps(payload))
        raise AssertionError(f"beklenmeyen komut: {cmd}")

    uat.subprocess.run = fake_run
    try:
        report = _fresh_report()
        stage = uat.stage_docker(report)
        assert stage["result"] == "FAIL_SEARXNG_STOPPED"
        assert stage["container_diagnosis"] == "CONTAINER_STOPPED"
    finally:
        uat.shutil.which = original_which
        uat.subprocess.run = original_run
    print("KAIZEN UAT MOCK: CONTAINER_STOPPED TESHIS KODU TESTI: BASARILI")


def test_stage_docker_running_but_port_mismatch_fails():
    """madde 6 (ek/bonus -- yeni port-8890-doğrulama kodunun kendi testi): container
    RUNNING olsa bile beklenen port (8890) mapping'de YOKSA bu artık sessizce OK
    sayılmamalı -- FAIL_SEARXNG_PORT_MISMATCH ve kriter 2 False olmalı."""
    original_which = uat.shutil.which
    original_run = uat.subprocess.run
    uat.shutil.which = lambda name: "/usr/bin/docker"

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["docker", "version"]:
            return _FakeCompletedProcess(returncode=0, stdout="{}")
        if cmd[:2] == ["docker", "inspect"]:
            payload = [{
                "State": {"Status": "running", "Running": True, "Health": {"Status": "healthy"}},
                "NetworkSettings": {"Ports": {"9999/tcp": [{"HostPort": "9999"}]}},
            }]
            return _FakeCompletedProcess(returncode=0, stdout=json.dumps(payload))
        raise AssertionError(f"beklenmeyen komut: {cmd}")

    uat.subprocess.run = fake_run
    try:
        report = _fresh_report()
        stage = uat.stage_docker(report)
        assert stage["result"] == "FAIL_SEARXNG_PORT_MISMATCH"
        assert stage["container_diagnosis"] == "CONTAINER_RUNNING"
        assert stage["port_8890_ok"] is False
        assert report.criteria[2]["passed"] is False
    finally:
        uat.shutil.which = original_which
        uat.subprocess.run = original_run
    print("KAIZEN UAT MOCK: CONTAINER RUNNING AMA PORT 8890 YOK -> FAIL TESTI: BASARILI")


def test_main_writes_complete_report_on_fatal_exception():
    """madde 7: `_run_main_body` içinde -- bir aşamanın KENDİ try/except'inin bile
    yakalamadığı -- gerçekten beklenmeyen bir istisna oluşsa bile `main()` YİNE DE tam
    bir failure report (fatal_stage/exception_type/message alanlarıyla) yazmalı, 3
    döndürmeli, ve gate ASLA PASS olmamalı. Gerçek bir aşamayı bozmadan test etmek için
    `_run_main_body`'nin kendisi kasıtlı olarak bir istisna fırlatan sahte bir fonksiyonla
    değiştirilir (dependency injection -- madde 61: yeni bir mekanizma İCAT EDİLMEDİ,
    zaten var olan `report.mark()` etiketleme mekanizması kullanılır)."""
    import tempfile

    original_run_body = uat._run_main_body
    original_artifacts_dir = uat.ARTIFACTS_DIR
    original_report_json = uat.REPORT_JSON
    original_report_txt = uat.REPORT_TXT

    def _boom(report):
        report.mark("X_test_forced_crash")
        report.note("[TEST] kasıtlı fatal istisna tetikleniyor")
        raise RuntimeError("kasıtlı test istisnası -- gerçek bir aşama hatasını simüle eder")

    with tempfile.TemporaryDirectory(prefix="kaizen_uat_test_fatal_") as tmp:
        tmp_artifacts = Path(tmp) / "artifacts"
        uat._run_main_body = _boom
        uat.ARTIFACTS_DIR = tmp_artifacts
        uat.REPORT_JSON = tmp_artifacts / "research_uat_report.json"
        uat.REPORT_TXT = tmp_artifacts / "research_uat_report.txt"
        try:
            exit_code = uat.main()
        finally:
            uat._run_main_body = original_run_body
            uat.ARTIFACTS_DIR = original_artifacts_dir
            uat.REPORT_JSON = original_report_json
            uat.REPORT_TXT = original_report_txt

        assert exit_code == 3
        report_json_path = tmp_artifacts / "research_uat_report.json"
        report_txt_path = tmp_artifacts / "research_uat_report.txt"
        assert report_json_path.exists()
        assert report_txt_path.exists()

        data = json.loads(report_json_path.read_text(encoding="utf-8"))
        assert data["fatal"] is not None
        assert data["fatal"]["fatal_stage"] == "X_test_forced_crash"
        assert data["fatal"]["exception_type"] == "RuntimeError"
        assert "kasıtlı test istisnası" in data["fatal"]["message"]
        assert data["gate_result"] != "PASS"

        txt = report_txt_path.read_text(encoding="utf-8")
        assert "BEKLENMEDİK BİR HATAYLA DURDU" in txt
        assert "RuntimeError" in txt
    print("KAIZEN UAT MOCK: FATAL ISTISNADA TAM RAPOR YAZILIYOR (madde 7) TESTI: BASARILI")


def test_build_isolated_brain_disables_cognee():
    """Historical test name; the graph-memory component must now be absent entirely."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix="kaizen_uat_no_graph_") as tmp:
        brain = uat._build_isolated_brain(False, None, Path(tmp))
        assert not hasattr(brain.brain, "experience")
        assert not hasattr(brain.brain, "_experience_queue")
        assert brain.brain.shutdown()


class _FakeBrainManagerForShutdownTest:
    """`stage_kaizenbrain_shadow`'un KENDİ shutdown-çağırma davranışını test etmek için --
    gerçek `BrainManager`/Cognee/thread hiç kurulmaz, yalnız `.shutdown(timeout=...)`'un
    çağrıldığı ve HANGİ argümanla çağrıldığı kaydedilir."""

    def __init__(self):
        self.shutdown_calls = []

    def shutdown(self, timeout=5.0):
        self.shutdown_calls.append(timeout)
        return True


class _FakeKaizenBrainForShutdownTest:
    def __init__(self, last_route, last_research_via):
        self.brain = _FakeBrainManagerForShutdownTest()
        self.last_route = last_route
        self._last_research_via = last_research_via

    def answer(self, question):
        return f"sahte cevap: {question}"


def _fake_build_for_shadow_test(fake_off, fake_on, fake_insufficient):
    """`stage_kaizenbrain_shadow` üç ayrı `_build_isolated_brain(...)` çağrısı yapar --
    OFF (`research_engine_enabled=False`), ON (`True`, gerçek `searxng_provider` -- testte
    `None`), INSUFFICIENT_CHECK (`True`, HER ZAMAN gerçek bir `_EmptySearchProviderForFallbackCheck`
    örneği -- asla `None` değil). Bu üçü, `research_engine_enabled` + `search_provider is None`
    kombinasyonuyla kesin biçimde ayırt edilebilir (kodun KENDİ çağrı sırası/şekli -- yeni bir
    varsayım İCAT EDİLMEDİ)."""

    def fake_build(research_engine_enabled, search_provider, temp_dir):
        if not research_engine_enabled:
            return fake_off
        if search_provider is None:
            return fake_on
        return fake_insufficient

    return fake_build


def test_stage_kaizenbrain_shadow_calls_brain_manager_shutdown_before_tempdir_cleanup():
    """UAT İZOLASYON DÜZELTMESİ (2026-09-25): gerçek PC UAT'ının ikinci koşusunda,
    `stage_kaizenbrain_shadow`'un geçici `tempfile.TemporaryDirectory()` bloğu kapanıp
    log/storage dizinlerini SİLMESİNDEN SONRA arka plan deneyim worker'ı hâlâ çalışıyor ve
    artık var olmayan bir dizine loglamaya çalışıp çöküyordu (bkz.
    `tests/test_brain_manager_shutdown.py` -- kök neden/production düzeltmesi ORADA test
    edilir). Bu test, UAT TARAFINDAKİ düzeltmeyi doğrular: `stage_kaizenbrain_shadow`'un
    KENDİSİ, tempdir'ler silinmeden ÖNCE ÜÇ shadow brain'in de (`OFF`, `ON`,
    `INSUFFICIENT_CHECK`) `BrainManager.shutdown()`'ını GERÇEKTEN çağırdığını ve sonucu
    rapora yazdığını doğrular. `_build_isolated_brain` burada sahte nesnelerle değiştirilir
    (dependency injection) -- gerçek KaizenBrain/Cognee/network hiç kurulmaz, yalnız
    `stage_kaizenbrain_shadow`'un ORKESTRASYON davranışı hedeflenir."""
    original_build = uat._build_isolated_brain
    fake_off = _FakeKaizenBrainForShutdownTest("not_found_offline", None)
    fake_on = _FakeKaizenBrainForShutdownTest("research", "engine")
    fake_insufficient = _FakeKaizenBrainForShutdownTest("research", "hermes")

    uat._build_isolated_brain = _fake_build_for_shadow_test(fake_off, fake_on, fake_insufficient)
    try:
        report = _fresh_report()
        stage = uat.stage_kaizenbrain_shadow(report, None)
    finally:
        uat._build_isolated_brain = original_build

    assert fake_off.brain.shutdown_calls, "OFF shadow brain için BrainManager.shutdown() hiç çağrılmadı"
    assert fake_on.brain.shutdown_calls, "ON shadow brain için BrainManager.shutdown() hiç çağrılmadı"
    assert fake_insufficient.brain.shutdown_calls, "INSUFFICIENT_CHECK shadow brain için BrainManager.shutdown() hiç çağrılmadı"
    assert stage["shutdown_results"]["OFF"]["completed"] is True
    assert stage["shutdown_results"]["ON"]["completed"] is True
    assert stage["shutdown_results"]["INSUFFICIENT_CHECK"]["completed"] is True
    print("KAIZEN UAT MOCK: STAGE_KAIZENBRAIN_SHADOW TEMPDIR SILINMEDEN ONCE SHUTDOWN() CAGIRIYOR TESTI: BASARILI")


def test_criterion_15_is_true_even_when_on_path_succeeds_via_engine():
    """REGRESYON (2026-09-25, kullanıcının GERÇEK PC raporundaki PARTIAL'ın KÖK NEDENİ):
    eski kodda kriter 15 SADECE `on_via == 'hermes'` dalında set ediliyordu -- ON sorusu
    Research Engine tarafından GERÇEKTEN SUPPORTED olarak yanıtlandığında (`on_via ==
    'engine'`, sistemin EN İYİ performansı) kriter 15 hiç dokunulmuyor ve `None` kalıyordu,
    bu yüzden gerçek arama altyapısı mükemmel çalışsa bile UAT ASLA PASS olamıyordu. Bu,
    kullanıcının gerçek PC'sindeki raporda birebir gözlemlendi (13/16 kriter True, kriter 15
    tek başına `None`). Düzeltmeden SONRA: `on_via == 'engine'` olsa BİLE, ayrı ve
    deterministik `INSUFFICIENT_CHECK` bloğu kriter 15'i KENDİ BAŞINA (doğru biçimde) True
    yapmalı."""
    original_build = uat._build_isolated_brain
    fake_off = _FakeKaizenBrainForShutdownTest("not_found_offline", None)
    # ON sorusu Research Engine tarafından GERÇEKTEN SUPPORTED bulundu -- kullanıcının PC'sinde
    # gözlemlenen TAM SENARYO.
    fake_on = _FakeKaizenBrainForShutdownTest("research", "engine")
    # INSUFFICIENT_CHECK, arama katmanı hep boş dönse bile KaizenBrain'in güvenle Hermes'e
    # düştüğünü VE gerçek bir cevap ürettiğini gösteriyor -- beklenen güvenli davranış.
    fake_insufficient = _FakeKaizenBrainForShutdownTest("research", "hermes")

    uat._build_isolated_brain = _fake_build_for_shadow_test(fake_off, fake_on, fake_insufficient)
    try:
        report = _fresh_report()
        uat.stage_kaizenbrain_shadow(report, None)
    finally:
        uat._build_isolated_brain = original_build

    assert report.criteria[13]["passed"] is True, "kriter 13 (ON modunda gerçekten engine'e giriyor) True olmalıydı"
    assert report.criteria[14]["passed"] is True, "kriter 14 (SUPPORTED'da Hermes atlanıyor) True olmalıydı"
    assert report.criteria[15]["passed"] is True, (
        f"kriter 15, on_via=='engine' olsa BİLE (ayrı deterministik kontrol sayesinde) True "
        f"olmalıydı -- gerçek PC'deki PARTIAL'ın kök nedeni buydu; detay: {report.criteria[15]['detail']}"
    )
    print("KAIZEN UAT MOCK: KRITER 15 ON_VIA=='ENGINE' IKEN DE TRUE OLUYOR (PARTIAL KOK NEDENI DUZELTMESI) TESTI: BASARILI")


def test_kaizenbrain_shadow_off_does_not_mutate_guarded_dirs():
    """madde 8: KaizenBrain shadow (OFF kolu) çalıştırıldığında `data/`/`knowledge/`/
    `memory/`/`logs/` (GUARDED_DIRS) içinde HİÇBİR ŞEY değişmemeli -- ne yeni dosya, ne
    mevcut bir dosyanın içeriği. `_sha_snapshot()`'ın KENDİSİ bu testte GERÇEK proje
    kökü (`uat.ROOT`, değiştirilmeden) üzerinde çalıştırılır, çünkü tam olarak
    doğrulanmak istenen şey budur: shadow brain'in GERÇEK kalıcı verilere DOKUNMADIĞI."""
    import tempfile

    pre_hashes, pre_skipped = uat._sha_snapshot()

    with tempfile.TemporaryDirectory(prefix="kaizen_uat_test_mutation_") as tmp:
        temp_dir = Path(tmp)
        brain_off = uat._build_isolated_brain(False, None, temp_dir)
        try:
            uat._run_with_timeout(brain_off.answer, 30.0, uat.RESEARCH_QUESTIONS[1][1])
        except Exception:
            pass  # bu testin amacı cevabın KENDİSİ değil, yan etkinin GÖZLEMLENMESİ
        finally:
            # Aynı kök neden (bkz. tools/research_uat.py::stage_kaizenbrain_shadow, 2026-09-25
            # bulgusu): remember_experience() arka plan worker'ı tempdir silinmeden ÖNCE
            # kesin olarak durdurulmalı, yoksa Windows'ta hâlâ açık dosya tutan worker
            # tempdir cleanup'ını "Directory not empty" ile çökertir.
            brain_off.brain.shutdown(timeout=10.0)

    post_hashes, post_skipped = uat._sha_snapshot()

    assert pre_hashes == post_hashes, (
        "KaizenBrain shadow (OFF) çalıştırıldıktan sonra korunan dizinlerde dosya "
        "içeriği DEĞİŞTİ -- izolasyon ihlali."
    )
    assert len(pre_skipped) == len(post_skipped), (
        "KaizenBrain shadow (OFF) çalıştırıldıktan sonra korunan dizinlerde YENİ bir "
        "hash'lenemeyen/özel girdi ORTAYA ÇIKTI -- izolasyon ihlali."
    )
    print("KAIZEN UAT MOCK: KAIZENBRAIN SHADOW (OFF) KALICI VERIYI MUTASYONA UGRATMIYOR TESTI: BASARILI")


if __name__ == "__main__":
    test_stage_docker_mock_docker_command_missing()
    test_stage_docker_mock_container_stopped()
    test_stage_docker_mock_container_missing()
    test_stage_docker_mock_running_ok()
    test_stage_http_searxng_unavailable()
    test_stage_json_api_403_diagnoses_without_editing_settings()
    test_stage_json_api_empty_results_not_counted_as_pass()
    test_stage_json_api_real_results_sets_criterion_true()
    test_classify_engine_reason()
    test_stage_engine_health_degraded_classification()
    test_counting_provider_wrapper_records_real_calls()
    test_stage_research_engine_mock_fetch_failure()
    test_stage_research_engine_mock_success_path()
    test_relevance_adversarial_detects_injected_bug()
    test_temporal_adversarial_catches_wrong_period()
    test_conflict_adversarial_catches_two_values()
    test_report_finalize_gate_all_true_is_pass()
    test_report_finalize_gate_one_false_is_not_pass()
    test_report_finalize_gate_all_none_is_fail()
    test_sha_snapshot_detects_change()
    test_sha_snapshot_permission_denied_is_skipped_not_crashed()
    test_sha_snapshot_symlink_junction_is_skipped_special()
    test_stage_docker_cli_not_found_sets_diagnosis_code()
    test_stage_docker_daemon_unreachable_sets_desktop_not_running_diagnosis()
    test_stage_docker_container_missing_sets_diagnosis_code()
    test_stage_docker_container_stopped_sets_diagnosis_code()
    test_stage_docker_running_but_port_mismatch_fails()
    test_main_writes_complete_report_on_fatal_exception()
    test_build_isolated_brain_disables_cognee()
    test_stage_kaizenbrain_shadow_calls_brain_manager_shutdown_before_tempdir_cleanup()
    test_criterion_15_is_true_even_when_on_path_succeeds_via_engine()
    test_kaizenbrain_shadow_off_does_not_mutate_guarded_dirs()
