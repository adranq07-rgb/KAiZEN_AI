"""Kuruşu kuruşuna doğru muhasebe hesaplayıcıları (Decimal, yarım yukarı yuvarlama).

Hiçbir yıllık oran/had bu dosyada sabit değildir: oran, tevkifat kesri, binde
gibi değerler her zaman çağıran tarafından verilir. Böylece bayat bir oran
yüzünden yanlış sonuç üretilmez; güncel değerler `facts` kayıt defterinden gelir.
"""
import re
from decimal import Decimal, ROUND_HALF_UP, getcontext

from accounting.natural_math import natural_math_answer
from core.text_tr import fold_tr, format_number_tr, format_tl, parse_tr_number

getcontext().prec = 40
ZERO = Decimal("0")
HUNDRED = Decimal("100")


class CalculationError(ValueError):
    pass


def D(value):
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        return parse_tr_number(value)
    return Decimal(str(value))


def money(value):
    return D(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _positive(value, name):
    value = D(value)
    if value < 0:
        raise CalculationError(f"{name} negatif olamaz")
    return value


# --- KDV -----------------------------------------------------------------------

def kdv(amount, rate, included=False):
    """KDV hariç tutardan KDV'li tutarı veya KDV dahil tutardan matrahı bulur."""
    amount, rate = _positive(amount, "Tutar"), _positive(rate, "KDV oranı")
    if included:
        matrah = money(amount * HUNDRED / (HUNDRED + rate))
        return {"matrah": matrah, "kdv": money(amount) - matrah, "toplam": money(amount), "oran": rate}
    matrah = money(amount)
    tax = money(matrah * rate / HUNDRED)
    return {"matrah": matrah, "kdv": tax, "toplam": matrah + tax, "oran": rate}


def kdv_tevkifat(matrah, kdv_rate, numerator, denominator):
    """Kısmi tevkifat: hesaplanan KDV'nin numerator/denominator kadarı alıcıca beyan edilir."""
    matrah = money(_positive(matrah, "Matrah"))
    if D(denominator) <= 0 or D(numerator) < 0 or D(numerator) > D(denominator):
        raise CalculationError("Tevkifat oranı 0 ile 1 arasında bir kesir olmalı (ör. 5/10)")
    hesaplanan = money(matrah * D(kdv_rate) / HUNDRED)
    tevkif = money(hesaplanan * D(numerator) / D(denominator))
    return {
        "matrah": matrah, "hesaplanan_kdv": hesaplanan, "tevkifat_kdv": tevkif,
        "satici_kdv": hesaplanan - tevkif, "satici_tahsilat": matrah + hesaplanan - tevkif,
        "alici_odeme": matrah + hesaplanan - tevkif,
    }


# --- Stopaj / SMM / damga ---------------------------------------------------------

def stopaj(amount, rate, amount_is_net=False):
    """Brüt tutardan stopajı bulur; net verilirse brüt tutara geri gider."""
    rate = _positive(rate, "Stopaj oranı")
    if rate >= HUNDRED:
        raise CalculationError("Stopaj oranı %100'den küçük olmalı")
    if amount_is_net:
        gross = money(D(amount) * HUNDRED / (HUNDRED - rate))
        return {"brut": gross, "stopaj": gross - money(amount), "net": money(amount), "oran": rate}
    gross = money(_positive(amount, "Tutar"))
    cut = money(gross * rate / HUNDRED)
    return {"brut": gross, "stopaj": cut, "net": gross - cut, "oran": rate}


def serbest_meslek_makbuzu(brut, kdv_rate, stopaj_rate):
    """SMM: brüt + KDV - stopaj = tahsil edilecek net tutar."""
    brut = money(_positive(brut, "Brüt ücret"))
    tax = money(brut * D(kdv_rate) / HUNDRED)
    cut = money(brut * D(stopaj_rate) / HUNDRED)
    return {"brut": brut, "kdv": tax, "stopaj": cut, "net_tahsilat": brut + tax - cut}


def serbest_meslek_makbuzu_netten(net_tahsilat, kdv_rate, stopaj_rate):
    factor = HUNDRED + D(kdv_rate) - D(stopaj_rate)
    if factor <= 0:
        raise CalculationError("Oranlar geçersiz")
    return serbest_meslek_makbuzu(D(net_tahsilat) * HUNDRED / factor, kdv_rate, stopaj_rate)


def damga_vergisi(amount, per_thousand):
    return money(_positive(amount, "Tutar") * _positive(per_thousand, "Binde oran") / Decimal(1000))


def iban_coz(iban):
    """TR IBAN doğrulaması (mod 97) ve bölümlerine ayırma. Banka adı uydurulmaz; yalnız banka kodu verilir."""
    compact = re.sub(r"\s+", "", str(iban)).upper()
    if not re.fullmatch(r"TR\d{24}", compact):
        raise CalculationError("TR IBAN 'TR' + 24 rakam (toplam 26 karakter) olmalıdır")
    rearranged = compact[4:] + compact[:4]
    number = "".join(str(int(ch, 36)) for ch in rearranged)
    valid = int(number) % 97 == 1
    return {
        "iban": " ".join(compact[i:i + 4] for i in range(0, 26, 4)), "gecerli": valid,
        "kontrol": compact[2:4], "banka_kodu": compact[4:9], "rezerv": compact[9], "hesap_no": compact[10:],
    }


def finansal_oran(ad, **v):
    """Bilanço/gelir tablosu oranları. Bölen sıfırsa hata verir; yorum katmaz, yalnız hesaplar."""
    def ratio(num, den, name):
        if D(den) == 0:
            raise CalculationError(f"{name}: bölen sıfır olamaz")
        return (D(num) / D(den))
    if ad == "cari_oran":
        return ratio(v["donen_varlik"], v["kvyk"], "Kısa vadeli yabancı kaynak")
    if ad == "asit_test":
        return ratio(D(v["donen_varlik"]) - D(v["stok"]), v["kvyk"], "Kısa vadeli yabancı kaynak")
    if ad == "nakit_oran":
        return ratio(v["hazir_deger"], v["kvyk"], "Kısa vadeli yabancı kaynak")
    if ad == "kaldirac":
        return ratio(v["toplam_borc"], v["toplam_varlik"], "Toplam varlık")
    if ad == "borc_ozkaynak":
        return ratio(v["toplam_borc"], v["ozkaynak"], "Özkaynak")
    if ad == "ozkaynak_orani":
        return ratio(v["ozkaynak"], v["toplam_varlik"], "Toplam varlık")
    if ad == "roe":
        return ratio(v["net_kar"], v["ozkaynak"], "Özkaynak") * HUNDRED
    if ad == "roa":
        return ratio(v["net_kar"], v["toplam_varlik"], "Toplam varlık") * HUNDRED
    if ad == "net_kar_marji":
        return ratio(v["net_kar"], v["net_satis"], "Net satış") * HUNDRED
    if ad == "brut_kar_marji":
        return ratio(D(v["net_satis"]) - D(v["smm"]), v["net_satis"], "Net satış") * HUNDRED
    raise CalculationError(f"Bilinmeyen oran: {ad}")


# --- Faiz / gecikme / iskonto -----------------------------------------------------

def basit_faiz(principal, annual_rate, days, basis=365):
    principal = _positive(principal, "Anapara")
    interest = money(principal * D(annual_rate) * D(days) / (HUNDRED * D(basis)))
    return {"faiz": interest, "toplam": money(principal) + interest}


def gecikme_zammi(amount, monthly_rate, months):
    """Aylık oran x ay sayısı (basit). Kesirli ay tam ay sayılır; ay sayısını çağıran verir."""
    amount = money(_positive(amount, "Tutar"))
    zam = money(amount * D(monthly_rate) * D(months) / HUNDRED)
    return {"gecikme_zammi": zam, "toplam": amount + zam}


def iskonto(nominal, annual_rate, days, kind="ic", basis=365):
    """Senet iskontosu. kind='dis': N*r*t/(100*basis); kind='ic': N*r*t/(100*basis + r*t)."""
    nominal, rate, days = _positive(nominal, "Nominal"), _positive(annual_rate, "Oran"), D(days)
    if kind == "dis":
        amount = nominal * rate * days / (HUNDRED * D(basis))
    else:
        amount = nominal * rate * days / (HUNDRED * D(basis) + rate * days)
    amount = money(amount)
    return {"iskonto": amount, "net_deger": money(nominal) - amount, "tur": kind}


# --- Amortisman ----------------------------------------------------------------

def depreciation_schedule(cost, useful_life_years, method="normal", first_year_months=12):
    """VUK amortisman planı.

    normal: oran = 100 / faydalı ömür. azalan: oran = 2 x normal oran (en çok %50),
    net kalan değer üzerinden; son yılda kalan tutarın tamamı yok yazılır.
    first_year_months < 12 ise ilk yıl kıst (ay) oranıyla hesaplanır ve plan bir yıl uzar.
    """
    cost = money(_positive(cost, "Maliyet bedeli"))
    years = int(useful_life_years)
    months = int(first_year_months)
    if years < 1 or not 1 <= months <= 12:
        raise CalculationError("Faydalı ömür en az 1 yıl, kıst ay sayısı 1-12 olmalı")
    if method not in ("normal", "azalan"):
        raise CalculationError("Yöntem 'normal' veya 'azalan' olmalı")
    normal_rate = HUNDRED / Decimal(years)
    rate = normal_rate if method == "normal" else min(normal_rate * 2, Decimal(50))
    last_year = years if months == 12 else years + 1
    rows, remaining = [], cost
    for year in range(1, last_year + 1):
        factor = Decimal(months) / Decimal(12) if year == 1 else Decimal(1)
        if method == "normal":
            amount = money(cost * rate / HUNDRED * factor)
        else:
            amount = money(remaining * rate / HUNDRED * factor)
        if year == last_year or amount > remaining:
            amount = remaining
        remaining -= amount
        rows.append({
            "yil": year, "oran": rate, "amortisman": amount,
            "birikmis": cost - remaining, "net_deger": remaining,
        })
        if remaining == 0:
            break
    return rows


# --- Kredi / yatırım -----------------------------------------------------------

def loan_schedule(principal, monthly_rate, installments, kind="esit_taksit"):
    principal = money(_positive(principal, "Anapara"))
    n = int(installments)
    r = D(monthly_rate) / HUNDRED
    if n < 1:
        raise CalculationError("Taksit sayısı en az 1 olmalı")
    balance, rows = principal, []
    if kind == "esit_taksit":
        payment = money(principal / n) if r == 0 else money(principal * r / (1 - (1 + r) ** (-n)))
    for i in range(1, n + 1):
        interest = money(balance * r)
        if kind == "esit_anapara":
            capital = money(principal / n)
        else:
            capital = payment - interest
        if i == n:
            capital = balance
        installment = capital + interest
        balance -= capital
        rows.append({"taksit_no": i, "taksit": installment, "anapara": capital, "faiz": interest, "kalan": balance})
    return rows


def npv(rate_percent, cashflows):
    r = D(rate_percent) / HUNDRED
    return sum((D(cf) / (1 + r) ** i for i, cf in enumerate(cashflows)), ZERO)


def irr(cashflows, low=Decimal("-0.99"), high=Decimal("10"), tolerance=Decimal("1e-12")):
    flows = [D(cf) for cf in cashflows]
    if not (any(cf < 0 for cf in flows) and any(cf > 0 for cf in flows)):
        raise CalculationError("IRR için hem giriş hem çıkış nakit akışı gerekir")

    def value(rate):
        return sum((cf / (1 + rate) ** i for i, cf in enumerate(flows)), ZERO)

    f_low, f_high = value(low), value(high)
    if f_low * f_high > 0:
        raise CalculationError("IRR bu aralıkta bulunamadı")
    for _ in range(300):
        mid = (low + high) / 2
        f_mid = value(mid)
        if abs(f_mid) < tolerance:
            break
        if f_low * f_mid < 0:
            high = mid
        else:
            low, f_low = mid, f_mid
    return (mid * HUNDRED).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def break_even(fixed_cost, unit_price, unit_variable_cost):
    margin = D(unit_price) - D(unit_variable_cost)
    if margin <= 0:
        raise CalculationError("Birim fiyat değişken maliyetten büyük olmalı")
    units = (D(fixed_cost) / margin).to_integral_value(rounding="ROUND_CEILING")
    return {"adet": units, "ciro": money(units * D(unit_price)), "birim_katki": money(margin)}


def percent_of(amount, percent):
    return money(D(amount) * D(percent) / HUNDRED)


def percent_change(old, new):
    old = D(old)
    if old == 0:
        raise CalculationError("Eski değer sıfır olamaz")
    return ((D(new) - old) / old * HUNDRED).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# --- Doğal dil yönlendirici ------------------------------------------------------

_RATE = re.compile(r"(?:%\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*%|yuzde\s*(\d+(?:[.,]\d+)?))")
_FRACTION = re.compile(r"(?<![\d.,/])(\d{1,2})\s*/\s*(\d{1,2})(?![\d/])")
_YEARS = re.compile(r"(?<![\d.,])(\d{1,2})\s*(?:yil|yillik|sene)")
_MONTHS = re.compile(r"(?<![\d.,])(\d{1,3})\s*(?:ay|aya|aylik)\b")
_DAYS = re.compile(r"(?<![\d.,])(\d{1,4})\s*(?:gun|gunluk)\b")
_INSTALLMENTS = re.compile(r"(?<![\d.,])(\d{1,3})\s*(?:taksit|taksitle|taksitli)\b")
_CALENDAR_YEAR = re.compile(r"(?<![\d.,])(?:19|20)\d{2}(?![\d.,])\s*['’]?\s*(?:yil\w*|da\b|de\b|ta\b|te\b|den\b|dan\b)")
_PER_MILLE = re.compile(r"binde\s*(\d+(?:[.,]\d+)?)")
_AMOUNT = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?|\d+\.\d{1,2})(?![\d])")
_RATE_TEXT = r"(?:%\s*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s*%|yuzde\s*\d+(?:[.,]\d+)?)"
_PERIOD_BEFORE = re.compile(r"(aylik|yillik|gunluk)\s*(?:faiz\w*|oran\w*)?\s*" + _RATE_TEXT)
_PERIOD_AFTER = re.compile(_RATE_TEXT + r"\s*(?:faiz\w*\s*)?(aylik|yillik|gunluk)")


