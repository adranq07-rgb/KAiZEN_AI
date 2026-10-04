"""KAIZEN — BÜYÜK İŞ EMRİ #2, Faz 9-10 (madde 10, 34): Research Query Planner'ın ≥20
vakalık testi. Ölçülen boyutlar (madde 34): doğru alt-sorular, gereksiz alt-soru,
eksik kritik alt-soru, uydurma fact (hallucination), yinelenen sorgu."""
from datetime import date

from research.planner import build_plan
from research.models import ResearchPlan


_TODAY = date(2026, 9, 24)

# (soru, beklenen_topic, beklenen_period, min_subq, sgk_domain_bekleniyor_mu)
CASES = [
    ("2026 asgari ücret tutarı ne kadar oldu?", "asgari_ucret", "2026", 2, False),
    ("Bu yılki SGK prim tavanı kaç TL?", "sgk", "2026", 2, True),
    ("Güncel KDV oranı yüzde kaç?", "kdv", "2026", 2, False),
    ("2025 yılı damga vergisi haddi nedir?", "damga_vergisi", "2025", 2, False),
    ("Kurumlar vergisi oranı geçen yıl neydi, 2024'te kaçtı?", "kurumlar_vergisi", "2024", 2, False),
    ("Amortisman mantığı nasıl işler?", "amortisman", None, 1, False),
    ("Çift taraflı kayıt (borç/alacak) mantığı nasıl işler?", "", None, 1, False),
    ("Dönemsellik ilkesi ne anlama gelir?", "", None, 1, False),
    ("Şu anki e-fatura zorunluluğu ciro sınırı nedir?", "e_fatura", "2026", 2, False),
    ("2026 yılı kıdem tazminatı tavanı ne kadar?", "kidem_tazminati", "2026", 2, False),
    ("Bu yıl geçerli gelir vergisi tarifesi dilimleri nedir?", "gelir_vergisi", "2026", 2, False),
    ("Harcirah (yolluk) güncel tutarları ne kadar?", "harcirah", "2026", 2, False),
    ("4/b sigortalılık statüsü kimleri kapsar?", "sgk", None, 1, False),
    ("2026 SGK işveren prim oranı yüzde kaç?", "sgk", "2026", 3, True),
    ("Hesap 100 Kasa ne için kullanılır?", "", None, 1, False),
    ("2027 yılında asgari ücret ne olur dersin?", "asgari_ucret", "2027", 2, False),
    ("KDV oranları hakkında genel bilgi verir misin?", "kdv", None, 1, False),
    ("Yeni yıl itibarıyla damga vergisi haddi değişti mi?", "damga_vergisi", "2026", 2, False),
    ("Maliyet esası ilkesi ne demektir?", "", None, 1, False),
    ("2026 yılı SGK taban ve tavan ücretleri nedir?", "sgk", "2026", 3, True),
]

assert len(CASES) >= 20, "madde 34: en az 20 vaka"


def test_research_planner_topic_and_period_detection():
    failures = []
    for question, expected_topic, expected_period, min_subq, _ in CASES:
        plan = build_plan(question, today=_TODAY)
        got_topic = plan.subquestions[0].accounting_topic
        if got_topic != expected_topic:
            failures.append(("topic", question, expected_topic, got_topic))
        if plan.requested_period != expected_period:
            failures.append(("period", question, expected_period, plan.requested_period))
        if len(plan.subquestions) < min_subq:
            failures.append(("min_subq", question, min_subq, len(plan.subquestions)))
    assert not failures, f"planlayici hatalari: {failures}"
    print(f"KAIZEN RESEARCH PLANNER KONU/DONEM TESPITI ({len(CASES)} SORU) TESTI: BASARILI")


