"""KAIZEN kabul testi (bağımsız; run_all'a kayıtlı DEĞİL). 12 sınıf, sahte arama/fetch double'ları.
Her vaka: EXPECTED BEHAVIOR / ACTUAL ROUTE / RESULT / SOURCE-EVIDENCE / LEARNING EFFECT."""
import sys
import tempfile
from search.provider import STATUS_OK
from research.fetcher import FetchOutcome
from tests.test_learning_loop import (
    _brain, _handler, _only_record, _RecordingProvider, _CorrectingAgent,
    PRINCIPLE_Q_A, PRINCIPLE_Q_B,
)
from tests.test_kaizen_brain_research_engine import _FakeFetcher, _FakeSearchProvider, _html, _sr

Q = "2026 SGK prim tavanı nedir?"
RESULTS = []


def _fetch(url, sentence, year="2026"):
    body = _html(sentence).replace(b"2026-01-05", f"{year}-01-05".encode())
    return FetchOutcome(status="FETCH_OK", url=url, final_url=url, content_type="text/html; charset=utf-8", body=body)


def _setup(pages, q=Q):
    prov = _FakeSearchProvider(results=[_sr(u, q) for u in pages])
    return prov, _FakeFetcher({u: _fetch(u, s, y) for u, (s, y) in pages.items()})


