"""KAIZEN — Learning Brain v1: Principle Layer transfer test seti.

İş emri (Learning Brain v1, iş emri madde 3 ve madde 25/adım 4): bu dosya, Principle
Layer'dan (memory/principle_registry.py, learning/principle_retriever.py — henüz
YAZILMADI) HİÇBİR SATIR KOD YAZILMADAN ÖNCE oluşturuldu. Amaç: Kaizen'in "A örneğinden
öğrendiği bir ilkeyi, kelimeleri farklı B probleminde" kullanabilip kullanamadığını
(TRANSFER SCORE, madde 17) hem ŞİMDİ (Principle Layer'sız baseline) hem de SONRA
(Principle Layer'lı final) AYNI veri seti ve AYNI ölçüm fonksiyonuyla ölçmek.

Yapı (madde 3, birebir):
    A — Öğrenilen/verilen ilke (principle_statement)
    B — Yüzeysel olarak farklı yeni problem (transfer_question) — aynı kelimeleri
        KOPYALAMAZ, aynı muhasebe mantığını gerektirir.
    C — Beklenen ilke (principle_id)
    D — Yanlış transfer riski: benzer kelimeler taşıyan ama AYNI ilkenin
        UYGULANMAMASI gereken karşı örnek (counter_question).

7 zorunlu ilke ailesi (madde 3, birebir sırayla): dönemsellik, borç/alacak mantığı,
hesap sınıflandırması, özün önceliği/işlemin ekonomik niteliği, maliyet mantığı,
amortisman, SGK statü mantığı.

BASELINE ÖLÇÜMÜ (bu dosyanın ilk hâli, Principle Layer'dan ÖNCE çalıştırıldı):
`_baseline_classify()`, KaizenBrain'in GERÇEKTEN kullandığı geri getirme yolunun AYNISINI
(accounting.retriever.Retriever + memory.learning_store.LearningStore — bkz.
memory/brain_manager.py::BrainManager.gather_evidence) izole bir kopyada (knowledge/*.json'dan
tohumlanmış geçici sqlite; GERÇEK data/kaizen_learning.sqlite3'e ASLA dokunulmaz) çalıştırıp,
en iyi eşleşen kanıt parçasının hangi ilkenin bölüm başlığına ait olduğunu KABA bir alt-metin
eşleşmesiyle tahmin eder. Bu, "mevcut sistem prensip seçseydi ne seçerdi" sorusunun en dürüst
yaklaşık cevabıdır — kelime eşleşmesinin (madde 9) TEK BAŞINA transferi ne kadar (yanlışlıkla)
başardığını gösterir. `_baseline_classify` bir PrincipleRetriever DEĞİLDİR ve asla biri gibi
sunulmaz; yalnız ölçüm için var.

Ölçülen ham baseline (2026-09-23, ilk çalıştırma, bu dosyanın oluşturulduğu commit):
    Positive Transfer Accuracy : 2/7  (%28.6)
    Negative Transfer Rejection: 6/7  (%85.7)
    Overall Transfer Score     : 8/14 (%57.1)
Ayrıntı: KAIZEN_HEDEF_VE_YOL_HARITASI.md bölüm 4z, "B — Transfer Baseline".

KURAL (madde 3, birebir): "Testleri sonradan sistemi başarılı gösterecek şekilde
değiştirme." — TRANSFER_SCENARIOS ve measure_transfer_score() Principle Layer
yazıldıktan SONRA da DEĞİŞTİRİLMEDİ; yalnız madde 25/adım 14'te PrincipleRetriever'a
karşı çalışan test_principle_* fonksiyonları bu dosyaya EKLENDİ.
"""
import tempfile
from dataclasses import dataclass
from pathlib import Path

from accounting.retriever import Retriever
from core.text_tr import fold_tr
from memory.learning_store import LearningStore
from memory.seed_loader import load_seeds


@dataclass(frozen=True)
class TransferScenario:
    principle_id: str          # C — beklenen ilke (kısa kod)
    family: str                # iş emri madde 3'teki 7 ailesinden biri (Türkçe adı)
    principle_statement: str   # A — öğrenilen/verilen ilke
    transfer_question: str     # B — yüzeysel olarak farklı yeni problem
    counter_question: str      # D — yanlış transfer riski (karşı örnek)
    counter_note: str          # D'de bu ilkenin NEDEN uygulanmaması gerektiği


