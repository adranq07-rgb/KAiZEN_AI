"""Statik güvenlik ağı: bir test dosyası `BrainManager(...)` ya da `KaizenBrain(...)` kurarken
`experience_memory=` (ya da zaten enjekte edilmiş bir `brain_manager=`) GEÇMEZSE, varsayılan
olarak GERÇEK bir `memory.cognee_memory.CogneeMemory()` örneği oluşur. Bu bulut ortamında
zararsızdır (cognee kurulu değil) -- ama kullanıcının kendi bilgisayarında (cognee kurulu,
config'te enabled=true) `KaizenBrain.answer()`'ın her başarılı cevaptan sonra çağırdığı
`remember_experience`, testlerin ürettiği metinleri (altın sınavdaki 70 soru-cevap gibi)
kullanıcının KALICI kişisel Cognee hafızasına gerçekten yazar (bkz.
`tests/doubles.py::NullExperienceMemory` docstring'i ve `KAIZEN_HEDEF_VE_YOL_HARITASI.md`).

Bu test, `tests/*.py` dosyalarını AST ile tarayıp her `BrainManager(...)`/`KaizenBrain(...)`
çağrısının `experience_memory=` veya `brain_manager=` anahtar kelime argümanı içerdiğini
doğrular -- ileride birisi (ben dahil) yeni bir test yazıp bu enjeksiyonu unutursa, testler
BAŞARISIZ olur ve gerçek kişisel hafızaya sessizce yazan bir test tekrar sızmaz.
"""
import ast
from pathlib import Path

_GUARDED_CALLS = {"BrainManager", "KaizenBrain"}
_SAFE_KEYWORDS = {"experience_memory", "brain_manager"}
# Kasıtlı olarak GERÇEK varsayılan (deneyim hafızasız) kurulumu test eden -- yani constructor'ın
# çökmediğini kanıtlayan ama ASLA .remember_experience()/.recall_experience()/.answer() ÇAĞIRMAYAN
# -- tek satırlık kod bu işaretle muaf tutulabilir. Yeni bir muafiyet eklerken dikkat: o satırın
# ardından deneyim hafızasına dokunan hiçbir çağrı YAPILMAMALI.
_DELIBERATE_DEFAULT_MARKER = "kasıtlı varsayılan"

# Bu dosyanın kendisi ve tests/doubles.py dışında, tests/ altındaki HER .py dosyası taranır.
_TESTS_DIR = Path(__file__).resolve().parent


def _unsafe_calls_in(path):
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    unsafe = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name not in _GUARDED_CALLS:
            continue
        keywords = {kw.arg for kw in node.keywords if kw.arg}
        if keywords & _SAFE_KEYWORDS:
            continue
        line_text = lines[node.lineno - 1] if 0 < node.lineno <= len(lines) else ""
        if _DELIBERATE_DEFAULT_MARKER in line_text:
            continue
        unsafe.append(node.lineno)
    return unsafe


@__import__("unittest").skip("Retired: Cognee removed from Kaizen-1 production")
def test_experience_memory_is_never_left_to_default_in_tests():
    problems = []
    for path in sorted(_TESTS_DIR.glob("*.py")):
        if path.name in ("test_experience_memory_isolation.py", "doubles.py"):
            continue
        unsafe = _unsafe_calls_in(path)
        if unsafe:
            problems.append(f"{path.name}: satır {unsafe} -- experience_memory=/brain_manager= eksik")
    assert not problems, (
        "BrainManager()/KaizenBrain() varsayılan (GERÇEK CogneeMemory) ile kuruluyor -- "
        "kullanıcının bilgisayarında gerçek kişisel hafızaya yazabilir. "
        "tests/doubles.py::NullExperienceMemory enjekte edin:\n" + "\n".join(problems)
    )
    print("KAIZEN DENEYIM HAFIZASI IZOLASYON TESTI: BASARILI")


if __name__ == "__main__":
    test_experience_memory_is_never_left_to_default_in_tests()
