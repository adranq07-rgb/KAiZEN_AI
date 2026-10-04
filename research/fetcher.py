"""KAIZEN Research Engine — Safe Fetcher (İş Emri #2 madde 14-15).

NEDEN `accounting/crawler.py::UrllibFetcher` KOPYALANMADI (bkz. docs/RESEARCH_ENGINE.md
§3): o fetcher YALNIZ önceden kayıtlı `accounting/source_registry.py` domain'lerini
çekmek için tasarlandı (`accept()` metodu domain allowlist'ini ZORUNLU kılıyor) --
Faz 1 denetimi bunun SSRF korumasına (private-IP/localhost/yönlendirme-sonrası-
doğrulama) hiç ihtiyacı olmadığını, çünkü zaten dar bir izin listesiyle çalıştığını
gösterdi. Bu modül ise arama motorunun (SearchProvider) bulduğu, ÖNCEDEN BİLİNMEYEN
herhangi bir domain'i güvenle çekmek ZORUNDA -- bu YENİ bir tehdit modeli, bu yüzden
YENİ (ama AYNI disiplinde: robots.txt zorunlu, 403/429 asla aşılmaz) bir modül.

Güvenlik kontrolleri (madde 14, hepsi):
  - yalnız http/https şeması (ftp://, file:// vb. RED)
  - URL içinde kimlik bilgisi (user:pass@host) RED
  - hostname private/loopback/link-local/reserved bir IP'ye çözülüyorsa RED (SSRF)
  - her YÖNLENDİRME (redirect) adımı YENİDEN doğrulanır (final_url'e kadar) -- madde 14
  - robots.txt zorunlu; durumu belirsiz/okunamıyorsa PERMISSIVE VARSAYILMAZ, RED
    (fail-safe deny, madde 15)
  - 403/429 ASLA aşılmaz (bir "engel" olarak işaretlenir, yeniden denenmez)
  - timeout, maksimum yanıt boyutu, temel MIME/tür kontrolü
  - host başına rate-limit (Crawl-delay varsa robots'tan okunur, yoksa min_delay)
"""
import ipaddress
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib import robotparser
from urllib.parse import urljoin, urlparse

from research.models import (
    FETCH_OK,
    FETCH_BLOCKED_ROBOTS,
    FETCH_BLOCKED_SSRF,
    FETCH_HTTP_ERROR,
    FETCH_MALFORMED,
    FETCH_TIMEOUT,
    FETCH_TOO_LARGE,
)

DEFAULT_TIMEOUT = 15.0
DEFAULT_MAX_BYTES = 5_000_000
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_MIN_DELAY = 1.5
DEFAULT_USER_AGENT = "KaizenResearchBot/1.0 (+kaizen research engine)"
ALLOWED_SCHEMES = ("http", "https")
ALLOWED_CONTENT_TYPE_PREFIXES = (
    "text/html", "application/xhtml+xml", "text/plain", "application/pdf",
)
_BLOCKED_HTTP_STATUSES = (401, 403, 429)


