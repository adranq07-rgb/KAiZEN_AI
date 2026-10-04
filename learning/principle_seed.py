"""KAIZEN — Learning Brain v1: başlangıç principle set'ini (madde 6) yükler.

`knowledge/principles/principles_seed.json`, memory/seed_loader.py'nin knowledge/*.json
deseniyle AYNI ruhta AMA AYRI bir dosyadır (LearningStore'un ders-notu parçalarıyla
KARIŞTIRILMAZ -- madde 5/23: principle registry, learning_store'dan ayrı bir depo).
BİLEREK `knowledge/` KÖKÜNDE DEĞİL bir alt klasörde tutulur: `memory/seed_loader.py::
load_seeds()` yalnız `knowledge/*.json`'u (alt klasörsüz, tek seviye glob) tarar --
dosya kökte olsaydı LearningStore onu (tamamen farklı bir şema ile: subject/text yok)
yutmaya çalışıp KeyError ile 161 testlik regresyonu kırardı (bu, ilk denemede
YAKALANIP DÜZELTİLDİ). Yalnızca 7 küratörlü ilke içerir (madde 6: "sistem kendi
kendine yüzlerce ilke üretmeye başlamasın"); her satırın `source` alanı hangi mevcut
knowledge/*.json bölümünden türetildiğini açıkça belirtir (madde 15: insan tarafından
denetlenebilir provenance).
"""
import json
from pathlib import Path

PRINCIPLES_SEED_PATH = (
    Path(__file__).resolve().parent.parent / "knowledge" / "principles" / "principles_seed.json"
)


def load_principle_seeds(registry, path=None):
    """Idempotent: aynı principle_id ile tekrar çağrılırsa upsert eder (üstüne yazar),
    çoğaltmaz. `status` alanı JSON'da yoksa registry'nin varsayılanı (STATUS_ACTIVE)
    kullanılır."""
    path = Path(path or PRINCIPLES_SEED_PATH)
    if not path.exists():
        return 0
    rows = json.loads(path.read_text(encoding="utf-8"))
    count = 0
    for row in rows:
        kwargs = dict(row)
        registry.upsert(**kwargs)
        count += 1
    return count
