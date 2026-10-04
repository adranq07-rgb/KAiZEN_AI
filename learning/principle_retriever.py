"""KAIZEN — Learning Brain v1: PrincipleRetriever (iş emri madde 8).

Fact retrieval (accounting/retriever.py::Retriever) "hangi bilgi?" sorusuna cevap
verir. Bu modül AYRI bir soruya cevap verir: "hangi düşünme kuralı (ilke)?".
KASITLI olarak accounting/retriever.py::Retriever'ı hiç İMPORT ETMEZ, hiç
ÇAĞIRMAZ -- iki bileşen mimari olarak bağımsızdır (madde 8).

Skorlama, memory/principle_registry.py'deki her ilkenin (veri odaklı, KOD içine
gömülü değil) `problem_structure.primary_signal`/`veto_signals` alanlarını
learning/problem_structure.py'nin ürettiği gözlemlenebilir yapısal sinyallerle
eşleştirir + applicability listesindeki birkaç sözcüksel ipucunu İKİNCİL bir
ağırlık olarak ekler (madde 9: yapısal sinyal birincil, kelime örtüşmesi ikincildir).

FACT güvenliği (madde 16, KESİNLİKLE YASAK): `RATE_QUERY` sinyali (güncel bir
oran/tutar/tarih sorusu) ateşlediğinde, HANGİ İLKE OLURSA OLSUN seçim EVRENSEL
olarak reddedilir -- bu, tek tek ilkelerin kendi `veto_signals` listesine güvenmek
yerine, retriever seviyesinde İKİNCİ bir (ve öncelikli) güvenlik katıdır.

Confidence (madde 11): HIGH/MEDIUM yalnız gerçek bir yapısal sinyal (primary_signal)
ateşlediğinde üretilir; LOW/NONE'da sistem bir ilke seçmeye ZORLANMAZ
(`selected` None kalır) -- "gözlemlenebilir eşleşme sinyallerinden türetilen",
modelin uydurduğu bir yüzde DEĞİL.
"""
from dataclasses import dataclass

from core.text_tr import fold_tr
from learning.problem_structure import detect_signals

HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"
NONE = "NONE"

# Evrensel FACT güvenlik sinyali (madde 16). Bu isim learning/problem_structure.py'nin
# ürettiği sinyal kimliğiyle AYNI OLMAK ZORUNDADIR; ayrılık olursa güvenlik kontrolü
# sessizce devre dışı kalır -- bu yüzden test_principle_retriever_rate_query_signal_name_matches
# bu ikisinin senkron kaldığını doğrular (bkz. tests/test_learning_transfer.py).
_FACT_SAFETY_SIGNAL = "RATE_QUERY"

_MAX_LEXICAL_SCORE = 2
_STRUCTURAL_SCORE = 3
_VETO_PENALTY = 4
_CLOSE_GAP_THRESHOLD = 2  # bu skordan az fark = "birden fazla yakın aday" (madde 18)


@dataclass(frozen=True)
class PrincipleCandidate:
    principle_id: str
    score: int
    structural_hit: bool
    veto_hit: bool
    matched_signals: tuple
    matched_keywords: tuple


@dataclass(frozen=True)
class PrincipleRetrievalResult:
    candidates: tuple            # skoru > 0 olan tüm adaylar (skor azalan sırada)
    selected: object              # principle_id (str) ya da None
    confidence: str                # HIGH/MEDIUM/LOW/NONE
    rejected: tuple                # (principle_id, reason) çiftleri -- seçilmeyen HER aday
    reason: str                    # tek satırlık, insan-okunur seçim gerekçesi
    fact_safety_triggered: bool = False  # madde 16: RATE_QUERY nedeniyle evrensel red mi?


def _score_entry(entry, signals, folded_question):
    structure = entry["problem_structure"]
    primary = structure.get("primary_signal")
    vetoes = set(structure.get("veto_signals", []))
    structural_hit = primary in signals
    veto_hit = bool(vetoes & signals)
    matched_keywords = tuple(
        kw for kw in entry["applicability"] if fold_tr(kw) in folded_question
    )
    score = (_STRUCTURAL_SCORE if structural_hit else 0)
    score += min(len(matched_keywords), _MAX_LEXICAL_SCORE)
    if veto_hit:
        score -= _VETO_PENALTY
    return PrincipleCandidate(
        principle_id=entry["principle_id"], score=score,
        structural_hit=structural_hit, veto_hit=veto_hit,
        matched_signals=tuple(sorted(signals & ({primary} | vetoes))),
        matched_keywords=matched_keywords,
    )


class PrincipleRetriever:
    """`registry`: memory.principle_registry.PrincipleRegistry (ya da aynı arayüze
    sahip herhangi bir nesne: `.all()` -> ilke sözlükleri listesi döner)."""

    def __init__(self, registry):
        self.registry = registry

    def retrieve(self, question):
        entries = self.registry.all()
        signals = detect_signals(question)
        folded_question = fold_tr(question)
        scored = [_score_entry(e, signals, folded_question) for e in entries]
        scored.sort(key=lambda c: c.score, reverse=True)
        positive = [c for c in scored if c.score > 0]

        fact_safety = _FACT_SAFETY_SIGNAL in signals
        if fact_safety:
            rejected = tuple(
                (c.principle_id, "FACT guvenligi geregi reddedildi (RATE_QUERY, madde 16): "
                                  "guncel oran/tutar/tarih sorulari ilke ile VERIFIED yapilamaz")
                for c in positive
            )
            return PrincipleRetrievalResult(
                candidates=tuple(positive), selected=None, confidence=NONE,
                rejected=rejected,
                reason="FACT sorusu tespit edildi (RATE_QUERY) — Principle Layer, madde 16 "
                       "geregi bu tur sorularda hicbir ilkeyi secmez.",
                fact_safety_triggered=True,
            )

        if not positive:
            return PrincipleRetrievalResult(
                candidates=(), selected=None, confidence=NONE,
                rejected=tuple((c.principle_id, "skor <= 0 (yapisal sinyal yok / veto edildi)")
                               for c in scored),
                reason="Hicbir ilke icin pozitif skor bulunamadi (ne yapisal sinyal ne "
                       "yeterli sozcuksel ortusme).",
            )

        top = positive[0]
        second = positive[1] if len(positive) > 1 else None
        gap = (top.score - second.score) if second else None
        ambiguous = second is not None and gap < _CLOSE_GAP_THRESHOLD

        if top.structural_hit and not ambiguous:
            confidence = HIGH
            selected = top.principle_id
            reason = (f"yapisal sinyal eslesti ({', '.join(top.matched_signals) or '-'}); "
                      f"net skor {top.score}, en yakin rakiple fark yeterli")
        elif top.structural_hit and ambiguous:
            confidence = MEDIUM
            selected = top.principle_id
            reason = (f"yapisal sinyal eslesti ama '{second.principle_id}' ile skor farki "
                      f"dusuk ({gap}); en yuksek skorlu aday secildi, iki aday da trace'te "
                      f"gorunur (madde 18: birden fazla aday)")
        else:
            confidence = LOW
            selected = None
            reason = ("yalnizca sozcuksel ortusme var, yapisal sinyal yok; dusuk guven — "
                       "sistem bir ilke secmeye ZORLANMADI (madde 11)")

        rejected = tuple(
            (c.principle_id, "en yuksek skorlu aday degil" if c.score <= top.score and c.principle_id != selected else "veto edildi")
            for c in positive if c.principle_id != selected
        )
        return PrincipleRetrievalResult(
            candidates=tuple(positive), selected=selected, confidence=confidence,
            rejected=rejected, reason=reason,
        )
