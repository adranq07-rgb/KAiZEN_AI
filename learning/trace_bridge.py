"""KAIZEN — Learning Brain v1: PrincipleRetrievalResult -> KaizenTrace köprüsü (madde 12).

Yalnız GÖZLEM için: `core/trace.py::KaizenTrace`'in principle_* alanlarını bir
`PrincipleRetrievalResult`'tan doldurur. `KaizenBrain._answer_core` bu fonksiyonu HİÇ
ÇAĞIRMAZ (madde 14: Principle Layer şu an üretim cevap zincirine bağlı değil,
shadow/observational) -- yalnız testlerde ve ileride (bir sonraki fazda) gerçek
entegrasyon için kullanılacak, izole bir köprü fonksiyonudur.
"""


def fill_principle_trace(trace, result):
    """`trace` (KaizenTrace) üzerinde principle_* alanlarını `result`
    (PrincipleRetrievalResult) ile doldurur ve AYNI `trace` nesnesini döner
    (zincirlenebilir). Trace'in kullanıcıya giden METİN CEVAPLA hiçbir ilgisi yok."""
    trace.principle_candidates = tuple((c.principle_id, c.score) for c in result.candidates)
    trace.principle_selected = result.selected
    trace.principle_confidence = result.confidence
    trace.principle_rejected = tuple(result.rejected)
    trace.principle_reason = result.reason
    return trace
