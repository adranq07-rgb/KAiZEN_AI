"""Tek Düzen Hesap Planı: hesap kodlarını ezbere bilen, arama yapabilen katman.

Veri config/tdhp.json içindedir. Kod, hesap adı ve normal bakiye yönü LLM'e
sorulmaz; doğrudan bu tablodan okunur (kuruşu kuruşuna doğru cevap ilkesi).
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path

from core.text_tr import fold_tr, stem_tr, title_tr, tokens_tr

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "tdhp.json"

_STOP = {
    "hesap", "hesabi", "hesaplari", "kodu", "kod", "kac", "kaci", "nedir", "hangi",
    "numarasi", "numarali", "no", "nosu", "ne", "demek", "ve", "veya", "ile", "icin",
    "bir", "bu", "olan", "hs", "tdhp", "tek", "duzen", "plani", "plandaki", "ait",
    "nin", "nun", "in", "un", "de", "da", "mi", "mu", "kayit", "kaydi", "hangisi",
    "numara", "numaradir", "grup", "grupta", "grubu", "grubunda", "nelerdir", "neler", "nerede",
}
_TRIGGERS = ("hesap", "hesab", "kodu", "kodlari", "nedir", "ne demek", "numara", "hs.", "tdhp")

# DÜZELTME (2026-09-23, iş emri "RAG v2 - Faz 1" madde 11 -- kanıt: KAIZEN_HEDEF_VE_YOL_HARITASI.md
# bölüm 4p, Bug C2/C3): iki hesap kodunu KARŞILAŞTIRAN doğal bir soru ("760 ile 770 arasındaki
# fark ne?", "153 ile 150 hesap arasındaki fark nedir?") iki AYRI şekilde bozuluyordu --
# (C2) `_TRIGGERS`'ta hiçbiri geçmeyebiliyordu (soru hiç denenmiyordu) ve (C3) trigger gate'i
# geçse bile aşağıdaki kod-regex'i yalnız İLK kodu yakalayıp (`re.search`), ikinci kodu ve asıl
# "fark ne" sorusunu sessizce yok sayıp yine de 'SONUÇ:' (VERIFIED) etiketiyle YARIM bir cevap
# veriyordu. Bu iki dar sabit, yalnız İKİ (ya da daha fazla) GEÇERLİ hesap kodu bir KARŞILAŞTIRMA
# kelimesiyle birlikte geçtiğinde `_TRIGGERS` kapısını atlayıp HER İKİ hesabı da açıklamayı
# sağlar -- tek bir hesap kodundan bahseden sıradan sorularda (ör. '191 hesap neden borç
# çalışıyor?') hiçbir şey değişmez, o yol aynen eskisi gibi `_TRIGGERS`'a bağlı kalır.
_COMPARISON_HINTS = ("ile", "fark", "arasinda", "karsilastir", "veya", "ya da")
_CODE_PATTERN = re.compile(
    r"(?<![\d.,])(\d{3})(?:\.\d+)?(?![\d,]|\.\d{3}|\s*(?:tl|lira|yil|ay|gun|%))"
)


@dataclass(frozen=True)
class Account:
    code: str
    name: str
    group: str
    group_name: str
    cls: str
    class_name: str
    statement: str
    normal_balance: str
    contra: bool

    def clean_name(self):
        return self.name.replace("(-)", "").strip()

    def describe(self):
        side = {"borç": "borç", "alacak": "alacak", "karma": "borç veya alacak (dönem sonucuna göre)"}[
            self.normal_balance
        ]
        extra = " Düzenleyici (indirim) hesabıdır; asıl hesabın tersi yönde bakiye verir." if self.contra else ""
        return (
            f"{self.code} {self.clean_name()} — {title_tr(self.class_name)} / {self.group} {title_tr(self.group_name)}; "
            f"{self.statement}; normal bakiyesi {side}.{extra}"
        )


class ChartOfAccounts:
    def __init__(self, path=None):
        data = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
        self.groups = data["groups"]
        self.classes = data["classes"]
        self.accounts = {}
        for row in data["accounts"]:
            self.accounts[row["code"]] = Account(
                code=row["code"], name=row["name"], group=row["group"],
                group_name=row["group_name"], cls=row["class"],
                class_name=row["class_name"], statement=row["statement"],
                normal_balance=row["normal_balance"], contra=row["contra"],
            )
        self._folded = {
            code: {stem_tr(t) for t in tokens_tr(account.clean_name())}
            for code, account in self.accounts.items()
        }

    def __contains__(self, code):
        return self.normalize_code(code) in self.accounts

    def __len__(self):
        return len(self.accounts)

    @staticmethod
    def normalize_code(code):
        """'153.01' ve '153 01' alt hesabı ana hesaba (153) indirger."""
        match = re.match(r"\s*(\d{3})", str(code))
        return match.group(1) if match else str(code).strip()

    def get(self, code):
        return self.accounts.get(self.normalize_code(code))

    def require(self, code):
        account = self.get(code)
        if account is None:
            raise KeyError(f"Tek düzen hesap planında {code} kodlu hesap yok")
        return account

    def group_accounts(self, group_code):
        return [a for a in self.accounts.values() if a.group == str(group_code)]

    def find(self, query, limit=5):
        """Hesap adına göre arar; en özgül (adı en kısa) eşleşmeler önde döner."""
        wanted = [
            stem_tr(t) for t in tokens_tr(query)
            if t not in _STOP and len(t) > 1 and not t.startswith(("hesab", "hesap"))
        ]
        if not wanted:
            return []
        ranked = []
        for code, words in self._folded.items():
            matched = 0
            exact = 0
            for token in wanted:
                if token in words:
                    matched += 1
                    exact += 1
                elif len(token) >= 4 and any(w.startswith(token) or token.startswith(w) and len(w) >= 4 for w in words):
                    matched += 1
            if matched == len(wanted):
                ranked.append((-exact, len(words), code))
        ranked.sort()
        return [self.accounts[code] for _, _, code in ranked[:limit]]

    def answer(self, question):
        """Hesap kodu sorularını doğrudan cevaplar; ilgisiz soruda None döner."""
        folded = fold_tr(question)

        # Çoklu-kod karşılaştırma yolu (bkz. yukarıdaki DÜZELTME notu): _TRIGGERS'tan BAĞIMSIZ,
        # yalnız 2+ GEÇERLİ (self.accounts'ta var olan) hesap kodu bir karşılaştırma kelimesiyle
        # birlikte geçtiğinde devreye girer.
        code_matches = [m.group(1) for m in _CODE_PATTERN.finditer(folded)]
        valid_codes, seen = [], set()
        for code in code_matches:
            if code in self.accounts and code not in seen:
                seen.add(code)
                valid_codes.append(code)
        if len(valid_codes) >= 2 and any(hint in folded for hint in _COMPARISON_HINTS):
            lines = "\n".join(f"- {self.accounts[c].describe()}" for c in valid_codes)
            return (
                f"SONUÇ: Karşılaştırma ({len(valid_codes)} hesap):\n{lines}\n"
                "DAYANAK: Tek Düzen Hesap Planı (Muhasebe Sistemi Uygulama Genel Tebliği)."
            )

        if not any(trigger in folded for trigger in _TRIGGERS):
            return None

        code_match = _CODE_PATTERN.search(folded)
        if code_match:
            account = self.accounts.get(code_match.group(1))
            if account:
                return f"SONUÇ: {account.describe()}\nDAYANAK: Tek Düzen Hesap Planı (Muhasebe Sistemi Uygulama Genel Tebliği)."
            return f"Kaizen: Tek düzen hesap planında {code_match.group(1)} kodlu bir ana hesap bulamadım."
        group_match = re.search(r"(?<![\d.,])(\d{2})\s+(?:nolu|numarali|grubu|hesap grubu)", folded)
        if group_match and group_match.group(1) in self.groups:
            code = group_match.group(1)
            members = ", ".join(f"{a.code} {a.clean_name()}" for a in self.group_accounts(code))
            return f"SONUÇ: {code} {title_tr(self.groups[code])} grubu: {members}."

        found = self.find(question)
        if not found:
            return None
        lines = "\n".join(f"- {a.code} {a.clean_name()} ({a.statement}, normal bakiye: {a.normal_balance})" for a in found)
        if len(found) == 1:
            return f"SONUÇ: {found[0].describe()}\nDAYANAK: Tek Düzen Hesap Planı."
        return f"SONUÇ: Eşleşen hesaplar:\n{lines}\nDAYANAK: Tek Düzen Hesap Planı."
