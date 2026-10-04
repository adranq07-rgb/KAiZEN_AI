"""KAIZEN — BÜYÜK İŞ EMRİ #2, Faz 13 (madde 14-15, 35): Safe Fetcher'ın adversarial
testi. madde 35'in istediği asgari küme birebir kapsanır: normal HTTPS, yönlendirme,
yönlendirme->localhost, localhost, 127.0.0.1, private IP, file://, aşırı büyük yanıt,
timeout, 403, 429, robots red, malformed URL, PDF, HTML. Hiçbiri GERÇEK ağa çıkmaz --
`opener`/`resolve_hostname`/`sleep`/`clock` tamamen enjekte edilir (search_provider
testleriyle AYNI disiplin, bkz. tests/test_search_provider.py)."""
import urllib.error

from research.fetcher import SafeFetcher
from research.models import (
    FETCH_OK, FETCH_BLOCKED_ROBOTS, FETCH_BLOCKED_SSRF, FETCH_HTTP_ERROR,
    FETCH_MALFORMED, FETCH_TIMEOUT, FETCH_TOO_LARGE,
)


class _FakeResponse:
    def __init__(self, status=200, headers=None, body=b""):
        self.status = status
        self.headers = headers or {}
        self._body = body

    def read(self, n=-1):
        return self._body if n is None or n < 0 else self._body[:n]

    def getcode(self):
        return self.status


_ROBOTS_ALLOW_ALL = _FakeResponse(200, {"Content-Type": "text/plain"}, b"")
_ROBOTS_DENY_ALL = _FakeResponse(
    200, {"Content-Type": "text/plain"}, b"User-agent: *\nDisallow: /\n"
)


class _FakeOpener:
    """url -> (callable() -> response) | (callable() -> raise exception)."""

    def __init__(self, handlers):
        self.handlers = handlers
        self.calls = []

    def open(self, req, timeout=None):
        url = req.full_url
        self.calls.append(url)
        handler = self.handlers.get(url)
        if handler is None:
            raise urllib.error.URLError(f"fake opener: tanimsiz URL {url}")
        return handler()


def _fetcher(handlers, resolve_hostname=None, max_bytes=None, min_delay=0.0):
    kwargs = dict(
        opener=_FakeOpener(handlers), sleep=lambda s: None, clock=lambda: 0.0,
        min_delay=min_delay,
    )
    if resolve_hostname is not None:
        kwargs["resolve_hostname"] = resolve_hostname
    if max_bytes is not None:
        kwargs["max_bytes"] = max_bytes
    return SafeFetcher(**kwargs)


def _default_resolve(host):
    # Host zaten sayısal bir IP literal'iyse (ör. testte doğrudan "127.0.0.1" verildiyse)
    # AYNEN döner -- gerçek DNS de böyle davranır, sahte bir "güvenli" IP'ye ÇEVİRMEZ.
    import ipaddress
    try:
        ipaddress.ip_address(host)
        return [host]
    except ValueError:
        pass
    # varsayılan test IP'si: gerçek/genel bir IP (özel/loopback DEĞİL).
    return {"ornek.com": ["93.184.216.34"], "yonlendirilen.com": ["93.184.216.34"]}.get(
        host, ["93.184.216.34"]
    )


def test_fetcher_normal_https_html_succeeds():
    handlers = {
        "https://ornek.com/robots.txt": lambda: _ROBOTS_ALLOW_ALL,
        "https://ornek.com/sayfa": lambda: _FakeResponse(
            200, {"Content-Type": "text/html; charset=utf-8"}, b"<html>merhaba</html>"
        ),
    }
    outcome = _fetcher(handlers, resolve_hostname=_default_resolve).fetch(
        "https://ornek.com/sayfa"
    )
    assert outcome.status == FETCH_OK and outcome.ok
    assert outcome.text == "<html>merhaba</html>"
    print("KAIZEN SAFE FETCHER NORMAL HTTPS/HTML TESTI: BASARILI")


def test_fetcher_pdf_content_type_succeeds():
    handlers = {
        "https://ornek.com/robots.txt": lambda: _ROBOTS_ALLOW_ALL,
        "https://ornek.com/belge.pdf": lambda: _FakeResponse(
            200, {"Content-Type": "application/pdf"}, b"%PDF-1.4 ..."
        ),
    }
    outcome = _fetcher(handlers, resolve_hostname=_default_resolve).fetch(
        "https://ornek.com/belge.pdf"
    )
    assert outcome.status == FETCH_OK and outcome.content_type == "application/pdf"
    print("KAIZEN SAFE FETCHER PDF ICERIK TURU TESTI: BASARILI")


