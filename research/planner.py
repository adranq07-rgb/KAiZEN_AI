"""KAIZEN Research Engine — Query Planner (İş Emri #2 madde 9-10).

KURAL (madde 10, KIRMIZI ÇİZGİ): bu modül bir oran/tutar/tarih/mevzuat SONUCU asla
ÜRETMEZ/UYDURMAZ -- yalnızca "hangi alt-sorular araştırılmalı" ve "hangi arama sorguları
denenmeli" kararını verir. Çıkardığı tek "yeni" bilgi, sorunun METNİNDE zaten var olan
bir yılı (ör. "2026") ya da "bu yıl/güncel" gibi göreli bir ifadeyi bugünün tarihine göre
somutlaştırmaktır -- bu bir SİSTEM GERÇEĞİdir (bugünün tarihi), bir mevzuat/oran/tutar
İDDİASI DEĞİLDİR.

Tasarım: LLM YOK (bu modül LLMProvider arayüzüne bağımlı değil -- madde 31: gelecekte
Hermes yerine yerel bir model gelse bile bu dosya değişmeden çalışır). Kural tabanlı,
`accounting/source_registry.py`'deki GERÇEKTEN KAYITLI güvenilir domain'leri kullanan basit
bir konu+dönem çıkarımı + şablon tabanlı arama sorgusu üretimi yapar.

TRUSTED SOURCE POLİTİKASI (EK DÜZELTME):
- Resmî kaynak (priority=1) ERİŞİLEBİLİRSE -> önceliklendir
- Resmî kaynak ERİŞİLEMEZSE (robots/WAF/rate-limit) -> diğer trusted kaynaklara (priority=2/3) geç
- Yeterli trusted evidence -> cevap ver
- 2+ bağımsız trusted kaynak aynı güncel bilgiyi destekliyorsa -> consensus oluştur
- Kaynaklar çelişiyorsa -> conflict olarak işaretle
- Yeterli evidence yoksa -> uydurma
- Resmî kaynak GERÇEKTEN okunmadıysa cevabı 'officially verified' olarak GÖSTERME
- Resmî kaynağa erişilememesi tek başına kullanıcıya cevap verilmesini ENGELLEME
- Stabil muhasebe bilgisinde web kaynağı ZORUNLULUĞU yaratma"""
import re
from datetime import date

from accounting.source_registry import TRUSTED_SOURCES
from core.text_tr import fold_tr
from research.models import ResearchPlan, Subquestion

# Konu anahtar kelimeleri -- core/kaizen_brain.py::ACCOUNTING_TERMS ile ÇAKIŞMAZ (o
# genel "bu soru muhasebe mi" sınıflandırması, bu ise "hangi ALT KONU" ayrımı içindir.
_TOPIC_KEYWORDS = (
    ("sgk", ("sgk", "sigorta", "prim", "4/a", "4/b", "4/c", "sigortali")),
    ("asgari_ucret", ("asgari ucret",)),
    ("kdv", ("kdv", "katma deger")),
    ("gelir_vergisi", ("gelir vergisi", "stopaj", "tevkifat", "gelir vergisi tarifesi")),
    ("kurumlar_vergisi", ("kurumlar vergisi",)),
    ("damga_vergisi", ("damga vergisi",)),
    ("amortisman", ("amortisman",)),
    ("e_fatura", ("e-fatura", "efatura", "e-arsiv", "e-defter")),
    ("kidem_tazminati", ("kidem", "ihbar tazminati")),
    ("harcirah", ("harcirah", "yolluk")),
)

# Tüm güvenilir domain'ler priority'ye göre ayrıştırılır
# priority=1: resmî (GİB, TÜRMOB, SGK, Resmi Gazete, Mevzuat)
# priority=2: mesleki/ikincil (Muhasebe TR, Alomaliye, PwC, vb.)
# priority=3: akademik (DergiPark)
_REGISTERED_OFFICIAL_DOMAINS = {
    d for source in TRUSTED_SOURCES if source.priority == 1 for d in source.domains
}
_REGISTERED_PROFESSIONAL_DOMAINS = {
    d for source in TRUSTED_SOURCES if source.priority == 2 for d in source.domains
}
_REGISTERED_SECONDARY_DOMAINS = {
    d for source in TRUSTED_SOURCES if source.priority == 3 for d in source.domains
}

# Konu -> öncelikli resmî domain'ler (kaynak registry'den gelenlerle sınırlı)
_TOPIC_OFFICIAL_DOMAINS = {
    "sgk": tuple(d for d in ("sgk.gov.tr",) if d in _REGISTERED_OFFICIAL_DOMAINS),
    "asgari_ucret": tuple(d for d in ("gib.gov.tr", "resmigazete.gov.tr")
                           if d in _REGISTERED_OFFICIAL_DOMAINS),
}

