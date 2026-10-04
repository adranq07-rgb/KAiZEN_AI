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
    topics = load_topics()
    extractor = FactExtractor(topics, current_year=2026)
    page = {"url": "https://www.muhasebetr.com/issizliksigortasi/", "effective_year": 2026,
            "content": ("2026 yılı için günlük kazancın alt sınırı 4 000 000 TL., üst sınırı ise "
                        "alt sınırın üç katıdır.")}
    cands = extractor.extract(page)
    for c in cands:
        assert c.value != "000 TL", f"kırpılmış değer üretildi: {c}"


def test_facts_asgari_ucret_ignores_gunluk_yillik_and_onda_bir_sentences():
    topics = load_topics()
    extractor = FactExtractor(topics, current_year=2026)

    aylik = extractor.extract({
        "url": "https://vergimerkezi.com.tr/2026-pratik-bilgiler-mali-rehber/", "effective_year": 2026,
        "content": "2026 yılı Brüt Asgari Ücret: 33.030,00 TL",
    })
    assert ("asgari_ucret_brut", 2026) in {(c.topic, c.effective_year): c.value for c in aylik}.keys()

    gunluk = extractor.extract({
        "url": "https://www.ozdogrular.com/v1/content/view/58616/175/", "effective_year": 2026,
        "content": "01.01.2026 - 31.12.2026 tarihleri arasında çalışanın bir günlük brüt asgari ücreti 1.101,00 TL olarak uygulanır.",
    })
    assert ("asgari_ucret_brut", 2026) not in {(c.topic, c.effective_year) for c in gunluk}

    yillik = extractor.extract({
        "url": "https://pkf.com.tr/yillik-asgari-ucret/", "effective_year": 2026,
        "content": "2026 yılı yıllık brüt asgari ücret tutarı 396.360,00 TL olarak uygulanmaktadır.",
    })
    assert ("asgari_ucret_brut", 2026) not in {(c.topic, c.effective_year) for c in yillik}

    onda_bir = extractor.extract({
        "url": "https://www.vertax.com.tr/2026/09/14/sgk-genelgesi-2026-21-turizm-ucret-destegi/", "effective_year": 2026,
        "content": "İlgili ayda toplam brüt asgari ücretin onda birini (3.303,00 TL) geçmeyecek tutarda eksik prime esas kazanç bildirimi yapılamaz.",
    })
    assert ("asgari_ucret_brut", 2026) not in {(c.topic, c.effective_year) for c in onda_bir}

    print("KAIZEN ASGARI UCRET SUZGEC DUZELTMESI TESTI: BASARILI")


def test_facts_vuk_313_ignores_binek_oto_otv_line():
    topics = load_topics()
    extractor = FactExtractor(topics, current_year=2024)

    gercek = extractor.extract({
        "url": "https://www.vergiport.com/blog/2023-yil-sonu-ve-2024-yili-vergi-uygulamalari", "effective_year": 2024,
        "content": "Doğrudan gider kaydedilecek küçük demirbaşlar için uygulanmakta olan sınır, 01.01.2024 tarihinden itibaren 6.900 TL olacaktır.",
    })
    assert ("vuk_313_amortisman_siniri", 2024) in {(c.topic, c.effective_year) for c in gercek}

    binek_otv = extractor.extract({
        "url": "https://www.muhasebenews.com/2024-binek-oto-muhasebe-kaydi/", "effective_year": 2024,
        "content": "2024 Gider yazılabilecek KDV+ÖTV Tutarı: 690.000 TL",
    })
    assert ("vuk_313_amortisman_siniri", 2024) not in {(c.topic, c.effective_year) for c in binek_otv}

    print("KAIZEN VUK 313 SUZGEC DUZELTMESI TESTI: BASARILI")


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
    assert values[("fatura_duzenleme_siniri", 2025)] == "9.999 TL"

    workspace = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    db = workspace / f"facts_{uuid4().hex}.sqlite3"
    try:
        store = SiteStore(db)
        # 3 sources needed for verified
        store.upsert_page(url="https://www.muhasebetr.com/a", source_name="Muhasebe TR", title="A", content=PAGE_A + " " * 5, effective_year=2026)
        store.upsert_page(url="https://www.alomaliye.com/makaleler/b", source_name="Alomaliye", title="B", content=PAGE_B, effective_year=2026)
        store.upsert_page(url="https://www.vergiport.com/c", source_name="Vergiport", title="C", content=PAGE_A + " " * 5, effective_year=2026)
        registry = FactRegistry(db, topics)
        summary = registry.rebuild(store, min_year=2025, extractor=extractor)
        assert summary.get("verified", 0) >= 1

        text = registry.answer("2026 fatura düzenleme sınırı ne kadar?")
        assert "11.111 TL" in text and "muhasebetr.com" in text
        assert "KANIT:" in text
        assert "DOĞRULANDI" in text

        rows = {(r["topic"], r["year"]): r for r in registry.rows()}
        assert rows[("fatura_duzenleme_siniri", 2025)]["status"] == "single_source"
        assert rows[("kurumlar_vergisi_orani", 2026)]["status"] == "partially_verified"
        assert "eşleşme eksik" in registry.answer("kurumlar vergisi oranı nedir")

        store.upsert_page(url="https://www.vergiport.com/c", source_name="Vergiport", title="C", content=PAGE_C, effective_year=2026)
        registry.rebuild(store, min_year=2025, extractor=extractor)
        assert "11.111 TL" in registry.answer("2026 fatura düzenleme sınırı")

        store.upsert_page(url="https://www.pkf.com.tr/d", source_name="PKF Istanbul", title="D",
                          content="2026 yılı fatura düzenleme sınırı 12.222 TL olarak güncellendi.", effective_year=2026)
        store.upsert_page(url="https://www.alomaliye.com/makaleler/b", source_name="Alomaliye", title="B", content="2026 yılında fatura düzenleme sınırı 12.222 TL oldu.", effective_year=2026)
        store.upsert_page(url="https://www.muhasebetr.com/a", source_name="Muhasebe TR", title="A", content="Fatura düzenleme sınırı 2026 yılında 12.222 TL olarak uygulanacaktır.", effective_year=2026)
        registry.rebuild(store, min_year=2025, extractor=extractor)
        assert "12.222 TL" in registry.answer("2026 fatura düzenleme sınırı")
        history = registry.history("fatura_duzenleme_siniri")
        old_values = [h["old_value"] for h in history]
        new_values = [h["new_value"] for h in history]
        assert "11.111 TL" in str(old_values) or "11.111 TL" in str(new_values)
        assert "12.222 TL" in str(new_values)
        final_rows = registry.rows()
        verified_row = [r for r in final_rows if r["topic"] == "fatura_duzenleme_siniri" and r["year"] == 2026]
        assert verified_row and verified_row[0]["status"] == "verified"
        assert "12.222 TL" in verified_row[0]["value"]

        assert registry.answer("Ankara'da hava nasıl?") is None
        assert "kayıt henüz yok" in registry.answer("2031 fatura düzenleme sınırı")
    finally:
        for path in workspace.glob("facts_*.sqlite3*"):
            path.unlink(missing_ok=True)

    print("KAIZEN YILLIK PARAMETRE (SUZGEC) TESTI: BASARILI")