class _NoAutoRedirect(urllib.request.HTTPRedirectHandler):
    """Standart urllib deyimi: `redirect_request` None dönerse otomatik yönlendirme
    devre dışı kalır -- yönlendirme bir HTTPError (code=3xx, headers['Location']) olarak
    yükselir, biz her adımı KENDİMİZ (yeniden SSRF/robots doğrulamasıyla) takip ederiz."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class FetchOutcome:
    status: str
    url: str
    final_url: str = ""
    http_status: int = 0
    content_type: str = ""
    body: bytes = b""
    detail: str = ""
    redirect_chain: tuple = ()

    @property
    def ok(self):
        return self.status == FETCH_OK

    @property
    def text(self):
        if not self.body:
            return ""
        return self.body.decode("utf-8", errors="replace")


def _is_unsafe_ip(ip_text):
    try:
        addr = ipaddress.ip_address(ip_text)
    except ValueError:
        return True  # ayrıştırılamayan bir IP -- fail-safe: güvenli SAYMA
    return (
        addr.is_private or addr.is_loopback or addr.is_link_local
        or addr.is_reserved or addr.is_multicast or addr.is_unspecified
    )


class SafeFetcher:
    def __init__(
        self, timeout=DEFAULT_TIMEOUT, max_bytes=DEFAULT_MAX_BYTES,
        max_redirects=DEFAULT_MAX_REDIRECTS, min_delay=DEFAULT_MIN_DELAY,
        user_agent=DEFAULT_USER_AGENT, opener=None, resolve_hostname=None,
        sleep=None, clock=None,
    ):
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.min_delay = min_delay
        self.user_agent = user_agent
        self._opener = opener or urllib.request.build_opener(_NoAutoRedirect)
        self._resolve_hostname = resolve_hostname or (
            lambda host: [info[4][0] for info in socket.getaddrinfo(host, None)]
        )
        self._sleep = sleep or time.sleep
        self._clock = clock or time.monotonic
        self._last_request_at = {}
        self._robots_cache = {}

    # --- SSRF/şema/kimlik-bilgisi doğrulaması (madde 14) ---------------------------
    def _validate_url_safety(self, url):
        try:
            parsed = urlparse(url)
        except ValueError:
            return None, FetchOutcome(status=FETCH_MALFORMED, url=url, detail="ayrıştırılamayan URL")
        if parsed.scheme not in ALLOWED_SCHEMES:
            return None, FetchOutcome(
                status=FETCH_BLOCKED_SSRF, url=url,
                detail=f"izin verilmeyen şema: {parsed.scheme!r}",
            )
        if not parsed.hostname:
            return None, FetchOutcome(status=FETCH_MALFORMED, url=url, detail="host yok")
        if parsed.username or parsed.password:
            return None, FetchOutcome(
                status=FETCH_BLOCKED_SSRF, url=url, detail="URL içinde kimlik bilgisi yasak",
            )
        host = parsed.hostname.lower()
        if host in ("localhost",) or host.endswith(".localhost"):
            return None, FetchOutcome(status=FETCH_BLOCKED_SSRF, url=url, detail="localhost yasak")
        try:
            resolved_ips = self._resolve_hostname(host)
        except (socket.gaierror, OSError):
            return None, FetchOutcome(
                status=FETCH_BLOCKED_SSRF, url=url,
                detail="hostname çözülemedi (fail-safe: güvenli sayılmadı)",
            )
        if not resolved_ips or any(_is_unsafe_ip(ip) for ip in resolved_ips):
            return None, FetchOutcome(
                status=FETCH_BLOCKED_SSRF, url=url,
                detail=f"private/loopback/rezerve IP'ye çözülüyor: {resolved_ips}",
            )
        return parsed, None

    # --- robots.txt (madde 15: fail-safe deny, asla varsayılan izin) ----------------
    def _robots_allows(self, parsed):
        origin = f"{parsed.scheme}://{parsed.netloc}"
        cached = self._robots_cache.get(origin)
        if cached is None:
            cached = self._fetch_robots(origin)
            self._robots_cache[origin] = cached
        if cached is False:
            return False  # okunamadı/belirsiz -> RED (madde 15)
        return cached.can_fetch(self.user_agent, parsed.geturl())

    def _fetch_robots(self, origin):
        robots_url = origin + "/robots.txt"
        req = urllib.request.Request(robots_url, headers={"User-Agent": self.user_agent})
        try:
            resp = self._opener.open(req, timeout=self.timeout)
            status = getattr(resp, "status", None) or resp.getcode()
            body = resp.read(self.max_bytes)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                rp = robotparser.RobotFileParser()
                rp.parse([])  # robots.txt yok -> tüm yollara izin (standart kural)
                return rp
            return False  # 401/403/5xx/diğer: BELİRSİZ -> fail-safe RED
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError):
            return False  # ağ hatası: BELİRSİZ -> fail-safe RED
        if status and status >= 400:
            return False
        rp = robotparser.RobotFileParser()
        rp.parse(body.decode("utf-8", errors="replace").splitlines())
        return rp

    # --- host başına rate-limit (madde 14) ------------------------------------------
    def _wait_for_host(self, host):
        last = self._last_request_at.get(host)
        now = self._clock()
        if last is not None:
            elapsed = now - last
            if elapsed < self.min_delay:
                self._sleep(self.min_delay - elapsed)
        self._last_request_at[host] = self._clock()

    # --- ana giriş noktası -----------------------------------------------------------
    def fetch(self, url):
        """madde 14: güvenli getir. Her yönlendirme adımı YENİDEN SSRF+robots
        doğrulamasından geçer (final_url dahil -- madde 14'ün özellikle vurguladığı
        boşluk, `accounting/crawler.py`'de YOKTU, burada VAR)."""
        redirect_chain = []
        current_url = url
        for _hop in range(self.max_redirects + 1):
            parsed, blocked = self._validate_url_safety(current_url)
            if blocked is not None:
                return FetchOutcome(
                    status=blocked.status, url=url, final_url=current_url,
                    detail=blocked.detail, redirect_chain=tuple(redirect_chain),
                )
            if not self._robots_allows(parsed):
                return FetchOutcome(
                    status=FETCH_BLOCKED_ROBOTS, url=url, final_url=current_url,
                    detail="robots.txt izin vermiyor (veya okunamadı -- fail-safe deny)",
                    redirect_chain=tuple(redirect_chain),
                )
            self._wait_for_host(parsed.hostname)
            req = urllib.request.Request(current_url, headers={"User-Agent": self.user_agent})
            try:
                resp = self._opener.open(req, timeout=self.timeout)
            except urllib.error.HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308):
                    location = exc.headers.get("Location") if exc.headers else None
                    if not location:
                        return FetchOutcome(
                            status=FETCH_MALFORMED, url=url, final_url=current_url,
                            detail="yönlendirme ama Location başlığı yok",
                            redirect_chain=tuple(redirect_chain),
                        )
                    redirect_chain.append(current_url)
                    current_url = urljoin(current_url, location)
                    continue
                if exc.code in _BLOCKED_HTTP_STATUSES:
                    return FetchOutcome(
                        status=FETCH_HTTP_ERROR, url=url, final_url=current_url,
                        http_status=exc.code, detail=f"HTTP {exc.code} (asla aşılmaz)",
                        redirect_chain=tuple(redirect_chain),
                    )
                return FetchOutcome(
                    status=FETCH_HTTP_ERROR, url=url, final_url=current_url,
                    http_status=exc.code, detail=f"HTTP {exc.code}",
                    redirect_chain=tuple(redirect_chain),
                )
            except (socket.timeout, TimeoutError):
                return FetchOutcome(
                    status=FETCH_TIMEOUT, url=url, final_url=current_url,
                    detail="zaman aşımı", redirect_chain=tuple(redirect_chain),
                )
            except urllib.error.URLError as exc:
                return FetchOutcome(
                    status=FETCH_HTTP_ERROR, url=url, final_url=current_url,
                    detail=str(exc.reason), redirect_chain=tuple(redirect_chain),
                )

            content_type = ""
            headers = getattr(resp, "headers", None)
            if headers is not None:
                content_type = (headers.get("Content-Type") or "").split(";")[0].strip()
            if content_type and not any(
                content_type.startswith(p) for p in ALLOWED_CONTENT_TYPE_PREFIXES
            ):
                return FetchOutcome(
                    status=FETCH_MALFORMED, url=url, final_url=current_url,
                    content_type=content_type, detail=f"desteklenmeyen içerik türü: {content_type}",
                    redirect_chain=tuple(redirect_chain),
                )
            # SAĞLAMLIK (2026-09-25, gerçek PC UAT bulgusu -- 3. çalıştırma): `opener.open()`
            # başarıyla dönmüş olsa bile (bağlantı/başlıklar geldi), YAVAŞ/damla-damla veri
            # gönderen bir sunucuda asıl gövde `resp.read()` sırasında AYRICA zaman aşımına
            # uğrayabilir -- bu, yukarıdaki (satır ~216) `opener.open()` zaman aşımından FARKLI
            # bir aşamadır ve eskiden hiç yakalanmıyordu; ham `TimeoutError` doğrudan
            # `research/engine.py::run_research()`'e kadar sızıp onun "ASLA raise etmez"
            # (madde 26) sözleşmesini ihlal ediyordu. `fetch()`'in KENDİ sözleşmesi de aynı
            # şekilde hiçbir zaman raise etmemek olduğundan (madde 14/15), burası da
            # `opener.open()` ile AYNI FETCH_TIMEOUT sonucuna eşlenir.
            try:
                body = resp.read(self.max_bytes + 1)
            except (socket.timeout, TimeoutError):
                return FetchOutcome(
                    status=FETCH_TIMEOUT, url=url, final_url=current_url,
                    detail="zaman aşımı (gövde okunurken)", redirect_chain=tuple(redirect_chain),
                )
            if len(body) > self.max_bytes:
                return FetchOutcome(
                    status=FETCH_TOO_LARGE, url=url, final_url=current_url,
                    content_type=content_type, detail=f"{self.max_bytes} bayt sınırı aşıldı",
                    redirect_chain=tuple(redirect_chain),
                )
            status_code = getattr(resp, "status", None) or resp.getcode() or 200
            return FetchOutcome(
                status=FETCH_OK, url=url, final_url=current_url, http_status=status_code,
                content_type=content_type, body=body, redirect_chain=tuple(redirect_chain),
            )
        return FetchOutcome(
            status=FETCH_MALFORMED, url=url, final_url=current_url,
            detail=f"{self.max_redirects} yönlendirme sınırı aşıldı",
            redirect_chain=tuple(redirect_chain),
        )
