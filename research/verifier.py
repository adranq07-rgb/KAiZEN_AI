"""KAIZEN Research Engine — İddia (Claim) Çıkarma + Uzlaşı/Çelişki (İş Emri #2
madde 18-19, 22-25).

TEKRAR KULLANIM (madde 61, KESİN kural): bağımsızlık/uzlaşı kararı için PARALEL bir
mantık YAZILMAZ -- `accounting/consensus.py::AccountingConsensus` (zaten domain-bazlı
dedup + "resmî VEYA 2+ bağımsız kaynak" kuralını uygulayan sınıf) DOĞRUDAN çağrılır.
Sayısal aday-değer çıkarımı için `accounting/facts.py::FactExtractor` (zaten konu-
çapalı, cümle-mesafeli aday bulma mantığına sahip) aynı şekilde ÇAĞRILIR -- bir
Evidence pasajı, `FactExtractor.extract()`'a tek sayfalık bir "page" gibi verilir.
Soru -> konu (FactTopic) eşleştirmesi için `accounting/facts.py::match_topics`
(2026-09-24'te `FactRegistry.find_topics`'ten saf fonksiyona çıkarıldı, bkz. o
dosyadaki değişiklik) çağrılır -- sqlite'a HİÇ dokunulmaz.

KRİTİK SINIR (dürüstçe belgelenir, gizlenmez): bu modül yalnızca SAYISAL/konu-çapalı
alt-sorular için (`accounting/config/fact_topics.json`'da kayıtlı bir FactTopic'e
eşleşenler) gerçek bir ÇOK-KAYNAK UZLAŞI/ÇELİŞKİ kararı verebilir -- çünkü yalnız o
yolda `AccountingConsensus`'un normalize edip KARŞILAŞTIRABİLECEĞİ bir değer vardır.
Konu-dışı (nitel) alt-sorular için (ör. "amortisman mantığı nasıl işler") bu modülde
HİÇ LLM/semantik karşılaştırma YOKTUR (research/planner.py ve research/trigger.py ile
aynı tasarım ilkesi: kural-tabanlı, LLM'siz, yeniden üretilebilir) -- o yüzden nitel
iddialar için yalnızca ERİŞİLEBİLİRLİK/OTORİTE kontrolü yapılır (resmî kaynak VEYA 2+
bağımsız kaynak GERÇEKTEN getirildi mi), kaynakların birbirleriyle İÇERİK OLARAK
uyuşup uyuşmadığı KONTROL EDİLMEZ. Bu, `_qualitative_claim`'in docstring'inde ve
`docs/RESEARCH_ENGINE.md`'de açıkça belgelenir -- sessizce SUPPORTED denip
gizlenmez."""
from research.evidence import temporal_matches
from research.extractor import ExtractedContent
from accounting.consensus import AccountingConsensus, FactCandidate
from accounting.facts import FactExtractor, load_topics, match_topics
from accounting.retriever import Retriever
from research.models import (
    Claim,
    CONFLICTED,
    INSUFFICIENT,
    PARTIAL,
    SUPPORTED,
)

_ALL_TOPICS = load_topics()

# UAT bulgusu (2026-09-24, "kritik bug kontrolü"): GÜVENİLİR bir kaynak olmak, o kaynağın
# PASAJININ soruyla İLGİLİ olduğu anlamına GELMEZ -- resmî bir sitenin tamamen alakasız bir
# sayfası (ör. KDV genelgesi, soru amortisman hakkında olsa bile) yalnız otorite kontrolünden
# geçerek yanlışlıkla SUPPORTED üretebiliyordu (release blocker, bkz. _is_relevant). madde 61
# (aynı iş için iki farklı kod yok): puanlama fonksiyonunun kendisi `accounting/retriever.py::
# Retriever.coverage`/`.phrase_ok` -- `extractive_answer`'ın (strict=False) KENDİSİNİN zaten
# üretimde kullandığı AYNI ikili ölçüm -- burada YENİ bir alaka puanlaması İCAT EDİLMEZ. Eşik
# değeri (0.34 ~ terimlerin en az 1/3'ü) bilerek `extractive_answer`'ın "bunu CEVAP olarak
# göster" barından (0.6/0.75) DAHA DÜŞÜK: buradaki soru "bu tamamen alakasız mı" (düşük bar,
# madde 15 UAT bulgusunun asıl hedefi), "bu pasaj cevabın kendisi olacak kadar iyi mi" DEĞİL.
_QUALITATIVE_MIN_COVERAGE = 0.34


def resolve_topic(question):
    """Soru -> en iyi eşleşen `FactTopic` (yoksa None -- madde 61: paralel liste yok,
    `accounting/facts.py::match_topics` ÇAĞRILIR)."""
    matches = match_topics(_ALL_TOPICS, question)
    return matches[0] if matches else None


