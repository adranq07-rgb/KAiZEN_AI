"""Retrieval ölçümü (iş emri "RAG v2 - Faz 1" madde 5 ve 12'nin 8. adımı).

`tests/test_retriever.py` (mevcut, DEĞİŞTİRİLMEDİ) Retriever'ın Türkçe ek farkını tanıdığı
İKİ yönlü durumu doğrular. Bu dosya farklı bir amaca hizmet eder: iş emri madde 5'in tek tek
sorduğu sorulara -- "%60 sınırı nerede kullanılıyor? soru kısaysa ne oluyor? eş anlamlı
kelimelerde ne oluyor? kelime sırası değişince ne oluyor? uzun doğal sorularda gereksiz
kelimeler skoru düşürüyor mu? Türkçe ek kırpıcı hangi örneklerde başarısız? bilgi mevcut
olduğu halde retrieval kaçırıyor mu?" -- somut, yeniden üretilebilir testlerle cevap verir.
En az 10 test istendi (madde 5); burada 12 var.

Bu aşamada (madde 5, son cümle) embedding'i ana retrieval'a KATMIYORUZ; yalnız mevcut
lexical (Jaccard/coverage benzeri) retrieval'ın gerçek başarısını ölçüyoruz.

Testlerin çoğu `Retriever.coverage`/`phrase_ok`/`extractive_answer`'ı DOĞRUDAN, sentetik
metinlerle çağırır (hızlı, gerçek dosyaya dokunmaz). Gerçek üretim içeriğiyle kanıtlanması
gereken bulgular (curriculum'da bilgi VARKEN kaçırılması) `memory.seed_loader.load_seeds` ile
izole bir `tempfile` LearningStore'a yüklenmiş GERÇEK Kaizen curriculum'unu (knowledge/*.json)
kullanır -- ama bu da salt-okunur, gerçek data/logs/memory dosyalarına hiç dokunulmaz.
"""
import tempfile
from pathlib import Path

from accounting.accounting_brain import AccountingBrain
from accounting.retriever import Retriever, Evidence
from core.kaizen_brain import KaizenBrain
from core.text_tr import fold_tr, stem_tr, tokens_tr
from memory.learning_store import LearningStore
from memory.seed_loader import load_seeds


def _seeded_accounting_brain():
    store = LearningStore(Path(tempfile.mkdtemp()) / "retrieval_probe.sqlite3")
    load_seeds(store)
    return AccountingBrain(store)


def _evidence_from_rows(rows):
    return [
        Evidence(
            "ders", f"{row['subject']} — {row.get('section') or 'bölüm'}",
            row["text"].split(" Anahtar sözcükler:")[0][:5000],
            curated=row.get("source_type") == "curated",
            keywords=row["text"].partition(" Anahtar sözcükler:")[2],
        )
        for row in rows
    ]


# --- 1) "%60 benzerlik sınırı nerelerde kullanılıyor?" --------------------------------------

def test_retrieval_min_coverage_threshold_is_060_non_strict_and_exact_boundary_passes():
    """extractive_answer() içinde `min_coverage = 1.0 if strict else 0.6` -- sınır DEĞERİN
    KENDİSİ (tam 0.6) hâlâ KABUL ediliyor (>=), bir altı (0.4) REDDEDİLİYOR."""
    question = "alfa beta gamma delta epsilon"  # 5 anlamlı terim
    text_060 = "Alfa Beta Gamma referans metni burada duruyor ve başka konulardan bahsetmiyor."  # 3/5 eşleşir
    text_040 = "Alfa Beta referans metni burada duruyor ve başka konulardan bahsetmiyor."  # 2/5 eşleşir
    assert Retriever.coverage(question, text_060) == 0.6
    assert Retriever.coverage(question, text_040) == 0.4
    assert Retriever.extractive_answer(question, [Evidence("ders", "t", text_060, curated=True)], strict=False) is not None
    assert Retriever.extractive_answer(question, [Evidence("ders", "t", text_040, curated=True)], strict=False) is None
    print("KAIZEN RETRIEVAL ESIK (0.6) SINIR DEGERI TESTI: BASARILI")


