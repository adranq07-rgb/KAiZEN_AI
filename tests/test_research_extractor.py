"""KAIZEN — BÜYÜK İŞ EMRİ #2, Faz 13 (madde 16): içerik çıkarmanın testi. HTML/PDF
ayrıştırmanın KENDİSİ zaten `tests/test_crawler.py`'de (accounting/html_extract.py,
accounting/crawler.py::extract_pdf_text) test ediliyor -- burada yalnız `research/
extractor.py`'nin YÖNLENDİRME (routing) ve pasaj seçme mantığı test edilir (kopyalama
yok, bkz. modül docstring'i)."""
from research.extractor import ExtractedContent, best_passage, extract
from research.fetcher import FetchOutcome
from research.models import FETCH_OK, FETCH_BLOCKED_SSRF


_HTML = """
<html><head><title>2026 Asgari Ucret Duyurusu</title>
<meta property="article:published_time" content="2026-01-05T10:00:00+03:00"></head>
<body>
<nav>Ana Sayfa | Iletisim | Reklam Alani</nav>
<article>
<h1>2026 Asgari Ucret Duyurusu</h1>
<p>2026 yilinda uygulanacak brut asgari ucret 26.005,50 TL olarak belirlendi.</p>
<p>Bu tutar Calisma ve Sosyal Guvenlik Bakanligi tarafindan aciklandi.</p>
</article>
<footer>Telif hakki 2026, tum haklari saklidir. Cerez politikasi.</footer>
</body></html>
"""


def test_extract_html_returns_title_date_and_excludes_nav_footer():
    outcome = FetchOutcome(
        status=FETCH_OK, url="https://ornek.com/haber", final_url="https://ornek.com/haber",
        content_type="text/html; charset=utf-8", body=_HTML.encode("utf-8"),
    )
    content = extract(outcome)
    assert isinstance(content, ExtractedContent)
    assert "Asgari" in content.title
    assert content.published_at == "2026-01-05"
    assert content.domain == "ornek.com"
    assert "26.005,50" in content.text
    assert "Reklam Alani" not in content.text
    assert "Cerez politikasi" not in content.text
    print("KAIZEN RESEARCH EXTRACTOR HTML BASLIK/TARIH/NAV-FOOTER DISLAMA TESTI: BASARILI")


def test_extract_pdf_routing_degrades_gracefully_on_corrupt_bytes():
    """Gerçek PDF üretimi test ortamında ek bağımlılık gerektirir (reportlab
    requirements.txt'de yok) -- burada YÖNLENDİRMENİN (PDF content-type ->
    extract_pdf_text çağrısı) çalıştığı ve BOZUK/geçersiz PDF baytlarında ÇÖKMEDEN
    (crash) zarifçe boş döndüğü doğrulanır (madde 53: hata durumunda uydurma/çökme yok)."""
    outcome = FetchOutcome(
        status=FETCH_OK, url="https://ornek.com/belge.pdf",
        final_url="https://ornek.com/belge.pdf", content_type="application/pdf",
        body=b"bu gecerli bir PDF degil",
    )
    content = extract(outcome)
    assert isinstance(content, ExtractedContent)
    assert content.text == "" and content.title == ""  # extract_pdf_text(None, None) -> graceful
    print("KAIZEN RESEARCH EXTRACTOR PDF YONLENDIRME + ZARIF BOZUK-DOSYA TESTI: BASARILI")


def test_extract_non_ok_fetch_outcome_returns_empty_content():
    """madde 13: getirilemeyen (SSRF engeli/timeout/vb.) bir sonuçtan ASLA içerik
    UYDURULMAZ -- boş `ExtractedContent` döner."""
    blocked = FetchOutcome(status=FETCH_BLOCKED_SSRF, url="http://localhost/x")
    content = extract(blocked)
    assert content.title == "" and content.text == "" and content.domain == ""
    print("KAIZEN RESEARCH EXTRACTOR ENGELLENEN FETCH ICIN BOS ICERIK TESTI: BASARILI")


def test_best_passage_picks_most_relevant_paragraph_not_whole_page():
    text = (
        "Bu sayfa cerez politikasi hakkinda genel bilgi verir ve reklam icerir.\n"
        "2026 yilinda uygulanacak brut asgari ucret 26.005,50 TL olarak belirlendi.\n"
        "Iletisim bilgilerimiz asagida yer almaktadir, telefon ve adres.\n"
    )
    passage = best_passage("2026 asgari ücret ne kadar", text)
    assert "26.005,50" in passage
    assert "cerez politikasi" not in passage.lower()
    assert len(passage) < len(text)  # sayfanin TAMAMI degil (madde 16)
    print("KAIZEN RESEARCH EXTRACTOR EN ILGILI PASAJ SECIMI TESTI: BASARILI")


def test_best_passage_truncates_to_max_chars():
    long_paragraph = "asgari ucret " + ("x" * 2000)
    passage = best_passage("asgari ucret", long_paragraph, max_chars=100)
    assert len(passage) == 100
    print("KAIZEN RESEARCH EXTRACTOR PASAJ MAX_CHARS KIRPMA TESTI: BASARILI")


def test_best_passage_empty_text_returns_empty():
    assert best_passage("soru", "") == ""
    print("KAIZEN RESEARCH EXTRACTOR BOS METIN ICIN BOS PASAJ TESTI: BASARILI")


if __name__ == "__main__":
    test_extract_html_returns_title_date_and_excludes_nav_footer()
    test_extract_pdf_routing_degrades_gracefully_on_corrupt_bytes()
    test_extract_non_ok_fetch_outcome_returns_empty_content()
    test_best_passage_picks_most_relevant_paragraph_not_whole_page()
    test_best_passage_truncates_to_max_chars()
    test_best_passage_empty_text_returns_empty()
