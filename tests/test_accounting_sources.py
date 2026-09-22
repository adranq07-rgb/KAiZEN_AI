from datetime import date
from pathlib import Path
from uuid import uuid4

from accounting.knowledge_store import AccountingKnowledgeStore
from accounting.source_registry import source_by_name, trusted_source_for_url
from accounting.site_ingestor import AccountingSiteIngestor
from accounting.source_registry import TRUSTED_SOURCES


def test_accounting_sources():
    assert trusted_source_for_url("https://www.gib.gov.tr/mevzuat").priority == 1
    assert trusted_source_for_url("https://www.alomaliye.com/makaleler/ornek")
    assert trusted_source_for_url("https://www.alomaliye.com/forum/ornek") is None
    assert trusted_source_for_url("https://example.com/yazi") is None

    # GİB'in genel sayfaları (mevzuat, duyuru listesi) JavaScript ile dolduruluyor, bu yüzden
    # açık keşif (sitemap/bağlantı takibi) yerine bilinen/doğrulanmış statik PDF belgeleri
    # (cdn.gib.gov.tr) seed olarak verildi -- artık "yalnız referans" değil, gerçekten taranıyor.
    gib = source_by_name("Gelir Idaresi Baskanligi")
    assert gib.reference_only is False
    assert gib.priority == 1
    assert len(gib.seed_urls) >= 1
    assert all(u.startswith("https://cdn.gib.gov.tr/") for u in gib.seed_urls)

    workspace = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    db_path = workspace / f"knowledge_{uuid4().hex}.sqlite3"
    try:
        store = AccountingKnowledgeStore(db_path)
        store.save(
            question="Kurumlar vergisi oranı nedir?",
            answer="SONUC: %25",
            evidence="Kurumlar vergisi oranı %25 olarak uygulanır.",
            source_name="Gelir Idaresi Baskanligi",
            url="https://www.gib.gov.tr/ornek",
            content="Kurumlar vergisi oranı %25 olarak uygulanır.",
            published_at=date.today().isoformat(),
            effective_year=date.today().year,
        )
        found = store.find_recent("  KURUMLAR vergisi oranı nedir? ", date.today())
        assert found and found["answer"] == "SONUC: %25"
        assert store.count() == 1
    finally:
        db_path.unlink(missing_ok=True)

    class FakeCollector:
        def collect_sources(self, prompt):
            assert "web_search" in prompt and "web_extract" in prompt
            return [{
                "url": "https://www.muhasebetr.com/makaleler/ornek",
                "title": "2026 Hadleri",
                "content": "2026 yilinda fatura duzenleme siniri aciklamasi.",
            }]

    db_path = workspace / f"ingestion_{uuid4().hex}.sqlite3"
    try:
        store = AccountingKnowledgeStore(db_path)
        ingestor = AccountingSiteIngestor(FakeCollector(), store)
        result = ingestor.ingest_source(TRUSTED_SOURCES[2], topics=("vergi 2026",))
        assert result["saved"] == 1
        found = store.search_latest("fatura düzenleme sınırı")
        assert found and found[0]["effective_year"] == 2026
    finally:
        db_path.unlink(missing_ok=True)

    print("KAIZEN MUHASEBE KAYNAK TESTI: BASARILI")


if __name__ == "__main__":
    test_accounting_sources()
