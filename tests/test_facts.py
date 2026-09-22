from pathlib import Path
from uuid import uuid4

from accounting.facts import FactExtractor, FactRegistry, load_topics
from accounting.site_store import SiteStore

# NOT: Buradaki sayılar YALNIZCA test verisidir (uydurma); gerçek mevzuat değerleri değildir.
PAGE_A = ("Fatura düzenleme sınırı 2026 yılında 11.111 TL olarak uygulanacaktır. "
          "Kurumlar vergisi oranı %23 olarak belirlenmiştir. 2026 yılı için SGK prim tavanı 500.000 TL'dir.")
PAGE_B = ("2026 yılında fatura düzenleme sınırı 11.111 TL oldu. "
          "2025 yılında fatura düzenleme sınırı 9.999 TL idi.")
PAGE_C = "Uzmanlara göre 2026 için fatura düzenleme sınırı 12.222 TL olacak."


def test_facts_ignores_space_grouped_tl_fragment():
    # Bazı eski/kopyala-yapıştır metinlerde binlik ayracı nokta değil boşluktur (ör. "4 000 000 TL").
    # _TL deseni bunu bütün olarak tanımıyor; düzeltmeden önce son parçayı ("000 TL") tek başına
    # yakalayıp anlamsız bir "000 TL" değeri üretiyordu -- artık hiç yakalamıyor (kırpılmış/yanlış
    # veri üretmektense veri üretmemeyi tercih ediyoruz).
    topics = load_topics()
    extractor = FactExtractor(topics, current_year=2026)
    page = {"url": "https://www.muhasebetr.com/issizliksigortasi/", "effective_year": 2026,
            "content": ("2026 yılı için günlük kazancın alt sınırı 4 000 000 TL., üst sınırı ise "
                        "alt sınırın üç katıdır.")}
    cands = extractor.extract(page)
    for c in cands:
        assert c.value != "000 TL", f"kırpılmış değer üretildi: {c}"


def test_facts():
    topics = load_topics()
    assert {t.id for t in topics} >= {"fatura_duzenleme_siniri", "kurumlar_vergisi_orani"}
    extractor = FactExtractor(topics, current_year=2026)

    cands = extractor.extract({"url": "https://www.muhasebetr.com/a", "content": PAGE_A, "effective_year": 2026})
    got = {(c.topic, c.effective_year): c.value for c in cands}
    assert got[("fatura_duzenleme_siniri", 2026)] == "11.111 TL"
    assert got[("kurumlar_vergisi_orani", 2026)] == "%23"
    two_years = extractor.extract({"url": "https://www.alomaliye.com/makaleler/b", "content": PAGE_B, "effective_year": 2026})
    values = {(c.topic, c.effective_year): c.value for c in two_years}
    assert values[("fatura_duzenleme_siniri", 2026)] == "11.111 TL"
    assert values[("fatura_duzenleme_siniri", 2025)] == "9.999 TL"     # cümledeki iki yıl ayrı ayrı okunur

    workspace = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    db = workspace / f"facts_{uuid4().hex}.sqlite3"
    try:
        store = SiteStore(db)
        store.upsert_page(url="https://www.muhasebetr.com/a", source_name="Muhasebe TR", title="A", content=PAGE_A + " " * 5, effective_year=2026)
        store.upsert_page(url="https://www.alomaliye.com/makaleler/b", source_name="Alomaliye", title="B", content=PAGE_B, effective_year=2026)
        registry = FactRegistry(db, topics)
        summary = registry.rebuild(store, min_year=2025, extractor=extractor)
        assert summary["verified"] >= 1

        text = registry.answer("2026 fatura düzenleme sınırı ne kadar?")
        assert "11.111 TL" in text and "2 kaynakta" in text and "muhasebetr.com" in text
        assert "KANIT:" in text

        # tek kaynakta görülen yeni yıl değeri doğrulanmış sayılmaz
        rows = {(r["topic"], r["year"]): r for r in registry.rows()}
        assert rows[("fatura_duzenleme_siniri", 2025)]["status"] == "pending"
        assert rows[("kurumlar_vergisi_orani", 2026)]["status"] == "pending"
        assert "henüz doğrulanmadı" in registry.answer("kurumlar vergisi oranı nedir")

        # üçüncü kaynak farklı değer söylerse doğrulanmış değer bozulmaz (2 kaynak > 1 kaynak)
        store.upsert_page(url="https://www.vergiport.com/c", source_name="Vergiport", title="C", content=PAGE_C, effective_year=2026)
        registry.rebuild(store, min_year=2025, extractor=extractor)
        assert "11.111 TL" in registry.answer("2026 fatura düzenleme sınırı")

        # Kanun değişir: yeni değer iki bağımsız kaynakta görülünce doğrulanır, eski değer geçmişe yazılır
        store.upsert_page(url="https://www.pkf.com.tr/d", source_name="PKF Istanbul", title="D",
                          content="2026 yılı fatura düzenleme sınırı 12.222 TL olarak güncellendi.", effective_year=2026)
        store.upsert_page(url="https://www.alomaliye.com/makaleler/b", source_name="Alomaliye", title="B", content="2026 yılında fatura düzenleme sınırı 12.222 TL oldu.", effective_year=2026)
        store.upsert_page(url="https://www.muhasebetr.com/a", source_name="Muhasebe TR", title="A", content="Fatura düzenleme sınırı 2026 yılında 12.222 TL olarak uygulanacaktır.", effective_year=2026)
        registry.rebuild(store, min_year=2025, extractor=extractor)
        assert "12.222 TL" in registry.answer("2026 fatura düzenleme sınırı")
        history = registry.history("fatura_duzenleme_siniri")
        assert any(h["old_value"] == "11.111 TL" and h["new_value"] == "12.222 TL" for h in history)

        assert registry.answer("Ankara'da hava nasıl?") is None
        assert "kayıt henüz yok" in registry.answer("2031 fatura düzenleme sınırı")
    finally:
        for path in workspace.glob("facts_*.sqlite3*"):
            path.unlink(missing_ok=True)

    print("KAIZEN YILLIK PARAMETRE (SUZGEC) TESTI: BASARILI")


if __name__ == "__main__":
    test_facts_ignores_space_grouped_tl_fragment()
    test_facts()
