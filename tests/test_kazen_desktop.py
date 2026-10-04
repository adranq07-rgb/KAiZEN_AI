"""KAİZEN Desktop (tkinter'sız mantık katmanı) testleri. Gerçek ağ/motor YOK; tkinter YÜKLENMEZ."""
import json
import os
import tempfile
import time
from pathlib import Path

from desktop import kazen_core as core
from desktop.chat_store import ChatStore
from desktop.controller import KazenController, STATUS_DOCUMENT, STATUS_RESEARCH, STATUS_THINKING
from desktop.health import check_local_fallback, check_nemotron, check_research, collect_health
from desktop.markdown_view import inline_spans, parse_markdown


def _tmp():
    return tempfile.mkdtemp(prefix="kazen_ui_")


def _file(name, content=b"x"):
    path = Path(_tmp()) / name
    path.write_bytes(content)
    return str(path)


class _Cfg:
    def __init__(self, data):
        self.data = data

    def get(self, section, key=None, default=None):
        node = self.data.get(section, {})
        return node if key is None else node.get(key, default)


# --- mod mimarisi -------------------------------------------------------------------------------
def test_kazen_modes_only_accounting_enabled():
    assert core.APP_NAME == "KAİZEN"
    assert core.mode_enabled(core.MODE_ACCOUNTING)
    assert not core.mode_enabled(core.MODE_GENERAL)
    assert "Yakında" in core.MODES[core.MODE_GENERAL]["label"]
    controller = KazenController(engine_factory=lambda: object(), store=ChatStore(Path(_tmp()) / "c.json"))
    assert controller.set_mode(core.MODE_GENERAL) is False and controller.mode == core.MODE_ACCOUNTING


# --- dosya doğrulama -------------------------------------------------------------------------------
def test_kazen_attachment_validation_explicit_errors():
    ok = core.validate_attachment(_file("fatura_001.pdf"))
    assert ok.ok and ok.name == "fatura_001.pdf"
    for suffix in ("xlsx", "xls", "csv", "docx", "txt", "md", "json", "jpg", "jpeg", "png"):
        assert core.validate_attachment(_file(f"a.{suffix}")).ok, suffix
    bad = core.validate_attachment(_file("virus.exe"))
    assert not bad.ok and "Desteklenmeyen" in bad.error and ".exe" in bad.error
    assert not core.validate_attachment(os.path.join(_tmp(), "yok.pdf")).ok
    assert "bulunamadı" in core.validate_attachment(os.path.join(_tmp(), "yok.pdf")).error
    assert "boş" in core.validate_attachment(_file("bos.pdf", b"")).error
    assert "Klasör" in core.validate_attachment(_tmp()).error


def test_kazen_compose_message_passes_real_path_and_reuses_previous_file():
    path = _file("fatura_001.pdf")
    message, used = core.compose_message("Bunu analiz et", [path])
    assert message == f'Bunu analiz et "{path}"' and used == [path]
    message, used = core.compose_message("", [path])
    assert message.startswith("Bu dosyayı oku") and path in message
    # önceki dosyaya atıf: yol tekrar sorulmadan bağlanır
    message, used = core.compose_message("bu faturayı muhasebe açısından analiz et", [], [path])
    assert used == [path] and path in message
    # atıf yok -> dosya bağlanmaz
    assert core.compose_message("Sen kimsin?", [], [path]) == ("Sen kimsin?", [])


# --- cevap ayrıştırma ---------------------------------------------------------------------------------
def test_kazen_parse_answer_sources_verification_and_outputs():
    out = _file("indirilecek_kdv_temiz.xlsx")
    answer = (
        "İlk dilim 190.000 TL, oran %15.\n\n"
        "KAYNAKLAR:\n- https://www.gib.gov.tr/vergi-oranlari\n- https://www.resmigazete.gov.tr/x\n"
        "DOĞRULAMA: 2 bağımsız güvenilir kaynakta doğrulandı\n"
        f"ÇIKTI DOSYASI: {out}\n"
    )
    view = core.parse_answer(answer, {"route": "research", "used_research": True, "research_status": "SUPPORTED"})
    assert "190.000" in view.body and "KAYNAKLAR" not in view.body and "DOĞRULAMA" not in view.body
    assert len(view.sources) == 2 and all(s.url.startswith("https://") for s in view.sources)
    assert view.verification == "2 bağımsız güvenilir kaynakta doğrulandı"
    assert view.outputs == [out] and "ÇIKTI DOSYASI" not in view.body


