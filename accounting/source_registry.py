from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class TrustedSource:
    name: str
    domains: tuple[str, ...]
    priority: int
    excluded_path_terms: tuple[str, ...] = ()
    reference_only: bool = False
    # Kaizen'in kendi toplayıcısı için: başlangıç adresleri ve alan adı başına yol kısıtı
    seed_urls: tuple[str, ...] = ()
    path_limits: tuple[tuple[str, str], ...] = ()


TRUSTED_SOURCES = (
    # Genel sayfalar JS ile doluyor; bunun yerine cdn.gib.gov.tr'deki statik resmi PDF'ler taranır
    TrustedSource("Gelir Idaresi Baskanligi", ("gib.gov.tr", "cdn.gib.gov.tr"), 1,
                  seed_urls=("https://cdn.gib.gov.tr/api/gibportal-file/file/getFileResources"
                             "?objectKey=arsiv%2Fyardim-kaynaklar%2Fyararli-bilgiler%2F"
                             "gelir-vergisi-tarifeleri%2Fgelir-vergisi-tarifesi-2026.pdf",)),
    TrustedSource("TURMOB", ("turmob.org.tr",), 1),
    TrustedSource("Muhasebe TR", ("muhasebetr.com",), 2),
    TrustedSource("Alomaliye", ("alomaliye.com",), 2,
                  ("forum", "soru-cevap", "yorum")),
    TrustedSource("PwC Turkiye", ("pwc.com.tr", "taxsummaries.pwc.com"), 2,
                  seed_urls=("https://taxsummaries.pwc.com/turkey",
                             "https://taxsummaries.pwc.com/turkey/corporate/taxes-on-corporate-income",
                             "https://www.pwc.com.tr/tr/",),
                  path_limits=(("taxsummaries.pwc.com", "/turkey"),)),
    TrustedSource("Vergiport", ("vergiport.com",), 2),
    TrustedSource("PKF Istanbul", ("pkf.com.tr",), 2),
    TrustedSource("Roedl Turkiye", ("roedl.com.tr",), 2),
    TrustedSource("Vergi Merkezi", ("vergimerkezi.com.tr",), 2),
    TrustedSource("Muhasebe Bilenler", ("muhasebebilenler.com",), 2,
                  ("forum", "sorular", "yorum")),
    TrustedSource("Muhasebe News", ("muhasebenews.com",), 2),
    TrustedSource("Vertax", ("vertax.com.tr",), 2),
    TrustedSource("DergiPark", ("dergipark.org.tr",), 3),
    TrustedSource("Verginet", ("verginet.net",), 2),
    TrustedSource("Denge Akademi", ("dengeakademi.com",), 2),
    TrustedSource("Ozdogrular", ("ozdogrular.com", "ozdogrular.com.tr"), 2),
    # Kullanıcının eklediği araç/parametre sitesi: hesaplama araçları ve Parametre Merkezi
    TrustedSource("Musavirler Kulubu", ("musavirlerkulubu.com.tr",), 2,
                  ("forum", "yorum", "giris", "uye"),
                  seed_urls=("https://musavirlerkulubu.com.tr/araclar",)),
)


def trusted_source_for_url(url):
    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return None
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    for source in TRUSTED_SOURCES:
        if not any(host == domain or host.endswith("." + domain)
                   for domain in source.domains):
            continue
        if any(term in path for term in source.excluded_path_terms):
            return None
        return source
    return None


def search_domains():
    return tuple(source.domains[0] for source in TRUSTED_SOURCES)


def source_by_name(name):
    for source in TRUSTED_SOURCES:
        if source.name.casefold() == name.casefold():
            return source
    return None


def path_allowed(source, url):
    """Alan adı başına tanımlı yol kısıtını uygular (ör. taxsummaries.pwc.com yalnız /turkey)."""
    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return False
    host = (parsed.hostname or "").lower()
    for domain, prefix in source.path_limits:
        if host == domain or host.endswith("." + domain):
            return parsed.path.lower().startswith(prefix.lower())
    return True