def _rate_period(folded):
    """Oranın dönemi: 'aylik' | 'yillik' | 'gunluk' | None (belirtilmemiş)."""
    match = _PERIOD_BEFORE.search(folded) or _PERIOD_AFTER.search(folded)
    return match.group(1) if match else None


def _extract(text):
    """Soru metninden oran, kesir, süre ve tutarları ayrıştırır."""
    folded = fold_tr(text)
    period = _rate_period(folded)
    rates = [D((a or b or c).replace(",", ".")) for a, b, c in _RATE.findall(folded)]
    working = _CALENDAR_YEAR.sub(" ", _RATE.sub(" ", folded))  # '2026 yılı' bir tutar değildir
    fraction = _FRACTION.search(working)
    working = _FRACTION.sub(" ", working)
    per_mille = _PER_MILLE.search(working)
    working = _PER_MILLE.sub(" ", working)
    installments = _INSTALLMENTS.search(working)
    working = _INSTALLMENTS.sub(" ", working)
    years = _YEARS.search(working)
    working = _YEARS.sub(" ", working)
    months = _MONTHS.search(working)
    working = _MONTHS.sub(" ", working)
    days = _DAYS.search(working)
    working = _DAYS.sub(" ", working)
    amounts = []
    for match in _AMOUNT.finditer(working):
        try:
            amounts.append(parse_tr_number(match.group(1)))
        except ValueError:
            continue
    return {
        "folded": folded, "rates": rates, "amounts": amounts, "rate_period": period,
        "fraction": (int(fraction.group(1)), int(fraction.group(2))) if fraction else None,
        "per_mille": D(per_mille.group(1).replace(",", ".")) if per_mille else None,
        "years": int(years.group(1)) if years else None,
        "months": int(months.group(1)) if months else None,
        "days": int(days.group(1)) if days else None,
        "installments": int(installments.group(1)) if installments else None,
    }


