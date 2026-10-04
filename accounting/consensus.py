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
    status: str  # "verified" | "partially_verified" | "single_source" | "unverified" | "conflict"
    value: str | None
    effective_year: int | None
    sources: tuple[str, ...]
    source_count: int = 0  # Number of independent sources supporting the consensus value


class AccountingConsensus:
    @staticmethod
    def _normalize_value(value):
        """"12.000 TL" ile "12.000,00 TL" aynı değer olarak görülsün diye önce birim/etiket
        (TL, %, binde ...) sayıdan ayrılır, sayı Decimal olarak normalize edilir, etiket ayrı
        tutulur (etiket "%"/"binde" varlığını da korur -- "20" ile "%20" birbirine karışmasın).
        Eskiden birim sayının hemen ardına yapışık kalınca ("12000.00 tl") Decimal ayrıştırması
        başarısız oluyor ve biçimi farklı iki aynı değer yanlışlıkla "çelişkili" sayılıyordu.

        DÜZELTME (2026-09-23): tek "." içeren sayılarda (virgül yok) eskiden HER ZAMAN "." bir
        binlik ayıracı sayılıp siliniyordu -- ama bu yalnızca noktadan sonra TAM 3 hane varsa
        doğrudur ("12.000" -> 12000). Fazla/eksik haneli ("4.5", "4.25") ya da oran/binde
        değerlerinde "." aslında ONDALIK ayıracıdır; eski kod bunu da siliyor, "%4.5" ile "%45"
        aynı değermiş gibi (ikisi de "45") gruplanıyordu -- iki farklı oranı "aynı" sayan ciddi
        bir muhasebe hatası. Oran/binde değerlerinde tek "." HER ZAMAN ondalık kabul edilir;
        parasal tutarlarda yalnızca tam 3 haneli grupsa binlik ayıracı sayılır (eski davranış
        parasal tutarlar için korunur).
        """
        original = value.strip().casefold()
        is_rate = "%" in original or "binde" in original or "‰" in original
        cleaned = original.replace("%", "").strip()
        match = _LEADING_NUMBER.search(cleaned)
        if not match:
            return " ".join(cleaned.split())
        prefix = cleaned[:match.start()].strip()
        suffix = cleaned[match.end():].strip()
        number = match.group(1).strip()
        has_comma = "," in number
        has_dot = "." in number
        if has_comma and has_dot:
            # ikisi birden varsa, hangisi sayıda daha SONRA görülüyorsa ondalık ayıracı odur
            # ("12.500,75" -> virgül ondalık; "12,500.75" -> nokta ondalık, İngilizce biçim)
            if number.rfind(",") > number.rfind("."):
                number = number.replace(".", "").replace(",", ".")
            else:
                number = number.replace(",", "")
        elif has_comma:
            number = number.replace(",", ".")
        elif has_dot and not is_rate and len(number.rsplit(".", 1)[1]) == 3:
            number = number.replace(".", "")
        # aksi halde (oran/binde'de tek nokta, ya da parasal tutarda 3 haneli olmayan tek
        # nokta) "." zaten ondalık ayıracı olarak Decimal tarafından doğru okunur -- dokunma.
        number = number.replace(" ", "")
        try:
            number = str(Decimal(number).normalize())
        except InvalidOperation:
            number = " ".join(number.split())
        label = " ".join(part for part in (prefix, suffix) if part)
        if is_rate and "%" not in label:
            label = f"% {label}".strip()
        return f"{number} {label}".strip()

    def decide(self, candidates):
        valid = []
        for candidate in candidates:
            source = trusted_source_for_url(candidate.source_url)
            if source and candidate.evidence.strip():
                valid.append((candidate, source))
        if not valid:
            return ConsensusResult("unverified", None, None, (), 0)

        # Group by effective year, use newest year
        newest_year = max(candidate.effective_year for candidate, _ in valid)
        newest = [(candidate, source) for candidate, source in valid
                  if candidate.effective_year == newest_year]

        # Group by normalized value, track unique source names (domains)
        groups = {}
        for candidate, source in newest:
            key = self._normalize_value(candidate.value)
            group = groups.setdefault(key, {
                "value": candidate.value,
                "sources": {},  # source_name -> url
                "official": False,
                "domains": set()  # unique domains for independent source counting
            })
            group["sources"][source.name] = candidate.source_url
            group["official"] = group["official"] or source.priority == 1
            # Track unique domains for independent source counting
            domain = source.domains[0] if source.domains else ""
            if domain:
                group["domains"].add(domain)

        # Filter groups that have at least 1 source
        groups_with_sources = {k: v for k, v in groups.items() if v["sources"]}

        if not groups_with_sources:
            return ConsensusResult("unverified", None, None, (), 0)

        # Determine verification level based on independent source count
        best_group = None
        best_source_count = 0
        for group in groups_with_sources.values():
            source_count = len(group["domains"]) if group["domains"] else len(group["sources"])
            # Official source counts as 1 independent source but we still need 2 total for verified
            if group["official"]:
                source_count = max(source_count, 1)
            if source_count > best_source_count:
                best_source_count = source_count
                best_group = group

        if best_group is None:
            return ConsensusResult("unverified", None, newest_year, (), 0)

        source_count = best_source_count
        status = "unverified"
        # 5-SOURCE / 3-MATCH MAJORITY CONSENSUS
        # Need at least 3 independent sources matching for VERIFIED
        if source_count >= 3:
            status = "verified"
        elif source_count >= 2:
            status = "partially_verified"
        elif source_count >= 1:
            status = "single_source"

        # Check for conflicts: multiple different values from trusted sources
        # Conflict exists when there are 2+ distinct values each from at least 1 trusted source
        if len(groups_with_sources) > 1:
            # If the best group has < 3 sources and there are competing values -> conflict
            if best_source_count < 3:
                status = "conflict"
            # If best has 3+ sources but there are other values with 2+ sources -> conflict
            elif any((len(g["domains"]) if g["domains"] else len(g["sources"])) >= 2
                    for k, g in groups_with_sources.items() if g != best_group):
                status = "conflict"

        if status == "conflict":
            # For conflict, return ALL sources from all conflicting groups
            all_sources = tuple(url for group in groups_with_sources.values() for url in group["sources"].values())
            return ConsensusResult(
                "conflict", None, newest_year, all_sources, best_source_count
            )

        return ConsensusResult(
            status,
            best_group["value"],
            newest_year,
            tuple(best_group["sources"].values()),
            source_count
        )
