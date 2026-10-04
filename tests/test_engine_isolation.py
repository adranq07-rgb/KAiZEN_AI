"""Statik güvenlik ağı: bir test dosyası `KaizenEngine(...)` kurarken `data_dir=` GEÇMEZSE,
motor varsayılan olarak GERÇEK `data/` ve `logs/` dizinlerini (ve config/Kaizen.json'dan
seçilen GERÇEK Hermes/yerel model provider'ını) kullanır. Bulut ortamında bu genelde
zararsızdır, ama kullanıcının kendi bilgisayarında bu, testlerin gerçek `kaizen_learning.sqlite3`,
`accounting_knowledge.sqlite3`, `accounting_learning.json`, `kaizen_memory.json`,
`auto_exam_candidates.jsonl` dosyalarına ve gerçek `logs/kaizen.log`'a yazması demektir --
tam da `tests/test_core.py`'nin şimdi engellediği durum (bkz. o dosyadaki `_snapshot`/kabul
ölçütü kontrolü).

Bu test, `tests/*.py` dosyalarını AST ile tarayıp her `KaizenEngine(...)` çağrısının
`data_dir=` anahtar kelime argümanı içerdiğini doğrular -- ileride birisi (ben dahil) yeni
bir test yazıp bu enjeksiyonu unutursa, testler BAŞARISIZ olur ve gerçek kullanıcı ortamına
sessizce yazan bir test tekrar sızmaz.

Not: `main.py` ve `desktop_app.py`'deki (tests/ dışındaki) parametresiz `KaizenEngine()`
çağrıları bilerek muaf -- onlar normal kullanım, oradaki varsayılan (gerçek dizinler/gerçek
provider) davranış tam olarak istenen şey.
"""
import ast
from pathlib import Path

_GUARDED_CALLS = {"KaizenEngine"}
_SAFE_KEYWORDS = {"data_dir"}

_TESTS_DIR = Path(__file__).resolve().parent


def _unsafe_calls_in(path):
    source = path.read_text(encoding="utf-8")
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
        unsafe.append(node.lineno)
    return unsafe


def test_engine_is_never_left_to_default_data_dir_in_tests():
    problems = []
    for path in sorted(_TESTS_DIR.glob("*.py")):
        if path.name == "test_engine_isolation.py":
            continue
        unsafe = _unsafe_calls_in(path)
        if unsafe:
            problems.append(f"{path.name}: satır {unsafe} -- data_dir= eksik")
    assert not problems, (
        "KaizenEngine() varsayılan (GERÇEK data/logs dizinleri + GERÇEK provider) ile "
        "kuruluyor -- kullanıcının bilgisayarında gerçek dosyalara yazabilir ve gerçek "
        "model/ağ çağrısı yapabilir. data_dir=<gecici klasör> (ve mümkünse "
        "provider=OfflineProvider()) enjekte edin:\n" + "\n".join(problems)
    )
    print("KAIZEN ENGINE IZOLASYON TESTI: BASARILI")


if __name__ == "__main__":
    test_engine_is_never_left_to_default_data_dir_in_tests()