TRANSFER_SCENARIOS = [
    TransferScenario(
        principle_id="donemsellik",
        family="dönemsellik",
        principle_statement=(
            "Dönemsellik ilkesi: gelir ve gider, tahsil/ödeme tarihine değil, ait olduğu "
            "faaliyet dönemine göre kayda alınır (tahakkuk esası)."
        ),
        transfer_question=(
            "Aralık ayında kullanılan elektrik faturası ocak ayında geldi ve ocakta ödendi, "
            "bu gideri hangi ayın defterine yazmalıyım?"
        ),
        counter_question=(
            "Aralık ayında alınan bir taşıt için ocak ayında ödenen KDV'yi hangi hesaba "
            "kaydederim, 191 mi 150 mi?"
        ),
        counter_note=(
            "'Aralık'/'ocak' kelimeleri dönemsellikle aynı ama soru aslında HANGİ HESABA "
            "kaydedileceği (hesap sınıflandırması) — dönemsellik ilkesi buraya uygulanmamalı."
        ),
    ),
    TransferScenario(
        principle_id="borc_alacak",
        family="borç/alacak mantığı",
        principle_statement=(
            "Borç/alacak yönü hesabın niteliğine göre belirlenir: aktif hesaplarda artış "
            "borca, pasif hesaplarda artış alacağa yazılır."
        ),
        transfer_question=(
            "İşletme bankadan kısa vadeli kredi kullandığında bu tutarı deftere nasıl "
            "işlerim, hangi tarafa yazarım?"
        ),
        counter_question=(
            "Banka kredisinin faiz giderini hangi hesap sınıfına kaydetmeliyim?"
        ),
        counter_note=(
            "'Banka kredisi' kelimeleri aynı ama soru borç/alacak YÖNÜ değil, hangi HESAP "
            "SINIFI (gider mi finansman mı) sorusu — borç/alacak mantığı uygulanmamalı."
        ),
    ),
    TransferScenario(
        principle_id="hesap_siniflandirma",
        family="hesap sınıflandırması",
        principle_statement=(
            "Tek Düzen Hesap Planı'nda hesaplar 1'den 9'a kadar ana sınıflara ayrılır: "
            "dönen varlıklar, duran varlıklar, kısa/uzun vadeli yabancı kaynaklar, "
            "özkaynaklar, gelir tablosu, maliyet, nazım hesaplar."
        ),
        transfer_question=(
            "Şirketin bir yıldan uzun sürede tahsil edeceği bir alacağı bilançoda hangi "
            "ana grupta göstermeliyim?"
        ),
        counter_question=(
            "Alacak hesabına ait açılan bir davanın şüpheli hale gelmesi durumunda ne "
            "yapmalıyım?"
        ),
        counter_note=(
            "'Alacak hesabı' kelimeleri aynı ama soru hangi SINIFA ait olduğu değil, "
            "şüpheli alacak KARŞILIĞI (ihtiyatlılık) — hesap sınıflandırması uygulanmamalı."
        ),
    ),
    TransferScenario(
        principle_id="ozun_onceligi",
        family="özün önceliği / işlemin ekonomik niteliği",
        principle_statement=(
            "Özün önceliği (ekonomik öz) ilkesi: işlemler hukuki biçiminden çok ekonomik "
            "özüne göre muhasebeleştirilir."
        ),
        transfer_question=(
            "Finansal kiralama yoluyla kullanılan ve sözleşme sonunda mülkiyeti işletmeye "
            "geçecek bir makineyi, kirası ödendiği sürece kimin varlığı olarak "
            "göstermeliyim?"
        ),
        counter_question=(
            "Finansal kiralama sözleşmesinin KDV'sini hangi ayda indirim konusu "
            "yapabilirim?"
        ),
        counter_note=(
            "'Finansal kiralama' kelimeleri aynı ama soru mülkiyetin/varlığın kimin "
            "üzerinde gösterileceği değil, KDV indirim ZAMANI (dönemsellik) — özün "
            "önceliği ilkesi uygulanmamalı."
        ),
    ),
    TransferScenario(
        principle_id="maliyet_ilkesi",
        family="maliyet mantığı",
        principle_statement=(
            "Maliyet esası ilkesi: iktisadi kıymetler elde etme maliyeti (satın "
            "alma/üretim maliyeti) üzerinden kayda alınır, sonraki piyasa değeri "
            "değişimiyle güncellenmez."
        ),
        transfer_question=(
            "3 yıl önce 200.000 TL'ye alınan bir arsanın bugünkü piyasa değeri 800.000 TL "
            "oldu, bilançoda hangi tutarla göstermeliyim?"
        ),
        counter_question=(
            "Bu arsa üzerine inşa edilen bina tamamlandığında hangi hesaba aktarılır, "
            "258 mi 252 mi?"
        ),
        counter_note=(
            "'Arsa' kelimesi aynı ama soru HANGİ TUTARLA değil hangi HESABA aktarılacağı "
            "— maliyet ilkesi değil hesap sınıflandırması sorusu."
        ),
    ),
    TransferScenario(
        principle_id="amortisman",
        family="amortisman",
        principle_statement=(
            "Amortisman ilkesi: duran varlığın faydalı ömrü boyunca aşınma payının "
            "dönemlere yayılarak gider yazılmasıdır (faydanın dönemlere dağıtılması)."
        ),
        transfer_question=(
            "5 yıl kullanacağımız bir üretim makinesinin maliyetini tek seferde mi "
            "yoksa yıllara yayarak mı gider yazmalıyım?"
        ),
        counter_question=(
            "Üretim makinesi için ödediğimiz KDV'yi hangi ayda indirim konusu "
            "yapabiliriz?"
        ),
        counter_note=(
            "'Üretim makinesi' kelimeleri aynı ama soru giderin dönemlere yayılması "
            "değil, KDV indirim ZAMANI (dönemsellik) — amortisman ilkesi uygulanmamalı."
        ),
    ),
    TransferScenario(
        principle_id="sgk_statu",
        family="SGK statü mantığı",
        principle_statement=(
            "SGK sigortalılık statüsü çalışma biçimine göre yapısal olarak "
            "sınıflandırılır: hizmet akdiyle bağımlı çalışan 4/a, kendi nam ve "
            "hesabına bağımsız çalışan 4/b, memur 4/c."
        ),
        transfer_question=(
            "Kendi muayenehanesini açan bir doktor SGK'ya hangi statüde bildirilir?"
        ),
        counter_question=(
            "Bir doktorun hastanede aldığı aylık ücretten kesilecek gelir vergisi "
            "stopaj oranı nedir?"
        ),
        counter_note=(
            "'Doktor' kelimesi aynı ama soru statü sınıflandırması değil, GÜNCEL bir "
            "vergi ORANI (bu bir FACT'tir, bkz. madde 4/16 — principle ile "
            "'VERIFIED' yapılamaz) — sgk_statu ilkesi uygulanmamalı."
        ),
    ),
]