def test_fetcher_follows_redirect_and_revalidates_target():
    handlers = {
        "https://ornek.com/robots.txt": lambda: _ROBOTS_ALLOW_ALL,
        "https://ornek.com/eski": lambda: (_ for _ in ()).throw(
            urllib.error.HTTPError(
                "https://ornek.com/eski", 302, "Found",
                {"Location": "https://yonlendirilen.com/yeni"}, None,
            )
        ),
        "https://yonlendirilen.com/robots.txt": lambda: _ROBOTS_ALLOW_ALL,
        "https://yonlendirilen.com/yeni": lambda: _FakeResponse(
            200, {"Content-Type": "text/html"}, b"<html>hedef</html>"
        ),
    }
    outcome = _fetcher(handlers, resolve_hostname=_default_resolve).fetch(
        "https://ornek.com/eski"
    )
    assert outcome.status == FETCH_OK
    assert outcome.final_url == "https://yonlendirilen.com/yeni"
    assert outcome.redirect_chain == ("https://ornek.com/eski",)
    print("KAIZEN SAFE FETCHER YONLENDIRME TAKIBI TESTI: BASARILI")


def test_fetcher_redirect_to_localhost_is_blocked_not_silently_followed():
    """madde 14 KRİTİK: final_url (yönlendirme SONRASI) SSRF için YENİDEN doğrulanmalı --
    `accounting/crawler.py`'de EKSİK olan tam bu kontrol (Faz 1 denetim bulgusu)."""
    handlers = {
        "https://ornek.com/robots.txt": lambda: _ROBOTS_ALLOW_ALL,
        "https://ornek.com/kotu": lambda: (_ for _ in ()).throw(
            urllib.error.HTTPError(
                "https://ornek.com/kotu", 302, "Found",
                {"Location": "http://localhost:8080/admin"}, None,
            )
        ),
    }
    outcome = _fetcher(handlers, resolve_hostname=_default_resolve).fetch(
        "https://ornek.com/kotu"
    )
    assert outcome.status == FETCH_BLOCKED_SSRF
    assert "localhost" in outcome.final_url
    print("KAIZEN SAFE FETCHER YONLENDIRME->LOCALHOST ENGELI TESTI: BASARILI")


def test_fetcher_localhost_direct_is_blocked():
    outcome = _fetcher({}, resolve_hostname=_default_resolve).fetch("http://localhost/gizli")
    assert outcome.status == FETCH_BLOCKED_SSRF
    print("KAIZEN SAFE FETCHER DOGRUDAN LOCALHOST ENGELI TESTI: BASARILI")


def test_fetcher_127_0_0_1_is_blocked():
    outcome = _fetcher({}, resolve_hostname=_default_resolve).fetch("http://127.0.0.1/gizli")
    assert outcome.status == FETCH_BLOCKED_SSRF
    print("KAIZEN SAFE FETCHER 127.0.0.1 ENGELI TESTI: BASARILI")


def test_fetcher_private_ip_is_blocked():
    def resolve(host):
        return ["192.168.1.50"] if host == "ic-sunucu.sirket.local" else _default_resolve(host)

    outcome = _fetcher({}, resolve_hostname=resolve).fetch(
        "http://ic-sunucu.sirket.local/panel"
    )
    assert outcome.status == FETCH_BLOCKED_SSRF
    print("KAIZEN SAFE FETCHER PRIVATE IP ENGELI TESTI: BASARILI")


def test_fetcher_file_scheme_is_blocked():
    outcome = _fetcher({}, resolve_hostname=_default_resolve).fetch("file:///etc/passwd")
    assert outcome.status == FETCH_BLOCKED_SSRF
    print("KAIZEN SAFE FETCHER file:// SEMASI ENGELI TESTI: BASARILI")


def test_fetcher_credentials_in_url_is_blocked():
    outcome = _fetcher({}, resolve_hostname=_default_resolve).fetch(
        "https://kullanici:sifre@ornek.com/gizli"
    )
    assert outcome.status == FETCH_BLOCKED_SSRF
    print("KAIZEN SAFE FETCHER URL ICINDE KIMLIK BILGISI ENGELI TESTI: BASARILI")


def test_fetcher_oversized_response_is_rejected():
    handlers = {
        "https://ornek.com/robots.txt": lambda: _ROBOTS_ALLOW_ALL,
        "https://ornek.com/buyuk": lambda: _FakeResponse(
            200, {"Content-Type": "text/html"}, b"x" * 1000
        ),
    }
    outcome = _fetcher(handlers, resolve_hostname=_default_resolve, max_bytes=100).fetch(
        "https://ornek.com/buyuk"
    )
    assert outcome.status == FETCH_TOO_LARGE
    print("KAIZEN SAFE FETCHER ASIRI BUYUK YANIT REDDI TESTI: BASARILI")


