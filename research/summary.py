"""KAIZEN — ResearchResult -> öğrenme katmanına GÜVENLİ METADATA özeti.

Research Engine'in (UAT'tan PASS almış) çıktısından, öğrenme/trace katmanına yalnızca
SAYAÇ ve DURUM bilgisi geçer -- ham pasaj, iddia değeri, snippet, oran/tutar ASLA geçmez.
Bu, "SUPPORTED olmak ile FactRegistry'de VERIFIED olmak aynı şey değildir" sınırının kodda
açık halidir: buradan çıkan hiçbir alan bir FACT taşıyamaz; `source_domains` yalnız alan
adıdır (ör. gib.gov.tr).

Yalnız GERÇEKTEN gözlemlenenler doldurulur; araştırma çalışmadıysa bu fonksiyon hiç
çağrılmaz (çağıran `None` tutar) -- olmayan olay uydurulmaz.
"""
from research.models import CONFLICTED, SUPPORTED, PARTIAL


def summarize_research(result, provider_name=""):
    real = [e for e in result.evidence if e.has_real_content()]
    official_real = [e for e in real if e.official]
    domains = sorted({e.domain for e in real if e.domain})
    independent_domains = {e.domain for e in real if e.domain}

    if result.status == SUPPORTED:
        consensus = "agreed"
    elif result.status == CONFLICTED:
        consensus = "conflicted"
    elif result.status == PARTIAL:
        consensus = "partial"
    else:
        consensus = "none"

    verified_periods = [c.period for c in result.verified_claims]
    if verified_periods and all(verified_periods):
        temporal_match = True      # doğrulanmış her iddianın dönemi belirlenmiş (verifier zorunlu kılar)
    else:
        temporal_match = None      # bilinmiyor -- uydurulmaz

    return {
        "status": result.status,
        "search_provider": provider_name,
        "search_health": result.search_health,
        "query_count": len(result.queries),
        "result_count": len(result.evidence),
        "fetched_count": len(real),
        "evidence_count": len(real),
        "official_evidence_count": len(official_real),
        "independent_source_count": len(independent_domains),
        "consensus_status": consensus,
        "conflict_count": len(result.conflicts),
        "temporal_match": temporal_match,
        "source_domains": tuple(domains[:6]),
        "elapsed_ms": int(round(result.elapsed_time * 1000)),
    }
