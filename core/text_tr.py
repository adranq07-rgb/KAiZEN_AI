"""Türkçe metin yardımcıları: harf normalleştirme, sayı ve para biçimleri.

Kaizen'in tüm modülleri aynı normalleştirmeyi kullanır; böylece
"Şüpheli", "ŞÜPHELİ" ve "supheli" aynı kelime sayılır.
"""
import re
from decimal import Decimal, InvalidOperation

_TR_MAP = str.maketrans({
    "ı": "i", "İ": "i", "I": "i",
    "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u", "ö": "o", "Ö": "o",
    "ç": "c", "Ç": "c", "â": "a", "î": "i", "û": "u",
})


def fold_tr(value):
    """Küçük harfe çevirir ve Türkçe harfleri ASCII karşılığına indirger."""
    text = str(value).translate(_TR_MAP).lower()
    return " ".join(text.replace("̇", "").split())


# '/' normalde bir kelime sınırı sayılır (ör. tarih "15/01/2026", kesir "1/5" -- ikisi de SAYI/
# SAYI örüntüsü, ayrı tokenlara bölünmeye devam eder). Ama muhasebe/SGK/vergi mevzuatında '/'
# aynı zamanda TEK bir kodun parçası olabilir: SGK sigortalılık rejim kodları ("4/a", "4/b",
# "4/c") ve kanun madde/bent referansları ("7/A", "7/B"). Bu örüntü her zaman SAYI/HARF ya da
# HARF/SAYI biçimindedir (SAYI/SAYI değil) -- bu yüzden aşağıdaki genel kural (yalnız SGK'ya
# özel bir yama DEĞİL) tarih/kesir ifadelerini bozmadan bu kodları TEK token olarak korur.
_SLASH_CODE_OR_WORD = re.compile(r"\d{1,4}/[a-z]{1,4}|[a-z]{1,4}/\d{1,4}|[a-z0-9]+")


def tokens_tr(value):
    return re.findall(_SLASH_CODE_OR_WORD, fold_tr(value))


_NUMBER = re.compile(r"[-+]?\d[\d.,]*")


def parse_tr_number(text):
    """'10.000,50', '10000.5', '1,5' gibi sayıları Decimal'e çevirir.

    Belirsizlik varsa (ör. '1.500') binlik ayracı kabul edilir; çünkü muhasebe
    metinlerinde üç haneli nokta grubu neredeyse her zaman binliktir.
    """
    raw = str(text).strip().replace(" ", "").replace(" ", "")
    raw = raw.replace("₺", "").replace("TL", "").replace("tl", "")
    if not raw:
        raise ValueError("Boş sayı")
    sign = -1 if raw.startswith("-") else 1
    raw = raw.lstrip("+-")
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        head, _, tail = raw.rpartition(",")
        raw = (head.replace(",", "") + "." + tail) if raw.count(",") == 1 else raw.replace(",", "")
    elif "." in raw:
        head, _, tail = raw.rpartition(".")
        if raw.count(".") > 1 or len(tail) == 3:
            raw = raw.replace(".", "")
    try:
        return Decimal(raw) * sign
    except InvalidOperation as exc:
        raise ValueError(f"Sayı okunamadı: {text!r}") from exc


def format_number_tr(value, places=2):
    """Decimal değeri 1.234,56 biçiminde yazar (yuvarlama: yarım yukarı)."""
    from decimal import ROUND_HALF_UP
    quant = Decimal(1).scaleb(-places)
    value = Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP)
    text = f"{abs(value):,.{places}f}"
    text = text.replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if value < 0 else "") + text


def format_tl(value, places=2):
    return f"{format_number_tr(value, places)} TL"


_SMALL_WORDS = {"ve", "veya", "ile", "ait", "olan", "icin"}


def lower_tr(value):
    return str(value).replace("İ", "i").replace("I", "ı").lower().replace("\u0307", "")


def title_tr(value):
    """'DİĞER KISA VADELİ YABANCI KAYNAKLAR' -> 'Diğer Kısa Vadeli Yabancı Kaynaklar'."""
    out = []
    for word in lower_tr(value).split():
        if word in _SMALL_WORDS:
            out.append(word)
            continue
        first = word[0]
        first = "İ" if first == "i" else ("I" if first == "ı" else first.upper())
        out.append(first + word[1:])
    return " ".join(out)


# Hafif çekim eki listesi (yalnız isim/sıfat ekleri: durum, iyelik, çoğul, çoğul+durum/iyelik
# bileşikleri). En uzun ek önce denenir ki 'lerinden' 'lerde'ye bölünüp yanlış kırpılmasın.
# Tek harfli ekler (yönelme -e/-a, belirtme -i/-ı) kasıtlı olarak yok: kısa kelimelerde
# yanlış eşleşme riski (ör. rastgele bir kelimenin sonunun 'a' ile bitmesi) çok yüksek.
_STEM_SUFFIXES = tuple(sorted((
    "lerinden", "larindan", "lerinde", "larinda", "lerini", "larini", "lerine", "larina",
    "leriyle", "lariyla", "sinden", "sindan", "sinde", "sinda", "sine", "sina",
    "lerden", "lardan", "lerde", "larda", "leri", "lari",
    "den", "dan", "ten", "tan", "de", "da", "te", "ta",
    "nin", "nun", "sin", "sun", "lik", "luk", "sel", "sal",
    "ler", "lar", "si", "su", "in", "un",
), key=len, reverse=True))


def stem_tr(token, min_stem=4, max_strips=2):
    """Hafif ek kırpma (arama/eşleştirme için, tam morfolojik analiz değil).

    'muhasebede' -> 'muhasebe', 'bankalar' -> 'banka', 'vergisi' -> 'vergi'. Türkçe eklemeli
    olduğundan (ör. 'kurumlarin' = kurum+lar+in) en çok `max_strips` ek arka arkaya kırpılır;
    kök her seferinde en az `min_stem` karaktere düşmüyorsa durulur (kısa kelimeler bozulmasın).
    """
    for _ in range(max_strips):
        for suffix in _STEM_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= min_stem:
                token = token[: -len(suffix)]
                break
        else:
            break
    return token


def format_decimal_tr(value, max_places=10):
    """Sonucu sadeleştirerek Türkçe yazar: 1250000 -> 1.250.000 ; 0.3 -> 0,3 (en çok max_places ondalık)."""
    from decimal import ROUND_HALF_UP
    value = Decimal(str(value))
    value = value.quantize(Decimal(1).scaleb(-max_places), rounding=ROUND_HALF_UP)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    whole, _, frac = text.partition(".")
    negative = whole.startswith("-")
    whole = f"{int(whole.lstrip('-') or 0):,}".replace(",", ".")
    return ("-" if negative else "") + whole + ("," + frac if frac else "")
