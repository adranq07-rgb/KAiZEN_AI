"""Belge doğrulamada KESİN (kodla, model karışmadan) katman.

DÜZELTME (2026-09-23): Dış incelemenin 2. maddesi -- "'Belge doğrulama' şu anda modele dayalı
inceleme yapıyor. Belgedeki rakamlar ile kayıtlı parametreler modele gönderiliyor;
'uyuşuyor/uyuşmuyor' kararını kodla yapılmış kesin karşılaştırma vermiyor." -- burada ele alınıyor.

Bu modül, `memory/brain_manager.py::_find_contradictions`'ın (araştırma metnini parametre
defteriyle çapraz kontrol eden) TAM AYNI desenini kullanır: `accounting/facts.py::FactExtractor`
ile belge metninden (kullanıcının kendi Excel/PDF/görsel metni) aday değerler çıkarılır, her biri
`accounting/consensus.py::AccountingConsensus._normalize_value` ile normalize edilip süzgeçten
geçmiş DOĞRULANMIŞ (status == "verified") değerle birebir karşılaştırılır.

Önemli: bu karşılaştırma modelin cevaba karışmasını GEREKTİRMEZ -- model yalnızca burada
karşılığı bulunamayan (parametre defterinde tanımlı bir konu OLMAYAN) kalemler için serbest yorum
ekler (bkz. accounting/accounting_agent.py::verify_document). Bu yüzden burada üretilen sonuç,
gönderilen belge metninin TAMAMI üzerinde çalışır -- modele gönderilen metnin (maliyet/bağlam
nedeniyle) kısaltılmış olması bu katmanı ETKİLEMEZ.
"""
from accounting.consensus import AccountingConsensus
from accounting.facts import FactExtractor


def deterministic_matches(document_text, facts_registry):
    """Belge metnindeki rakam adaylarını çıkarır, süzgeçten geçmiş DOĞRULANMIŞ değerlerle kodla
    (model olmadan) karşılaştırır.

    Döner: liste of dict {topic, title, year, extracted_value, verified_value, matches, evidence}.
    `facts_registry` None ise veya belgede/parametre defterinde eşleşen bir konu yoksa boş liste
    döner (o durumda tüm yorum modele bırakılır -- eski davranış aynen korunur).
    """
    if facts_registry is None or not (document_text or "").strip():
        return []
    topics = getattr(facts_registry, "topics", None)
    if not topics:
        return []
    extractor = FactExtractor(topics)
    page = {"content": document_text, "url": "kaizen://kullanici-belgesi", "effective_year": None}
    titles = {t.id: t.title for t in topics}
    results = []
    for candidate in extractor.extract(page):
        verified = next(
            (r for r in facts_registry.rows(candidate.topic)
             if r["year"] == candidate.effective_year and r["status"] == "verified"), None,
        )
        if verified is None:
            continue
        matches = (
            AccountingConsensus._normalize_value(verified["value"])
            == AccountingConsensus._normalize_value(candidate.value)
        )
        results.append({
            "topic": candidate.topic,
            "title": titles.get(candidate.topic, candidate.topic),
            "year": candidate.effective_year,
            "extracted_value": candidate.value,
            "verified_value": verified["value"],
            "matches": matches,
            "evidence": candidate.evidence,
        })
    return results


def format_deterministic_block(matches):
    """`deterministic_matches()` sonucunu, kullanıcıya gösterilecek kısa bir metin bloğuna çevirir.
    Boş listede boş string döner (çağıran taraf bu durumda bloğu hiç eklemez)."""
    if not matches:
        return ""
    lines = ["KESİN KOD KARŞILAŞTIRMASI (model karışmadı, doğrudan hesaplandı):"]
    for m in matches:
        verdict = "UYUŞUYOR" if m["matches"] else "UYUŞMUYOR"
        lines.append(
            f"- {m['title']} ({m['year']}): belgede '{m['extracted_value']}', "
            f"doğrulanmış parametre defterinde '{m['verified_value']}' -> {verdict}"
        )
    return "\n".join(lines)
