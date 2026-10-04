"""KAIZEN Research Engine — İçerik Çıkarma (İş Emri #2 madde 16).

TEKRAR KULLANIM (madde 61: kopyalama yok): HTML ayrıştırma için `accounting/
html_extract.py::extract_html` (nav/footer/script/cookie-banner zaten dışarıda bırakıyor,
başlık+yayın tarihi+ana metni ayırıyor), PDF için `accounting/crawler.py::
extract_pdf_text` (pypdf tabanlı), pasaj ALAKA puanlaması için `accounting/
retriever.py::Retriever.coverage` (LearningStore'un zaten kullandığı AYNI skor
fonksiyonu) ÇAĞRILIR -- hiçbiri burada YENİDEN YAZILMAZ."""
from dataclasses import dataclass
from urllib.parse import urlparse

from accounting.crawler import extract_pdf_text
from accounting.html_extract import extract_html
from accounting.retriever import Retriever
from research.models import FETCH_OK


@dataclass(frozen=True)
class ExtractedContent:
    title: str
    text: str
    published_at: str  # "" ise bulunamadı (madde 20: UYDURULMAZ, boş bırakılır)
    domain: str


def extract(fetch_outcome):
    """`research/fetcher.py::FetchOutcome` (yalnız `status==FETCH_OK` olanlar) ->
    `ExtractedContent`. Sayfanın TAMAMI değil, temizlenmiş ana metin döner (madde 16:
    nav/footer/script/reklam mümkün olduğunca dışarıda -- bu iş `extract_html`'in
    kendi `_SKIP`/`_in_main` mantığıyla zaten yapılıyor)."""
    if fetch_outcome.status != FETCH_OK:
        return ExtractedContent(title="", text="", published_at="", domain="")
    url = fetch_outcome.final_url or fetch_outcome.url
    domain = (urlparse(url).hostname or "").lower()
    content_type = fetch_outcome.content_type or ""

    if content_type.startswith("application/pdf"):
        title, text = extract_pdf_text(fetch_outcome.body)
        return ExtractedContent(
            title=title or "", text=text or "", published_at="", domain=domain,
        )

    result = extract_html(fetch_outcome.text, base_url=url)
    return ExtractedContent(
        title=result.get("title") or "", text=getattr(fetch_outcome, "extracted_text", "") or result.get("text") or "",
        published_at=result.get("published_at") or "", domain=domain,
    )


def best_passage(question_or_query, text, max_chars=800, min_paragraph_len=20):
    """madde 16: sayfanın TAMAMI DEĞİL, en İLGİLİ pasaj seçilir -- soru/sorguyla en
    yüksek `Retriever.coverage` skoruna sahip paragraf, `max_chars`'a kırpılarak döner.
    Boş metinde boş döner (UYDURMA yok)."""
    if not text:
        return ""
    paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) >= min_paragraph_len]
    if not paragraphs:
        return text.strip()[:max_chars]
    best_index = max(range(len(paragraphs)), key=lambda i: Retriever.coverage(question_or_query, paragraphs[i]))
    best = paragraphs[best_index]
    # Cevap-verme düzeltmesi (2026-10-03): resmî PDF tarifelerinde en alakalı "paragraf" çoğu kez
    # yalnız BAŞLIK satırıdır ("Gelir Vergisi Tarifesi 2026"); değerler hemen sonraki tablo
    # satırlarındadır. Yalnız kısa (başlık benzeri) bir en-iyi satır için, ARDIŞIK ve rakam içeren
    # satırlar eklenir (ilk rakamsız satırda durulur) -- uzun paragraflarda davranış DEĞİŞMEZ.
    if len(best) < 60:
        lines = [best]
        for following in paragraphs[best_index + 1:best_index + 13]:
            if not any(ch.isdigit() for ch in following) or len(" ".join(lines)) >= max_chars:
                break
            lines.append(following)
        best = " | ".join(lines) if len(lines) > 1 else best
    return best[:max_chars]