def test_kazen_parse_answer_does_not_invent_verification():
    view = core.parse_answer("Merhaba, ben Kaizen.", {"route": "identity"})
    assert view.sources == [] and view.verification == "" and not view.research_used
    view = core.parse_answer("Yetersiz.", {"route": "x", "used_research": True, "research_status": "INSUFFICIENT",
                                           "official_evidence_count": 0, "evidence_count": 2})
    assert "yetersiz kanıt" in view.verification and "0/2" in view.verification


def test_kazen_parse_answer_trace_summary_has_no_secrets():
    view = core.parse_answer("x", {"route": "provider", "api_key": "SECRET", "NGC_API_KEY": "SECRET"})
    assert "SECRET" not in json.dumps(view.trace_summary)


# --- markdown ------------------------------------------------------------------------------------------
def test_kazen_markdown_blocks_and_turkish_characters():
    text = ("# Yevmiye Kaydı\n\nAlış **ticari mal** kaydı:\n\n- 153 Ticari Mallar\n- 191 İndirilecek KDV\n\n"
            "1. Borç\n2. Alacak\n\n| Hesap | Borç | Alacak |\n|---|---|---|\n| 153 Ticari Mallar | 100.000 | |\n"
            "| 320 Satıcılar | | 120.000 |\n\nSONUÇ: Kayıt dengelidir.\n```\n153 / 320\n```")
    blocks = parse_markdown(text)
    kinds = [b.kind for b in blocks]
    for k in ("heading", "para", "bullet", "numbered", "table", "section", "code"):
        assert k in kinds, k
    table = next(b for b in blocks if b.kind == "table")
    assert table.rows[0] == ["Hesap", "Borç", "Alacak"] and len(table.rows) == 3
    assert any(t == "ticari mal" and s == "bold" for t, s in inline_spans("Alış **ticari mal** kaydı"))
    assert "İndirilecek" in "".join(t for b in blocks if b.kind == "bullet" for t, _ in b.spans)


# --- sohbet geçmişi ----------------------------------------------------------------------------------------
def test_kazen_chat_store_persists_and_survives_corrupt_file():
    path = Path(_tmp()) / "conv.json"
    store = ChatStore(path)
    conv = store.new_conversation()
    store.add_message(conv["id"], "user", "Vadeli mal aldım, kayıt nasıl olur?", attachments=[{"path": "C:\\f.pdf", "name": "f.pdf"}])
    store.add_message(conv["id"], "kaizen", "Cevap", outputs=["C:\\o.xlsx"])
    again = ChatStore(path)
    assert again.get(conv["id"])["title"].startswith("Vadeli mal")
    assert again.attachments_of(conv["id"]) == ["C:\\f.pdf"]
    assert {f["kind"] for f in again.all_files()} == {"ek", "çıktı"}
    path.write_text("{bozuk", encoding="utf-8")
    broken = ChatStore(path)
    assert broken.conversations == [] and path.with_suffix(".bak").exists()
    saved = path.read_text(encoding="utf-8") if path.exists() else ""
    assert "NGC" not in saved


# --- sağlık ----------------------------------------------------------------------------------------------------
def test_kazen_health_never_shows_key_and_reports_states():
    cfg = _Cfg({"model": {"provider": "local", "nemotron": {"base_url": "https://x/v1", "model_name": "n", "api_key_env": "NGC_API_KEY"},
                          "local": {"base_url": "http://localhost:11434/v1", "model_name": "llama3.2:3b"}},
                "research": {"research_engine_enabled": True, "base_url": "http://127.0.0.1:8890"}})
    secret = "nvapi-SUPER-SECRET"
    seen = {}

    def http_get(url, headers=None, timeout=6):
        seen[url] = headers
        if url.endswith("/api/tags"):
            return 200, json.dumps({"models": [{"name": "llama3.2:3b"}]}).encode(), ""
        if "/models" in url:
            return 200, b"{}", ""
        return None, b"", "ConnectionRefusedError"

    assert check_nemotron(cfg, http_get, {}).state != "ok" and "ayarlı değil" in check_nemotron(cfg, http_get, {}).text
    item = check_nemotron(cfg, http_get, {"NGC_API_KEY": secret})
    assert item.state == "ok" and "Connected" in item.text and secret not in item.text
    assert check_local_fallback(cfg, http_get).state == "ok"
    research = check_research(cfg, http_get)
    assert research.state == "bad" and "Docker" in research.text
    items = collect_health(cfg, True, http_get, {"NGC_API_KEY": secret})
    assert secret not in " ".join(i.text for i in items)
    assert [i.name for i in items][0].startswith("Backend")


