"""accounting.retriever.Retriever: soru-metin örtüşmesi (coverage/phrase_ok), özellikle
Türkçe ek farkının iki yönlü de tanınması (bkz. core.text_tr.stem_tr).
"""
from accounting.retriever import Retriever

TEXT = "Muhasebe temel kavramlarından dönemsellik kavramı, işletmenin faaliyetlerinin belirli dönemlere bölünmesidir."


def test_coverage_matches_suffixed_question_word_against_bare_text_word():
    # "muhasebede" (soruda, ek'li) metindeki "muhasebe" (ek'siz) ile eşleşmeli. Eskiden bu
    # yalnız TERSİ yönde çalışıyordu (soru kökü -> metindeki ekli hal); bu yüzden ek soruda
    # olunca ("...de" gibi) eşleşme kaçıyordu.
    assert Retriever.coverage("Muhasebede dönemsellik kavramı nedir", TEXT) == 1.0
    assert Retriever.phrase_ok("Muhasebede dönemsellik kavramı nedir", TEXT)


def test_coverage_still_low_for_unrelated_question():
    assert Retriever.coverage("Excel'de düşeyara nasıl kullanılır", TEXT) < 0.5


def test_coverage_matches_possessive_suffix_variant():
    # "vergisi" (metin) ~ "vergi" (soru) gibi iyelik eki farkı da artık tanınıyor.
    text = "Kurumlar vergisi oranı, ilgili kanunda belirlenen orandır."
    assert Retriever.coverage("kurumlar vergi oranı nedir", text) == 1.0


if __name__ == "__main__":
    test_coverage_matches_suffixed_question_word_against_bare_text_word()
    test_coverage_still_low_for_unrelated_question()
    test_coverage_matches_possessive_suffix_variant()
    print("KAIZEN RETRIEVER EK ESLESTIRME TESTI: BASARILI")