def test_retrieval_strict_mode_requires_full_100_percent_coverage():
    """`strict=True` (needs_current_research()==True olduğunda kullanılıyor) eşiği 1.0'a
    çıkarıyor -- 0.6 durumunda BİLE (bir önceki testteki text_060) strict modda reddediliyor."""
    question = "alfa beta gamma delta epsilon"
    text_060 = "Alfa Beta Gamma referans metni burada duruyor ve başka konulardan bahsetmiyor."
    assert Retriever.extractive_answer(question, [Evidence("ders", "t", text_060, curated=True)], strict=True) is None
    print("KAIZEN RETRIEVAL STRICT MOD (1.0 ESIK) TESTI: BASARILI")


# --- 2) "Soru kısaysa ne oluyor?" -------------------------------------------------------------

def test_retrieval_short_single_term_question_over_trusts_a_coincidental_match():
    """BULGU: soru TEK anlamlı terimden oluşuyorsa (ör. yalnız 'vergi'), o terim metinde HANGİ
    BAĞLAMDA geçerse geçsin coverage=1.0 (yani '%100 örtüşme') çıkıyor -- konuyla hiç ilgisi
    olmayan bir cümlede bile. Kısa sorularda coverage tek başına güvenilir bir ölçü değil."""
    question = "vergi nedir"  # "nedir" FILLER'da olduğu için tek anlamlı terim: "vergi"
    assert Retriever._terms(question) == ["vergi"]
    unrelated_text = "Bu belgede vergi kelimesi bir kere geçer ama konu tamamen farklıdır: partiye kim geliyor sorusu."
    assert Retriever.coverage(question, unrelated_text) == 1.0
    print("KAIZEN RETRIEVAL KISA SORU ASIRI GUVEN TESTI: BASARILI")


# --- 3) "Eş anlamlı kelimelerde ne oluyor?" ----------------------------------------------------

def test_retrieval_synonyms_are_not_recognized_no_thesaurus():
    """BULGU: 'işçi' (soru) ile 'çalışan' (metin) eş anlamlıdır ama Retriever'da hiçbir eş
    anlamlı/kavramsal sözlük yok -- yalnız YÜZEYSEL ek kırpma (stem_tr) var, anlam eşleşmesi
    yok. Sonuç: coverage 1.0 DEĞİL (yalnız diğer terimler üzerinden kısmi bir skor)."""
    question = "işçi sigorta primi ne kadar"
    text = "Çalışanın sigorta primi işveren tarafından ödenir."
    coverage = Retriever.coverage(question, text)
    assert 0.0 < coverage < 1.0, f"beklenen: kısmi (0-1 arası) skor, gelen: {coverage}"
    assert "isci" not in tokens_tr(text) and "calisan" not in tokens_tr(question)  # gerçekten eş anlamlı, ortak kelime yok
    print(f"KAIZEN RETRIEVAL ES ANLAMLI KELIME (ISCI/CALISAN) TESTI: BASARILI (coverage={coverage:.3f})")


# --- 4) "Kelime sırası değişince ne oluyor?" ---------------------------------------------------

def test_retrieval_word_order_does_not_affect_coverage_or_phrase_ok():
    """coverage()/phrase_ok() küme (bag-of-words) tabanlı çalışıyor -- soru kelimelerinin SIRASI
    hiçbir fark yaratmıyor. Bu, doğal dilin çeşitliliğine karşı FAYDALI bir sağlamlık (ÖNEMLİ
    NEGATİF SONUÇ: sıra bir başarısızlık kaynağı DEĞİL) ama aynı zamanda sırayla taşınan anlam
    farklarını ('X Y'den farklıdır' ile 'Y X'ten farklıdır' arasındaki farkı) da ayırt edemediği
    anlamına geliyor -- bu ayrı bir (henüz gözlenmemiş, teorik) sınırlama olarak not edilir."""
    text = "Kurumlar vergisi oranı, ilgili kanunda belirlenen orandır."
    q_normal = "kurumlar vergisi oranı nedir"
    q_reordered = "oranı nedir kurumlar vergisi"
    assert Retriever.coverage(q_normal, text) == Retriever.coverage(q_reordered, text) == 1.0
    assert Retriever.phrase_ok(q_normal, text) == Retriever.phrase_ok(q_reordered, text) is True
    print("KAIZEN RETRIEVAL KELIME SIRASI ETKISIZ (SAGLAMLIK) TESTI: BASARILI")


