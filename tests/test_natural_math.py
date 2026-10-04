"""KAIZEN — Doğal dil deterministik hesap (kök neden #1, Learning Loop fazı).

Hem ÇÖZÜLEN kalıplar hem de YANLIŞ POZİTİF koruması: 'seçenekleri' içindeki 'ekle', '7/A ve 7/B'
kod parçaları, 'bölüm', yıl sayıları hesap SANILMAMALI."""
from accounting.calculators import CalculatorRouter
from accounting.natural_math import natural_math_answer


def _answer(question):
    return CalculatorRouter().answer(question)


def test_natural_math_chain_infix_reverse_percent_split_and_date_difference():
    assert "SONUÇ: 41" in _answer("45 ile 78'i topla sonra 3'e böl")
    assert "SONUÇ: 293" in _answer("100 ile 3'ü çarp sonra 7'yi çıkar")
    assert "SONUÇ: 1.000" in _answer("125 çarpı 8 kaç eder?")
    assert "SONUÇ: %20" in _answer("300 TL'nin yüzde kaçı 60 TL eder?")
    assert "SONUÇ: 64 gün" in _answer("15 Ocak 2026 ile 20 Mart 2026 arasında kaç gün var?")
    assert "SONUÇ: 64 gün" in _answer("15.01.2026 ile 20.03.2026 arasında kaç gün var?")
    assert "625,00 TL" in _answer("2500 lirayı 4 kişiye eşit paylaştırırsak kişi başı kaç TL düşer?")
    print("KAIZEN DOGAL DIL HESAP: ZINCIR/KELIME ISLEM/TERS YUZDE/PAYLASTIRMA/TARIH FARKI TESTI: BASARILI")


def test_natural_math_never_guesses_or_misfires_on_non_math_text():
    for question in (
        "Maliyet muhasebesinde 7/A ve 7/B seçenekleri ne fark eder?",  # 'seçenekleri' içinde 'ekle'
        "3. bölüm ve 5. bölüm nedir",                                    # 'bölüm' bir işlem değil
        "2026 yılında 500 TL fatura ekle",                               # 2026 bir yıl, operand değil
        "Bugün hava nasıl 3 kişi",
    ):
        assert natural_math_answer(question, []) is None, question
    # Belirsiz tarih sorusu (tek tarih) tahmin edilmez
    assert natural_math_answer("15 Ocak 2026 ile bugün arasında kaç gün var?", []) is None
    print("KAIZEN DOGAL DIL HESAP: YANLIS POZITIF/TAHMIN KORUMASI TESTI: BASARILI")


def test_natural_math_division_by_zero_is_honest_not_a_crash():
    text = _answer("10 bölü 0 kaç eder")
    assert text.startswith("Kaizen:") and "Sıfıra bölme" in text
    print("KAIZEN DOGAL DIL HESAP: SIFIRA BOLME DURUST MESAJ TESTI: BASARILI")


def test_trade_discount_is_not_misrouted_to_term_discount_but_bond_discount_is_unchanged():
    assert "1.700,00 TL" in _answer("Yüzde 15 iskonto uyguladığım 2000 TL'lik ürün kaç TL olur?")
    assert "Vade süresini belirtmediniz" not in _answer("Yüzde 15 iskonto uyguladığım 2000 TL'lik ürün kaç TL olur?")
    # Vadeli/senetli iskonto eski hesaplayıcıda kalır (vade eksikse hâlâ SORAR, tahmin etmez)
    asked = _answer("10000 TL nominal senedin yıllık %20 iskontosunu hesapla")
    assert asked is not None and "Vade süresini belirtmediniz" in asked
    print("KAIZEN TICARI INDIRIM vs VADELI ISKONTO YONLENDIRME TESTI: BASARILI")


if __name__ == "__main__":
    test_natural_math_chain_infix_reverse_percent_split_and_date_difference()
    test_natural_math_never_guesses_or_misfires_on_non_math_text()
    test_natural_math_division_by_zero_is_honest_not_a_crash()
    test_trade_discount_is_not_misrouted_to_term_discount_but_bond_discount_is_unchanged()