assert len(TRANSFER_SCENARIOS) == 7, "iş emri madde 3: en az 7 transfer senaryosu"
assert len({s.principle_id for s in TRANSFER_SCENARIOS}) == 7, "her aile benzersiz olmalı"


# --- BASELINE (Principle Layer'sız) ölçüm yardımcıları --------------------------------
# Yalnızca ÖLÇÜM içindir; PrincipleRetriever'ın YERİNE geçmez, madde 9'un ("kelime
# eşleşmesine düşme") tam karşıtı bir davranışı KASITLI olarak sergiler ki fark ölçülebilsin.
_BASELINE_MARKERS = {
    "donemsellik": "donemsellik",
    "borc_alacak": "cift tarafli kayit",
    "hesap_siniflandirma": "tek duzen hesap plani",
    "ozun_onceligi": "ozun onceligi",
    "maliyet_ilkesi": "maliyet esasi",
    "amortisman": "faydali omru",
    "sgk_statu": "sigortalilik halleri",
}

_cached_retriever = None
_cached_tmpdir = None


def _current_system_retriever():
    """KaizenBrain'in GERÇEKTEN kullandığı geri getirme bileşeni (bkz.
    memory/brain_manager.py::BrainManager.gather_evidence -> Retriever.gather), izole
    bir geçici sqlite'a knowledge/*.json'dan tohumlanmış — gerçek data/kaizen_learning.sqlite3
    veya kullanıcının gerçek hafızası ASLA açılmaz/değiştirilmez (madde 23)."""
    global _cached_retriever, _cached_tmpdir
    if _cached_retriever is None:
        _cached_tmpdir = tempfile.TemporaryDirectory()
        store = LearningStore(Path(_cached_tmpdir.name) / "learning.sqlite3")
        load_seeds(store)
        _cached_retriever = Retriever(store)
    return _cached_retriever


def _baseline_classify(question):
    """Mevcut (Principle Layer'sız) sistem bir "ilke" seçmek ZORUNDA bırakılsaydı ne
    seçerdi: en iyi eşleşen kanıtın etiket+metninde 7 ilkeden hangisinin bölüm başlığı
    geçiyorsa onu döner; hiçbiri geçmiyorsa None (madde 11'in ruhuyla: zorla seçim yok)."""
    retriever = _current_system_retriever()
    evidence = retriever.gather(question, "accounting", current=False)
    if not evidence:
        return None
    haystack = fold_tr(f"{evidence[0].label} {evidence[0].text}")
    for principle_id, marker in _BASELINE_MARKERS.items():
        if marker in haystack:
            return principle_id
    return None


def measure_transfer_score(select_principle):
    """Genel ölçüm fonksiyonu (madde 17): select_principle(question) -> principle_id|None.

    BASELINE (bu commit'te _baseline_classify ile) VE FINAL (madde 25/adım 15'te gerçek
    PrincipleRetriever ile) AYNI fonksiyonu kullanır — karşılaştırma adil olsun diye.
    Pozitif: B sorusunda doğru ilke seçildi mi? Negatif: D sorusunda YANLIŞ ilke
    (B'nin ilkesi) REDDEDİLDİ mi (başka bir şey ya da None seçildi mi)?
    """
    detail = []
    positive_hits = 0
    negative_hits = 0
    for scenario in TRANSFER_SCENARIOS:
        got_b = select_principle(scenario.transfer_question)
        positive_ok = got_b == scenario.principle_id
        got_d = select_principle(scenario.counter_question)
        negative_ok = got_d != scenario.principle_id
        positive_hits += positive_ok
        negative_hits += negative_ok
        detail.append({
            "principle_id": scenario.principle_id, "family": scenario.family,
            "got_b": got_b, "positive_ok": positive_ok,
            "got_d": got_d, "negative_ok": negative_ok,
        })
    n = len(TRANSFER_SCENARIOS)
    overall_correct = positive_hits + negative_hits
    overall_total = 2 * n

    def _fmt(hit, total):
        return f"{hit}/{total} = %{round(100 * hit / total, 1)}"

    return {
        "n": n,
        "positive_hits": positive_hits, "positive_total": n,
        "negative_hits": negative_hits, "negative_total": n,
        "overall_correct": overall_correct, "overall_total": overall_total,
        "positive_label": _fmt(positive_hits, n),
        "negative_label": _fmt(negative_hits, n),
        "overall_label": _fmt(overall_correct, overall_total),
        "detail": detail,
    }


