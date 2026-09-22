import io
import threading
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from uuid import uuid4

from accounting.crawler import SiteCrawler, UrllibFetcher, parse_feed, parse_sitemap
from accounting.site_store import SiteStore
from accounting.source_registry import TrustedSource

TODAY = date.today()
RECENT = (TODAY - timedelta(days=20)).isoformat()
OLD = "2019-04-01"

ARTICLE = """<html><head><title>{title} | Site</title>
<meta property="article:published_time" content="{date}T09:00:00+03:00"></head><body>
<nav>Menü Ana Sayfa</nav><article><h1>{title}</h1><p>{body}</p>
<p>Bu yazı Kaizen toplayıcı testi için hazırlanmış örnek içeriktir ve yeterince uzundur; muhasebe
uygulamalarında kullanılan sınırlar ve oranlar konusunda ayrıntılı bilgi içerir. Yazının devamında
uygulama örnekleri ve açıklamalar bulunmaktadır. Toplayıcı bu metni depoya almalıdır.</p></article>
<footer>Alt bilgi</footer></body></html>"""


def _pages(port):
    base = f"http://127.0.0.1:{port}"
    return {
        "/robots.txt": ("text/plain", f"User-agent: *\nDisallow: /private/\nSitemap: {base}/sitemap.xml\n"),
        "/sitemap.xml": ("application/xml", f"""<?xml version="1.0"?><urlset>
<url><loc>{base}/haber/fatura-siniri</loc><lastmod>{RECENT}</lastmod></url>
<url><loc>{base}/haber/amortisman</loc><lastmod>{RECENT}</lastmod></url>
<url><loc>{base}/haber/eski-yazi</loc><lastmod>{OLD}</lastmod></url>
<url><loc>{base}/private/gizli</loc><lastmod>{RECENT}</lastmod></url>
<url><loc>{base}/forum/konu</loc><lastmod>{RECENT}</lastmod></url>
</urlset>"""),
        "/": ("text/html", f'<html><body><a href="/haber/fatura-siniri">a</a><a href="/haber/yeni-baglanti">b</a>'
                            f'<a href="https://baska-site.example/x">dis</a></body></html>'),
        "/haber/fatura-siniri": ("text/html", ARTICLE.format(title="Fatura Düzenleme Sınırı 2026", date=RECENT,
                                                            body="2026 yılında fatura düzenleme sınırı 10.000 TL olarak uygulanır.")),
        "/haber/amortisman": ("text/html", ARTICLE.format(title="Amortisman Hadleri 2026", date=RECENT,
                                                         body="2026 yılı amortisman had sınırı 12.000 TL olarak belirlenmiştir.")),
        "/haber/eski-yazi": ("text/html", ARTICLE.format(title="Eski Yazı 2019", date=OLD, body="2019 eski içerik.")),
        "/haber/yeni-baglanti": ("text/html", ARTICLE.format(title="Bağlantıdan Bulunan", date=RECENT,
                                                            body="Site içi bağlantıdan keşfedilen makale.")),
        "/private/gizli": ("text/html", ARTICLE.format(title="Gizli", date=RECENT, body="robots engelli")),
        "/forum/konu": ("text/html", ARTICLE.format(title="Forum", date=RECENT, body="forum")),
    }


def _xlsx_bytes():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Hadler"
    ws.append(["Had", "2026 Tutar"])
    ws.append(["Fatura düzenleme sınırı", 10000])
    for i in range(30):
        ws.append([f"Satır {i}", "Kaizen toplayıcı excel içeriği " * 3])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_fetcher_encodes_turkish_characters_in_url():
    """Ham Türkçe karakter içeren adresler (ör. '.../AramizdanAyrilanlar/Ağustos') daha önce
    'ascii' codec can't encode character hatasıyla patlıyordu (canlı taramada TURMOB ve Denge
    Akademi'de görüldü); artık istek öncesi yüzde-kodlanıyor, sayfa normal şekilde alınabiliyor.
    """
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            hits.append(self.path)
            body = "<html><body>tamam</body></html>".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        fetcher = UrllibFetcher(min_delay=0, timeout=5, respect_robots=False)
        url = f"http://127.0.0.1:{port}/AramizdanAyrilanlar/Ağustos"
        result = fetcher.get(url)
        assert result.status == 200, result.error
        assert hits and hits[0] == "/AramizdanAyrilanlar/A%C4%9Fustos", hits
    finally:
        server.shutdown()

    print("KAIZEN TURKCE URL KODLAMA TESTI: BASARILI")