# Konu -> mesleki/ikincil domain'ler (fallback için)
_TOPIC_PROFESSIONAL_DOMAINS = {
    "sgk": tuple(d for d in ("muhasebetr.com", "muhasebebilenler.com", "vergiport.com", "musavirlerkulubu.com.tr")
                           if d in _REGISTERED_PROFESSIONAL_DOMAINS),
    "kdv": tuple(d for d in ("muhasebetr.com", "vergiport.com", "alomaliye.com", "muhasebenews.com", "vertax.com.tr")
                          if d in _REGISTERED_PROFESSIONAL_DOMAINS),
    "gelir_vergisi": tuple(d for d in ("pwc.com.tr", "taxsummaries.pwc.com", "pkf.com.tr", "roedl.com.tr")
                                    if d in _REGISTERED_PROFESSIONAL_DOMAINS),
    "amortisman": tuple(d for d in ("muhasebetr.com", "muhasebebilenler.com")
                                     if d in _REGISTERED_PROFESSIONAL_DOMAINS),
    "asgari_ucret": tuple(d for d in ("muhasebetr.com", "vergiport.com")
                                       if d in _REGISTERED_PROFESSIONAL_DOMAINS),
}

_YEAR = re.compile(r"\b(20[0-9]{2})\b")
_CURRENT_YEAR_PHRASES = ("bu yil", "guncel", "simdiki", "su anki", "yeni yil")


def _detect_topic(normalized):
    for topic, keywords in _TOPIC_KEYWORDS:
        if any(kw in normalized for kw in keywords):
            return topic
    return ""


def _detect_period(question, today):
    """Sorunun METNİNDE zaten var olan bir yılı okur; yoksa 'bu yıl/güncel' gibi göreli
    bir ifade varsa bugünün YILINI (sistem gerçeği) döner; hiçbiri yoksa None (madde 10:
    UYDURMA YOK -- period belirsizse None kalır, bir yıl İCAT EDİLMEZ)."""
    normalized = fold_tr(question)
    match = _YEAR.search(question)
    if match:
        return match.group(1)
    if any(phrase in normalized for phrase in _CURRENT_YEAR_PHRASES):
        return str(today.year)
    return None


def build_plan(question, today=None):
    """madde 9-10: soru -> alt-sorular -> arama sorguları. En az 1, en çok 4 alt-soru
    üretir (madde 34: 'gereksiz alt-soru' / 'eksik kritik alt-soru' dengesi -- sabit 5
    değil, duruma göre).

    TRUSTED SOURCE POLİTİKASI:
    1. Önce genel sorgu (tüm domain'ler)
    2. Resmî kaynaklar (priority=1) - varsa önceliklendir
    3. Mesleki/ikincil kaynaklar (priority=2) - resmî erişilemezse fallback
    4. Resmi Gazete / Mevzuat - genel mevzuat araması
    5. Akademik kaynaklar (priority=3) - son çare
    """
    today = today or date.today()
    normalized = fold_tr(question)
    topic = _detect_topic(normalized)
    period = _detect_period(question, today)

    subquestions = [
        Subquestion(text=question, search_query=question.strip(), accounting_topic=topic)
    ]

    if period:
        topic_label = topic or question.strip()

        # 1. Resmî kaynaklar (priority=1) - öncelikli denenir
        official_domains = _TOPIC_OFFICIAL_DOMAINS.get(topic, ("gib.gov.tr",))
        for domain in official_domains:
            query = f"site:{domain} {topic_label} {period}"
            if query not in {s.search_query for s in subquestions}:
                subquestions.append(Subquestion(
                    text=f"{question} — resmî kaynak ({domain}, {period})",
                    search_query=query, accounting_topic=topic,
                ))

        # 2. Mesleki/ikincil kaynaklar (priority=2) - resmî erişilemezse fallback
        # Tek bir "mesleki kaynaklar" alt-sorusu oluştur (birden fazla domain'de arama
        # yapması için site: kısıtlaması YOK -- arama motoru ilgili mesleki siteleri
        # bulabilir). Bu sayede birden fazla bağımsız mesleki kaynak TEK alt-soruda
        # toplanır ve verifier 2+ kaynak uzlaşı kontrolü yapabilir.
        professional_domains = _TOPIC_PROFESSIONAL_DOMAINS.get(topic, ())
        if professional_domains:
            query = f"{topic_label} {period}"
            if query not in {s.search_query for s in subquestions}:
                subquestions.append(Subquestion(
                    text=f"{question} — mesleki kaynaklar",
                    search_query=query, accounting_topic=topic,
                ))

        # 3. Resmi Gazete / Mevzuat genel araması
        resmi_gazete_query = f"resmi gazete {topic_label} {period}"
        if resmi_gazete_query not in {s.search_query for s in subquestions}:
            subquestions.append(Subquestion(
                text=f"{question} — Resmî Gazete ({period})",
                search_query=resmi_gazete_query, accounting_topic=topic,
            ))

        # 4. Akademik kaynaklar (priority=3) - son çare
        secondary_domains = tuple(d for d in _REGISTERED_SECONDARY_DOMAINS)
        if secondary_domains:
            query = f"{topic_label} {period}"
            if query not in {s.search_query for s in subquestions}:
                subquestions.append(Subquestion(
                    text=f"{question} — akademik kaynaklar ({period})",
                    search_query=query, accounting_topic=topic,
                ))

    # En fazla 4 alt-soruyla sınırla (madde 34: dengeli plan)
    if len(subquestions) > 4:
        subquestions = subquestions[:4]

    return ResearchPlan(
        question=question, subquestions=tuple(subquestions), requested_period=period,
    )
