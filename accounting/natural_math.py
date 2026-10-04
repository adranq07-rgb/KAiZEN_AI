"""KAIZEN — Doğal dilde yazılmış DETERMİNİSTİK hesaplar (Decimal, uydurma yok).

Gerçek kullanıcı başarısızlığının kök nedeni #1 (33 soruluk sınav analizi): "45 ile 78'i
topla sonra 3'e böl", "125 çarpı 8", "300 TL'nin yüzde kaçı 60 TL", "15 Ocak ile 20 Mart
arası kaç gün", "2500 lirayı 4 kişiye paylaştır" gibi tamamen hesaplanabilir sorular kesin
araçlara (arithmetic/CalculatorRouter) HİÇ ulaşmıyor, modele/'bulamadım'a düşüyordu.

Bu modül GENEL kalıpları çözer (belirli bir sorunun kelimeleri/sayıları değil): zincirleme
dört işlem fiilleri, kelimeyle yazılmış işlem, ters yüzde, eşit paylaştırma, iki tarih farkı.
Hiçbir oran/had sabit değildir. Belirsizlikte (eksik/fazla sayı, sıra karışıklığı) TAHMİN
ETMEZ, None döner -- çağıran zincir eskisi gibi devam eder.
"""
import re
from datetime import date
from decimal import Decimal

from core.text_tr import fold_tr, format_decimal_tr, format_number_tr, format_tl, parse_tr_number

# Sayı: kesir/kod parçası ('7/A', '3/4') ve takvim yılı DEĞİL. Sondaki noktalama sayıya ait değildir.
_NUM = r"\d[\d.,]*"
_NUM_TOKEN = re.compile(r"(?<![\d.,/])\d(?:[\d.,]*\d)?(?![\d/]|[.,]\d)")
_YEAR_WORD = re.compile(r"(?<![\d.,])(?:19|20)\d{2}\s*['’]?\s*(?:yil\w*|da\b|de\b|ta\b|te\b|den\b|dan\b)")
_MONTH_NUMBERS = {
    "ocak": 1, "subat": 2, "mart": 3, "nisan": 4, "mayis": 5, "haziran": 6, "temmuz": 7,
    "agustos": 8, "eylul": 9, "ekim": 10, "kasim": 11, "aralik": 12,
}
_INFIX = re.compile(rf"(?<![\d.,])({_NUM})\s*(?:tl|lira)?\s+(arti|eksi|carpi|bolu|kere)\s+({_NUM})")
_VERB_OPS = (("topla", "+"), ("ekle", "+"), ("cikar", "-"), ("carp", "*"), ("bol", "/"))
# Fiil TAM sözcük olarak (emir/istek/-ıp kipleri) geçmeli: 'seçenekleri' içindeki 'ekle' ya da
# 'bölüm' içindeki 'böl' bir işlem DEĞİLDİR.
_VERB_WORD = re.compile(
    r"\b(topla|ekle|cikar|carp|bol)(?:yin|yip|yarak|rsak|rsam|arsak|arsam|ersek|ersem|in|un|ip|up|sak|sek|mak|mek)?\b"
)
_CLAUSE_SPLIT = re.compile(r"\b(?:daha\s+)?sonra\b|\bardindan\b|\bsonrasinda\b|,|\bsonuc(?:u)?\b")
_SYMBOL = {"+": "+", "-": "−", "*": "×", "/": "÷"}
_REVERSE_PERCENT = re.compile(
    rf"(?<![\d.,])({_NUM})\s*(?:tl|lira)?\s*['’]?\s*(?:nin|nun|in|un)\s+yuzde\s*kac"
)
_SPLIT_PEOPLE = re.compile(r"(?<![\d.,])(\d{1,4})\s*(?:kisi|ortak|calisan|personel|isci|hisse)\w*")
_MONEY = re.compile(rf"(?<![\d.,])({_NUM})\s*(?:tl|lira)")
_SPLIT_WORDS = ("esit", "paylas", "bol", "kisi basi", "kisi basina", "ortak basi", "pay ")
_DATE_TEXT = re.compile(r"(?<![\d.,])(\d{1,2})\s+(" + "|".join(_MONTH_NUMBERS) + r")\s+(\d{4})")
_DATE_NUM = re.compile(r"(?<![\d.,])(\d{1,2})[./](\d{1,2})[./](\d{4})(?![\d])")
_DAYS_ASKED = re.compile(r"kac gun|gun var|gun fark|kac gundur|kac takvim gun")


class NaturalMathError(ValueError):
    pass


def _dec(text):
    return parse_tr_number(text)


def _apply(op, left, right):
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if right == 0:
        raise NaturalMathError("Sıfıra bölme yapılamaz.")
    return left / right


def _op_in(clause):
    symbols = {dict(_VERB_OPS)[m.group(1)] for m in _VERB_WORD.finditer(clause)}
    return symbols.pop() if len(symbols) == 1 else None