def _candidate_for(evidence, topic):
    """Bir `Evidence`'ın pasajından, `FactExtractor` ÇAĞRILARAK (yeniden yazılmadan)
    tek bir sayfa gibi aday değer(ler) çıkarır. `research/evidence.py::detect_period`
    zaten Evidence.period'u belirlemiş (madde 20) -- burada TEKRAR tahmin edilmez,
    doğrudan `effective_year` olarak geçirilir (None ise FactExtractor kendi metin-içi
    yıl arama mantığıyla dener, yine UYDURMAZ)."""
    if not evidence.has_real_content() or not evidence.passage:
        return []
    extractor = FactExtractor(topics=[topic])
    page = {
        "content": evidence.passage,
        "url": evidence.url,
        "effective_year": int(evidence.period) if evidence.period else None,
    }
    return extractor.extract(page)


def _numeric_claim(subquestion_text, evidence_list, topic, requested_period):
    """madde 18-19, 22-24: sayısal/konu-çapalı bir alt-soru için `AccountingConsensus`
    çağrılarak SUPPORTED/CONFLICTED/PARTIAL/INSUFFICIENT kararı verilir. PARTIAL ve
    CONFLICTED durumlarında Claim.value KASITLI OLARAK None bırakılır (madde 13: yalnız
    consensus'un ONAYLADIĞI -- yani SUPPORTED -- bir değer sayısal olarak taşınabilir;
    doğrulanmamış/çelişen bir "geçici" sayıyı Claim.value'ya koymak, henüz ONAYLANMAMIŞ
    bir rakamı onaylanmış gibi göstermeye çok yakın bir risktir -- ilgilenen taraf yine
    de `supporting_evidence_ids` üzerinden Evidence.passage'a ulaşabilir, madde 25:
    eksik/belirsiz bilgi GİZLENMEZ, yalnızca sayısal ALAN doldurulmaz).

    YENİ DOĞRULAMA SEVİYELERİ (5-KAYNAK / 3-EŞLEŞME MAJORITY KURALI):
    - verified (3+ bağımsız kaynak eşleşme) -> SUPPORTED (value dolu)
    - partially_verified (2 bağımsız kaynak) -> PARTIAL (value dolu ama kısıtlı notla)
    - single_source (1 kaynak) -> PARTIAL (value None, kaynağı göster)
    - unverified (0 kaynak) -> INSUFFICIENT
    - conflict -> CONFLICTED"""
    by_url = {}
    candidates = []
    for evidence in evidence_list:
        # Only use FACT-classified evidence for consensus
        if not evidence.is_fact_evidence():
            continue
        for candidate in _candidate_for(evidence, topic):
            candidates.append(candidate)
            by_url.setdefault(candidate.source_url, []).append(evidence.evidence_id)

    if not candidates:
        return None

    result = AccountingConsensus().decide(candidates)
    supporting_ids = tuple(sorted({
        eid for url in result.sources for eid in by_url.get(url, ())
    })) or tuple(sorted({e.evidence_id for e in evidence_list if e.is_fact_evidence()}))

    if result.status == "unverified":
        return Claim(
            text=subquestion_text, value=None, period=None,
            supporting_evidence_ids=supporting_ids, status=INSUFFICIENT,
        )
    if result.status == "verified":
        period_ok = temporal_matches(requested_period, str(result.effective_year))
        status = SUPPORTED if period_ok else PARTIAL
        return Claim(
            text=subquestion_text,
            value=result.value if status == SUPPORTED else None,
            period=str(result.effective_year) if result.effective_year else None,
            supporting_evidence_ids=supporting_ids, status=status,
        )
    if result.status == "partially_verified":
        # 2 kaynak - value döndür ama PARTIAL olarak işaretle
        period_ok = temporal_matches(requested_period, str(result.effective_year))
        status = PARTIAL
        return Claim(
            text=subquestion_text,
            value=result.value if period_ok else None,
            period=str(result.effective_year) if result.effective_year else None,
            supporting_evidence_ids=supporting_ids, status=status,
        )
    if result.status == "single_source":
        # 1 kaynak - value None, ama kaynak bilgisini göster
        period_ok = temporal_matches(requested_period, str(result.effective_year))
        status = PARTIAL
        return Claim(
            text=subquestion_text, value=None,
            period=str(result.effective_year) if result.effective_year else None,
            supporting_evidence_ids=supporting_ids, status=status,
        )
    if result.status == "conflict":
        return Claim(
            text=subquestion_text, value=None,
            period=str(result.effective_year) if result.effective_year else None,
            supporting_evidence_ids=supporting_ids, status=CONFLICTED,
        )
    # fallback
    return Claim(
        text=subquestion_text, value=None,
        period=str(result.effective_year) if result.effective_year else None,
        supporting_evidence_ids=supporting_ids, status=INSUFFICIENT,
    )