# --- denetleyici (sahte motor) ------------------------------------------------------------------------------------
class _FakeBrain:
    last_trace = {"route": "provider"}

    @staticmethod
    def needs_current_research(message):
        return "2026" in message


class _FakeEngine:
    def __init__(self):
        self.brain = _FakeBrain()
        self.seen = []

    def cevap_ver(self, message):
        self.seen.append(message)
        time.sleep(0.05)
        return "Ben Kaizen, muhasebe asistanıyım."


def _drain(controller, until, timeout=5.0):
    events = []
    end = time.time() + timeout
    while time.time() < end:
        try:
            events.append(controller.events.get(timeout=0.1))
        except Exception:
            continue
        if events[-1][0] in until:
            break
    return events


def test_kazen_controller_calls_cevap_ver_once_with_real_path_and_is_not_blocking():
    engine = _FakeEngine()
    controller = KazenController(engine_factory=lambda: engine, store=ChatStore(Path(_tmp()) / "c.json"))
    controller.start_engine()
    assert _drain(controller, {"engine_ready", "engine_error"})[-1][0] == "engine_ready"
    started = time.perf_counter()
    assert controller.submit("Sen kimsin?") is True
    assert time.perf_counter() - started < 0.04          # submit hemen döner (UI donmaz)
    events = _drain(controller, {"answer", "error"})
    names = [e[0] for e in events]
    assert "user" in names and "status" in names and names[-1] == "answer"
    assert [e[1] for e in events if e[0] == "status"][0] == STATUS_THINKING
    view, _ = events[-1][1]
    assert "Kaizen" in view.body and engine.seen == ["Sen kimsin?"]

    path = _file("fatura_001.pdf")
    _drain(controller, {"status"}, 0.3)
    assert controller.submit("Bunu muhasebe açısından analiz et", [path]) is True
    events = _drain(controller, {"answer", "error"})
    assert [e[1] for e in events if e[0] == "status"][0] == STATUS_DOCUMENT
    assert engine.seen[-1] == f'Bunu muhasebe açısından analiz et "{path}"'
    # sonraki mesajda dosya yolu yeniden sorulmaz
    time.sleep(0.2)
    controller.submit("bu faturayı özetle")
    _drain(controller, {"answer", "error"})
    assert path in engine.seen[-1]


def test_kazen_controller_rejects_unsupported_file_and_reports_research_status():
    engine = _FakeEngine()
    controller = KazenController(engine_factory=lambda: engine, store=ChatStore(Path(_tmp()) / "c.json"))
    controller.start_engine()
    _drain(controller, {"engine_ready"})
    assert controller.submit("Analiz et", [_file("a.exe")]) is False
    kinds = _drain(controller, {"attach_error"})
    assert kinds[-1][0] == "attach_error" and "Desteklenmeyen" in kinds[-1][1][0]
    assert engine.seen == []
    assert controller.initial_status("2026 gelir vergisi tarifesi nedir?", False) == STATUS_RESEARCH


def test_kazen_controller_engine_failure_is_reported_not_raised():
    def boom():
        raise RuntimeError("model yok")

    controller = KazenController(engine_factory=boom, store=ChatStore(Path(_tmp()) / "c.json"))
    controller.start_engine()
    events = _drain(controller, {"engine_error"})
    assert events[-1][0] == "engine_error" and "model yok" in events[-1][1]
    assert controller.submit("merhaba") is False