def run_baseline():
    """Şu an (Principle Layer YOK) mevcut sistemin transfer skorunu ölçer ve basar.

    Bu fonksiyon `python -m tests.test_learning_transfer` ile elle çalıştırılır;
    run_all.py'ye BİLEREK bağlanmadı (madde 3: Principle Layer'dan önceki tek seferlik
    baseline ölçümüdür, düzenli regresyonun bir parçası değildir)."""
    result = measure_transfer_score(_baseline_classify)
    print("=== KAIZEN LEARNING BRAIN v1 — TRANSFER BASELINE (Principle Layer ÖNCESİ) ===")
    for row in result["detail"]:
        pos = "OK" if row["positive_ok"] else "FAIL"
        neg = "OK" if row["negative_ok"] else "FAIL"
        print(f"  [{row['family']}] B->{row['got_b']!r} pos={pos}   D->{row['got_d']!r} neg={neg}")
    print(f"Positive Transfer Accuracy : {result['positive_label']}")
    print(f"Negative Transfer Rejection: {result['negative_label']}")
    print(f"Overall Transfer Score     : {result['overall_label']}")
    return result


# --- yapısal doğrulama testleri (regresyon-güvenli; run_all.py'ye HENÜZ bağlanmadı,
#     PrincipleRetriever testleriyle BİRLİKTE madde 25/adım 16'da tek seferde bağlanacak) ---
def test_transfer_dataset_has_all_seven_mandated_families():
    families = {s.family for s in TRANSFER_SCENARIOS}
    expected = {
        "dönemsellik", "borç/alacak mantığı", "hesap sınıflandırması",
        "özün önceliği / işlemin ekonomik niteliği", "maliyet mantığı",
        "amortisman", "SGK statü mantığı",
    }
    assert families == expected
    print("KAIZEN TRANSFER VERI SETI 7 ILKE AILESI TESTI: BASARILI")


def test_transfer_dataset_each_scenario_has_distinct_b_and_d_questions():
    for s in TRANSFER_SCENARIOS:
        assert s.transfer_question.strip() and s.counter_question.strip()
        assert fold_tr(s.transfer_question) != fold_tr(s.counter_question)
    print("KAIZEN TRANSFER VERI SETI B/D FARKLILIK TESTI: BASARILI")


def test_transfer_dataset_no_annual_figures_leak_into_principle_statements():
    """madde 4/16: principle_statement'lar (A) hiçbir yıl/oran/tutar İÇERMEMELİ — bunlar
    FACT'tir, Principle Registry'nin konusu değildir."""
    import re
    year_pattern = re.compile(r"\b20\d{2}\b")
    for s in TRANSFER_SCENARIOS:
        assert not year_pattern.search(s.principle_statement), (
            f"{s.principle_id}: principle_statement bir YIL içeriyor (FACT sızması): "
            f"{s.principle_statement!r}"
        )
    print("KAIZEN PRINCIPLE STATEMENT FACT SIZINTISI YOK TESTI: BASARILI")


# --- FINAL testler (madde 25/adım 14: Principle Layer YAZILDIKTAN SONRA eklendi) -----
# KURAL (madde 3): yukarıdaki TRANSFER_SCENARIOS/measure_transfer_score DEĞİŞTİRİLMEDİ;
# yalnız burada gerçek PrincipleRetriever'a karşı çalışan yeni testler EKLENDİ.
import re as _re  # sadece bu bölümdeki testler için

from learning.decision_bridge import PRINCIPLE_SHADOW_ROUTE, to_decision
from learning.principle_retriever import HIGH, LOW, MEDIUM
from learning.principle_retriever import NONE as PRINCIPLE_NONE
from learning.principle_retriever import PrincipleRetriever
from learning.principle_seed import load_principle_seeds
from learning.trace_bridge import fill_principle_trace
from memory.principle_registry import PrincipleRegistry
from core.trace import KaizenTrace, ROUTE_CONFIDENCE

_cached_seeded_registry = None
_cached_registry_tmpdir = None


def _seeded_registry():
    """Gerçek data/kaizen_principles.sqlite3 DEĞİL -- izole bir geçici sqlite'a
    knowledge/principles/principles_seed.json'dan tohumlanmış 7 ilke (madde 23:
    test fixture'ları gerçek memory ile karıştırılmaz)."""
    global _cached_seeded_registry, _cached_registry_tmpdir
    if _cached_seeded_registry is None:
        _cached_registry_tmpdir = tempfile.TemporaryDirectory()
        registry = PrincipleRegistry(Path(_cached_registry_tmpdir.name) / "principles.sqlite3")
        load_principle_seeds(registry)
        _cached_seeded_registry = registry
    return _cached_seeded_registry