# --- 5) "Uzun doğal sorularda gereksiz kelimeler skoru düşürüyor mu?" --------------------------

def test_retrieval_long_natural_question_dilutes_coverage_with_extra_real_words():
    """BULGU: coverage() = eşleşen terim / TOPLAM terim. Sorunun ÖZÜ aynı kalsa da, kullanıcı
    doğal, kibar, dolaylı bir cümle kurarsa (STOP_WORDS/FILLER'da olmayan ekstra GERÇEK
    kelimeler eklerse) payda büyüyor ve skor SERTÇE düşüyor -- konuya alakalı hiçbir kelime
    kaybetmeden bile eşiğin (0.6) altına inebiliyor."""
    text = "Amortisman, duran varlıkların kullanım süresince değer kaybının muhasebeleştirilmesidir."
    short_question = "amortisman nedir"
    long_question = (
        "acaba bu konuda bilgi almak istiyorum, muhasebe defterlerimi tutarken karşıma çıkan "
        "bir kavram var, amortisman nedir merak ediyorum"
    )
    short_coverage = Retriever.coverage(short_question, text)
    long_coverage = Retriever.coverage(long_question, text)
    assert short_coverage == 1.0
    assert long_coverage < 0.2, f"beklenen: ciddi düşüş, gelen: {long_coverage}"
    assert long_coverage < 0.6  # extractive_answer eşiğinin altına düşüyor
    print(f"KAIZEN RETRIEVAL UZUN SORU SEYRELMESI TESTI: BASARILI (kisa={short_coverage:.3f} uzun={long_coverage:.3f})")


# --- 6-7) "Türkçe ek kırpıcı hangi örneklerde başarısız?" --------------------------------------

def test_retrieval_stemmer_fails_on_accusative_yi_yı_yu_yu_suffix():
    """BULGU: `core.text_tr._STEM_SUFFIXES` listesinde -i/-ı/-u/-ü TÜREVİ (araya 'y' tampon
    ünsüzü giren) belirtme durumu ekleri ('işçiYİ', 'vergiYİ') YOK -- yalnız yalın çekim ekleri
    (-den/-de/-nin/-ler vb.) var. Sonuç: 'işçiyi' hiç kırpılmadan kalıyor, 'işçi' ile eşleşmiyor."""
    assert stem_tr(fold_tr("işçiyi")) != stem_tr(fold_tr("işçi"))
    assert stem_tr(fold_tr("vergiyi")) != stem_tr(fold_tr("vergi"))
    print("KAIZEN TURKCE EK KIRPICI BASARISIZLIGI (BELIRTME -YI) TESTI: BASARILI")


def test_retrieval_stemmer_fails_on_dative_ye_ya_suffix():
    """Aynı kök neden: yönelme durumu eki ('işçiYE', 'vergiYE') de -- araya 'y' giren tüm
    ekler -- listede yok (yalnız çıplak -e/-a bilinçli olarak dışlanmış, ama -ye/-ya'nın da
    dışarıda kaldığı ayrı, dokümante edilmemiş bir yan etki)."""
    assert stem_tr(fold_tr("işçiye")) != stem_tr(fold_tr("işçi"))
    assert stem_tr(fold_tr("vergiye")) != stem_tr(fold_tr("vergi"))
    print("KAIZEN TURKCE EK KIRPICI BASARISIZLIGI (YONELME -YE) TESTI: BASARILI")


# --- en somut bulgu (DÜZELTİLDİ -- bkz. iş emri "KAIZEN — FAZ 1.1" madde 1, 2026-09-23):
# eğik çizgili kodlar (4/a, 7/A) artık KAYBOLMUYOR ------------------------------------------
#
# Bu üç test eskiden (bu iş emrinden önce) '4/a' gibi kodların tamamen kaybolduğu BUG'ı
# belgeliyordu. `core/text_tr.py::tokens_tr()`'ye eklenen genel (SGK'ya özel değil) SAYI/HARF
# ve HARF/SAYI kodu tanıma kuralından sonra davranış değişti; testler DÜZELTİLMİŞ davranışı
# doğrulayacak şekilde güncellendi (ayrıntılı, adım adım kanıt: yeni
# tests/test_tokenizer_slash_code_fix.py).

