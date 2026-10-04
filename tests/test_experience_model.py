"""KAIZEN — BÜYÜK GELİŞTİRME PAKETİ #1, Faz D (madde 15): Experience Model / ReflectionStore testleri.

D1 (alan seti), D2 (FACT/VERIFIED LAW asla tasinmaz -- yapisal: ilgili alan yok), D3
(otomatik guven yok -- yalnizca iki ayri acik cagriyla reusable olur), D4 (bu katman
KaizenBrain/KaizenEngine'e BAGLANMAZ -- bu dosyada da hicbir yerde KaizenBrain import
edilmez, bu kasitli)."""
import tempfile
from pathlib import Path

from learning.experience_model import (
    Experience, ExperienceModelError, OUTCOME_SUCCESS, OUTCOME_REFUSED,
    VERIFICATION_NONE, VERIFICATION_USER_APPROVED,
)
from learning.reflection_store import ReflectionStore


def _tmp_store():
    return ReflectionStore(Path(tempfile.mkdtemp()) / "reflections.sqlite3")


def test_experience_model_has_the_ten_mandated_fields():
    exp = Experience(
        problem_signature="ACCOUNT_CLASS_QUERY",
        selected_principle="hesap_siniflandirma",
        strategy="memory_grounded+principle_assist",
        tools_used=("retriever", "principle_retriever"),
        evidence_used=("Ders notu — Sayfa 3",),
        outcome=OUTCOME_SUCCESS,
        verification=VERIFICATION_NONE,
    )
    for attr in ("problem_signature", "selected_principle", "strategy", "tools_used",
                 "evidence_used", "outcome", "verification", "user_approved", "reusable",
                 "created_at"):
        assert hasattr(exp, attr)
    assert exp.user_approved is False
    assert exp.reusable is False
    print("KAIZEN EXPERIENCE MODEL 10 ALAN TESTI: BASARILI")


def test_experience_model_rejects_empty_signature_and_strategy():
    for kwargs in (
        dict(problem_signature="", strategy="x", selected_principle=None,
             tools_used=(), evidence_used=(), outcome=OUTCOME_SUCCESS, verification=VERIFICATION_NONE),
        dict(problem_signature="x", strategy="  ", selected_principle=None,
             tools_used=(), evidence_used=(), outcome=OUTCOME_SUCCESS, verification=VERIFICATION_NONE),
    ):
        try:
            Experience(**kwargs)
        except ExperienceModelError:
            pass
        else:
            raise AssertionError("bos imza/strateji kabul edildi")
    print("KAIZEN EXPERIENCE MODEL BOS ALAN REDDI TESTI: BASARILI")


def test_experience_model_rejects_unknown_outcome_and_verification():
    for kwargs in (
        dict(problem_signature="x", strategy="y", selected_principle=None, tools_used=(),
             evidence_used=(), outcome="UYDURMA", verification=VERIFICATION_NONE),
        dict(problem_signature="x", strategy="y", selected_principle=None, tools_used=(),
             evidence_used=(), outcome=OUTCOME_SUCCESS, verification="UYDURMA"),
    ):
        try:
            Experience(**kwargs)
        except ExperienceModelError:
            pass
        else:
            raise AssertionError("bilinmeyen outcome/verification kabul edildi")
    print("KAIZEN EXPERIENCE MODEL BILINMEYEN OUTCOME/VERIFICATION REDDI TESTI: BASARILI")


def test_experience_model_d2_has_no_raw_fact_or_answer_field():
    """D2: Experience dataclass'inda ham cevap metni/FACT degeri tasiyacak bir alan
    YOK -- alan adlari sabit 10 alanla SINIRLI (yeni bir 'answer'/'fact_value' alani
    sessizce eklenmedi)."""
    fields = set(Experience.__dataclass_fields__.keys())
    expected = {
        "problem_signature", "selected_principle", "strategy", "tools_used",
        "evidence_used", "outcome", "verification", "user_approved", "reusable", "created_at",
    }
    assert fields == expected, f"beklenmeyen alan seti: {fields}"
    assert "answer" not in fields and "answer_text" not in fields and "fact_value" not in fields
    print("KAIZEN EXPERIENCE MODEL D2 (HAM FACT/CEVAP ALANI YOK) TESTI: BASARILI")


def test_experience_model_d3_reusable_true_requires_user_approved_true_at_construction():
    try:
        Experience(
            problem_signature="x", strategy="y", selected_principle=None, tools_used=(),
            evidence_used=(), outcome=OUTCOME_SUCCESS, verification=VERIFICATION_NONE,
            reusable=True, user_approved=False,
        )
    except ExperienceModelError:
        pass
    else:
        raise AssertionError("user_approved=False iken reusable=True kabul edildi")
    # user_approved=True + reusable=True ELDEN olusturmak (kayit ANINDA) hala kabul edilir --
    # D3'un yasakladigi 'ReflectionStore uzerinden OTOMATIK gecis', dataclass'in kendisi
    # dogrudan True/True verilmesini engellemez (o, ReflectionStore.mark_* ikilisinin isi).
    exp = Experience(
        problem_signature="x", strategy="y", selected_principle=None, tools_used=(),
        evidence_used=(), outcome=OUTCOME_SUCCESS, verification=VERIFICATION_USER_APPROVED,
        reusable=True, user_approved=True,
    )
    assert exp.reusable is True
    print("KAIZEN EXPERIENCE MODEL D3 (REUSABLE ONCESI USER_APPROVED SARTI) TESTI: BASARILI")