def _principle_retriever():
    return PrincipleRetriever(_seeded_registry())


def _select(question):
    return _principle_retriever().retrieve(question).selected


# --- 1) pozitif transfer: 7 aile, yüzeysel olarak farklı B sorusu, doğru ilke -----------
def test_principle_positive_transfer_donemsellik():
    s = next(x for x in TRANSFER_SCENARIOS if x.principle_id == "donemsellik")
    result = _principle_retriever().retrieve(s.transfer_question)
    assert result.selected == "donemsellik"
    assert result.confidence in (HIGH, MEDIUM)
    print("KAIZEN PRINCIPLE POZITIF TRANSFER (DONEMSELLIK) TESTI: BASARILI")


def test_principle_positive_transfer_borc_alacak():
    s = next(x for x in TRANSFER_SCENARIOS if x.principle_id == "borc_alacak")
    result = _principle_retriever().retrieve(s.transfer_question)
    assert result.selected == "borc_alacak"
    assert result.confidence in (HIGH, MEDIUM)
    print("KAIZEN PRINCIPLE POZITIF TRANSFER (BORC/ALACAK) TESTI: BASARILI")


def test_principle_positive_transfer_hesap_siniflandirma():
    s = next(x for x in TRANSFER_SCENARIOS if x.principle_id == "hesap_siniflandirma")
    result = _principle_retriever().retrieve(s.transfer_question)
    assert result.selected == "hesap_siniflandirma"
    assert result.confidence in (HIGH, MEDIUM)
    print("KAIZEN PRINCIPLE POZITIF TRANSFER (HESAP SINIFLANDIRMA) TESTI: BASARILI")


def test_principle_positive_transfer_ozun_onceligi():
    s = next(x for x in TRANSFER_SCENARIOS if x.principle_id == "ozun_onceligi")
    result = _principle_retriever().retrieve(s.transfer_question)
    assert result.selected == "ozun_onceligi"
    assert result.confidence in (HIGH, MEDIUM)
    print("KAIZEN PRINCIPLE POZITIF TRANSFER (OZUN ONCELIGI) TESTI: BASARILI")


def test_principle_positive_transfer_maliyet_ilkesi():
    s = next(x for x in TRANSFER_SCENARIOS if x.principle_id == "maliyet_ilkesi")
    result = _principle_retriever().retrieve(s.transfer_question)
    assert result.selected == "maliyet_ilkesi"
    assert result.confidence in (HIGH, MEDIUM)
    print("KAIZEN PRINCIPLE POZITIF TRANSFER (MALIYET ILKESI) TESTI: BASARILI")


def test_principle_positive_transfer_amortisman():
    s = next(x for x in TRANSFER_SCENARIOS if x.principle_id == "amortisman")
    result = _principle_retriever().retrieve(s.transfer_question)
    assert result.selected == "amortisman"
    assert result.confidence in (HIGH, MEDIUM)
    print("KAIZEN PRINCIPLE POZITIF TRANSFER (AMORTISMAN) TESTI: BASARILI")


def test_principle_positive_transfer_sgk_statu():
    s = next(x for x in TRANSFER_SCENARIOS if x.principle_id == "sgk_statu")
    result = _principle_retriever().retrieve(s.transfer_question)
    assert result.selected == "sgk_statu"
    assert result.confidence in (HIGH, MEDIUM)
    print("KAIZEN PRINCIPLE POZITIF TRANSFER (SGK STATU) TESTI: BASARILI")


# --- 2) negatif transfer: D sorusunda B'nin ilkesi YANLIŞLIKLA seçilmemeli -------------
def test_principle_negative_transfer_rejects_all_seven_counter_examples():
    """madde 10: en kritik güvenlik testi. Her aile için D (benzer kelimeli karşı
    örnek) B'nin ilkesini YANLIŞ TRANSFER etmemeli. Yanlış transfer BAŞARI SAYILMAZ."""
    for s in TRANSFER_SCENARIOS:
        result = _principle_retriever().retrieve(s.counter_question)
        assert result.selected != s.principle_id, (
            f"{s.principle_id}: NEGATIVE TRANSFER HATASI — D sorusunda yine "
            f"{s.principle_id!r} seçildi. {s.counter_note}"
        )
    print("KAIZEN PRINCIPLE NEGATIF TRANSFER (7 KARSI ORNEK) TESTI: BASARILI")


def test_principle_negative_transfer_sgk_counter_example_is_a_fact_not_a_principle():
    """sgk_statu'nun D'si bir güncel ORAN (FACT) sorusudur — madde 16 gereği hiçbir
    ilke VERIFIED gibi sunulmamalı; retriever bunu fact_safety_triggered ile açıkça
    işaretlemeli, sessizce yanlış bir ilke DÖNDÜRMEMELİ."""
    s = next(x for x in TRANSFER_SCENARIOS if x.principle_id == "sgk_statu")
    result = _principle_retriever().retrieve(s.counter_question)
    assert result.selected is None
    assert result.confidence == PRINCIPLE_NONE
    assert result.fact_safety_triggered is True
    print("KAIZEN PRINCIPLE FACT GUVENLIGI (SGK ORAN SORUSU) TESTI: BASARILI")