def test_retrieval_tokenizer_no_longer_shreds_slash_codes_after_fix():
    """DÜZELTİLDİ: eskiden `core.text_tr.tokens_tr()` `[a-z0-9]+` regex'i yüzünden '/' bir
    kelime sınırı sayılıyordu -- '4/a' -> ['4', 'a'] (İKİ ayrı, anlamsız tek karakterli parça).
    Artık '4/a' TEK bir token (bkz. tests/test_tokenizer_slash_code_fix.py, ana kanıt)."""
    assert tokens_tr("4/a 4/b 4/c nedir") == ["4/a", "4/b", "4/c", "nedir"]
    print("KAIZEN TOKENIZER EGIK CIZGI ARTIK PARCALAMIYOR (DUZELTME) TESTI: BASARILI")


def test_retrieval_significance_filter_no_longer_drops_slash_code_fragments_after_fix():
    """DÜZELTİLDİ: eskiden `Retriever._terms()`'teki `len(t) > 2` anlamlılık filtresi,
    tokenizer'ın ürettiği TEK KARAKTERLİ parçaları ('4','a','b','c') tamamen atıyordu. Artık
    '4/a' gibi kodlar (uzunluk 3) tek token olduğu için filtreyi geçip terimler arasında
    KALIYOR."""
    terms = Retriever._terms("4/a 4/b 4/c nedir, aralarındaki fark ne?")
    assert "4/a" in terms and "4/b" in terms and "4/c" in terms
    assert "aralarindaki" in terms and "fark" in terms
    print("KAIZEN ANLAMLILIK FILTRESI ARTIK EGIK CIZGIYI KAYBETMIYOR (DUZELTME) TESTI: BASARILI")


def test_retrieval_information_exists_locally_and_extractive_answer_now_returns_it_after_fix():
    """DÜZELTİLDİ (gerçek hayat sınavı kanıtı: tests/test_real_world_exam.py'deki '4/a 4/b 4/c'
    sorusu artık route='memory_extractive'/confidence='SUPPORTED'): gerçek Kaizen
    curriculum'unda (knowledge/sgk_temel_yapi.json) '4/a, 4/b, 4/c' konusunu BİREBİR anlatan bir
    kayıt var VE bu kayıt LearningStore.search()'ün candidate seçiminde İLK sırada doğru
    bulunuyordu -- eskiden tokenizer/filtre zincirinden dolayı extractive_answer() yine de None
    dönüyordu; artık DOLU bir cevap dönüyor. Üretim API'sinin TAM KENDİSİYLE (sentetik değil,
    gerçek curriculum metniyle) kanıtlanıyor."""
    question = "4/a 4/b 4/c nedir, aralarındaki fark ne?"
    accounting_brain = _seeded_accounting_brain()
    _, rows = accounting_brain.retrieve(question, limit=1)
    assert rows and "4/a" in rows[0]["text"]  # bilgi GERÇEKTEN mevcut ve İLK sırada bulundu
    evidence = _evidence_from_rows(rows)
    answer = Retriever.extractive_answer(question, evidence, strict=False)
    assert answer is not None and "4/a" in answer
    print("KAIZEN BILGI MEVCUTKEN RETRIEVAL ARTIK BULUYOR (4/A DUZELTME) TESTI: BASARILI")


def test_retrieval_multi_topic_comparison_question_now_returns_both_topics_after_frame_fix():
    """DÜZELTİLDİ (Learning Loop fazı, kök neden #2). Eski BULGU: '7/A seçeneği' ve '7/B seçeneği' AYRI
    AYRI var ama karşılaştıran doğal soru ('... ne fark eder?') hiçbir kayıtla 0.6 eşiğini geçemiyordu.
    Neden: 'ne fark eder' SORU İSKELETİ sözcükleri ve 'seçenekleri'~'seçeneği' ünsüz yumuşaması
    (k/ğ) kanıtla eşleşmiyordu. Eşik 0.6'da KALDI (düşürülmedi); yalnız iskelet sözcükleri artık
    'gerekli terim' sayılmıyor ve yumuşama eşleşiyor. Artık iki kayıt da gösteriliyor."""
    question = "Maliyet muhasebesinde 7/A ve 7/B seçenekleri ne fark eder?"
    accounting_brain = _seeded_accounting_brain()
    _, rows = accounting_brain.retrieve(question, limit=3)
    subjects = {row.get("section") for row in rows}
    assert any("7/A" in s for s in subjects) and any("7/B" in s for s in subjects)  # ikisi de bulundu
    evidence = _evidence_from_rows(rows)
    answer = Retriever.extractive_answer(question, evidence, strict=False)
    assert answer is not None and "7/A seçeneği" in answer and "7/B seçeneği" in answer
    # Eşik hâlâ 0.6: soruyla ilgisiz bir kayıt yine geçemez
    assert Retriever.coverage(question, "Kasa hesabı nakit girişlerini izler.") < 0.6
    print("KAIZEN COKLU-KONU KARSILASTIRMA SORUSU ARTIK IKI KONUYU DA GETIRIYOR (DUZELTME) TESTI: BASARILI")