def _table(rows, headers, keys):
    lines = ["  ".join(headers)]
    for row in rows:
        cells = []
        for key in keys:
            value = row[key]
            cells.append(format_number_tr(value) if isinstance(value, Decimal) else str(value))
        lines.append("  ".join(cells))
    return "\n".join(lines)


def _net_given(folded):
    """Soruda NET tutar mı verilmiş ('net 10.400 TL', 'netten') yoksa net mi soruluyor ('net kaç')?"""
    return "netten" in folded or bool(re.search(r"\bnet\w*\s*(?:tutar\w*|tahsilat\w*|ucret\w*)?\s*\d", folded)) or "eline gecen" in folded


_ORAN_ADLARI = {
    "donen_varlik": "dönen varlıklar", "kvyk": "kısa vadeli yabancı kaynaklar", "stok": "stoklar",
    "hazir_deger": "hazır değerler", "toplam_borc": "toplam borç (yabancı kaynak)", "toplam_varlik": "toplam varlık",
    "ozkaynak": "özkaynak", "net_kar": "net kâr", "net_satis": "net satışlar", "smm": "satılan malın maliyeti",
}
_PERIOD_TR = {"aylik": "aylık", "yillik": "yıllık", "gunluk": "günlük"}


class CalculatorRouter:
    """Doğal dildeki hesap isteğini ilgili kesin hesaplayıcıya yönlendirir."""

    def answer(self, question):
        info = _extract(question)
        folded = info["folded"]
        try:
            if "tevkifat" in folded and info["fraction"] and info["amounts"]:
                return self._tevkifat(info)
            if "amortisman" in folded and info["years"] and info["amounts"]:
                return self._amortisman(info)
            if "makbuz" in folded and info["amounts"] and "kdv" in folded and "stopaj" in folded:
                return self._makbuz(info)
            if "stopaj" in folded and info["amounts"]:
                return self._stopaj(info)
            if "damga" in folded and info["amounts"] and info["per_mille"] is not None:
                tax = damga_vergisi(info["amounts"][0], info["per_mille"])
                return (f"SONUÇ: Damga vergisi {format_tl(tax)}\n"
                        f"HESAP: {format_tl(info['amounts'][0])} x binde {info['per_mille']} = {format_tl(tax)}")
            if "iban" in folded:
                match = re.search(r"tr\s*\d{2}(?:\s*\d){22}", folded)
                if not match:
                    return "Kaizen: IBAN'ı 'TR' ile başlayan 26 karakter olarak yazın."
                return self._iban(match.group(0))
            oran = self._finansal_oran(info)
            if oran:
                return oran
            if "gecikme zammi" in folded and info["amounts"]:
                return self._gecikme(info)
            if self._is_trade_discount(info):
                return self._trade_discount(info)
            if "iskonto" in folded and info["amounts"]:
                return self._iskonto(info)
            if any(w in folded for w in ("kredi", "taksit", "anuite")) and info["amounts"] and (
                info["installments"] or info["months"]
            ):
                if not info["rates"]:
                    return "Kaizen: Kredi faiz oranını belirtmediniz (ör. 'aylık %2'). Oranı uydurmadan taksit hesaplayamam."
                return self._kredi(info)
            if "faiz" in folded and info["amounts"] and info["rates"]:
                return self._faiz(info)
            if ("basabas" in folded or "kar zarar noktasi" in folded) and info["amounts"]:
                return self._basabas(info)
            if any(w in folded for w in ("npv", "net bugunku", "irr", "ic verim")):
                return self._nakit_akisi(question, info)
            if len(info["amounts"]) >= 2 and any(
                w in folded for w in ("degisim", "artis orani", "yuzde kac art", "yuzde kac azal", "yuzde kac deg")
            ):
                old, new = info["amounts"][0], info["amounts"][1]
                change = percent_change(old, new)
                return (f"SONUÇ: %{format_number_tr(change)} ({'artış' if change >= 0 else 'azalış'})\n"
                        f"HESAP: ({format_tl(new)} - {format_tl(old)}) / {format_tl(old)} x 100")
            if "kdv" in folded and info["amounts"] and any(
                word in folded for word in ("hesapla", "dahil", "haric", "tutari", "kac", "ne kadar", "ekle")
            ):
                return self._kdv(info)
            if any(w in folded for w in ("yuzde", "%")) and info["amounts"] and info["rates"] and (
                "ekle" in folded or "artir" in folded or "indir" in folded or "yuzdesi" in folded
                or re.search(r"(?:nin|nun|in|un|'i)\s*(?:%|yuzde)", folded)
            ):
                return self._percent(info)
            natural = natural_math_answer(question, info["amounts"])
            if natural:
                return natural
        except CalculationError as exc:
            return f"Kaizen: Hesaplama yapılamadı: {exc}"
        return None

    @staticmethod
    def _is_trade_discount(info):
        """'Yüzde 15 iskonto uyguladığım 2000 TL'lik ürün': vadesiz, oranı verilmiş, senet/
        bono/vade kavramı olmayan iskonto bir TİCARİ İNDİRİMDİR (tutar - yüzde). Vadeli/senetli
        iskonto (iç/dış iskonto) eski hesaplayıcıda kalır -- KÖK NEDEN: eskiden 'iskonto'
        kelimesi her durumda vade/faiz hesaplayıcısına yönlendiriliyordu."""
        folded = info["folded"]
        if "iskonto" not in folded or not info["amounts"] or not info["rates"]:
            return False
        if info["days"] or info["months"] or info["years"] or info["rate_period"]:
            return False
        return not any(w in folded for w in (
            "senet", "vade", "nominal", "bono", "police", "cek", "dis iskonto", "ic iskonto",
            "ticari iskonto", "banka",
        ))

    @staticmethod
    def _trade_discount(info):
        amount, rate = info["amounts"][0], info["rates"][0]
        part = percent_of(amount, rate)
        folded = info["folded"]
        if any(w in folded for w in ("iskonto tutari", "indirim tutari", "ne kadar iskonto", "kac tl iskonto", "kac tl indirim")):
            return f"SONUÇ: {format_tl(part)}\nHESAP: {format_tl(amount)} x %{rate} / 100"
        return (f"SONUÇ: {format_tl(amount - part)}\n"
                f"HESAP: {format_tl(amount)} - %{rate} = {format_tl(amount)} - {format_tl(part)}")

    @staticmethod
    def _iban(text):
        result = iban_coz(text)
        durum = "GEÇERLİ (kontrol basamakları doğru)" if result["gecerli"] else "GEÇERSİZ (kontrol basamakları tutmuyor)"
        return (f"SONUÇ: {result['iban']} — {durum}\n"
                f"HESAP: kontrol {result['kontrol']}, banka kodu {result['banka_kodu']}, rezerv {result['rezerv']}, "
                f"hesap no {result['hesap_no']}. Banka adını IBAN'dan uydurmam; kodu bankanın resmî listesinden kontrol edin.")

    @staticmethod
    def _rate_after(folded, word):
        match = re.search(word + r"\D{0,14}?" + _RATE_TEXT, folded)
        if not match:
            return None
        return D(re.search(r"\d+(?:[.,]\d+)?", match.group(0)[len(word):]).group(0).replace(",", "."))

    def _makbuz(self, info):
        folded = info["folded"]
        kdv_rate, stopaj_rate = self._rate_after(folded, "kdv"), self._rate_after(folded, "stopaj")
        if kdv_rate is None or stopaj_rate is None:
            return "Kaizen: Makbuz için KDV ve stopaj oranlarını ayrı ayrı yazın."
        amount = info["amounts"][0]
        from_net = _net_given(folded)
        r = serbest_meslek_makbuzu_netten(amount, kdv_rate, stopaj_rate) if from_net else serbest_meslek_makbuzu(amount, kdv_rate, stopaj_rate)
        return (f"SONUÇ: Brüt ücret {format_tl(r['brut'])}; KDV {format_tl(r['kdv'])}; stopaj {format_tl(r['stopaj'])}; "
                f"net tahsilat {format_tl(r['net_tahsilat'])}\n"
                f"HESAP: net = brüt + KDV(%{format_number_tr(kdv_rate, 2)}) - stopaj(%{format_number_tr(stopaj_rate, 2)})"
                + (" (net tutardan brüte geri gidildi)" if from_net else ""))

    _ORAN_TERIMLERI = (
        # (ad, tetikleyici, gerekli alanlar ve soruda geçen etiketleri, başlık, yüzde mi)
        ("cari_oran", ("cari oran",), {"donen_varlik": ("donen varlik",), "kvyk": ("kisa vadeli yabanci kaynak", "kisa vadeli borc", "kvyk")}, "Cari oran", False),
        ("asit_test", ("asit test", "likidite oran", "asit-test"), {"donen_varlik": ("donen varlik",), "stok": ("stok",), "kvyk": ("kisa vadeli yabanci kaynak", "kisa vadeli borc", "kvyk")}, "Asit-test oranı", False),
        ("nakit_oran", ("nakit oran",), {"hazir_deger": ("hazir deger", "nakit"), "kvyk": ("kisa vadeli yabanci kaynak", "kisa vadeli borc", "kvyk")}, "Nakit oranı", False),
        ("kaldirac", ("kaldirac", "borclanma oran"), {"toplam_borc": ("toplam borc", "toplam yabanci kaynak", "yabanci kaynak"), "toplam_varlik": ("toplam varlik", "toplam aktif", "aktif toplam")}, "Kaldıraç oranı", False),
        ("borc_ozkaynak", ("borc ozkaynak", "borc/ozkaynak"), {"toplam_borc": ("toplam borc", "toplam yabanci kaynak", "yabanci kaynak"), "ozkaynak": ("ozkaynak", "oz sermaye")}, "Borç / özkaynak oranı", False),
        ("roe", ("roe", "ozkaynak karlilik"), {"net_kar": ("net kar", "donem net kari"), "ozkaynak": ("ozkaynak", "oz sermaye")}, "Özkaynak karlılığı (ROE)", True),
        ("roa", ("roa", "aktif karlilik"), {"net_kar": ("net kar", "donem net kari"), "toplam_varlik": ("toplam varlik", "toplam aktif", "aktif toplam")}, "Aktif karlılığı (ROA)", True),
        ("net_kar_marji", ("net kar marji",), {"net_kar": ("net kar", "donem net kari"), "net_satis": ("net satis", "satis")}, "Net kâr marjı", True),
        ("brut_kar_marji", ("brut kar marji",), {"net_satis": ("net satis", "satis"), "smm": ("satilan mal maliyet", "smm")}, "Brüt kâr marjı", True),
    )

    def _finansal_oran(self, info):
        folded = info["folded"]
        for ad, triggers, fields, title, is_percent in self._ORAN_TERIMLERI:
            if not any(t in folded for t in triggers):
                continue
            values, missing = {}, []
            for key, labels in fields.items():
                found = None
                for label in sorted(labels, key=len, reverse=True):
                    match = re.search(re.escape(label) + r"\w*\D{0,12}?(\d[\d.,]*)", folded)
                    if match:
                        found = parse_tr_number(match.group(1).rstrip(".,"))
                        break
                if found is None:
                    missing.append(key)
                values[key] = found
            if missing:
                if not info["amounts"]:
                    return None  # kavramsal soru ('cari oran nedir'): hafızadan cevaplanır
                names = [_ORAN_ADLARI[m] for m in missing]
                return f"Kaizen: {title} için şu değerleri de yazın: " + ", ".join(names) + "."
            value = finansal_oran(ad, **values)
            shown = f"%{format_number_tr(value, 2)}" if is_percent else format_number_tr(value, 2)
            used = ", ".join(f"{_ORAN_ADLARI.get(k, k)} = {format_number_tr(v)}" for k, v in values.items())
            return f"SONUÇ: {title} = {shown}\nHESAP: {used}"
        return None

    # --- faiz, gecikme, iskonto, kredi ---------------------------------------------------
    @staticmethod
    def _need_period():
        return ("Kaizen: Faiz oranının aylık mı yıllık mı olduğunu belirtmediniz (ör. 'aylık %2' ya da 'yıllık %24'). "
                "Dönemi tahmin ederek hesaplamayacağım.")

    @staticmethod
    def _term_in(period, info):
        """Süreyi oranın dönemine çevirir; (değer, açıklama) döner. Çevrilemezse None."""
        months, days, years = info["months"], info["days"], info["years"]
        if period == "aylik":
            total = D(0)
            if months: total += months
            if days: total += D(days) / 30
            if years: total += years * 12
            return total, "ay (1 ay = 30 gün)" if days else "ay"
        if period == "yillik":
            total = D(0)
            if years: total += years
            if months: total += D(months) / 12
            if days: total += D(days) / 365
            return total, "yıl (gün için 365 esas)" if days else "yıl"
        if period == "gunluk":
            total = D(0)
            if days: total += days
            if months: total += months * 30
            if years: total += years * 365
            return total, "gün"
        return None, ""

    def _faiz(self, info):
        period = info["rate_period"]
        if not period:
            return self._need_period()
        term, unit = self._term_in(period, info)
        if not term:
            return "Kaizen: Faiz süresini belirtmediniz (ör. '3 ay', '90 gün', '2 yıl')."
        principal, rate = info["amounts"][0], info["rates"][0]
        interest = money(_positive(principal, "Anapara") * rate * term / HUNDRED)
        term_text = format_number_tr(term, 0 if term == term.to_integral_value() else 4)
        return (f"SONUÇ: Basit faiz {format_tl(interest)}; anapara + faiz = {format_tl(money(principal) + interest)}\n"
                f"HESAP: {format_tl(principal)} x %{format_number_tr(rate, 2)} ({_PERIOD_TR[period]}) x {term_text} {unit} / 100")

    def _gecikme(self, info):
        if not info["rates"]:
            return "Kaizen: Gecikme zammı oranını belirtmediniz; güncel oran değişebileceği için tahmin etmem."
        rate, amount = info["rates"][0], info["amounts"][0]
        note = ""
        months = info["months"]
        if not months and info["days"]:
            months = -(-info["days"] // 30)
            note = f"\nNOT: {info['days']} gün, 30 güne bölünüp yukarı yuvarlanarak {months} ay alındı (varsayım; güncel uygulamayı kontrol edin)."
        if not months:
            return "Kaizen: Gecikme süresini belirtmediniz (ay ya da gün)."
        result = gecikme_zammi(amount, rate, months)
        return (f"SONUÇ: Gecikme zammı {format_tl(result['gecikme_zammi'])}; toplam ödenecek {format_tl(result['toplam'])}\n"
                f"HESAP: {format_tl(amount)} x %{format_number_tr(rate, 2)} (aylık) x {months} ay / 100{note}")

    def _iskonto(self, info):
        if not info["rates"]:
            return "Kaizen: İskonto oranını belirtmediniz (yıllık %). Oranı uydurmadan hesaplayamam."
        days = info["days"] or ((info["months"] or 0) * 30) or ((info["years"] or 0) * 365)
        if not days:
            return "Kaizen: Vade süresini belirtmediniz (gün ya da ay)."
        kind = "dis" if "dis iskonto" in info["folded"] or "ticari iskonto" in info["folded"] else "ic"
        nominal, rate = info["amounts"][0], info["rates"][0]
        result = iskonto(nominal, rate, days, kind=kind)
        name = "Dış (ticari)" if kind == "dis" else "İç (matematiksel)"
        return (f"SONUÇ: {name} iskonto {format_tl(result['iskonto'])}; net değer {format_tl(result['net_deger'])}\n"
                f"HESAP: nominal {format_tl(nominal)}, yıllık %{format_number_tr(rate, 2)}, {days} gün (yıl = 365 gün)")

    def _kredi(self, info):
        period = info["rate_period"]
        if period not in ("aylik", "yillik"):
            return self._need_period()
        n = info["installments"] or info["months"]
        rate = info["rates"][0]
        monthly = rate if period == "aylik" else rate / 12
        kind = "esit_anapara" if "esit anapara" in info["folded"] else "esit_taksit"
        rows = loan_schedule(info["amounts"][0], monthly, n, kind)
        shown = rows if len(rows) <= 24 else rows[:12] + [None] + rows[-3:]
        lines = ["No  Taksit  Anapara  Faiz  Kalan"]
        for row in shown:
            if row is None:
                lines.append("...")
                continue
            lines.append(f"{row['taksit_no']}  {format_number_tr(row['taksit'])}  {format_number_tr(row['anapara'])}  "
                         f"{format_number_tr(row['faiz'])}  {format_number_tr(row['kalan'])}")
        total_interest = sum((r["faiz"] for r in rows), ZERO)
        note = "" if period == "aylik" else f"\nNOT: Yıllık oran 12'ye bölünerek aylık %{format_number_tr(monthly, 4)} alındı (bileşik yıllık maliyet farklıdır)."
        name = "Eşit anapara" if kind == "esit_anapara" else "Eşit taksit"
        return (f"SONUÇ: {name}li kredi, {n} ay; ilk taksit {format_tl(rows[0]['taksit'])}; toplam faiz {format_tl(total_interest)}\n"
                + "\n".join(lines) + note)

    @staticmethod
    def _basabas(info):
        folded = info["folded"]

        def find(pattern):
            match = re.search(r"(?:" + pattern + r")\D{0,25}?(\d[\d.,]*)", folded)
            return parse_tr_number(match.group(1).rstrip(".,")) if match else None

        fixed = find(r"sabit\s*(?:gider|maliyet)\w*")
        price = find(r"birim\s*(?:satis\s*)?fiyat\w*|satis\s*fiyat\w*")
        variable = find(r"degisken\s*(?:gider|maliyet)\w*|birim\s*degisken\w*|birim\s*maliyet\w*")
        if None in (fixed, price, variable):
            return ("Kaizen: Başabaş için üç değer gerekir: sabit gider, birim satış fiyatı ve birim değişken maliyet "
                    "(ör. 'sabit gider 100.000 TL, birim fiyat 50 TL, birim değişken maliyet 30 TL').")
        result = break_even(fixed, price, variable)
        return (f"SONUÇ: Başabaş noktası {format_number_tr(result['adet'], 0)} adet; ciro {format_tl(result['ciro'])}\n"
                f"HESAP: sabit gider / (birim fiyat - birim değişken maliyet) = {format_tl(fixed)} / {format_tl(result['birim_katki'])}")

    @staticmethod
    def _nakit_akisi(question, info):
        rate_match = _RATE.search(info["folded"])
        text = _RATE.sub(" ", question.replace("−", "-"))
        flows = [parse_tr_number(m) for m in re.findall(r"-?\d[\d.,]*", text)]
        if "irr" in info["folded"] or "ic verim" in info["folded"]:
            if len(flows) < 2:
                return "Kaizen: İç verim oranı için nakit akışlarını yazın (ör. IRR -100000, 30000, 40000, 50000)."
            return f"SONUÇ: İç verim oranı (IRR) %{format_number_tr(irr(flows), 2)}\nHESAP: NBD = 0 yapan oran (nakit akışları: {', '.join(format_number_tr(f) for f in flows)})"
        if not rate_match:
            return "Kaizen: İskonto oranını belirtmediniz (ör. %10)."
        if len(flows) < 2:
            return "Kaizen: Nakit akışlarını yazın (ör. NPV %10 -100000, 30000, 40000, 50000)."
        value = npv(D(next(g for g in rate_match.groups() if g).replace(",", ".")), flows)
        return f"SONUÇ: Net bugünkü değer (NBD) {format_tl(value)}\nHESAP: ilk akış t=0 kabul edilerek iskonto edildi"

    @staticmethod
    def _kdv(info):
        if not info["rates"]:
            return "Kaizen: KDV oranını belirtmediniz. Oranı uydurmadan hesaplayamam."
        rate, amount = info["rates"][0], info["amounts"][0]
        included = "dahil" in info["folded"] and "haric" not in info["folded"]
        result = kdv(amount, rate, included=included)
        kind = "KDV dahil" if included else "KDV hariç"
        return (
            f"SONUÇ: Matrah {format_tl(result['matrah'])}, KDV (%{format_number_tr(rate, 0 if rate == rate.to_integral_value() else 2)}) "
            f"{format_tl(result['kdv'])}, KDV dahil toplam {format_tl(result['toplam'])}\n"
            f"HESAP: {format_tl(amount)} ({kind}); "
            + ("matrah = tutar / (1 + oran); KDV = tutar - matrah" if included
               else "KDV = matrah x oran; toplam = matrah + KDV")
        )

    @staticmethod
    def _tevkifat(info):
        if not info["rates"]:
            return "Kaizen: KDV oranını belirtmediniz."
        num, den = info["fraction"]
        result = kdv_tevkifat(info["amounts"][0], info["rates"][0], num, den)
        return (
            f"SONUÇ: Hesaplanan KDV {format_tl(result['hesaplanan_kdv'])}; tevkif edilen KDV ({num}/{den}) "
            f"{format_tl(result['tevkifat_kdv'])}; satıcıya ödenecek KDV {format_tl(result['satici_kdv'])}; "
            f"satıcıya toplam ödeme {format_tl(result['satici_tahsilat'])}\n"
            f"HESAP: KDV = matrah x oran; tevkifat = KDV x {num}/{den}"
        )

    @staticmethod
    def _stopaj(info):
        if not info["rates"]:
            return "Kaizen: Stopaj oranını belirtmediniz. Oranı uydurmadan hesaplayamam."
        net = _net_given(info["folded"])
        result = stopaj(info["amounts"][0], info["rates"][0], amount_is_net=net)
        return (f"SONUÇ: Brüt {format_tl(result['brut'])}, stopaj {format_tl(result['stopaj'])}, "
                f"net {format_tl(result['net'])}\nHESAP: stopaj = brüt x oran")

    @staticmethod
    def _amortisman(info):
        method = "azalan" if "azalan" in info["folded"] else "normal"
        rows = depreciation_schedule(info["amounts"][0], info["years"], method)
        table = _table(rows, ("Yıl", "Oran%", "Amortisman", "Birikmiş", "Net değer"),
                       ("yil", "oran", "amortisman", "birikmis", "net_deger"))
        name = "Azalan bakiyeler" if method == "azalan" else "Normal"
        return (f"SONUÇ: {name} amortisman planı ({format_tl(info['amounts'][0])}, {info['years']} yıl)\n{table}\n"
                "DAYANAK: VUK md. 313-321 amortisman usulleri (oranlar faydalı ömre göre hesaplandı).")

    @staticmethod
    def _percent(info):
        amount, rate = info["amounts"][0], info["rates"][0]
        folded = info["folded"]
        part = percent_of(amount, rate)
        if "ekle" in folded or "artir" in folded:
            return f"SONUÇ: {format_tl(amount + part)}\nHESAP: {format_tl(amount)} + %{rate} = {format_tl(amount)} + {format_tl(part)}"
        if "indir" in folded:
            return f"SONUÇ: {format_tl(amount - part)}\nHESAP: {format_tl(amount)} - %{rate} = {format_tl(amount)} - {format_tl(part)}"
        return f"SONUÇ: {format_tl(part)}\nHESAP: {format_tl(amount)} x %{rate} / 100"
