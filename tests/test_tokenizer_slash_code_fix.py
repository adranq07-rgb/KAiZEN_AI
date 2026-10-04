"""tokens_tr() eğik-çizgili kod düzeltmesi (iş emri "KAIZEN — FAZ 1.1", madde 1).

Kök neden (kanıtlandı: tests/test_retrieval_failures.py, roadmap bölüm 4p/4q/4r):
`core.text_tr.tokens_tr()` `[a-z0-9]+` regex'i kullanıyordu -- '/' bir kelime sınırı
sayılıyordu. Bu yüzden '4/a', '4/b', '4/c' gibi SGK rejim kodları VEYA '7/A', '7/B' gibi
kanun madde/bent referansları TEK KARAKTERLİK anlamsız parçalara bölünüyordu (`'4/a'` ->
`['4', 'a']`) ve `Retriever._terms()`'teki `len(t) > 2` anlamlılık süzgeci bu parçaları
TAMAMEN atıyordu -- bilgi yerel hafızada GERÇEKTEN varken bile sorunun tüm sinyali
kayboluyordu.

Bu dosya ÖNCE (TDD, "önce başarısız testi yaz, sonra minimum kod değişikliğini yap"):
istenen DOĞRU davranışı -- eğik çizgili "sayı/harf" ya da "harf/sayı" kodlarının TEK bir
token olarak korunmasını -- kilitler. Düzeltmeden ÖNCE bu testlerin ilk ikisi BAŞARISIZ olur
(bkz. iş emri kaydı: ilk çalıştırmada `AssertionError` alındı, ardından `core/text_tr.py`
değiştirildi).

Düzeltme KASITLI OLARAK genel bir tokenizer kuralıdır (SAYI/HARF ya da HARF/SAYI örüntüsü),
SGK'ya özel hard-code edilmiş bir yama DEĞİLDİR -- bu yüzden dosyanın geri kalanı, düzeltmenin
hesap kodlarını (760, 153...), oran ifadelerini (%18, çıplak sayı/sayı kesirleri) ve
tarih/yıl ifadelerini (15/01/2026) BOZMADIĞINI ayrı ayrı kilitler (regresyon güvencesi).
"""
import tempfile
from pathlib import Path

from accounting.accounting_brain import AccountingBrain
from accounting.retriever import Retriever, Evidence
from core.text_tr import fold_tr, tokens_tr
from memory.learning_store import LearningStore
from memory.seed_loader import load_seeds


def _seeded_accounting_brain():
    store = LearningStore(Path(tempfile.mkdtemp()) / "tokenizer_fix_probe.sqlite3")
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


# --- 1) Ana düzeltme: sayı/harf kodları artık TEK token -----------------------------------

def test_tokenizer_preserves_digit_slash_letter_codes_as_single_tokens():
    """Düzeltmenin doğrudan kanıtı: '4/a' artık İKİ değil TEK token."""
    assert tokens_tr("4/a 4/b 4/c nedir") == ["4/a", "4/b", "4/c", "nedir"]
    print("KAIZEN TOKENIZER EGIK CIZGILI KOD TEK TOKEN (4/A) TESTI: BASARILI")


def test_tokenizer_preserves_digit_slash_letter_codes_uppercase_input():
    """'7/A', '7/B' gibi büyük harfli kanun madde/bent referansları da (fold_tr küçük harfe
    indirdikten sonra) tek token olarak korunmalı -- yalnız SGK'ya özgü değil, genel kural."""
    tokens = tokens_tr("Maliyet muhasebesinde 7/A ve 7/B seçenekleri ne fark eder?")
    assert "7/a" in tokens and "7/b" in tokens
    assert "7" not in tokens and "a" not in tokens and "b" not in tokens  # eskiden bölünen parçalar artık YOK
    print("KAIZEN TOKENIZER EGIK CIZGILI KOD TEK TOKEN (7/A, 7/B BUYUK HARF) TESTI: BASARILI")


# --- 2) Regresyon: hesap kodları (eğik çizgisiz) hiç etkilenmemeli ------------------------

def test_tokenizer_does_not_break_plain_account_codes_without_slash():
    """Regresyon: eğik çizgisiz, sade hesap kodları (760, 153, 320...) HİÇ etkilenmemeli --
    hâlâ eskisi gibi ayrı, sade sayısal tokenlar (chart_of_accounts.py bu davranışa bağımlı)."""
    assert tokens_tr("760 ile 770 arasındaki fark ne?") == [
        "760", "ile", "770", "arasindaki", "fark", "ne",
    ]
    assert tokens_tr("153 ile 150 hesap arasındaki fark nedir?") == [
        "153", "ile", "150", "hesap", "arasindaki", "fark", "nedir",
    ]
    print("KAIZEN TOKENIZER HESAP KODU REGRESYONU TESTI: BASARILI")