def test_crawler():
    hits = []
    holder = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            hits.append(self.path)
            pages = holder["pages"]
            if self.path == "/veri.xlsx":
                body = _xlsx_bytes()
                ctype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif self.path in pages:
                ctype, text = pages[self.path]
                body = text.encode("utf-8")
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    holder["pages"] = _pages(port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    workspace = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    db = workspace / f"crawler_{uuid4().hex}.sqlite3"
    try:
        # ayrıştırıcılar
        children, pages = parse_sitemap("<sitemapindex><sitemap><loc>http://a/x.xml</loc><lastmod>2026-01-02</lastmod></sitemap></sitemapindex>")
        assert children == [("http://a/x.xml", "2026-01-02")] and pages == []
        feed = parse_feed("<rss><channel><item><title>t</title><link>http://a/1</link><pubDate>Tue, 05 May 2026 10:00:00 +0300</pubDate></item></channel></rss>")
        assert feed == [("http://a/1", "2026-05-05")]

        store = SiteStore(db)
        source = TrustedSource("Test Kaynak", ("127.0.0.1",), 2, ("forum",),
                               seed_urls=(f"http://127.0.0.1:{port}/", f"http://127.0.0.1:{port}/veri.xlsx"))
        fetcher = UrllibFetcher(min_delay=0, timeout=5)
        crawler = SiteCrawler(store, fetcher)
        report = crawler.crawl_source(source, max_pages=20)

        urls = {p["url"] for p in store.iter_pages("Test Kaynak")}
        base = f"http://127.0.0.1:{port}"
        assert f"{base}/haber/fatura-siniri" in urls and f"{base}/haber/amortisman" in urls
        assert f"{base}/haber/yeni-baglanti" in urls                       # site içi bağlantıdan keşif
        assert f"{base}/veri.xlsx" in urls                                 # Excel metni okundu
        assert not any("/private/" in u or "/forum/" in u for u in urls)   # robots + forum filtresi
        assert f"{base}/haber/eski-yazi" not in urls                       # 2 yıldan eski atlandı
        assert not any(p.startswith("/private/") or p.startswith("/forum/") for p in hits)  # hiç istenmedi
        assert report["new"] >= 4 and report["sitemaps"] == 1

        found = store.search("fatura düzenleme sınırı ne kadar", limit=3)
        assert found and found[0]["url"].endswith("/haber/fatura-siniri")
        assert found[0]["published_at"] == RECENT and found[0]["effective_year"] == 2026
        assert "Menü Ana Sayfa" not in found[0]["content"] and "Alt bilgi" not in found[0]["content"]
        sheet = store.search("fatura düzenleme sınırı 2026 tutar", limit=5)
        assert any(r["kind"] == "xlsx" for r in sheet)

        # ikinci koşu: değişmeyen sayfalar tekrar indirilmez
        before = len(hits)
        second = crawler.crawl_source(source, max_pages=20)
        assert second["new"] == 0 and second["unchanged"] >= 3
        assert len([h for h in hits[before:] if h.startswith("/haber/")]) == 0

        # robots.txt her şeyi yasaklarsa hiçbir sayfa alınmaz
        holder["pages"]["/robots.txt"] = ("text/plain", "User-agent: *\nDisallow: /\n")
        blocked_store = SiteStore(workspace / f"crawler_{uuid4().hex}.sqlite3")
        blocked_crawler = SiteCrawler(blocked_store, UrllibFetcher(min_delay=0, timeout=5))
        rep = blocked_crawler.crawl_source(source, max_pages=5)
        assert blocked_store.count() == 0 and "robots" in (rep["stopped"] or "")
    finally:
        server.shutdown()
        for path in workspace.glob("crawler_*.sqlite3*"):
            path.unlink(missing_ok=True)

    print("KAIZEN SITE TOPLAYICI TESTI: BASARILI")


if __name__ == "__main__":
    test_fetcher_encodes_turkish_characters_in_url()
    test_crawler()