def test_fetcher_timeout_is_reported_not_raised():
    def raise_timeout():
        raise TimeoutError("zaman asimi")

    handlers = {
        "https://ornek.com/robots.txt": lambda: _ROBOTS_ALLOW_ALL,
        "https://ornek.com/yavas": raise_timeout,
    }
    outcome = _fetcher(handlers, resolve_hostname=_default_resolve).fetch(
        "https://ornek.com/yavas"
    )
    assert outcome.status == FETCH_TIMEOUT
    print("KAIZEN SAFE FETCHER TIMEOUT TESTI: BASARILI")


class _ResponseThatTimesOutDuringRead:
    """GERÇEK PC BULGUSU (2026-09-25, 3. gerçek UAT çalışması): bağlantı/başlıklar
    SORUNSUZ açılır (`opener.open()` başarılı döner -- madde 15'teki mevcut timeout
    korumasının kapsadığı aşama BUDUR), ama YAVAŞ/damla-damla veri gönderen bir sunucuda
    asıl gövde `resp.read()` sırasında zaman aşımına uğrayabilir -- bu FARKLI bir aşama,
    eski kodda HİÇ yakalanmıyordu. Gerçek PC'de `research/engine.py::run_research` içinde
    ham `TimeoutError` olarak dışarı sızdı (madde 26 ihlali: '4/a-4/b-4/c' sorularından
    ikisi ('A','B') UAT raporunda `UNEXPECTED_EXCEPTION` olarak yakalandı)."""

    def __init__(self):
        self.status = 200
        self.headers = {"Content-Type": "text/html; charset=utf-8"}

    def read(self, n=-1):
        raise TimeoutError("govde okunurken zaman asimi (yavas/damla-damla sunucu)")

    def getcode(self):
        return self.status


def test_fetcher_timeout_during_body_read_is_reported_not_raised():
    """REPRODUCER: bağlantı açılır, başlıklar gelir, ama `resp.read()` zaman aşımına
    uğrar. ESKİ kodda bu `TimeoutError` `SafeFetcher.fetch()`'ten (ve dolayısıyla
    `research/engine.py::run_research()`'ten) YAKALANMADAN dışarı sızar -- bu test ESKİ
    kodda `TimeoutError` ile BAŞARISIZ olur (fetch() 'ASLA raise etmez' sözleşmesini
    ihlal eder)."""
    handlers = {
        "https://ornek.com/robots.txt": lambda: _ROBOTS_ALLOW_ALL,
        "https://ornek.com/damla-damla": lambda: _ResponseThatTimesOutDuringRead(),
    }
    outcome = _fetcher(handlers, resolve_hostname=_default_resolve).fetch(
        "https://ornek.com/damla-damla"
    )
    assert outcome.status == FETCH_TIMEOUT, (
        f"gövde okuma zaman aşımı FETCH_TIMEOUT olarak raporlanmalıydı, "
        f"alınan: {outcome.status!r}"
    )
    print("KAIZEN SAFE FETCHER GOVDE OKUMA SIRASINDA TIMEOUT TESTI: BASARILI")


def test_fetcher_403_is_never_bypassed():
    def raise_403():
        raise urllib.error.HTTPError("https://ornek.com/yasak", 403, "Forbidden", {}, None)

    handlers = {
        "https://ornek.com/robots.txt": lambda: _ROBOTS_ALLOW_ALL,
        "https://ornek.com/yasak": raise_403,
    }
    outcome = _fetcher(handlers, resolve_hostname=_default_resolve).fetch(
        "https://ornek.com/yasak"
    )
    assert outcome.status == FETCH_HTTP_ERROR and outcome.http_status == 403
    print("KAIZEN SAFE FETCHER 403 ASLA ASILMAZ TESTI: BASARILI")


def test_fetcher_429_is_never_bypassed():
    def raise_429():
        raise urllib.error.HTTPError(
            "https://ornek.com/limit", 429, "Too Many Requests", {}, None
        )

    handlers = {
        "https://ornek.com/robots.txt": lambda: _ROBOTS_ALLOW_ALL,
        "https://ornek.com/limit": raise_429,
    }
    outcome = _fetcher(handlers, resolve_hostname=_default_resolve).fetch(
        "https://ornek.com/limit"
    )
    assert outcome.status == FETCH_HTTP_ERROR and outcome.http_status == 429
    print("KAIZEN SAFE FETCHER 429 ASLA ASILMAZ TESTI: BASARILI")


