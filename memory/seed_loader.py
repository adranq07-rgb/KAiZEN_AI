"""Kaizen'e önceden öğretilen (derlenmiş) bilgileri yerel hafızaya yükler.

knowledge/*.json dosyaları elle derlenmiş ders notlarıdır (Excel işlevleri, kayıt şablonları,
Word/PDF bilgisi...). Dosya değişmedikçe tekrar yüklenmez; aynı bilgi iki kez saklanmaz.
"""
import hashlib
import json
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


def load_seeds(store, directory=None):
    directory = Path(directory or KNOWLEDGE_DIR)
    added = {}
    if not directory.exists():
        return added
    for path in sorted(directory.glob("*.json")):
        raw = path.read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        meta_key = f"seed:{path.name}"
        if store.get_meta(meta_key) == checksum:
            continue
        chunks = json.loads(raw.decode("utf-8"))
        # Dosya değiştiyse eski sürümün parçalarını kaldır; aksi halde aynı bilgi iki kez (eski+yeni) kalır
        store.remove_by_source(f"knowledge/{path.name}", "curated")
        count = 0
        for index, chunk in enumerate(chunks, start=1):
            result = store.add(
                domain=chunk["domain"], subject=chunk["subject"],
                source_path=f"knowledge/{path.name}", source_type="curated",
                section=chunk.get("section"), locator=f"kayıt {index}/{len(chunks)}",
                text=chunk["text"],
            )
            if result:
                count += 1
        store.set_meta(meta_key, checksum)
        added[path.name] = count
    return added