def test_research_planner_no_unnecessary_subquestions_when_no_period():
    """madde 34 'gereksiz alt-soru': dönem/güncellik sinyali OLMAYAN bir soruda (ör.
    zamansız bir muhasebe ilkesi sorusu) planlayıcı yalnız 1 alt-soru üretmeli --
    resmî-kaynak sorgusu icat ETMEMELİ (o sorgu yalnız period bulunduğunda anlamlı)."""
    for question, _, expected_period, _, _ in CASES:
        if expected_period is None:
            plan = build_plan(question, today=_TODAY)
            assert len(plan.subquestions) == 1, (
                f"donem yokken gereksiz alt-soru uretildi: {question!r} -> {plan.subquestions}"
            )
    print("KAIZEN RESEARCH PLANNER GEREKSIZ ALT-SORU URETMEME TESTI: BASARILI")


def test_research_planner_sgk_topic_includes_sgk_domain_subquery():
    """madde 34 'eksik kritik alt-soru': SGK + dönem sinyali olan bir soruda,
    site:sgk.gov.tr sorgusu MUTLAKA alt-sorular arasında olmalı (kritik resmî kaynak
    atlanmamalı)."""
    for question, expected_topic, expected_period, _, needs_sgk_domain in CASES:
        if needs_sgk_domain:
            plan = build_plan(question, today=_TODAY)
            queries = [s.search_query for s in plan.subquestions]
            assert any("site:sgk.gov.tr" in q for q in queries), (
                f"SGK sorusu ama sgk.gov.tr sorgusu eksik: {question!r} -> {queries}"
            )
    print("KAIZEN RESEARCH PLANNER SGK KRITIK ALT-SORU TESTI: BASARILI")


def test_research_planner_no_duplicate_queries_within_a_plan():
    for question, *_ in CASES:
        plan = build_plan(question, today=_TODAY)
        queries = [s.search_query for s in plan.subquestions]
        assert len(queries) == len(set(queries)), f"yinelenen sorgu: {question!r} -> {queries}"
    print("KAIZEN RESEARCH PLANNER YINELENEN SORGU YOK TESTI: BASARILI")


def test_research_planner_never_hallucinates_a_number_not_in_the_question():
    """madde 10 KIRMIZI ÇİZGİ: üretilen sorgularda, SORUDA zaten geçen yıl/sayılar VE
    bugünün yılı (göreli 'bu yıl/güncel' ifadeleri için) DIŞINDA hiçbir sayı olmamalı --
    yani planlayıcı bir oran/tutar İCAT ETMİYOR, yalnızca metni ve bugünün tarihini
    kullanıyor."""
    import re
    digit_run = re.compile(r"\d+")
    for question, *_ in CASES:
        plan = build_plan(question, today=_TODAY)
        allowed_numbers = set(digit_run.findall(question)) | {str(_TODAY.year)}
        for sq in plan.subquestions:
            found = set(digit_run.findall(sq.search_query))
            extra = found - allowed_numbers
            assert not extra, (
                f"UYDURMA SAYI tespit edildi: soru={question!r} sorgu={sq.search_query!r} "
                f"beklenmeyen={extra}"
            )
    print("KAIZEN RESEARCH PLANNER UYDURMA SAYI YOK TESTI: BASARILI")


def test_research_planner_returns_a_valid_research_plan_contract():
    plan = build_plan("2026 SGK prim tavanı kaç TL?", today=_TODAY)
    assert isinstance(plan, ResearchPlan)
    assert plan.question and plan.subquestions
    print("KAIZEN RESEARCH PLANNER GECERLI SOZLESME DONUSU TESTI: BASARILI")


if __name__ == "__main__":
    test_research_planner_topic_and_period_detection()
    test_research_planner_no_unnecessary_subquestions_when_no_period()
    test_research_planner_sgk_topic_includes_sgk_domain_subquery()
    test_research_planner_no_duplicate_queries_within_a_plan()
    test_research_planner_never_hallucinates_a_number_not_in_the_question()
    test_research_planner_returns_a_valid_research_plan_contract()