# --- 3) ilke bulunamaması: konuyla hiç ilgisi olmayan soru --------------------------
def test_principle_not_found_for_unrelated_question():
    result = _principle_retriever().retrieve("Excel'de pivot tablo nasıl oluşturulur?")
    assert result.selected is None
    assert result.confidence == PRINCIPLE_NONE
    assert result.candidates == ()
    print("KAIZEN PRINCIPLE BULUNAMADI (ALAKASIZ SORU) TESTI: BASARILI")


# --- 4) birden fazla aday: iki yapısal sinyal aynı anda ateşleyebilir ------------------
def test_principle_multiple_candidates_are_both_visible_when_scores_are_close():
    """Hem 'piyasa değeri' (maliyet_ilkesi) hem 'tek seferde mi yıllara yayarak mı'
    (amortisman) aynı soruda geçerse İKİ aday da candidates/rejected'te GÖRÜNMELİ
    (madde 18: 'birden fazla aday'); sistem en yüksek skorluyu seçer ama MEDIUM'a
    düşürerek belirsizliği trace'te açıkça işaretler (madde 11/12)."""
    question = (
        "3 yıl önce 200.000 TL'ye alınan makinenin bugünkü piyasa değeri 500.000 TL; "
        "bu makineyi tek seferde mi yoksa yıllara yayarak mı gider yazmalıyım?"
    )
    result = _principle_retriever().retrieve(question)
    candidate_ids = {c.principle_id for c in result.candidates}
    assert {"amortisman", "maliyet_ilkesi"} <= candidate_ids
    assert result.selected == "amortisman"  # daha yüksek net skor
    assert result.confidence == MEDIUM  # tek başına HIGH değil -- yakın rakip var
    rejected_ids = {pid for pid, _ in result.rejected}
    assert "maliyet_ilkesi" in rejected_ids
    print("KAIZEN PRINCIPLE BIRDEN FAZLA ADAY (MEDIUM CONFIDENCE) TESTI: BASARILI")


# --- 5) confidence: yalnız gözlemlenebilir sinyalden, LOW/NONE'da zorla seçim yok -----
def test_principle_confidence_levels_are_one_of_the_four_labels():
    for s in TRANSFER_SCENARIOS:
        for question in (s.transfer_question, s.counter_question):
            result = _principle_retriever().retrieve(question)
            assert result.confidence in (HIGH, MEDIUM, LOW, PRINCIPLE_NONE)
    print("KAIZEN PRINCIPLE CONFIDENCE 4 ETIKET TESTI: BASARILI")


def test_principle_low_or_none_confidence_never_forces_a_selection():
    """madde 11: 'LOW/NONE durumunda sistemi zorla principle seçmeye mecbur bırakma.'"""
    for s in TRANSFER_SCENARIOS:
        for question in (s.transfer_question, s.counter_question):
            result = _principle_retriever().retrieve(question)
            if result.confidence in (LOW, PRINCIPLE_NONE):
                assert result.selected is None, (
                    f"{question!r}: confidence={result.confidence} ama selected="
                    f"{result.selected!r} — LOW/NONE'da secim ZORLANMAMALI (madde 11)"
                )
    print("KAIZEN PRINCIPLE LOW/NONE ZORLA SECIM YOK TESTI: BASARILI")


def test_principle_confidence_never_reaches_verified_label():
    """madde 16: Principle Layer bir FACT'i asla 'VERIFIED' yapamaz. PrincipleRetriever
    HIGH/MEDIUM/LOW/NONE dışında core.trace.VERIFIED gibi bir güven etiketi üretmemeli
    (mimari olarak bu kelime dağarcığında hiç yok)."""
    from core.trace import VERIFIED
    for s in TRANSFER_SCENARIOS:
        result = _principle_retriever().retrieve(s.transfer_question)
        assert result.confidence != VERIFIED
        assert result.confidence in (HIGH, MEDIUM, LOW, PRINCIPLE_NONE)
    print("KAIZEN PRINCIPLE ASLA VERIFIED URETMEZ TESTI: BASARILI")


# --- 6) FACT/PRINCIPLE ayrımı ve yıllık figürlerin registry'ye sızmaması --------------
def test_principle_registry_rows_never_contain_annual_figures():
    """madde 4/16/23: registry'deki HİÇBİR satır (name/description/examples/
    counter_examples) bir yıl (2020-2099) İÇERMEMELİ — bu, principle_statement'ların
    (yukarıdaki dataset testi) ötesinde, GERÇEK seed edilmiş registry üzerinde
    çalışan bağımsız bir kontrol."""
    year_pattern = _re.compile(r"\b20[2-9]\d\b")
    for row in _seeded_registry().all():
        haystack = " ".join([
            row["name"], row["description"],
            " ".join(row["examples"]), " ".join(row["counter_examples"]),
        ])
        assert not year_pattern.search(haystack), (
            f"{row['principle_id']}: registry satırında YIL var (FACT sızıntısı): {haystack!r}"
        )
    print("KAIZEN PRINCIPLE REGISTRY FACT SIZINTISI YOK (GERCEK REGISTRY) TESTI: BASARILI")


