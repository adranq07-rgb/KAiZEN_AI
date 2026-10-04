"""classify() ölçümü (iş emri "RAG v2 - Faz 1" madde 4 ve 12'nin 7. adımı).

`KaizenBrain.classify()` şu an tamamen SÖZCÜK-İÇERME (substring membership) tabanlı: dört
sabit küme (`ACCOUNTING_TERMS`, `OFFICE_TERMS`, matematik için bir regex, yoksa "general")
üzerinde `terim in fold_tr(mesaj)` kontrolü yapılıyor -- kelime sınırı, morfoloji ya da
bağlam YOK. Bu dosya iş emrinin madde 4'te sorduğu sorulara TEK TEK, kanıtla cevap verir:

  * hangi intent'ler var?            -> `test_classify_documents_the_four_intents_and_their_keyword_sets`
  * hangi anahtar kelimeler?          -> aynı test (ACCOUNTING_TERMS/OFFICE_TERMS'i class'tan okur)
  * doğal sorularda nerede kaçırıyor? -> `test_classify_false_negative_*` (bilgi VAR ama intent yanlış)
  * YANLIŞ POZİTİF de var mı?         -> `test_classify_false_positive_*` (BULGU: bu dosyada YENİ
                                          bulunan, iş emrinde sorulmayan ama ciddi bir ek durum --
                                          "gelir"/"gider" gibi kısa terimler, alakasız günlük
                                          cümlelerdeki fiil çekimlerinin İÇİNDE bile eşleşiyor)
  * yanlış sınıflandırma sonraki zincire ne yapıyor? / fallback var mı? / cevap kaybına
    neden oluyor mu? -> `test_classify_false_negative_*` ve `test_classify_false_positive_causes_unnecessary_research`
    fonksiyonları, her durumda TAM `brain.answer()` zincirini de çalıştırıp `last_trace` ile
    sonucu (cevap kaybı mı, fallback mi kurtardı mı, gereksiz araştırma mı) kanıtlıyor.

Golden exam'i ve gerçek hayat sınavını (tests/test_real_world_exam.py) DEĞİŞTİRMİYORUZ; bu
dosya classify()'ı TEK BAŞINA (unit seviyesinde) izole ederek daha kesin kanıt üretiyor.
Henüz classify()'ı LLM tabanlı bir sınıflandırıcıyla DEĞİŞTİRMİYORUZ (iş emri madde 4:
"Henüz bunu LLM classifier ile değiştirme. Önce başarısızlık örneklerini testlerle kanıtla.").

Yalnız sahte sağlayıcılar ve izole (tempfile) bir LearningStore kullanılır; gerçek
Hermes/Ollama'ya ya da gerçek data/logs/memory dosyalarına hiç dokunulmaz.
"""
import tempfile
from pathlib import Path

from core.kaizen_brain import KaizenBrain
from memory.brain_manager import BrainManager
from memory.learning_store import LearningStore
from tests.doubles import NullExperienceMemory


class OfflineProvider:
    def ask(self, prompt):
        return "Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod); yalnız yerel hafızadan cevap verebilirim."


class CountingAgent:
    """Araştırma zincirinin KAÇ KEZ ve HANGİ soruyla çağrıldığını sayar -- 'araştırmaya gereksiz
    gidildi mi?' sorusunu (iş emri madde 3) doğrudan, sayıyla kanıtlamak için."""

    def __init__(self, reply="Kaizen: araştırma başarısız (offline test ortamı)."):
        self.calls = []
        self.reply = reply

    def ask(self, question):
        self.calls.append(question)
        return self.reply


def _brain(agent=None, store=None):
    return KaizenBrain(
        OfflineProvider(), agent or CountingAgent(),
        brain_manager=BrainManager(
            learning_store=store or LearningStore(Path(tempfile.mkdtemp()) / "cls.sqlite3"),
            experience_memory=NullExperienceMemory(), log_dir=tempfile.mkdtemp(),
        ),
    )


