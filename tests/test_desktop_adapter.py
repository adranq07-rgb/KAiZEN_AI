"""KAIZEN BÜYÜK GELİŞTİRME PAKETİ #1, Faz L: Desktop iş mantığı (adapter) testleri.

Faz L'nin açık izniyle (tkinter bu ortamda kurulu değil -- bkz. desktop/adapter.py modül
docstring'i ve desktop/ARCHITECTURE_DECISION.md "Ortam Kanıtı"): burada `desktop_app.py`
(gerçek pencere) DEĞİL, ondan ayrıştırılmış `desktop/adapter.py` iş mantığı test edilir.
Hiçbir satır `tkinter` import ETMEZ."""
from core.trace import KaizenTrace, VERIFIED, SUPPORTED, UNKNOWN
from desktop.adapter import (
    StatusMapper, TraceSummary, context_panel_summary, full_inspector_lines,
    ErrorPresenter, ConversationHistory, ConversationTurn,
    STATE_STARTING, STATE_READY, STATE_BUSY, STATE_ENGINE_ERROR,
)


def test_status_mapper_labels_are_turkish_and_cover_all_states():
    assert StatusMapper.label_for_state(STATE_STARTING) == "Başlatılıyor"
    assert StatusMapper.label_for_state(STATE_READY) == "Hazır"
    assert StatusMapper.label_for_state(STATE_BUSY) == "Düşünüyor"
    assert StatusMapper.label_for_state(STATE_ENGINE_ERROR) == "Hata"
    assert StatusMapper.label_for_state("bilinmeyen-durum") == "Bilinmiyor"
    print("KAIZEN DESKTOP STATUS MAPPER ETIKETLERI TESTI: BASARILI")


def test_status_mapper_summarize_trace_reflects_real_route_and_confidence():
    trace = KaizenTrace(route="memory_grounded", confidence=SUPPORTED)
    summary = StatusMapper.summarize_trace(trace)
    assert summary == "Son yanıt: yerel hafızadan (kanıt destekli) — Kaynak destekli"

    exact_trace = KaizenTrace(route="arithmetic", confidence=VERIFIED)
    assert "hesaplayarak (kesin)" in StatusMapper.summarize_trace(exact_trace)
    assert "Doğrulanmış" in StatusMapper.summarize_trace(exact_trace)

    assert StatusMapper.summarize_trace(None) is None
    print("KAIZEN DESKTOP STATUS MAPPER TRACE OZETI (GERCEK ROUTE/CONFIDENCE) TESTI: BASARILI")


def test_status_mapper_never_fabricates_unknown_route():
    """F3: bilinmeyen/eksik bir route UYDURULMAZ -- olduğu gibi (None/route adı) gösterilir."""
    trace = KaizenTrace(route=None, confidence=UNKNOWN)
    summary = StatusMapper.summarize_trace(trace)
    assert "bilinmiyor" in summary
    print("KAIZEN DESKTOP STATUS MAPPER SAHTE DURUM UYDURMAZ TESTI: BASARILI")


def test_context_panel_summary_hides_technical_fields():
    trace = KaizenTrace(
        intent="accounting", route="memory_grounded", confidence=SUPPORTED,
        retrieval_score=0.83, used_research=False,
        principle_selected="donemsellik", principle_confidence="HIGH",
        refusal_reason=None,
    )
    summary = context_panel_summary(trace)
    assert isinstance(summary, TraceSummary)
    assert summary.confidence_label == "Kaynak destekli"
    assert summary.principle_hint == ("donemsellik", "HIGH")
    assert summary.retrieval_score == 0.83
    assert not hasattr(summary, "refusal_reason")  # teknik alan bilinçli olarak yok
    assert context_panel_summary(None) is None
    print("KAIZEN DESKTOP BAGLAM PANELI TEKNIK ALANLARI GIZLER TESTI: BASARILI")


def test_full_inspector_lines_exposes_all_trace_fields():
    trace = KaizenTrace(
        intent="accounting", route="research", confidence="PENDING",
        refusal_reason=None, used_research=True,
        principle_candidates=(("donemsellik", 5),), principle_selected="donemsellik",
        principle_confidence="HIGH", principle_rejected=(), principle_reason="test",
    )
    lines = full_inspector_lines(trace)
    joined = "\n".join(lines)
    for field in ("intent", "route", "confidence", "used_research", "principle_selected",
                  "principle_confidence", "principle_reason"):
        assert field in joined, f"{field} eksik"
    assert full_inspector_lines(None) == ["(henüz bir cevap üretilmedi)"]
    print("KAIZEN DESKTOP BRAIN INSPECTOR TUM ALANLARI GOSTERIR TESTI: BASARILI")


def test_error_presenter_never_leaks_raw_exception_to_user_message():
    exc = ValueError("gizli ic detay: /home/kullanici/secret_path.sqlite3")
    user_msg = ErrorPresenter.user_message(exc)
    assert "secret_path" not in user_msg
    assert "ValueError" not in user_msg
    assert "beklenmeyen bir hata" in user_msg
    detail = ErrorPresenter.technical_detail(exc)
    assert "ValueError" in detail and "secret_path" in detail
    print("KAIZEN DESKTOP ERROR PRESENTER HAM HATA SIZDIRMAZ TESTI: BASARILI")


def test_conversation_history_is_session_only_and_independent_of_kaizen_memory():
    history = ConversationHistory()
    assert len(history) == 0
    history.add("user", "Merhaba")
    history.add("kaizen", "Merhaba, nasıl yardımcı olabilirim?", trace=KaizenTrace())
    assert len(history) == 2
    turns = history.all()
    assert isinstance(turns[0], ConversationTurn)
    assert turns[0].role == "user" and turns[0].text == "Merhaba"
    assert turns[1].trace is not None
    history.clear()
    assert len(history) == 0
    # H4: bu modul core.kaizen_brain / core.engine / memory.* 'i hic IMPORT ETMEZ -- Kaizen'in
    # gercek hafizasina/motoruna kod seviyesinde dokunmadigi, import satirlarina bakilarak
    # dogrulanir (docstring ACIKLAMA metni bu kontrolun disinda tutulur, kasitli).
    import ast
    from pathlib import Path
    tree = ast.parse(Path(__file__).resolve().parent.parent.joinpath("desktop", "adapter.py").read_text(encoding="utf-8"))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    assert not any(m.startswith("core.") or m.startswith("memory.") for m in imported_modules), imported_modules
    print("KAIZEN DESKTOP CONVERSATION HISTORY (OTURUM ICI, KAIZEN HAFIZASINDAN BAGIMSIZ) TESTI: BASARILI")


if __name__ == "__main__":
    test_status_mapper_labels_are_turkish_and_cover_all_states()
    test_status_mapper_summarize_trace_reflects_real_route_and_confidence()
    test_status_mapper_never_fabricates_unknown_route()
    test_context_panel_summary_hides_technical_fields()
    test_full_inspector_lines_exposes_all_trace_fields()
    test_error_presenter_never_leaks_raw_exception_to_user_message()
    test_conversation_history_is_session_only_and_independent_of_kaizen_memory()