def test_principle_registry_every_row_has_non_empty_provenance():
    """madde 15: her ilke küratörlü, açık kaynak/provenance sahibi olmalı."""
    for row in _seeded_registry().all():
        assert row["source"].strip()
        assert "knowledge/" in row["source"]  # gerçek bir dosyaya işaret etmeli
    print("KAIZEN PRINCIPLE REGISTRY PROVENANCE TESTI: BASARILI")


def test_principle_registry_has_exactly_the_seven_curated_principles():
    """madde 6: v1'de yalnızca 5-7 küratörlü ilke; sistem kendi kendine yüzlerce
    ilke üretmemeli."""
    ids = {row["principle_id"] for row in _seeded_registry().all()}
    assert ids == {
        "donemsellik", "borc_alacak", "hesap_siniflandirma", "ozun_onceligi",
        "maliyet_ilkesi", "amortisman", "sgk_statu",
    }
    assert 5 <= len(ids) <= 7
    print("KAIZEN PRINCIPLE REGISTRY 5-7 KURATORLU ILKE TESTI: BASARILI")


# --- 7) Türkçe Unicode sağlamlığı ----------------------------------------------------
def test_principle_retrieval_handles_turkish_unicode_case_variants():
    """Büyük/küçük harf ve Türkçe İ/I/ı farkı sonucu DEĞİŞTİRMEMELİ (core.text_tr.fold_tr
    ile aynı normalleştirme -- learning/problem_structure.py da bunu kullanıyor)."""
    lower = "kendi muayenehanesini açan bir doktor sgk'ya hangi statüde bildirilir?"
    upper = "KENDİ MUAYENEHANESİNİ AÇAN BİR DOKTOR SGK'YA HANGİ STATÜDE BİLDİRİLİR?"
    mixed = "Kendi Muayenehanesini Açan Bir Doktor SGK'ya Hangi Statüde Bildirilir?"
    results = [_select(q) for q in (lower, upper, mixed)]
    assert results == ["sgk_statu", "sgk_statu", "sgk_statu"]
    print("KAIZEN PRINCIPLE TURKCE UNICODE BUYUK/KUCUK HARF TESTI: BASARILI")


# --- 8) yapı vs kelime: aynı yapı farklı kelime / aynı kelime farklı yapı --------------
def test_principle_different_words_same_structure_still_transfers():
    """madde 9: kelimeler tamamen FARKLI olsa da (elektrik faturası -> sigorta primi,
    borç -> alacak yok bile) aynı YAPISAL rol (iki farklı ay + 'hangi ayın defterine')
    aynı ilkeye (dönemsellik) bağlanmalı."""
    original = "Aralık ayında kullanılan elektrik faturası ocak ayında geldi ve ocakta ödendi, bu gideri hangi ayın defterine yazmalıyım?"
    different_words = "Şubat ayına ait sigorta primi mart ayında bankadan ödendi, bu gideri hangi ayın defterine yazmalıyım?"
    assert fold_tr(original) != fold_tr(different_words)
    assert _select(original) == _select(different_words) == "donemsellik"
    print("KAIZEN PRINCIPLE FARKLI KELIME AYNI YAPI TESTI: BASARILI")


def test_principle_same_words_different_structure_does_not_transfer():
    """madde 9 (tersi): 'banka kredisi'/'faiz gideri' kelimeleri B (borç/alacak, yön
    sorusu) ile D (hesap sınıflandırması, sınıf sorusu) arasında ORTAK ama yapı
    (hangi TARAFA vs hangi SINIFA) farklı olduğu için FARKLI ilkeye gitmeli."""
    s = next(x for x in TRANSFER_SCENARIOS if x.principle_id == "borc_alacak")
    assert _select(s.transfer_question) == "borc_alacak"
    assert _select(s.counter_question) == "hesap_siniflandirma"
    assert _select(s.counter_question) != "borc_alacak"
    print("KAIZEN PRINCIPLE AYNI KELIME FARKLI YAPI TESTI: BASARILI")


# --- 9) trace çıktısı (madde 12) -----------------------------------------------------
def test_principle_trace_output_shows_candidates_selected_confidence_rejected_reason():
    s = next(x for x in TRANSFER_SCENARIOS if x.principle_id == "sgk_statu")
    result = _principle_retriever().retrieve(s.transfer_question)
    trace = fill_principle_trace(KaizenTrace(), result)
    assert trace.principle_selected == "sgk_statu"
    assert trace.principle_confidence in (HIGH, MEDIUM)
    assert trace.principle_candidates and trace.principle_candidates[0][0] == "sgk_statu"
    assert isinstance(trace.principle_rejected, tuple)
    assert trace.principle_reason
    # madde 12: cevap metnini DEĞİŞTİRMEK zorunda değilsin -- KaizenTrace'in geri kalanı
    # (route/intent/confidence gibi asıl cevap-zinciri alanları) bu doldurmadan ETKİLENMEMELİ.
    assert trace.route is None and trace.intent is None
    print("KAIZEN PRINCIPLE TRACE (CANDIDATES/SELECTED/CONFIDENCE/REJECTED/REASON) TESTI: BASARILI")