def test_classify_documents_the_four_intents_and_their_keyword_sets():
    """iş emri madde 4, soru 1-2: 'hangi intent'ler var? hangi anahtar kelimeler kullanılıyor?'

    Dört intent VAR: accounting / office / mathematics / general (kodun kendisinden okunuyor,
    burada YİNELENMİYOR ki liste ileride değişince bu test sessizce eskimesin)."""
    assert KaizenBrain.classify("muhasebe: her hangi bir şey") == "accounting"
    assert isinstance(KaizenBrain.ACCOUNTING_TERMS, set) and len(KaizenBrain.ACCOUNTING_TERMS) > 10
    assert isinstance(KaizenBrain.OFFICE_TERMS, set) and len(KaizenBrain.OFFICE_TERMS) > 5
    # "general" -- hiçbir kümeye girmeyen, matematik regex'ine de uymayan her şey için varsayılan.
    assert KaizenBrain.classify("bugün hava nasıl") == "general"
    assert KaizenBrain.classify("2 + 2") == "mathematics"
    assert KaizenBrain.classify("excel'de hücre birleştirme") == "office"
    print("KAIZEN CLASSIFY DORT INTENT/ANAHTAR KELIME BELGELEME TESTI: BASARILI")


# --- YANLIŞ NEGATİF: bilgi yerel hafızada mevcutken, classify() yüzünden domain yanlış çıkıyor ---

def test_classify_false_negative_account_code_reference_is_no_longer_fatal_after_chart_fix():
    """'760 ile 770 arasındaki fark ne?' -- classify() HÂLÂ (bilerek, düzeltilmeden) 'general'
    diyor; ACCOUNTING_TERMS çıplak hesap kodlarını (760/770) tanımıyor, bu BAŞLI BAŞINA hâlâ bir
    classify() hatası (kanıtlanmaya devam ediyor). AMA iş emri madde 11 kapsamında YAPILAN bir
    düzeltmeyle (bkz. accounting/chart_of_accounts.py'deki 2026-09-23 DÜZELTME notu:
    ChartOfAccounts.answer()'a eklenen çoklu-kod karşılaştırma yolu, _TRIGGERS kapısından ve
    dolayısıyla classify()'dan TAMAMEN BAĞIMSIZ çalışıyor), bu ÖRNEK artık CEVAP KAYBINA yol
    AÇMIYOR -- `_exact_tools` zaten domain'den önce, domain'den bağımsız çalıştığı için (bkz.
    core/kaizen_brain.py::_answer_core). Bu, classify() hatalarının katmanlar arası BAĞIMSIZ
    güvenlik ağlarıyla (burada: chart'ın kendi çoklu-kod mantığı; başka bir örnekte: 'general'
    dalının _from_memory fallback'i, bkz. aşağıdaki test) telafi edilebildiğinin İKİNCİ, FARKLI
    bir mekanizmayla kanıtı."""
    question = "760 ile 770 arasındaki fark ne?"
    assert KaizenBrain.classify(question) == "general"  # hâlâ yanlış: 'accounting' olmalıydı

    brain = _brain()
    answer = brain.answer(question)
    assert brain.last_trace.intent == "general"  # classify() hatası hâlâ orada
    assert brain.last_trace.route == "chart"  # ama artık cevap kaybolmuyor
    assert brain.last_trace.confidence == "VERIFIED"
    assert brain.last_trace.refusal_reason is None
    assert "760" in answer and "770" in answer
    print("KAIZEN CLASSIFY YANLIS NEGATIF (HESAP KODU) ARTIK CEVAP KAYBETMIYOR TESTI: BASARILI")


def test_classify_false_negative_sgk_regime_codes_without_literal_sgk_word():
    """'4/a 4/b 4/c nedir...' -- metinde harfiyen 'sgk' geçmiyor (yalnız rejim kodları geçiyor),
    ACCOUNTING_TERMS yalnız TAM 'sgk' alt dizisini arıyor. SONUÇ: domain='general'. Burada CEVAP
    KAYBI var (ayrı bir retrieval bulgusuyla BİRLEŞEREK -- bkz. tests/test_retrieval_failures.py:
    domain doğru 'accounting' olsaydı bile coverage() aynı nedenle 0 çıkardı)."""
    question = "4/a 4/b 4/c nedir, aralarındaki fark ne?"
    assert KaizenBrain.classify(question) == "general"  # BEKLENEN: 'accounting' olmalıydı

    brain = _brain()
    answer = brain.answer(question)
    assert brain.last_trace.intent == "general"
    assert brain.last_trace.refusal_reason == "model_unavailable"
    assert answer
    print("KAIZEN CLASSIFY YANLIS NEGATIF (SGK REJIM KODU) = CEVAP KAYBI TESTI: BASARILI")


