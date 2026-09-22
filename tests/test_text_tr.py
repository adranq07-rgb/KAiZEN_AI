"""core.text_tr.stem_tr: hafif Türkçe ek kırpma (arama/eşleştirme için).

Kaizen'in hiçbir yerinde ağır bir NLP/morfoloji kütüphanesi yok (Zemberek vb.); bu, elle
yazılmış küçük bir ek listesiyle 'aynı kök' sayılması gereken kelime çiftlerini yakalar.
Tam bir morfolojik analiz DEĞİLDİR -- yalnız arama eşleşmesi için yeterince iyi olması hedeflenir.
"""
from core.text_tr import stem_tr


def test_stem_tr_same_root_pairs_match():
    # Önceden Retriever'da yalnız TEK yönlü bir kırpma vardı (soru kökünü, metindeki ekli
    # haliyle eşleştirebiliyordu ama tersini değil); bu yüzden "muhasebede" (soruda, ekli)
    # "muhasebe" (metinde, eksiz) ile eşleşmiyordu. Artık ikisi de aynı köke iniyor.
    pairs = [
        ("muhasebede", "muhasebe"),
        ("muhasebe", "muhasebede"),          # yön önemli değil
        ("muhasebesi", "muhasebe"),
        ("bankalar", "banka"),
        ("vergisi", "vergi"),
        ("hesaplardan", "hesap"),
        ("kurumlarin", "kurum"),
        ("gecikmeden", "gecikme"),
    ]
    for a, b in pairs:
        assert stem_tr(a) == stem_tr(b), f"{a!r} ~ {b!r} aynı kök sayılmalı"


def test_stem_tr_does_not_over_strip_short_words():
    # Kök 4 karakterin altına düşecekse kırpma yapılmaz (kısa kelimeler bozulmasın diye).
    assert stem_tr("kar") == "kar"
    assert stem_tr("sac") == "sac"
    assert stem_tr("de") == "de"
    assert stem_tr("sgkda") == "sgkda"   # "sgk" (3) min_stem=4'ün altında kalır, kırpılmaz


def test_stem_tr_unrelated_words_stay_different():
    assert stem_tr("fatura") != stem_tr("vergi")
    assert stem_tr("kasa") != stem_tr("banka")


if __name__ == "__main__":
    test_stem_tr_same_root_pairs_match()
    test_stem_tr_does_not_over_strip_short_words()
    test_stem_tr_unrelated_words_stay_different()
    print("KAIZEN TURKCE EK KIRPMA (STEM_TR) TESTI: BASARILI")