def test_principle_trace_fields_default_empty_when_principle_layer_not_used():
    """Principle Layer HİÇ çağrılmazsa (bugünkü KaizenBrain._answer_core davranışı --
    madde 14, henüz bağlı değil) yeni trace alanları hep boş/None kalmalı; mevcut
    KaizenTrace kullanıcıları hiç etkilenmemeli (additive alan garantisi)."""
    trace = KaizenTrace()
    assert trace.principle_candidates == ()
    assert trace.principle_selected is None
    assert trace.principle_confidence is None
    assert trace.principle_rejected == ()
    assert trace.principle_reason is None
    print("KAIZEN PRINCIPLE TRACE ALANLARI VARSAYILAN BOS (SHADOW MODE) TESTI: BASARILI")


# --- 10) Decision Engine kontratıyla gözlemsel uyumluluk (madde 13) -------------------
def test_principle_decision_bridge_never_claims_verified_and_uses_known_route():
    """madde 13 'gerekirse ... uyumlu hale getir', madde 16 (asla VERIFIED). Bu köprü
    core/decision.py::DecisionEngine'i HİÇ ÇAĞIRMAZ, KaizenBrain.last_route'u DA HİÇ
    ETKİLEMEZ -- yalnız aynı alan adlarını taşıyan bağımsız bir Decision üretir."""
    from core.trace import VERIFIED
    s = next(x for x in TRANSFER_SCENARIOS if x.principle_id == "donemsellik")
    result = _principle_retriever().retrieve(s.transfer_question)
    decision = to_decision(result)
    assert set(decision.__dataclass_fields__.keys()) == {
        "intent", "preferred_route", "needs_current_data", "required_confidence", "reason",
    }
    assert decision.required_confidence != VERIFIED
    assert decision.preferred_route == PRINCIPLE_SHADOW_ROUTE
    assert decision.preferred_route in ROUTE_CONFIDENCE
    print("KAIZEN PRINCIPLE DECISION KONTRATI UYUMLULUGU (SHADOW) TESTI: BASARILI")


def run_final():
    """Principle Layer YAZILDIKTAN SONRA (madde 25/adım 15) transfer skorunu tekrar
    ölçer; BASELINE ile AYNI measure_transfer_score() fonksiyonunu kullanır."""
    baseline = measure_transfer_score(_baseline_classify)
    final = measure_transfer_score(_select)
    print("=== KAIZEN LEARNING BRAIN v1 — TRANSFER SCORE: ONCE/SONRA ===")
    print(f"{'':28s}{'ONCE (baseline)':>20s}{'SONRA (PrincipleRetriever)':>30s}")
    print(f"{'Positive Transfer Accuracy':28s}{baseline['positive_label']:>20s}{final['positive_label']:>30s}")
    print(f"{'Negative Transfer Rejection':28s}{baseline['negative_label']:>20s}{final['negative_label']:>30s}")
    print(f"{'Overall Transfer Score':28s}{baseline['overall_label']:>20s}{final['overall_label']:>30s}")
    return baseline, final


if __name__ == "__main__":
    test_transfer_dataset_has_all_seven_mandated_families()
    test_transfer_dataset_each_scenario_has_distinct_b_and_d_questions()
    test_transfer_dataset_no_annual_figures_leak_into_principle_statements()
    test_principle_positive_transfer_donemsellik()
    test_principle_positive_transfer_borc_alacak()
    test_principle_positive_transfer_hesap_siniflandirma()
    test_principle_positive_transfer_ozun_onceligi()
    test_principle_positive_transfer_maliyet_ilkesi()
    test_principle_positive_transfer_amortisman()
    test_principle_positive_transfer_sgk_statu()
    test_principle_negative_transfer_rejects_all_seven_counter_examples()
    test_principle_negative_transfer_sgk_counter_example_is_a_fact_not_a_principle()
    test_principle_not_found_for_unrelated_question()
    test_principle_multiple_candidates_are_both_visible_when_scores_are_close()
    test_principle_confidence_levels_are_one_of_the_four_labels()
    test_principle_low_or_none_confidence_never_forces_a_selection()
    test_principle_confidence_never_reaches_verified_label()
    test_principle_registry_rows_never_contain_annual_figures()
    test_principle_registry_every_row_has_non_empty_provenance()
    test_principle_registry_has_exactly_the_seven_curated_principles()
    test_principle_retrieval_handles_turkish_unicode_case_variants()
    test_principle_different_words_same_structure_still_transfers()
    test_principle_same_words_different_structure_does_not_transfer()
    test_principle_trace_output_shows_candidates_selected_confidence_rejected_reason()
    test_principle_trace_fields_default_empty_when_principle_layer_not_used()
    test_principle_decision_bridge_never_claims_verified_and_uses_known_route()
    print()
    print("TUM KAIZEN LEARNING BRAIN v1 TRANSFER TESTLERI: BASARILI")
    print()
    run_final()
