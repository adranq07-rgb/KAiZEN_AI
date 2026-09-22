"""HTML sayfasından başlık, ana metin, tarih ve bağlantıları çıkarır (yalnız standart kütüphane)."""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urldefrag

_SKIP = {"script", "style", "noscript", "nav", "footer", "aside", "form", "svg", "iframe", "template", "button", "select"}
_BLOCK = {"p", "div", "li", "ul", "ol", "br", "tr", "table", "section", "article", "main", "header",
          "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "dd", "dt", "td", "th"}
_VOID = {"br", "img", "input", "meta", "link", "hr", "area", "base", "col", "embed", "source", "track", "wbr"}
_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def normalize_date(value):
    """'2026-03-05T10:00:00+03:00' veya '05.03.2026' -> '2026-03-05' (bulunamazsa None)."""
    if not value:
        return None
    match = _DATE.search(value)
    if match:
        return match.group(0)
    match = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", value)
    if match:
        d, m, y = match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"
    return None


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.h1 = ""
        self.canonical = None
        self.published = None
        self.links = []
        self.feeds = []
        self._skip_depth = 0
        self._stack = []
        self._in_title = False
        self._in_h1 = False
        self._in_main = 0
        self._ld_buffer = None
        self._pieces = []
        self._main_pieces = []

    def handle_starttag(self, tag, attrs):
        attrs = {k: (v or "") for k, v in attrs}
        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self._ld_buffer = []
        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self._in_h1 = True
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or attrs.get("itemprop") or "").lower()
            if key in ("article:published_time", "og:published_time", "datepublished", "date", "dc.date",
                       "article:modified_time", "og:updated_time") and not self.published:
                self.published = normalize_date(attrs.get("content"))
        if tag == "time" and not self.published:
            self.published = normalize_date(attrs.get("datetime") or "")
        if tag == "link":
            rel = attrs.get("rel", "").lower()
            if rel == "canonical":
                self.canonical = attrs.get("href")
            if "alternate" in rel and ("rss" in attrs.get("type", "") or "atom" in attrs.get("type", "")):
                self.feeds.append(attrs.get("href", ""))
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag in ("article", "main") and not self._skip_depth:
            self._in_main += 1
        if tag in _SKIP and tag not in _VOID:
            self._skip_depth += 1
        if tag in _BLOCK and not self._skip_depth:
            self._emit("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_h1 = False
        if tag == "script" and self._ld_buffer is not None:
            self._parse_ld("".join(self._ld_buffer))
            self._ld_buffer = None
        if tag in _SKIP and self._skip_depth:
            self._skip_depth -= 1
        if tag in ("article", "main") and self._in_main and not self._skip_depth:
            self._in_main -= 1
        if tag in _BLOCK and not self._skip_depth:
            self._emit("\n")

    def handle_data(self, data):
        if self._ld_buffer is not None:
            self._ld_buffer.append(data)
            return
        if self._in_title:
            self.title += data
            return
        if self._skip_depth:
            return
        if self._in_h1:
            self.h1 += data
        self._emit(data)

    def _emit(self, text):
        self._pieces.append(text)
        if self._in_main:
            self._main_pieces.append(text)

    def _parse_ld(self, raw):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if not self.published:
                    self.published = normalize_date(str(item.get("datePublished") or item.get("dateModified") or ""))
                stack.extend(v for v in item.values() if isinstance(v, (dict, list)))
            elif isinstance(item, list):
                stack.extend(item)


def _clean(pieces):
    text = "".join(pieces)
    text = re.sub(r"[ \t\r\f\v ]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_html(html, base_url=""):
    """Döner: {'title','text','published_at','links','feeds','canonical'}."""
    parser = _Extractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # bozuk HTML: elde edilen kadarıyla devam
        pass
    main_text, all_text = _clean(parser._main_pieces), _clean(parser._pieces)
    use_main = len(main_text) >= 200 or (main_text and len(main_text) >= 0.5 * len(all_text))
    text = main_text if use_main else all_text
    title = " ".join((parser.h1 or parser.title).split()) or " ".join(parser.title.split())
    links = []
    for href in parser.links:
        href = href.strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        links.append(urldefrag(urljoin(base_url, href))[0])
    feeds = [urljoin(base_url, f) for f in parser.feeds if f]
    return {
        "title": title, "text": text, "published_at": parser.published,
        "links": links, "feeds": feeds, "canonical": parser.canonical,
    }