def test_retrieval_needs_current_research_false_positive_no_longer_hides_stable_knowledge_after_frame_fix():
    """BULGU (kök neden analizi -- gerçek hayat sınavındaki 'İşveren ve işçi prim oranları nasıl
    paylaşılıyor?' başarısızlığının TAM açıklaması): `needs_current_research()` yalnız 'oran'
    kelimesi geçtiği için bu soruyu 'güncel/mevzuat' sayıyor (CURRENT_TERMS'te çıplak 'oran'
    var) VE bu, `_from_memory`'de `extractive_answer(..., strict=current)` çağrısını
    strict=True yapıyor (min_coverage 1.0'a çıkıyor). Oysa bu sorunun cevabı (işveren/işçi PAY
    MANTIĞI) kalıcı bir kural -- yalnız ORANLARIN SAYISAL DEĞERİ güncelliğe tabi, mantığın
    kendisi değil. Sonuç: aynı içerik strict=False'ta BAŞARIYLA çıkarılabilirken, strict=True'da
    (needs_current_research'ün yanlış pozitifi yüzünden) reddediliyor."""
    question = "İşveren ve işçi prim oranları nasıl paylaşılıyor?"
    assert KaizenBrain.needs_current_research(question) is True  # yanlış pozitif: bu kavramsal bir soru
    accounting_brain = _seeded_accounting_brain()
    _, rows = accounting_brain.retrieve(question, limit=3)
    evidence = _evidence_from_rows(rows)
    assert Retriever.extractive_answer(question, evidence, strict=False) is not None  # içerik aslında YETERLİ
    # DÜZELTİLDİ (Learning Loop fazı, kök neden #2): 'nasıl paylaşılıyor' edilgen SORU İSKELETİ artık
    # kanıt terimi sayılmadığı için strict modda da (eşik 1.0 DEĞİŞMEDEN) içerik bulunuyor.
    assert Retriever.extractive_answer(question, evidence, strict=True) is not None
    print("KAIZEN NEEDS_CURRENT_RESEARCH YANLIS POZITIFI -> STRICT ESIK TESTI: BASARILI")


if __name__ == "__main__":
    test_retrieval_min_coverage_threshold_is_060_non_strict_and_exact_boundary_passes()
    test_retrieval_strict_mode_requires_full_100_percent_coverage()
    test_retrieval_short_single_term_question_over_trusts_a_coincidental_match()
    test_retrieval_synonyms_are_not_recognized_no_thesaurus()
    test_retrieval_word_order_does_not_affect_coverage_or_phrase_ok()
    test_retrieval_long_natural_question_dilutes_coverage_with_extra_real_words()
    test_retrieval_stemmer_fails_on_accusative_yi_yı_yu_yu_suffix()
    test_retrieval_stemmer_fails_on_dative_ye_ya_suffix()
    test_retrieval_tokenizer_no_longer_shreds_slash_codes_after_fix()
    test_retrieval_significance_filter_no_longer_drops_slash_code_fragments_after_fix()
    test_retrieval_information_exists_locally_and_extractive_answer_now_returns_it_after_fix()
    test_retrieval_multi_topic_comparison_question_now_returns_both_topics_after_frame_fix()
    test_retrieval_needs_current_research_false_positive_no_longer_hides_stable_knowledge_after_frame_fix()
    print("KAIZEN RETRIEVAL OLCUM TESTLERI: BASARILI")
