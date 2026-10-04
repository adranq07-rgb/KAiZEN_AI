"""KAIZEN Research Engine — Evidence İnşası, Kaynak Otoritesi, Tazelik/Dönem Eşleşmesi
(İş Emri #2 madde 17, 18, 20, 21).

TEKRAR KULLANIM (madde 18, KESİN kural): kaynak otoritesi için PARALEL bir liste
YAZILMAZ -- `accounting/source_registry.py::trusted_source_for_url` DOĞRUDAN çağrılır.
`accounting/source_registry.py`'nin `priority` alanı (1=resmî, 2=meslekî/ikincil,
3=akademik) burada `research/models.py`'nin OFFICIAL/PROFESSIONAL/SECONDARY/UNKNOWN
sözleşmesine eşlenir -- iki liste değil, TEK gerçek kaynağın (source_registry) İKİ
farklı sözleşmeye çevrilmesi."""
import re
from datetime import date, datetime, timezone

from accounting.source_registry import trusted_source_for_url
from research.extractor import best_passage
from research.models import (
    Evidence,
    EVIDENCE_HIGH,
    EVIDENCE_LOW,
    EVIDENCE_MEDIUM,
    FETCH_OK,
    FETCH_SNIPPET_ONLY,
    OFFICIAL,
    PROFESSIONAL,
    SECONDARY,
    UNKNOWN_SOURCE,
    EVIDENCE_NEGATIVE_SIGNALS,
    EVIDENCE_POSITIVE_SIGNALS,
    EVIDENCE_FACT,
    EVIDENCE_EXAMPLE,
    EVIDENCE_FORECAST,
    EVIDENCE_HYPOTHETICAL,
    EVIDENCE_OUT_OF_PERIOD,
    EVIDENCE_UNKNOWN,
)

_YEAR = re.compile(r"\b(20\d{2})\b")


def source_type_and_authority(url):
    """madde 18: `source_registry`'nin priority'sinden TÜRETİLİR. Döner:
    (source_type, official: bool, source_name: str)."""
    source = trusted_source_for_url(url)
    if source is None:
        return UNKNOWN_SOURCE, False, ""
    if source.priority == 1:
        return OFFICIAL, True, source.name
    if source.priority == 2:
        return PROFESSIONAL, False, source.name
    return SECONDARY, False, source.name


def detect_period(published_at, text, today=None):
    """madde 20: SearXNG'nin kendi `publishedDate`'ine KÖRÜ KÖRÜNE güvenilmez -- önce
    İÇERİKTEN çıkarılan `published_at` (research/extractor.py), yoksa metindeki en
    yakın-zamanlı (bugünden ileri olmayan) yıl referansı denenir. Hiçbiri yoksa None
    (madde 20: bulunamazsa UYDURULMAZ, UNKNOWN bırakılır)."""
    today = today or date.today()
    if published_at:
        match = _YEAR.search(published_at)
        if match:
            return match.group(1)
    if text:
        years = [y for y in _YEAR.findall(text) if int(y) <= today.year + 1]
        if years:
            return max(years, key=int)
    return None


def temporal_matches(requested_period, evidence_period):
    """madde 21: istenen dönem (ör. planlayıcının '2026' talebi) ile kanıtın dönemi
    KESİN olarak uyuşmuyorsa (ikisi de biliniyor VE farklıysa) False -- 2024 kaynağı
    2026 sorusuna cevap SAYILMAZ. Belirsizlik (biri None) reddetmek için TEK BAŞINA
    yeterli değildir (o durumda çağıran taraf confidence'ı düşürür, ama Evidence'ı
    tamamen ATMAZ -- madde 25: eksik bilgiyi de raporla, gizleme)."""
    if requested_period is None or evidence_period is None:
        return True
    return requested_period == evidence_period


def _confidence_for(source_type, official, period_ok, has_real_content):
    if not has_real_content:
        return EVIDENCE_LOW  # madde 36: snippet-only asla yüksek güven değil
    if not period_ok:
        return EVIDENCE_LOW  # madde 21: dönem uyuşmazlığı güveni düşürür
    if official:
        return EVIDENCE_HIGH
    if source_type == PROFESSIONAL:
        return EVIDENCE_MEDIUM
    return EVIDENCE_LOW