def test_fetcher_robots_deny_blocks_before_any_content_fetch():
    handlers = {
        "https://ornek.com/robots.txt": lambda: _ROBOTS_DENY_ALL,
        "https://ornek.com/yasakli-sayfa": lambda: _FakeResponse(
            200, {"Content-Type": "text/html"}, b"<html>bu asla okunmamali</html>"
        ),
    }
    opener = _FakeOpener(handlers)
    fetcher = SafeFetcher(
        opener=opener, resolve_hostname=_default_resolve, sleep=lambda s: None,
        clock=lambda: 0.0,
    )
    outcome = fetcher.fetch("https://ornek.com/yasakli-sayfa")
    assert outcome.status == FETCH_BLOCKED_ROBOTS
    assert "https://ornek.com/yasakli-sayfa" not in opener.calls, (
        "robots red dedikten SONRA asil sayfaya YINE DE istek atilmis -- KRITIK HATA"
    )
    print("KAIZEN SAFE FETCHER ROBOTS RED (ICERIGE HIC DOKUNMADAN) TESTI: BASARILI")


def test_fetcher_robots_unreadable_fails_safe_deny_not_permissive():
    """madde 15: robots durumu belirsiz/okunamıyorsa PERMISSIVE varsayılmaz."""
    def raise_error():
        raise urllib.error.URLError("baglanti reddedildi")

    handlers = {
        "https://ornek.com/robots.txt": raise_error,
        "https://ornek.com/sayfa": lambda: _FakeResponse(
            200, {"Content-Type": "text/html"}, b"<html>x</html>"
        ),
    }
    opener = _FakeOpener(handlers)
    fetcher = SafeFetcher(
        opener=opener, resolve_hostname=_default_resolve, sleep=lambda s: None,
        clock=lambda: 0.0,
    )
    outcome = fetcher.fetch("https://ornek.com/sayfa")
    assert outcome.status == FETCH_BLOCKED_ROBOTS
    assert "https://ornek.com/sayfa" not in opener.calls
    print("KAIZEN SAFE FETCHER ROBOTS OKUNAMIYORSA FAIL-SAFE RED TESTI: BASARILI")


def test_fetcher_robots_404_means_allow_all():
    """robots.txt'nin kendisi 404 ise -- standart kural -- tüm yollara izin var sayılır
    (bu PERMISSIVE-varsayım DEĞİL, robots.txt standardının kendisi)."""
    def raise_404():
        raise urllib.error.HTTPError("https://ornek.com/robots.txt", 404, "Not Found", {}, None)

    handlers = {
        "https://ornek.com/robots.txt": raise_404,
        "https://ornek.com/sayfa": lambda: _FakeResponse(
            200, {"Content-Type": "text/html"}, b"<html>x</html>"
        ),
    }
    outcome = _fetcher(handlers, resolve_hostname=_default_resolve).fetch(
        "https://ornek.com/sayfa"
    )
    assert outcome.status == FETCH_OK
    print("KAIZEN SAFE FETCHER ROBOTS 404 = TUM YOLLARA IZIN TESTI: BASARILI")


def test_fetcher_malformed_url_is_rejected():
    # host'u olan ama gecersiz (http:// / https:///...) -> FETCH_MALFORMED (net "host yok").
    for bad_url in ("http://", "https:///yol-var-host-yok"):
        outcome = _fetcher({}, resolve_hostname=_default_resolve).fetch(bad_url)
        assert outcome.status == FETCH_MALFORMED, f"{bad_url!r} -> {outcome.status}"
    # şeması bile olmayan çöp bir string -> güvenli şema listesinde olmadığı için
    # FETCH_BLOCKED_SSRF olarak reddedilir -- ikisi de "asla getirilmedi" anlamına gelir,
    # önemli olan REDDEDİLMESİ, etiketin ikisinden hangisi olduğu değil.
    outcome = _fetcher({}, resolve_hostname=_default_resolve).fetch("not-a-url-at-all")
    assert outcome.status in (FETCH_MALFORMED, FETCH_BLOCKED_SSRF)
    print("KAIZEN SAFE FETCHER MALFORMED URL REDDI TESTI: BASARILI")


if __name__ == "__main__":
    test_fetcher_normal_https_html_succeeds()
    test_fetcher_pdf_content_type_succeeds()
    test_fetcher_follows_redirect_and_revalidates_target()
    test_fetcher_redirect_to_localhost_is_blocked_not_silently_followed()
    test_fetcher_localhost_direct_is_blocked()
    test_fetcher_127_0_0_1_is_blocked()
    test_fetcher_private_ip_is_blocked()
    test_fetcher_file_scheme_is_blocked()
    test_fetcher_credentials_in_url_is_blocked()
    test_fetcher_oversized_response_is_rejected()
    test_fetcher_timeout_is_reported_not_raised()
    test_fetcher_403_is_never_bypassed()
    test_fetcher_429_is_never_bypassed()
    test_fetcher_robots_deny_blocks_before_any_content_fetch()
    test_fetcher_robots_unreadable_fails_safe_deny_not_permissive()
    test_fetcher_robots_404_means_allow_all()
    test_fetcher_malformed_url_is_rejected()