def test_rebuild_removes_stale_facts_when_extraction_rule_is_corrected():
    from accounting.facts import FactTopic

    bad_sentence = ("Test konusu ile ilgili istisna kapsamındaki sınır 2026 yılında 700.000 TL "
                    "olarak açıklanmıştır.")
    buggy_topic = FactTopic(id="test_konu", title="Test Konusu", unit="tl", anchors=("test konusu",))
    fixed_topic = FactTopic(id="test_konu", title="Test Konusu", unit="tl",
                            anchors=("test konusu",), avoid=("istisna",))

    workspace = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    db = workspace / f"facts_stale_{uuid4().hex}.sqlite3"
    try:
        store = SiteStore(db)
        store.upsert_page(url="https://www.muhasebetr.com/karisik-sayfa", source_name="Muhasebe TR",
                          title="Karışık", content=bad_sentence, effective_year=2026)
        store.upsert_page(url="https://www.alomaliye.com/makaleler/karisik-sayfa", source_name="Alomaliye",
                          title="Karışık 2", content=bad_sentence, effective_year=2026)

        registry = FactRegistry(db, [buggy_topic])
        buggy_extractor = FactExtractor([buggy_topic], current_year=2026)
        summary = registry.rebuild(store, min_year=2025, extractor=buggy_extractor)
        assert summary["removed"] == 0
        rows = {(r["topic"], r["year"]): r for r in registry.rows()}
        assert ("test_konu", 2026) in rows

        registry_fixed = FactRegistry(db, [fixed_topic])
        fixed_extractor = FactExtractor([fixed_topic], current_year=2026)
        summary2 = registry_fixed.rebuild(store, min_year=2025, extractor=fixed_extractor)
        assert summary2["removed"] == 1
        rows_after = {(r["topic"], r["year"]): r for r in registry_fixed.rows()}
        assert ("test_konu", 2026) not in rows_after

        history = registry_fixed.history("test_konu")
        assert any(h["new_status"] == "removed" and h["new_value"] is None for h in history)

    finally:
        for path in workspace.glob("facts_stale_*.sqlite3*"):
            path.unlink(missing_ok=True)

    print("KAIZEN SUZGEC ESKI KAYIT TEMIZLEME TESTI: BASARILI")


if __name__ == "__main__":
    test_facts_ignores_space_grouped_tl_fragment()
    test_facts_asgari_ucret_ignores_gunluk_yillik_and_onda_bir_sentences()
    test_facts_vuk_313_ignores_binek_oto_otv_line()
    test_facts()
    test_rebuild_removes_stale_facts_when_extraction_rule_is_corrected()