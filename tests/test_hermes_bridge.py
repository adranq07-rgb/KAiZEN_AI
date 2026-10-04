from core.hermes_bridge import HermesBridge
import json
import tempfile
from unittest.mock import patch
from types import SimpleNamespace


def test_hermes_bridge_lock():
    with tempfile.TemporaryDirectory() as log_dir:
        _run_hermes_bridge_lock(log_dir)


def _run_hermes_bridge_lock(log_dir):
    bridge = HermesBridge(log_dir=log_dir)
    bridge.config.cloud_allowed = lambda: False

    assert bridge.is_ready() is False

    bridge.config.get = lambda section, key, default=None: "local"
    assert bridge.is_ready() is False

    result = bridge.ask("Bu mesaj Hermes'e gitmemeli.")

    assert "Hermes su anda calistirilamiyor" in result

    print("KAIZEN HERMES GUVENLIK TESTI: BASARILI")


def test_hermes_research_sources():
    # log_dir: gercek logs/kaizen.log yerine izole bir gecici klasor (bkz. test_hermes_bridge_lock).
    bridge = HermesBridge(log_dir=tempfile.mkdtemp())
    bridge.config.cloud_allowed = lambda: True

    trusted_url = "https://www.gib.gov.tr/ornek"
    answer = {"type": "result", "text": f"SONUC: Oran %25.\nKAYNAKLAR: {trusted_url}\nYAYIN_TARIHI: 2026-09-01\nKANIT: Genel kurumlar vergisi orani %25 olarak aciklandi."}
    source = {
        "type": "tool_result",
        "name": "web_extract",
        "output": json.dumps({"results": [{
            "url": trusted_url,
            "content": "Example Domain: Genel kurumlar vergisi orani %25 olarak aciklandi.",
            "error": None,
        }]})
    }
    output = "\n".join(json.dumps(item) for item in (source, answer))

    with patch("core.hermes_bridge.subprocess.run") as run:
        run.return_value = SimpleNamespace(returncode=0, stdout=output, stderr="")
        result = bridge.research("Ornek soru")

    assert "SONUC: Oran %25" in result
    assert trusted_url in result
    assert ["-t", "web", "--format", "stream-json"] == run.call_args.args[0][-4:]

    with patch("core.hermes_bridge.subprocess.run") as run:
        run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(answer), stderr="")
        result = bridge.research("Ornek soru")

    assert "dogrulanamadi" in result

    uncited = {"type": "result", "text": "SONUC: Oran %25."}
    result = bridge._parse_research("\n".join(json.dumps(item) for item in (source, uncited)))
    assert "baglantisi yok" in result

    wrong_rate = {"type": "result", "text": f"SONUC: Oran %30.\nKAYNAKLAR: {trusted_url}\nYAYIN_TARIHI: 2026-09-01\nKANIT: Genel kurumlar vergisi orani %25 olarak aciklandi."}
    result = bridge._parse_research("\n".join(json.dumps(item) for item in (source, wrong_rate)))
    assert "oranlar" in result

    fake_evidence = {"type": "result", "text": f"SONUC: Oran %25.\nKAYNAKLAR: {trusted_url}\nYAYIN_TARIHI: 2026-09-01\nKANIT: Genel kurumlar vergisi orani %25 degilmis."}
    result = bridge._parse_research("\n".join(json.dumps(item) for item in (source, fake_evidence)))
    assert "Kanit cumlesi" in result

    failed_source = dict(source)
    failed_source["output"] = json.dumps({"results": [{"url": trusted_url, "content": "Oran %25", "error": "fetch failed"}]})
    result = bridge._parse_research("\n".join(json.dumps(item) for item in (failed_source, answer)))
    assert "dogrulanamadi" in result

    def parse_case(claim, quote="Genel kurumlar vergisi orani %25 olarak aciklandi."):
        extracted = dict(source)
        extracted["output"] = json.dumps({"results": [{
            "url": trusted_url, "content": quote,
        }]})
        response = {"type": "result", "text": (
            f"SONUC: {claim}\nKAYNAKLAR: {trusted_url}\nYAYIN_TARIHI: 2026-09-01\nKANIT: {quote}"
        )}
        return bridge._parse_research("\n".join(map(json.dumps, (extracted, response))))

    for rate in ("yüzde 99", "yuzde 99", "YÜZDE 99", "yüzde doksan dokuz"):
        assert "oranlar" in parse_case(f"Oran {rate}.")
    for rate in ("yüzde 25", "yuzde 25,0", "25%", "%25.00"):
        assert "SONUC:" in parse_case(f"Oran {rate}.")

    unrelated = "2026 yilinda B kategorisinin orani %25."
    result = parse_case(unrelated, "2020 yilinda yalnizca A kategorisinde oran %25 idi.")
    assert unrelated not in result
    assert "yeterince eslesmedi" in result

    # A valid quote must not allow an unsupported non-numeric claim either.
    unsupported = "Butun basvurular kosulsuz kabul edilir."
    assert unsupported not in parse_case(unsupported)

    for malformed in ("null", "[]", '{"type":"result","text":42}',
                      '{"type":"tool_result","name":"web_extract","output":"[]"}'):
        assert "kesin cevap veremiyorum" in bridge._parse_research(malformed)

    print("KAIZEN HERMES KAYNAK TESTI: BASARILI")


if __name__ == "__main__":
    test_hermes_bridge_lock()
