"""Belge doğrulamada KESİN (kodla) katman: accounting/document_verifier.py +
accounting/accounting_agent.py::verify_document ile bütünleşmesi.

Dış inceleme madde 2 ("'Belge doğrulama' şu anda modele dayalı inceleme yapıyor... 'uyuşuyor/
uyuşmuyor' kararını kodla yapılmış kesin karşılaştırma vermiyor... büyük bir dosyanın tamamı
kontrol edilmiş sanılabilir") burada ele alınıyor. Bkz. KAIZEN_HEDEF_VE_YOL_HARITASI.md bölüm 4n.
"""
import tempfile
from pathlib import Path

from accounting.accounting_agent import AccountingAgent
from accounting.document_verifier import deterministic_matches, format_deterministic_block
from accounting.facts import FactRegistry, FactTopic
from accounting.site_store import SiteStore


class _FakeRegistry:
    """deterministic_matches'in ihtiyaç duyduğu minimal arayüz (topics + rows()) -- gerçek
    FactRegistry'nin SQLite'a gitmeden, izole birim testi için."""

    def __init__(self, topics, rows_by_topic):
        self.topics = topics
        self._rows = rows_by_topic

    def rows(self, topic=None):
        if topic is None:
            return [r for rows in self._rows.values() for r in rows]
        return self._rows.get(topic, [])


def test_deterministic_matches_detects_match_and_mismatch():
    topics = [FactTopic(id="test_kdv", title="Test KDV oranı", unit="percent", anchors=("kdv oran",))]
    registry = _FakeRegistry(topics, {
        "test_kdv": [{"topic": "test_kdv", "year": 2026, "value": "%20", "status": "verified"}],
    })

    # belgede DOĞRU değer -- model hiç karışmadan kodla UYUŞUYOR demeli
    matches = deterministic_matches("2026 yılında KDV oranı %20 olarak uygulanmıştır.", registry)
    assert len(matches) == 1 and matches[0]["matches"] is True
    assert matches[0]["title"] == "Test KDV oranı"

    # belgede YANLIŞ değer -- model hiç karışmadan kodla UYUŞMUYOR demeli
    matches = deterministic_matches("2026 yılında KDV oranı %25 olarak uygulanmıştır.", registry)
    assert len(matches) == 1 and matches[0]["matches"] is False
    assert matches[0]["extracted_value"] == "%25" and matches[0]["verified_value"] == "%20"

    # facts_registry yoksa (None) veya belge boşsa -- sessizce boş liste (eski davranış korunur)
    assert deterministic_matches("herhangi bir metin", None) == []
    assert deterministic_matches("", registry) == []

    block = format_deterministic_block(matches)
    assert "KESİN KOD KARŞILAŞTIRMASI" in block and "UYUŞMUYOR" in block
    assert format_deterministic_block([]) == ""

    print("KAIZEN BELGE DOGRULAMA KESIN KATMAN TESTI: BASARILI")


class _FakeAskProvider:
    def __init__(self, reply="AI serbest yorum metni burada."):
        self.reply = reply
        self.prompt = None

    def ask(self, prompt):
        self.prompt = prompt
        return self.reply


def test_verify_document_uses_deterministic_layer_with_real_fact_registry():
    """Gerçek FactRegistry (SiteStore'dan rebuild edilmiş) ile uçtan uca: araştırma zincirinin
    (memory/brain_manager.py::_find_contradictions) kullandığı AYNI mekanizma burada da doğru
    çalışıyor mu -- belgedeki YANLIŞ bir rakam, model hiç karışmadan kodla yakalanıyor mu?"""
    with tempfile.TemporaryDirectory() as folder:
        site_db = Path(folder) / "site.sqlite3"
        sites = SiteStore(site_db)
        for url, source in (
            ("https://www.alomaliye.com/2026-asgari", "Alomaliye"),
            ("https://vergimerkezi.com.tr/2026-asgari", "Vergi Merkezi"),
            ("https://www.muhasebetr.com/2026-asgari", "Muhasebe TR"),
        ):
            sites.upsert_page(
                url=url, source_name=source, title="2026 asgari ücret",
                content="2026 yılında brüt asgari ücret aylık 33.030,00 TL olarak uygulanır.",
                published_at="2026-01-05", effective_year=2026,
            )
        facts = FactRegistry(site_db)
        facts.rebuild(sites)
        assert any(r["status"] == "verified" for r in facts.rows("asgari_ucret_brut"))

        provider = _FakeAskProvider()
        agent = AccountingAgent(provider, learning_memory_path=Path(folder) / "corrections.json")
        document_text = "Bordroda 2026 yılı brüt asgari ücret 40.000,00 TL olarak hesaplanmış."
        result = agent.verify_document(document_text, facts_context="", facts_registry=facts)

        assert "KESİN KOD KARŞILAŞTIRMASI" in result and "UYUŞMUYOR" in result
        assert "33.030" in result and "40.000" in result
        assert "AI YORUMU" in result and provider.reply in result

    print("KAIZEN BELGE DOGRULAMA UCTAN UCA TESTI: BASARILI")


def test_verify_document_flags_truncation_regardless_of_model_output():
    """DÜZELTME (2026-09-23): eskiden 8.000 karakterlik kesilme yalnız PROMPT'a (modele) not
    olarak ekleniyordu -- model bunu cevabına yansıtmazsa kullanıcı hiç haberdar olmuyordu.
    Artık kesilme varsa, modelin ne yazdığından TAMAMEN bağımsız, kodla garanti bir uyarı çıktıya
    ekleniyor."""
    with tempfile.TemporaryDirectory() as folder:
        provider = _FakeAskProvider(reply="Kısa AI cevabı (kesilmeyi hiç anmıyor).")
        agent = AccountingAgent(provider, learning_memory_path=Path(folder) / "corrections.json")
        long_text = "Kira: 1000 TL. " * 1000
        assert len(long_text) > 8000

        # facts_registry YOK -- yine de kesilme uyarısı garanti eklenmeli
        result = agent.verify_document(long_text, facts_context="")
        assert "yalnız ilk 8.000 karakteri kapsıyor" in result
        assert str(len(long_text.strip())) in result
        assert provider.reply in result

        # kısa bir belgede (kesilme YOK) bu uyarı hiç eklenmemeli
        short_result = agent.verify_document("Kira: 1000 TL.", facts_context="")
        assert "8.000 karakteri kapsıyor" not in short_result

    print("KAIZEN BELGE DOGRULAMA KESILME UYARISI TESTI: BASARILI")


if __name__ == "__main__":
    test_deterministic_matches_detects_match_and_mismatch()
    test_verify_document_uses_deterministic_layer_with_real_fact_registry()
    test_verify_document_flags_truncation_regardless_of_model_output()