def test_reflection_store_record_and_get_round_trips():
    store = _tmp_store()
    exp = Experience(
        problem_signature="TEMPORAL_MISMATCH", strategy="memory_grounded",
        selected_principle="donemsellik", tools_used=("retriever",),
        evidence_used=("Ders notu — Sayfa 1",), outcome=OUTCOME_SUCCESS,
        verification=VERIFICATION_NONE,
    )
    record_id = store.record(exp)
    fetched = store.get(record_id)
    assert fetched.problem_signature == "TEMPORAL_MISMATCH"
    assert fetched.selected_principle == "donemsellik"
    assert fetched.user_approved is False
    assert fetched.reusable is False
    assert store.get("olmayan-id") is None
    print("KAIZEN REFLECTION STORE KAYIT/OKUMA TESTI: BASARILI")


def test_reflection_store_d3_no_auto_trust_two_separate_explicit_calls_required():
    store = _tmp_store()
    exp = Experience(
        problem_signature="x", strategy="research", selected_principle=None,
        tools_used=("accounting_agent",), evidence_used=(), outcome=OUTCOME_REFUSED,
        verification=VERIFICATION_NONE,
    )
    record_id = store.record(exp)
    assert store.get(record_id).reusable is False

    # mark_reusable ONAY OLMADAN cagrilirsa reddedilir -- sessizce yok SAYILMAZ.
    try:
        store.mark_reusable(record_id)
    except Exception:
        pass
    else:
        raise AssertionError("onay olmadan reusable=True yapildi (D3 ihlali)")
    assert store.get(record_id).reusable is False

    # yalnizca IKI AYRI, ACIK cagriyla reusable olur.
    assert store.mark_user_approved(record_id) is True
    assert store.get(record_id).user_approved is True
    assert store.get(record_id).reusable is False  # onay TEK BASINA reusable yapmaz
    assert store.mark_reusable(record_id) is True
    assert store.get(record_id).reusable is True
    print("KAIZEN REFLECTION STORE D3 (OTOMATIK GUVEN YOK, IKI AYRI ONAY) TESTI: BASARILI")


def test_reflection_store_list_filters_by_signature_outcome_and_reusable():
    store = _tmp_store()
    id1 = store.record(Experience(
        problem_signature="SIG_A", strategy="s1", selected_principle=None, tools_used=(),
        evidence_used=(), outcome=OUTCOME_SUCCESS, verification=VERIFICATION_NONE))
    id2 = store.record(Experience(
        problem_signature="SIG_A", strategy="s2", selected_principle=None, tools_used=(),
        evidence_used=(), outcome=OUTCOME_REFUSED, verification=VERIFICATION_NONE))
    store.record(Experience(
        problem_signature="SIG_B", strategy="s3", selected_principle=None, tools_used=(),
        evidence_used=(), outcome=OUTCOME_SUCCESS, verification=VERIFICATION_NONE))

    assert len(store.list(problem_signature="SIG_A")) == 2
    assert len(store.list(problem_signature="SIG_B")) == 1
    assert len(store.list(outcome=OUTCOME_REFUSED)) == 1
    assert store.list(reusable_only=True) == []

    store.mark_user_approved(id1)
    store.mark_reusable(id1)
    reusable = store.list(reusable_only=True)
    assert len(reusable) == 1 and reusable[0].problem_signature == "SIG_A"
    assert store.count() == 3
    print("KAIZEN REFLECTION STORE FILTRELEME TESTI: BASARILI")


def test_experience_model_is_never_imported_by_kaizen_brain_d4():
    """D4 (madde 15, birebir): bu faz `core/kaizen_brain.py`'ye HIC BAGLANMAZ -- statik
    kaynak taramasiyla dogrulanir (test_engine_isolation.py'deki AST-guard deseniyle ayni
    ruhta, ama burada basit bir metin taramasi yeterli)."""
    src = (Path(__file__).resolve().parent.parent / "core" / "kaizen_brain.py").read_text(encoding="utf-8")
    assert "experience_model" not in src
    assert "reflection_store" not in src
    print("KAIZEN EXPERIENCE MODEL D4 (KAIZENBRAIN'E BAGLANMADI) TESTI: BASARILI")


if __name__ == "__main__":
    test_experience_model_has_the_ten_mandated_fields()
    test_experience_model_rejects_empty_signature_and_strategy()
    test_experience_model_rejects_unknown_outcome_and_verification()
    test_experience_model_d2_has_no_raw_fact_or_answer_field()
    test_experience_model_d3_reusable_true_requires_user_approved_true_at_construction()
    test_reflection_store_record_and_get_round_trips()
    test_reflection_store_d3_no_auto_trust_two_separate_explicit_calls_required()
    test_reflection_store_list_filters_by_signature_outcome_and_reusable()
    test_experience_model_is_never_imported_by_kaizen_brain_d4()