def classify_evidence_passage(passage):
    """Passage içeriğine göre evidence sınıflandırması yapar."""
    if not passage:
        return EVIDENCE_UNKNOWN
    
    text = passage.lower()
    
    # Negative signals - hypothetical/example content
    for signal in EVIDENCE_NEGATIVE_SIGNALS:
        if signal in text:
            return EVIDENCE_HYPOTHETICAL
    
    # Check for example patterns
    if any(pattern in text for pattern in ["örnek", "örneğin", "örnek hesaplama", "hesaplama örneği", "varsayımsal", "varsayım"]):
        return EVIDENCE_EXAMPLE
    
    # Check for forecast/forecast signals
    if any(signal in text for signal in ["tahmini", "tahmin", "öngörü", "farazi", "öngörü", "temsili"]):
        return EVIDENCE_FORECAST
    
    # Positive signals - factual content
    for signal in EVIDENCE_POSITIVE_SIGNALS:
        if signal in text:
            return EVIDENCE_FACT
    
    # Default to FACT if it has real content and no negative signals
    return EVIDENCE_FACT


def build_evidence(
    evidence_id, subquestion, query, url, extracted=None, requested_period=None,
    search_provider="", retrieved_at=None, fetch_status=None,
):
    """Arama sonucu + (varsa) getirilip çıkarılmış içerik (`research/extractor.py::
    ExtractedContent`) -> `Evidence` (madde 17). `extracted` None ise -- hiç
    getirilmediyse (yalnızca arama sonucu URL/başlık biliniyor) YA DA getirilmeye
    ÇALIŞILIP engellendiyse (robots/SSRF/timeout/vb.) -- gerçek içerik yoktur. Hangi
    durumun bu olduğu `fetch_status` ile AYIRT EDİLİR (madde 13: 'hiç denenmedi' ile
    'denendi ama engellendi' KARIŞTIRILMAZ): `research/engine.py` gerçek bir
    `research/fetcher.py::FetchOutcome.status` geçirir (ör. FETCH_BLOCKED_ROBOTS);
    hiç geçirilmezse (yalnızca arama sonucu, fetch hiç denenmedi) varsayılan olarak
    `FETCH_SNIPPET_ONLY` kullanılır. Ne olursa olsun ASLA yüksek güvenle/VERIFIED ile
    karıştırılamaz (madde 13/36)."""
    retrieved_at = retrieved_at or datetime.now(timezone.utc).isoformat()
    source_type, official, source_name = source_type_and_authority(url)

    if extracted is None or not extracted.text:
        return Evidence(
            evidence_id=evidence_id, query=query, subquestion=subquestion, url=url,
            domain=extracted.domain if extracted else "", source_name=source_name,
            source_type=source_type, title=extracted.title if extracted else "",
            published_at=None, retrieved_at=retrieved_at, passage="", extracted_claim="",
            period=None, official=official, confidence=EVIDENCE_LOW,
            search_provider=search_provider, fetch_status=fetch_status or FETCH_SNIPPET_ONLY,
            classification=EVIDENCE_UNKNOWN,
        )

    period = detect_period(extracted.published_at, extracted.text)
    period_ok = temporal_matches(requested_period, period)
    passage = best_passage(subquestion or query, extracted.text)
    confidence = _confidence_for(source_type, official, period_ok, has_real_content=True)
    classification = classify_evidence_passage(passage)

    return Evidence(
        evidence_id=evidence_id, query=query, subquestion=subquestion, url=url,
        domain=extracted.domain, source_name=source_name, source_type=source_type,
        title=extracted.title, published_at=extracted.published_at or None,
        retrieved_at=retrieved_at, passage=passage, extracted_claim=passage,
        period=period, official=official, confidence=confidence,
        search_provider=search_provider, fetch_status=FETCH_OK,
        classification=classification,
    )