def _chain(folded):
    """'45 ile 78'i topla sonra 3'e böl' -> ((45 + 78) ÷ 3). Yalnız TÜM cümleler temiz
    çözülürse döner; aksi halde None (tahmin yok)."""
    folded = _YEAR_WORD.sub(" ", folded)
    clauses = [c.strip() for c in _CLAUSE_SPLIT.split(folded) if c.strip()]
    if not clauses:
        return None
    value, expr = None, ""
    for index, clause in enumerate(clauses):
        numbers = _NUM_TOKEN.findall(clause)
        op = _op_in(clause)
        if op is None or not numbers:
            if index == 0:
                return None
            continue
        if index == 0:
            if len(numbers) != 2:
                return None
            left, right = _dec(numbers[0]), _dec(numbers[1])
            # 'A'dan B'yi çıkar' ve 'A'yı B'ye böl' sıralı okunur: A op B
            value = _apply(op, left, right)
            expr = f"{format_decimal_tr(left)} {_SYMBOL[op]} {format_decimal_tr(right)}"
        else:
            if len(numbers) != 1:
                return None
            operand = _dec(numbers[0])
            value = _apply(op, value, operand)
            expr = f"({expr}) {_SYMBOL[op]} {format_decimal_tr(operand)}"
    if value is None:
        return None
    return f"SONUÇ: {format_decimal_tr(value)}\nHESAP: {expr} = {format_decimal_tr(value)}"


def _infix(folded):
    match = _INFIX.search(_YEAR_WORD.sub(" ", folded))
    if not match:
        return None
    left, word, right = _dec(match.group(1)), match.group(2), _dec(match.group(3))
    op = {"arti": "+", "eksi": "-", "carpi": "*", "kere": "*", "bolu": "/"}[word]
    value = _apply(op, left, right)
    return (f"SONUÇ: {format_decimal_tr(value)}\n"
            f"HESAP: {format_decimal_tr(left)} {_SYMBOL[op]} {format_decimal_tr(right)} = {format_decimal_tr(value)}")


def _reverse_percent(folded, amounts):
    """'300 TL'nin yüzde kaçı 60 TL eder' -> 60 / 300 x 100. Bütün, 'X'in yüzde kaçı' ile
    gösterilen sayıdır; sıra belirsizse tahmin edilmez."""
    match = _REVERSE_PERCENT.search(folded)
    if not match or len(amounts) < 2:
        return None
    whole = _dec(match.group(1))
    rest = [a for a in amounts if a != whole] or [amounts[1]]
    part = rest[0]
    if whole == 0:
        raise NaturalMathError("Bütün değer sıfır olamaz.")
    percent = part / whole * Decimal(100)
    shown = format_decimal_tr(percent.quantize(Decimal("0.01")))
    return (f"SONUÇ: %{shown}\n"
            f"HESAP: {format_tl(part)} / {format_tl(whole)} x 100")


def _equal_split(folded):
    people = _SPLIT_PEOPLE.search(folded)
    money = _MONEY.search(folded)
    if not people or not money or not any(w in folded for w in _SPLIT_WORDS):
        return None
    n = int(people.group(1))
    if n <= 0:
        raise NaturalMathError("Kişi sayısı sıfır olamaz.")
    total = _dec(money.group(1))
    share = total / Decimal(n)
    return (f"SONUÇ: kişi başı {format_tl(share)}\n"
            f"HESAP: {format_tl(total)} / {n} = {format_tl(share)}")


def _to_date(day, month, year):
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        raise NaturalMathError(f"Geçersiz tarih: {day}.{month}.{year}")


def _date_difference(folded):
    if not _DAYS_ASKED.search(folded):
        return None
    dates = [(m.start(), _to_date(m.group(1), _MONTH_NUMBERS[m.group(2)], m.group(3)))
             for m in _DATE_TEXT.finditer(folded)]
    dates += [(m.start(), _to_date(m.group(1), m.group(2), m.group(3))) for m in _DATE_NUM.finditer(folded)]
    if len(dates) != 2:
        return None
    dates.sort()
    first, second = dates[0][1], dates[1][1]
    days = abs((second - first).days)
    return (f"SONUÇ: {days} gün\n"
            f"HESAP: {second.strftime('%d.%m.%Y')} - {first.strftime('%d.%m.%Y')} = {days} takvim günü "
            "(başlangıç günü hariç, bitiş günü dahil).")


def natural_math_answer(question, amounts=()):
    """Doğal dil hesap sorusunu çözer; tanınmazsa None. Hata durumunda dürüst mesaj döner."""
    folded = fold_tr(question)
    try:
        for solver in (
            lambda: _date_difference(folded),
            lambda: _reverse_percent(folded, list(amounts)),
            lambda: _equal_split(folded),
            lambda: _infix(folded),
            lambda: _chain(folded),
        ):
            result = solver()
            if result:
                return result
    except NaturalMathError as exc:
        return f"Kaizen: Hesaplama yapılamadı: {exc}"
    return None
