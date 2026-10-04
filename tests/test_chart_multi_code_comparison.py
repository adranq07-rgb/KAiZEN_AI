"""ChartOfAccounts.answer() çoklu-kod karşılaştırma düzeltmesi (iş emri "RAG v2 - Faz 1"
madde 11 -- kanıt: KAIZEN_HEDEF_VE_YOL_HARITASI.md bölüm 4p, Bug C2/C3; ölçüm:
tests/test_real_world_exam.py, tests/test_classification_failures.py, tests/test_retriever.py'nin
KENDİSİ değil ama aynı ruhla).

Düzeltmeden ÖNCE iki gerçek, kanıtlanmış hata vardı (accounting/chart_of_accounts.py):
  * Bug C2: `_TRIGGERS` gate'i, "760 ile 770 arasındaki fark ne?" gibi soruları (hiçbir tetikleyici
    kelime geçmediği için) hiç DENEMİYORDU bile.
  * Bug C3: gate'i geçen "153 ile 150 hesap arasındaki fark nedir?" gibi bir soruda bile, kod-regex'i
    yalnız İLK kodu (153) yakalayıp İKİNCİYİ (150) sessizce yok sayıyordu -- yine de 'SONUÇ:'
    (VERIFIED) etiketiyle YARIM bir cevap veriyordu.

Bu dosya düzeltmeyi doğrudan `ChartOfAccounts.answer()` üzerinde (gerçek `config/tdhp.json`
verisiyle, hiçbir sahte/mock olmadan) kilitler. Gerçek dosyalara hiç yazma yapılmaz (yalnız
okuma).
"""
from accounting.chart_of_accounts import ChartOfAccounts


def test_chart_multi_code_comparison_describes_both_accounts():
    chart = ChartOfAccounts()
    answer = chart.answer("760 ile 770 arasındaki fark ne?")
    assert answer is not None
    assert answer.startswith("SONUÇ:")
    assert "760 Pazarlama" in answer
    assert "770 Genel Yönetim" in answer
    print("KAIZEN CHART COKLU-KOD KARSILASTIRMA (760/770) TESTI: BASARILI")


def test_chart_multi_code_comparison_bypasses_the_triggers_gate():
    """Bug C2'nin doğrudan kanıtı: bu soruda `_TRIGGERS`'taki HİÇBİR kelime ('hesap', 'kodu',
    'nedir', 'numara', 'tdhp' vb.) geçmiyor -- eskiden bu yüzden `answer()` hiç denemeden
    `None` dönerdi."""
    chart = ChartOfAccounts()
    question = "760 ile 770 arasındaki fark ne?"
    from accounting.chart_of_accounts import _TRIGGERS
    from core.text_tr import fold_tr
    assert not any(t in fold_tr(question) for t in _TRIGGERS)  # gate'i BOŞ geçerdi
    assert chart.answer(question) is not None  # ama yine de cevaplıyor
    print("KAIZEN CHART TETIKLEYICI KAPISINI ATLAMA (BUG C2) TESTI: BASARILI")


def test_chart_multi_code_comparison_no_longer_drops_the_second_account():
    """Bug C3'ün doğrudan kanıtı: eskiden yalnız İLK kod (153) açıklanır, İKİNCİ kod (150)
    sessizce kaybolurdu. Artık her ikisi de cevapta."""
    chart = ChartOfAccounts()
    answer = chart.answer("153 ile 150 hesap arasındaki fark nedir?")
    assert "153 Ticari Mallar" in answer
    assert "150 İlk Madde" in answer  # eskiden burada YOKTU (bkz. modül docstring'i)
    print("KAIZEN CHART IKINCI HESABI ARTIK KAYBETMIYOR (BUG C3) TESTI: BASARILI")


def test_chart_single_code_questions_are_completely_unaffected():
    """Regresyon güvencesi: TEK bir geçerli koddan bahseden sıradan sorularda (çoklu-kod yolu
    hiç tetiklenmemeli) davranış BİREBİR eskisi gibi kalmalı."""
    chart = ChartOfAccounts()
    assert chart.answer("191 hesap neden borç çalışıyor?").startswith(
        "SONUÇ: 191 İndirilecek KDV"
    )
    assert chart.answer("153 hesap kodu nedir").startswith("SONUÇ: 153 Ticari Mallar")
    assert chart.answer("Kasa hesabının kodu kaç?").startswith("SONUÇ: 100 Kasa")


    print("KAIZEN CHART TEK-KOD SORULARI ETKILENMEDI (REGRESYON) TESTI: BASARILI")


def test_chart_two_numbers_without_comparison_word_do_not_trigger_the_new_path():
    """Yanlış pozitif koruması: metinde 2 geçerli hesap kodu olsa bile, hiçbir karşılaştırma
    kelimesi (`_COMPARISON_HINTS`: 'ile', 'fark', 'arasında'...) yoksa YENİ çoklu-kod yolu HİÇ
    tetiklenmemeli (ve eski _TRIGGERS mantığı da hiçbir tetikleyici kelime içermediği için None
    dönmeli) -- rastgele iki 3 haneli sayı geçen alakasız bir cümle yanlışlıkla 'hesap
    karşılaştırması' sayılmamalı."""
    chart = ChartOfAccounts()
    # "153" ve "320" ikisi de geçerli hesap kodu ama cümlede karşılaştırma kelimesi yok ve
    # hiçbir _TRIGGERS kelimesi de yok.
    assert chart.answer("153 kişi geldi, 320 kişi de gelecekti") is None
    print("KAIZEN CHART YANLIS POZITIF KORUMASI TESTI: BASARILI")


if __name__ == "__main__":
    test_chart_multi_code_comparison_describes_both_accounts()
    test_chart_multi_code_comparison_bypasses_the_triggers_gate()
    test_chart_multi_code_comparison_no_longer_drops_the_second_account()
    test_chart_single_code_questions_are_completely_unaffected()
    test_chart_two_numbers_without_comparison_word_do_not_trigger_the_new_path()
    print("KAIZEN CHART COKLU-KOD DUZELTME TESTLERI: BASARILI")