def report(name, expected, brain, check, learning="-", answer=""):
    t = brain.last_trace
    ok, why = check(brain, answer)
    sev = f"evidence={getattr(t,'evidence_count',None)} official={getattr(t,'official_evidence_count',None)} consensus={getattr(t,'consensus_status',None)} research={getattr(t,'research_status',None)}"
    RESULTS.append(ok)
    print(f"\n### {name}\nEXPECTED BEHAVIOR : {expected}\nACTUAL ROUTE      : {brain.last_route} (confidence={getattr(t,'confidence',None)}, fallback={getattr(t,'fallback_used',None)})\nRESULT            : {'PASS' if ok else 'FAIL'} — {why}\nSOURCE/EVIDENCE   : {sev}\nLEARNING EFFECT   : {learning}\nANSWER            : {answer[:160].replace(chr(10),' ')}")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        # 1 deterministik
        b, r = _brain(tmp + "/a")
        a = b.answer("1000 TL'nin %20'si kaç?")
        report("1 deterministik hesap", "araç ile hesaplanır, öğrenme/araştırma yok", b,
               lambda b, a: ("200" in a and b.last_trace.research_needed is not True, "200 hesaplandı"), "yok (NON_LEARNING_ROUTE)", a)
        # 2 muhasebe prensibi
        b, r = _brain(tmp + "/b")
        a = b.answer(PRINCIPLE_Q_A)
        report("2 muhasebe prensibi", "kalıcı prensip, araştırma tetiklenmez, VERIFIED değil", b,
               lambda b, a: (b.last_route == "memory_grounded" and b.last_trace.research_needed is not True, "hafızadan"), "reflection kaydı (onaysız, yönlendirmez)", a)
        # 3 güncel research
        p, f = _setup({"https://www.sgk.gov.tr/duyuru/2026": ("2026 yılı için SGK prim tavanı 750.000 TL'dir.", "2026")})
        b, r = _brain(tmp + "/c", engine=True, provider=p, fetcher=f)
        a = b.answer(Q)
        report("3 güncel research", "araştırma, SUPPORTED, kaynak gösterilir", b,
               lambda b, a: (b.last_trace.research_needed is True and "500.000" in a, "resmi kaynaklı"), "deneyim kaydı: yalnız sayı/durum/domain", a)
        exp = r.get(_only_record(r, Q)[0])
        # 4 resmi kaynak şart, sadece blog
        p, f = _setup({"https://www.muhasebetr.com/x": ("2026 SGK prim tavanı 750.000 TL'dir.", "2026")})
        b, r4 = _brain(tmp + "/d", engine=True, provider=p, fetcher=f, llm=_RecordingProvider("Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod)"), accounting=_CorrectingAgent(reply="Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod)"))
        a = b.answer(Q)
        report("4 resmi kaynak şart / yalnız blog", "resmi kanıt yok -> VERIFIED gösterilmez", b,
               lambda b, a: (b.last_trace.official_evidence_count in (0, None) and b.last_trace.confidence != "VERIFIED", "blog tek başına doğrulama sayılmadı"), "-", a)
        # 5 çok kaynak
        p, f = _setup({"https://www.sgk.gov.tr/a": ("2026 yılı için SGK prim tavanı 750.000 TL'dir.", "2026"),
                       "https://www.resmigazete.gov.tr/b": ("2026 yılı için SGK prim tavanı 750.000 TL'dir.", "2026")})
        b, _r = _brain(tmp + "/e", engine=True, provider=p, fetcher=f)
        a = b.answer(Q)
        report("5 çok kaynak", "mutabakat, 2 resmi kanıt", b,
               lambda b, a: ((b.last_trace.evidence_count or 0) >= 2 and "500.000" in a, "2+ kaynak"), "-", a)
        # 6 çelişki
        p, f = _setup({"https://www.sgk.gov.tr/a": ("2026 yılı için SGK prim tavanı 750.000 TL'dir.", "2026"),
                       "https://www.gib.gov.tr/b": ("2026 yılı için SGK prim tavanı 450.000 TL'dir.", "2026")})
        b, _r = _brain(tmp + "/f", engine=True, provider=p, fetcher=f)
        a = b.answer(Q)
        report("6 çelişkili kaynak", "tek rakamla doğrulanmış cevap VERİLMEZ", b,
               lambda b, a: (b.last_trace.confidence != "VERIFIED" and not ("750.000" in a and "450.000" not in a and "SUPPORTED" == b.last_trace.confidence), f"consensus={b.last_trace.consensus_status}"), "-", a)
        # 7 eski yıl
        p, f = _setup({"https://www.sgk.gov.tr/a": ("2024 yılı için SGK prim tavanı 300.000 TL'dir.", "2024")})
        b, _r = _brain(tmp + "/g", engine=True, provider=p, fetcher=f)
        a = b.answer(Q)
        report("7 eski yıl kaynağı", "2024 kaynağı 2026 sorusuna VERIFIED cevap olmaz", b,
               lambda b, a: ("300.000" not in a or b.last_trace.confidence != "VERIFIED", "eski yıl doğrulanmadı"), "-", a)
        # 8/9 strateji transferi + yanlış transfer
        llm = _RecordingProvider()
        b, r = _brain(tmp + "/h", llm=llm)
        b.answer(PRINCIPLE_Q_A); _handler(b).handle(f"onayla: {PRINCIPLE_Q_A}"); llm.prompts.clear()
        a = b.answer(PRINCIPLE_Q_B)
        hint = any("DENEYİM STRATEJİ İPUCU" in x for x in llm.prompts)
        report("8 strateji transferi", "A onaylandı -> yapısal benzer B'de süreç ipucu", b,
               lambda b, a: (hint and b.last_trace.experience_reusable is True, "ipucu var, fact yok"), "A onayı -> B'de yönlendirme", a)
        llm.prompts.clear()
        a = b.answer("2026 asgari ücret brüt kaç TL?")
        hint2 = any("DENEYİM STRATEJİ İPUCU" in x and "grounded" in x.lower() for x in llm.prompts)
        report("9 yanlış transfer reddi", "prensip stratejisi güncel-FACT sorusuna aktarılmaz", b,
               lambda b, a: (not hint2, "prensip ipucu uygulanmadı"), "negatif transfer reddedildi", a)
        # 10 düzeltme / 11 onay
        p, f = _setup({"https://www.sgk.gov.tr/a": ("2026 yılı için SGK prim tavanı 750.000 TL'dir.", "2026")})
        b, r = _brain(tmp + "/i", engine=True, provider=p, fetcher=f)
        b.answer(Q); h = _handler(b)
        rep = h.handle(f"düzelt: {Q} => 400.000 TL")
        _, e, m = _only_record(r, Q)
        report("10 kullanıcı düzeltmesi", "negatif sonuç, reusable=False, 400.000 FACT olmaz", b,
               lambda b, a: (e.outcome == "failure" and not e.reusable and m.negative_count == 1, "yapışkan negatif"), f"negatif={m.negative_count}", rep)
        b, r = _brain(tmp + "/j", engine=True, provider=p, fetcher=f)
        b.answer(Q); rep = _handler(b).handle(f"onayla: {Q}")
        _, e, m = _only_record(r, Q)
        report("11 kullanıcı onayı", "pozitif sonuç, reusable=True, FACT kaydı yok", b,
               lambda b, a: (e.reusable and e.user_approved and m.positive_count == 1, "strateji öğrenildi"), f"pozitif={m.positive_count}", rep)
        # 12 arama yok
        p = _FakeSearchProvider(results=[], status="SEARCH_UNAVAILABLE")
        b, _r = _brain(tmp + "/k", engine=True, provider=p, fetcher=_FakeFetcher({}))
        a = b.answer(Q)
        report("12 arama erişilemez", "güvenli fallback, uydurma rakam yok, VERIFIED yok", b,
               lambda b, a: (b.last_trace.confidence != "VERIFIED", "fallback güvenli"), "-", a)
    print(f"\nKABUL: {sum(RESULTS)}/{len(RESULTS)} PASS")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
