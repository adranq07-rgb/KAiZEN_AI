import json
import re
import subprocess
from decimal import Decimal
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from config.config_manager import ConfigManager
from core.logger import KaizenLogger
from core.response_cleaner import ResponseCleaner
from accounting.source_registry import trusted_source_for_url


class HermesBridge:
    def __init__(self, log_dir=None):
        self.project_dir = Path(__file__).resolve().parent.parent
        self.config = ConfigManager()
        self.logger = KaizenLogger(log_dir=log_dir)

    def is_ready(self):
        provider = self.config.get(
            "model",
            "provider",
            "not_configured"
        )

        if provider == "not_configured":
            return False

        if not self.config.cloud_allowed():
            return False

        return True

    def _run(self, message, research=False, return_packet=False, trusted_only=True):
        if not self.is_ready():
            self.logger.warning(
                "Hermes cagrisi engellendi: provider hazir degil."
            )
            return (
                "Kaizen: Hermes su anda calistirilamiyor. "
                "AI provider yapilandirmasini kontrol et."
            )

        command = [
            "hermes",
            "chat",
            "-q",
            message,
            "--oneshot",
            "--in",
            str(self.project_dir),
            "--source",
            "tool",
        ]

        if research:
            command.extend(["-t", "web", "--format", "stream-json"])
        else:
            command.append("-Q")

        mode = "RESEARCH" if research else "NORMAL"

        # Normal sohbet: 60 saniye
        # Muhasebe arastirmasi: 180 saniye
        timeout_seconds = 180 if research else 60

        self.logger.info(
            f"Hermes cagrisi baslatildi. "
            f"Mod={mode} | Timeout={timeout_seconds}s"
        )

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )

            if result.returncode != 0:
                self.logger.error(
                    f"Hermes hata kodu: {result.returncode}"
                )

                error_text = result.stderr.strip()

                return (
                    "Kaizen: Hermes hatasi -> "
                    f"{error_text}"
                )

            self.logger.info(
                f"Hermes cagrisi tamamlandi. Mod={mode}"
            )

            if research:
                packet = self._parse_research_packet(result.stdout, trusted_only=trusted_only)
                return packet if return_packet else packet["answer"]

            raw_response = result.stdout.strip()

            clean_response = ResponseCleaner.clean(
                raw_response
            )

            return clean_response

        except subprocess.TimeoutExpired:
            self.logger.error(
                f"Hermes zaman asimina ugradi. "
                f"Mod={mode} | Limit={timeout_seconds}s"
            )

            if research:
                return (
                    "Kaizen: Arastirma 180 saniyelik sure "
                    "sinirini asti. Arastirma durduruldu."
                )

            return (
                "Kaizen: AI cevabi zaman asimina ugradi."
            )

        except FileNotFoundError:
            self.logger.error(
                "Hermes bilgisayarda bulunamadi."
            )
            return "Kaizen: Hermes bilgisayarda bulunamadi."

    @staticmethod
    def _parse_research_packet(output, trusted_only=True):
        answer = None
        opened_sources = {}

        for line in output.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(event, dict):
                continue

            if event.get("type") == "result":
                answer = event.get("text")

            if event.get("type") != "tool_result" or event.get("name") != "web_extract":
                continue

            try:
                extracted = event.get("output", "")
                if isinstance(extracted, str):
                    extracted = json.loads(extracted)
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(extracted, dict) or not isinstance(extracted.get("results"), list):
                continue
            for item in extracted.get("results", []):
                if (isinstance(item, dict) and isinstance(item.get("url"), str)
                        and isinstance(item.get("content"), str)
                        and item["url"] and item["content"] and not item.get("error")):
                    opened_sources[item["url"]] = {
                        "content": item["content"],
                        "title": item.get("title") or "",
                    }

        def rejected(message):
            return {"verified": False, "answer": message, "sources": []}

        if not isinstance(answer, str) or not answer or not opened_sources:
            return rejected("Kaizen: Arastirma kaynagi acilip dogrulanamadi; kesin cevap veremiyorum.")

        cited_sources = {url: item for url, item in opened_sources.items() if url in answer}
        if trusted_only:
            cited_sources = {
                url: item for url, item in cited_sources.items()
                if trusted_source_for_url(url)
            }
        elif len({urlparse(url).hostname for url in cited_sources}) < 2:
            return rejected("Kaizen: Derin arastirmada iki bagimsiz kaynak bulunamadi; kesin cevap veremiyorum.")
        if not cited_sources:
            return rejected("Kaizen: Cevapta guvenilir ve acilmis kaynak baglantisi yok; kesin cevap veremiyorum.")

        evidence_match = re.search(r"(?im)^KANIT:\s*(.+)$", answer)
        if not evidence_match:
            return rejected("Kaizen: Cevapta kaynak metninden kanit yok; kesin cevap veremiyorum.")
        evidence = " ".join(evidence_match.group(1).split())
        evidence_sources = {
            url: item for url, item in cited_sources.items()
            if evidence in " ".join(item["content"].split())
        }
        if len(evidence) < 20 or not evidence_sources:
            return rejected("Kaizen: Kanit cumlesi acilan kaynakta bulunamadi; kesin cevap veremiyorum.")

        def percentages(value):
            # A word-only rate cannot be reliably parsed here; fail closed.
            if re.search(r"\by[üu]zde\b\s*(?!\s|\d)\S", value, re.IGNORECASE):
                return None
            matches = re.findall(
                r"(?:%|\by[üu]zde\b)\s*(\d+(?:[.,]\d+)?)|"
                r"(\d+(?:[.,]\d+)?)\s*%", value, re.IGNORECASE
            )
            return {Decimal((prefix or suffix).replace(",", "."))
                    for prefix, suffix in matches}

        claimed_rates = percentages(answer)
        source_text = "\n".join(item["content"] for item in cited_sources.values())
        source_rates = percentages(source_text)
        if claimed_rates is None or source_rates is None or claimed_rates - source_rates:
            return rejected("Kaizen: Cevaptaki oranlar acilan kaynakta dogrulanamadi; kesin cevap veremiyorum.")

        conclusion_match = re.search(
            r"(?is)^\s*SONUC:\s*(.+?)(?:\n[A-ZÇĞİÖŞÜ_ ]+:|$)", answer
        )
        if not conclusion_match:
            return rejected("Kaizen: Cevapta net sonuc bulunamadi; kesin cevap veremiyorum.")
        conclusion = conclusion_match.group(1).strip()
        stopwords = {"ve", "veya", "ile", "icin", "için", "bu", "bir", "olarak",
                     "oran", "orani", "oranı", "genel", "yuzde", "yüzde",
                     "dir", "dır", "tir", "tır"}
        words = lambda value: {
            word for word in re.findall(r"[a-zçğıöşü]{3,}", value.casefold())
            if word not in stopwords
        }
        conclusion_words = words(conclusion)
        source_words = words(source_text)
        if conclusion_words and len(conclusion_words & source_words) / len(conclusion_words) < 0.6:
            return rejected("Kaizen: Sonuc ile kaynak kaniti yeterince eslesmedi; kesin cevap veremiyorum.")

        published_match = re.search(
            r"(?im)^YAYIN_TARIHI:\s*(\d{4}-\d{2}-\d{2})\s*$", answer
        )
        if not published_match:
            return rejected("Kaizen: Kaynagin yayin tarihi dogrulanamadi; kesin cevap veremiyorum.")
        try:
            published_at = datetime.strptime(published_match.group(1), "%Y-%m-%d").date()
        except ValueError:
            return rejected("Kaizen: Kaynagin yayin tarihi gecersiz; kesin cevap veremiyorum.")
        try:
            earliest = date.today().replace(year=date.today().year - 2)
        except ValueError:
            earliest = date.today().replace(year=date.today().year - 2, day=28)
        current_year = date.today().year
        effective_year = max(
            (year for year in (current_year, current_year - 1)
             if any(str(year) in item["content"] for item in evidence_sources.values())),
            default=None,
        )
        if published_at < earliest and effective_year is None:
            return rejected("Kaizen: Guvenilir kaynak bulundu ancak son iki yil disinda; derin arastirma gerekli.")

        sources = []
        for url, item in evidence_sources.items():
            source = trusted_source_for_url(url)
            sources.append({
                "url": url,
                "content": item["content"],
                "title": item["title"],
                "source_name": source.name if source else (urlparse(url).hostname or "Derin arastirma"),
                "priority": source.priority if source else 4,
                "published_at": published_match.group(1),
                "effective_year": effective_year,
                "evidence": evidence,
            })
        return {"verified": True, "answer": answer.strip(), "sources": sources}

    @staticmethod
    def _parse_research(output):
        return HermesBridge._parse_research_packet(output)["answer"]

    def ask(self, message):
        return self._run(
            message=message,
            research=False
        )

    def research(self, message):
        return self._run(
            message=message,
            research=True
        )

    def research_packet(self, message, trusted_only=True):
        return self._run(
            message=message,
            research=True,
            return_packet=True,
            trusted_only=trusted_only,
        )

    def collect_sources(self, message):
        if not self.is_ready():
            return []
        command = [
            "hermes", "chat", "-q", message, "--oneshot",
            "--in", str(self.project_dir), "--source", "tool",
            "-t", "web", "--max-turns", "8", "--run-budget", "90",
            "--format", "stream-json",
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []
        if result.returncode != 0:
            return []
        sources = []
        for line in result.stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "tool_result":
                continue
            try:
                extracted = json.loads(event.get("output", ""))
            except (json.JSONDecodeError, TypeError):
                continue
            if event.get("name") == "web_search":
                web_items = extracted.get("data", {}).get("web", [])
                for item in web_items:
                    url = item.get("url", "")
                    if re.search(r"(?i)\.(?:pdf|xlsx?|csv)(?:$|[?&])", url):
                        sources.append({
                            "url": url,
                            "title": item.get("title") or "",
                            "content": "",
                            "link_only": True,
                        })
                continue
            if event.get("name") != "web_extract":
                continue
            for item in extracted.get("results", []):
                if (isinstance(item, dict) and item.get("url") and item.get("content")
                        and not item.get("error")):
                    if re.search(r"(?i)\.(?:pdf|xlsx?|csv)(?:$|[?&])", item["url"]):
                        item = {**item, "content": "", "link_only": True}
                    sources.append(item)
        return sources
