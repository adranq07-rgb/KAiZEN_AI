"""Static Scrapling transport behind the existing SSRF/robots/redirect policy."""
import io
import time
import urllib.error
from email.message import Message
from dataclasses import dataclass
from urllib.parse import urlparse
from research.fetcher import SafeFetcher, FetchOutcome
from research.models import FETCH_OK, FETCH_HTTP_ERROR, FETCH_TIMEOUT, FETCH_TOO_LARGE


@dataclass(frozen=True)
class ScraplingOutcome(FetchOutcome):
    extracted_text: str = ""


class _SizeLimit(Exception):
    pass


class _Transport:
    def __init__(self, owner, robots_opener):
        self.owner = owner
        self.robots_opener = robots_opener

    def open(self, request, timeout):
        # Existing robots handling stays authoritative; redirects remain disabled.
        if urlparse(request.full_url).path == '/robots.txt':
            return self.robots_opener.open(request, timeout=timeout)
        from scrapling.fetchers import Fetcher
        chunks = bytearray()
        too_large = False
        def receive(data):
            nonlocal too_large
            if len(chunks) + len(data) > self.owner.max_bytes:
                too_large = True
                return 0
            chunks.extend(data)
            return len(data)
        self.owner.metrics['scrapling_attempted'] = True
        try:
            response = Fetcher.get(request.full_url, timeout=timeout,
                headers=dict(request.header_items()), follow_redirects=False,
                retries=1, stealthy_headers=False, impersonate=None,
                content_callback=receive)
        except Exception as exc:
            if too_large:
                raise _SizeLimit() from None
            raise urllib.error.URLError(type(exc).__name__) from None
        headers = Message()
        for key, value in response.headers.items():
            headers[key] = str(value)
        if response.status >= 300:
            raise urllib.error.HTTPError(request.full_url, response.status,
                                         'HTTP response', headers, None)
        result = io.BytesIO(bytes(chunks))
        result.status = response.status
        result.headers = headers
        return result


class ScraplingAdapter:
    def __init__(self, timeout=15.0, max_bytes=5_000_000, max_redirects=5, min_delay=1.5):
        self.max_bytes = max_bytes
        self._fallback = SafeFetcher(timeout=timeout, max_bytes=max_bytes,
            max_redirects=max_redirects, min_delay=min_delay)
        self._primary = SafeFetcher(timeout=timeout, max_bytes=max_bytes,
            max_redirects=max_redirects, min_delay=min_delay)
        self._primary._opener = _Transport(self, self._primary._opener)
        self.reset_metrics()

    def reset_metrics(self):
        self.metrics = dict(scrapling_attempted=False, scrapling_success=False,
            scrapling_latency_ms=0.0, scrapling_fallback_used=False)
        self.events = []

    def fetch(self, url):
        start = time.perf_counter()
        used = False
        fallback = False
        try:
            outcome = self._primary.fetch(url)
            if outcome.ok:
                if outcome.content_type.startswith(('text/html', 'application/xhtml')):
                    from scrapling.parser import Selector
                    page = Selector(outcome.body, url=outcome.final_url)
                    main = page.css('main, article')
                    text = (main[0] if main else page).get_all_text(strip=True,
                        ignore_tags=('script', 'style', 'nav', 'footer', 'noscript'))
                    outcome = ScraplingOutcome(**outcome.__dict__, extracted_text=str(text))
                used = True
            elif outcome.status in (FETCH_TIMEOUT, FETCH_HTTP_ERROR) and outcome.http_status not in (401,403,429):
                fallback = True
        except _SizeLimit:
            outcome = FetchOutcome(status=FETCH_TOO_LARGE, url=url, detail='Scrapling content limit')
        except Exception:
            fallback = True
        if fallback:
            self.metrics['scrapling_fallback_used'] = True
            try:
                outcome = self._fallback.fetch(url)
            except Exception:
                outcome = FetchOutcome(status=FETCH_HTTP_ERROR, url=url, detail='Fetch unavailable')
        elapsed = (time.perf_counter()-start)*1000
        self.metrics['scrapling_success'] |= used
        self.metrics['scrapling_latency_ms'] += elapsed
        self.events.append(dict(url=url, final_url=outcome.final_url, status=outcome.status,
            scrapling_success=used, fallback=fallback, latency_ms=elapsed,
            bytes=len(outcome.body)))
        return outcome


def get_adapter(timeout=15.0, max_bytes=5_000_000):
    # Per-brain instance: no global mutable telemetry or import-time network work.
    return ScraplingAdapter(timeout=timeout, max_bytes=max_bytes)
