import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from accounting.source_registry import trusted_source_for_url

_LEADING_NUMBER = re.compile(r"(\d[\d.,\s]*\d|\d)")


@dataclass(frozen=True)
class FactCandidate:
    topic: str
    value: str
    effective_year: int
    source_url: str
    evidence: str


@dataclass(frozen=True)
class ConsensusResult:
    status: str
    value: str | None
    effective_year: int | None
    sources: tuple[str, ...]


class AccountingConsensus:
    @staticmethod
    def _normalize_value(value):
        """"12.000 TL" ile "12.000,00 TL" aynı değer olarak görülsün diye önce birim/etiket
        (TL, %, binde ...) sayıdan ayrılır, sayı Decimal olarak normalize edilir, etiket ayrı
        tutulur. Eskiden birim sayının hemen ardına yapışık kalınca ("12000.00 tl") Decimal
        ayrıştırması başarısız oluyor ve biçimi farklı iki aynı değer yanlışlıkla "çelişkili"
        sayılıyordu.
        """
        cleaned = value.strip().casefold().replace("%", "").strip()
        match = _LEADING_NUMBER.search(cleaned)
        if not match:
            return " ".join(cleaned.split())
        prefix = cleaned[:match.start()].strip()
        suffix = cleaned[match.end():].strip()
        number = match.group(1).strip()
        if "," not in number and number.count(".") == 1 and len(number.rsplit(".", 1)[1]) == 3:
            number = number.replace(".", "")
        else:
            number = number.replace(" ", "").replace(".", "").replace(",", ".")
        try:
            number = str(Decimal(number).normalize())
        except InvalidOperation:
            number = " ".join(number.split())
        label = " ".join(part for part in (prefix, suffix) if part)
        return f"{number} {label}".strip()

    def decide(self, candidates):
        valid = []
        for candidate in candidates:
            source = trusted_source_for_url(candidate.source_url)
            if source and candidate.evidence.strip():
                valid.append((candidate, source))
        if not valid:
            return ConsensusResult("unverified", None, None, ())

        newest_year = max(candidate.effective_year for candidate, _ in valid)
        newest = [(candidate, source) for candidate, source in valid
                  if candidate.effective_year == newest_year]
        groups = {}
        for candidate, source in newest:
            key = self._normalize_value(candidate.value)
            group = groups.setdefault(key, {"value": candidate.value, "sources": {}, "official": False})
            group["sources"][source.name] = candidate.source_url
            group["official"] = group["official"] or source.priority == 1

        accepted = [group for group in groups.values()
                    if group["official"] or len(group["sources"]) >= 2]
        if len(accepted) != 1:
            status = "conflict" if len(groups) > 1 else "pending_confirmation"
            return ConsensusResult(status, None, newest_year, tuple(
                url for group in groups.values() for url in group["sources"].values()
            ))
        group = accepted[0]
        return ConsensusResult(
            "verified",
            group["value"],
            newest_year,
            tuple(group["sources"].values()),
        )