# --- 3) Regresyon: sayı/sayı örüntüleri (tarih, kesir) hâlâ ayrı tokenlara bölünmeli ------

def test_tokenizer_does_not_merge_pure_numeric_date_or_fraction_slashes():
    """Regresyon: '/' hem SAYI/SAYI (tarih: 15/01/2026, kesir: 1/5) hem SAYI/HARF (SGK kodu)
    ayracı olarak kullanılabiliyor. Düzeltme YALNIZ SAYI/HARF (ya da HARF/SAYI) örüntüsünü tek
    tokene birleştirir -- SAYI/SAYI örüntüsü (harf YOK) kasıtlı olarak eskisi gibi AYRI
    tokenlara bölünmeye devam etmeli (tarih/yıl ifadelerinin bozulmaması için bilinçli sınır)."""
    assert tokens_tr("15/01/2026 tarihli belge") == ["15", "01", "2026", "tarihli", "belge"]
    assert tokens_tr("amortisman oranı 1/5 kullanılır") == [
        "amortisman", "orani", "1", "5", "kullanilir",
    ]
    print("KAIZEN TOKENIZER TARIH/KESIR (SAYI-SAYI) REGRESYONU TESTI: BASARILI")


# --- 4) Regresyon: oran ifadeleri (%18 gibi) hiç etkilenmemeli ---------------------------

def test_tokenizer_does_not_affect_percent_rate_expressions():
    """Regresyon: '%18' gibi oran ifadeleri zaten '/' içermiyor -- düzeltme bunlara hiç
    dokunmuyor (yüzde işareti zaten [a-z0-9] sınıfının dışında, eskiden de düşüyordu)."""
    assert tokens_tr("%18 KDV oranı") == ["18", "kdv", "orani"]
    print("KAIZEN TOKENIZER ORAN IFADESI (%) REGRESYONU TESTI: BASARILI")


# --- 5) Sonuç: anlamlılık süzgeci artık kodları TUTUYOR (eskiden atıyordu) ----------------

def test_significance_filter_now_keeps_slash_codes_instead_of_dropping_them():
    """`Retriever._terms()`'teki `len(t) > 2` süzgeci artık '4/a' gibi (uzunluk 3) kodları
    TUTUYOR -- eskiden ('4','a' diye ikiye bölündüğü için, ikisi de uzunluk 1) ikisi de
    tamamen atılıyordu (bkz. tests/test_retrieval_failures.py'nin GÜNCELLENMİŞ testi)."""
    terms = Retriever._terms("4/a 4/b 4/c nedir, aralarındaki fark ne?")
    assert "4/a" in terms and "4/b" in terms and "4/c" in terms
    print("KAIZEN ANLAMLILIK FILTRESI ARTIK EGIK CIZGILI KODU TUTUYOR TESTI: BASARILI")


# --- 6) Ana kanıt: gerçek curriculum içeriğiyle extractive_answer artık BULUYOR -----------

def test_extractive_answer_now_finds_the_4a_4b_4c_curriculum_entry_real_data():
    """Gerçek `knowledge/sgk_temel_yapi.json` içeriğiyle (sentetik değil, üretim API'sinin
    kendisiyle): eskiden None dönen extractive_answer() artık DOLU bir cevap döndürüyor --
    bilgi zaten yerel hafızada #1 sırada bulunuyordu, artık gerçekten KULLANILABİLİYOR da."""
    question = "4/a 4/b 4/c nedir, aralarındaki fark ne?"
    accounting_brain = _seeded_accounting_brain()
    _, rows = accounting_brain.retrieve(question, limit=1)
    assert rows and "4/a" in rows[0]["text"]
    evidence = _evidence_from_rows(rows)
    answer = Retriever.extractive_answer(question, evidence, strict=False)
    assert answer is not None
    print("KAIZEN EXTRACTIVE_ANSWER ARTIK 4/A ICERIGINI BULUYOR (DUZELTME KANITI) TESTI: BASARILI")


if __name__ == "__main__":
    test_tokenizer_preserves_digit_slash_letter_codes_as_single_tokens()
    test_tokenizer_preserves_digit_slash_letter_codes_uppercase_input()
    test_tokenizer_does_not_break_plain_account_codes_without_slash()
    test_tokenizer_does_not_merge_pure_numeric_date_or_fraction_slashes()
    test_tokenizer_does_not_affect_percent_rate_expressions()
    test_significance_filter_now_keeps_slash_codes_instead_of_dropping_them()
    test_extractive_answer_now_finds_the_4a_4b_4c_curriculum_entry_real_data()
    print("KAIZEN TOKENIZER EGIK CIZGI DUZELTME TESTLERI: BASARILI")
