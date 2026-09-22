import re
from datetime import date

from accounting.knowledge_store import AccountingKnowledgeStore
from accounting.source_registry import TRUSTED_SOURCES, trusted_source_for_url


class AccountingSiteIngestor:
    TOPICS = (
        "vergi oranlari hadler sinirlar 2026",
        "muhasebe uygulamalari sirkuler 2026",
        "SGK isveren uygulamalari 2026",
        "e-fatura e-defter e-belge 2026",
    )
    def __init__(self, provider, store=None):
        self.provider = provider
        self.store = store or AccountingKnowledgeStore()

    @staticmethod
    def _effective_year(title, content):
        years = [int(value) for value in re.findall(r"\b20\d{2}\b", f"{title} {content}")]
        current = date.today().year
        valid = [year for year in years if current - 10 <= year <= current]
        return max(valid, default=None)

    def ingest_source(self, source, topics=None):
        collect = getattr(self.provider, "collect_sources", None)
        if not callable(collect):
            return {"source": source.name, "saved": 0, "error": "collect_sources yok"}
        domain = source.domains[0]
        if source.reference_only:
            return {
                "source": source.name,
                "saved": 0,
                "error": None,
                "mode": "reference_only",
            }
        saved = 0
        for topic in topics or self.TOPICS:
            prompt = (
                f"web_search ile site:{domain} {topic} ara. Buldugun en ilgili "
                "sayfayi web_extract ile ac. Yalniz bu iki araci kullan; dosya "
                "veya ayar degistirme."
            )
            for item in collect(prompt):
                matched = trusted_source_for_url(item.get("url"))
                if not matched or matched.name != source.name:
                    continue
                content = item.get("content", "")
                title = item.get("title", "")
                link_only = bool(item.get("link_only"))
                self.store.save_page(
                    title=title,
                    source_name=source.name,
                    url=item["url"],
                    content="" if link_only else content,
                    effective_year=self._effective_year(title, content),
                    metadata={
                        "priority": source.priority,
                        "ingested_by": "hermes",
                        "topic": topic,
                        "link_only": link_only,
                    },
                )
                saved += 1
        return {"source": source.name, "saved": saved, "error": None}

    def ingest_all(self):
        return [self.ingest_source(source) for source in TRUSTED_SOURCES]