def test_classify_false_negative_is_not_always_fatal_thanks_to_general_fallback():
    """iş emri madde 4, soru: 'bir soru yanlış sınıflandırıldığında sonraki zincire ne oluyor?
    fallback mekanizması var mı?' -- CEVAP: EVET, var. `_answer_core`'daki domain=='general' dalı,
    model cevap veremeyince `_from_memory(question, 'general', current)`'a düşüyor; bu, sorunun
    konusu yerel curriculum'da (learning_store) VARSA classify() hatasını TELAFİ EDİYOR. Yani
    'sınıflandırma başarısızlığı DOĞRUDAN cevap kaybına neden oluyor mu?' sorusunun cevabı: HAYIR,
    HER ZAMAN değil -- yalnız fallback'in de bulamadığı durumlarda (yukarıdaki iki test)."""
    question = "İşe giriş bildirgesi kaç gün içinde verilmeli?"  # 'sgk' kelimesi geçmiyor
    assert KaizenBrain.classify(question) == "general"  # yanlış: 'accounting' olmalıydı

    store = LearningStore(Path(tempfile.mkdtemp()) / "seeded.sqlite3")
    from memory.seed_loader import load_seeds
    load_seeds(store)
    brain = _brain(store=store)
    answer = brain.answer(question)
    # classify() hâlâ yanlış ama cevap KAYBOLMADI -- fallback curriculum'dan buldu.
    assert brain.last_trace.intent == "general"
    assert brain.last_trace.route == "memory_extractive"
    assert brain.last_trace.confidence == "SUPPORTED"
    assert "İşe Giriş Bildirgesi" in answer
    print("KAIZEN CLASSIFY YANLIS NEGATIF AMA FALLBACK KURTARIYOR TESTI: BASARILI")


# --- YANLIŞ POZİTİF: substring-içerme, alakasız cümleleri de 'accounting' sayıyor (YENİ bulgu) ---

def test_classify_false_positive_verb_conjugation_contains_accounting_term_as_substring():
    """BULGU (bu ölçümde YENİ bulundu, iş emrinde doğrudan sorulmasa da GÜVEN MODELİ ve 'araştırmaya
    gereksiz gidildi mi?' sorularıyla doğrudan ilgili): classify() `terim in metin` diye SUBSTRING
    kontrolü yapıyor, kelime sınırı YOK. ACCOUNTING_TERMS'teki 'gelir' (gelir=income) ve 'gider'
    (gider=expense), gündelik Türkçenin en sık koşullu fiil çekimlerinden 'gelirse' (gelmek+se,
    'eğer gelirse') ve 'giderse'/'gidersem' (gitmek+se, 'eğer giderse') İÇİNDE de birebir geçiyor.
    Muhasebeyle HİÇ ilgisi olmayan gündelik cümleler böylece 'accounting' domain'ine düşüyor."""
    for question in (
        "Yarın müşteri gelirse ne yapayım?",
        "Oraya giderse ne olur?",
        "Bu yoldan gidersem daha hızlı olur mu?",
    ):
        assert KaizenBrain.classify(question) == "accounting", (
            f"{question!r} artık 'accounting' saymıyor -- bu test güncellenmeli (regresyon değil, "
            "düzelme olabilir; iş emri madde 11 kapsamında classify() düzeltilirse burası güncellenecek)"
        )
    print("KAIZEN CLASSIFY YANLIS POZITIF (FIIL COKUMU/SUBSTRING) TESPIT TESTI: BASARILI")


def test_classify_false_positive_causes_unnecessary_research():
    """Tarihsel test adı: yanlış domain artık tek başına araştırmayı tetiklememeli."""
    agent = CountingAgent()
    brain = _brain(agent=agent)
    question = "Yarın müşteri gelirse ne yapayım?"
    brain.answer(question)
    assert brain.last_trace.intent == "accounting"
    assert brain.last_trace.route == "not_found_offline"
    assert brain.last_trace.used_research is False
    assert agent.calls == [], "Güncel bilgi gerektirmeyen soru araştırma çağırmamalı"
    print("KAIZEN GEREKSIZ ARASTIRMA YOK TESTI: BASARILI")


if __name__ == "__main__":
    test_classify_documents_the_four_intents_and_their_keyword_sets()
    test_classify_false_negative_account_code_reference_without_trigger_word()
    test_classify_false_negative_sgk_regime_codes_without_literal_sgk_word()
    test_classify_false_negative_is_not_always_fatal_thanks_to_general_fallback()
    test_classify_false_positive_verb_conjugation_contains_accounting_term_as_substring()
    test_classify_false_positive_causes_unnecessary_research()
    print("KAIZEN CLASSIFY OLCUM TESTLERI: BASARILI")
