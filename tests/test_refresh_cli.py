"""accounting.refresh CLI'nin ağ gerektirmeyen kısımları: --rebuild-only.

Süzgeç (facts) çıkarım kurallarında düzeltme yapıldığında, saatlerce süren tam siteleri
tekrar tarama olmadan, yalnız depodaki (zaten indirilmiş) sayfalardan süzgecin yeniden
kurulabildiğini doğrular.
"""
from pathlib import Path
from uuid import uuid4

from accounting.facts import FactRegistry
from accounting.refresh import rebuild_only
from accounting.site_store import SiteStore

# NOT: Aşağıdaki tutar yalnızca test verisidir, gerçek mevzuat değeri değildir.
PAGE = ("Fatura düzenleme sınırı 2026 yılında 11.111 TL olarak uygulanacaktır. "
        "2026 yılında fatura düzenleme sınırı 11.111 TL oldu.")


def test_rebuild_only_uses_stored_pages_without_crawling():
    workspace = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    db = workspace / f"rebuild_only_{uuid4().hex}.sqlite3"
    try:
        store = SiteStore(db)
        # 3 sources needed for "verified" (3+ independent trusted sources)
        store.upsert_page(url="https://www.muhasebetr.com/a", source_name="Muhasebe TR",
                          title="A", content=PAGE, effective_year=2026)
        store.upsert_page(url="https://www.alomaliye.com/makaleler/b", source_name="Alomaliye",
                          title="B", content=PAGE, effective_year=2026)
        store.upsert_page(url="https://www.vergiport.com/c", source_name="Vergiport",
                          title="C", content=PAGE, effective_year=2026)
        registry = FactRegistry(db)

        logs = []
        summary = rebuild_only(store=store, registry=registry, log=logs.append)

        assert summary["verified"] >= 1
        assert logs and "Süzgeç yeniden kuruldu" in logs[0]

        text = registry.answer("2026 fatura düzenleme sınırı ne kadar?")
        assert "11.111 TL" in text
    finally:
        for path in workspace.glob("rebuild_only_*.sqlite3*"):
            path.unlink(missing_ok=True)

    print("KAIZEN SUZGEC YENIDEN KURMA (REBUILD-ONLY) TESTI: BASARILI")


if __name__ == "__main__":
    test_rebuild_only_uses_stored_pages_without_crawling()