def _is_relevant(subquestion_text, evidence):
    """UAT bulgusu (madde 15): bir kaynağın GÜVENİLİR (official/professional, kayıtlı
    domain) olması, o kaynağın PASAJININ bu alt-soruyla İLGİLİ olduğu anlamına GELMEZ.
    `accounting/retriever.py::Retriever.coverage`/`.phrase_ok` -- `extractive_answer`'ın
    (strict=False) zaten kullandığı AYNI ikili eşik -- burada ÇAĞRILIR (madde 61: yeni
    bir alaka puanlaması İCAT EDİLMEZ). Boş pasaj asla 'ilgili' sayılmaz."""
    passage = evidence.passage or ""
    if not passage:
        return False
    return (
        Retriever.coverage(subquestion_text, passage) >= _QUALITATIVE_MIN_COVERAGE
        and Retriever.phrase_ok(subquestion_text, passage, window=12)
    )


def _qualitative_claim(subquestion_text, evidence_list, requested_period):
    """Konu-dışı (nitel) bir alt-soru için: önce İLGİLİLİK süzgeci (`_is_relevant`,
    madde 15 UAT düzeltmesi), SONRA yalnızca ERİŞİLEBİLİRLİK/OTORİTE kontrolü (bkz.
    modül docstring'i -- birden fazla İLGİLİ kaynağın birbirleriyle İÇERİK OLARAK tam
    uyuşup uyuşmadığı hâlâ KONTROL EDİLMEZ, bu dürüstçe bir sınırdır, uydurma bir
    'semantik uzlaşı' değildir; yalnızca 'bu pasaj soruyla alakalı mı' elenir)."""
    real = [e for e in evidence_list if e.has_real_content()]
    relevant = [e for e in real if _is_relevant(subquestion_text, e)]
    if not relevant:
        return None
    supporting_ids = tuple(sorted(e.evidence_id for e in relevant))
    official_ok = [e for e in relevant if e.official and temporal_matches(requested_period, e.period)]
    independent_sources = {e.source_name or e.domain for e in relevant
                            if temporal_matches(requested_period, e.period)}
    if official_ok or len(independent_sources) >= 2:
        return Claim(
            text=subquestion_text, value=None, period=requested_period,
            supporting_evidence_ids=supporting_ids, status=SUPPORTED,
        )
    return Claim(
        text=subquestion_text, value=None, period=requested_period,
        supporting_evidence_ids=supporting_ids, status=PARTIAL,
    )


def build_claims(plan, evidence_by_subquestion):
    """`research/planner.py::ResearchPlan` + `{subquestion.text: [Evidence, ...]}` ->
    `Tuple[Claim, ...]` (madde 22: bir alt-soru, hiç kanıt getirilmediyse -- evidence
    listesi boşsa ya da tamamı snippet-only ise -- HİÇ Claim ÜRETMEZ; bu durum
    `research/engine.py`'de `ResearchResult.missing_information`'a yansır, burada
    UYDURULMAZ)."""
    claims = []
    for subquestion in plan.subquestions:
        evidence_list = evidence_by_subquestion.get(subquestion.text, [])
        if not evidence_list:
            continue
        topic = resolve_topic(subquestion.text) or _topic_by_id(subquestion.accounting_topic)
        claim = None
        if topic is not None:
            claim = _numeric_claim(subquestion.text, evidence_list, topic, plan.requested_period)
        if claim is None:
            claim = _qualitative_claim(subquestion.text, evidence_list, plan.requested_period)
        if claim is not None:
            claims.append(claim)
    return tuple(claims)


def _topic_by_id(accounting_topic_hint):
    """`research/planner.py::Subquestion.accounting_topic` KABA bir alan sınıfı
    (ör. "sgk", "kdv") -- `accounting/config/fact_topics.json`'daki İNCE taneli
    `FactTopic.id`'lerle (ör. "sgk_prim_tavani") BİREBİR eşleşmez (iki farklı
    ontoloji, bkz. modül docstring'i). Bu yüzden yalnızca `resolve_topic` (soru
    metniyle `question_terms` eşleşmesi) GÜVENİLİR birincil yol; bu fonksiyon yalnız
    ek bir son çare olarak `accounting_topic` dizgesinin bir FactTopic id'sinin ALT
    dizgesi olduğu nadir örtüşen durumları yakalar, YENİ bir eşleme tablosu KURMAZ."""
    if not accounting_topic_hint:
        return None
    for topic in _ALL_TOPICS:
        if accounting_topic_hint in topic.id:
            return topic
    return None
