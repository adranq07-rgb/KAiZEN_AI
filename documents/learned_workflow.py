"""
LearnedWorkflow — Teach-Once → Reuse sistemi (LOCAL_ONLY).

LAB'deki learned_workflow_spec.json şemasını production'a uygular:
- Workflow kaydetme/yükleme (JSON, UTF-8)
- Uygulanabilirlik kontrolü (applicability_conditions)
- Extraction rules çalıştırma (anchor_word, regex, table_column)
- Normalization + validation kuralları
- Kullanıcı düzeltme döngüsü (correction_log, feedback_loop)
- Provenance politikası (kaynak dosya, sayfa, bölge)

Tüm işlemler yereldir; belge içeriği modele/provider'a GÖNDERİLMEZ.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from core.text_tr import fold_tr


# ---------------------------------------------------------------- storage ----------

def workflow_dir():
    """Workflow depolama dizini (outputs/ altında)."""
    root = Path(r"C:\Users\ANL\Desktop\KAZEN_AI") / "outputs" / "workflows"
    root.mkdir(parents=True, exist_ok=True)
    return root


def list_workflows():
    """Kayıtlı tüm workflow'ları listeler."""
    dir_path = workflow_dir()
    if not dir_path.exists():
        return []
    result = []
    for f in sorted(dir_path.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result.append({
                "workflow_id": data.get("workflow_id"),
                "name": data.get("name"),
                "version": data.get("version"),
                "document_type": data.get("document_type"),
                "file": str(f),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return result


def save_workflow(workflow: dict) -> Path:
    """Workflow'u JSON olarak kaydeder (UTF-8, ensure_ascii=False).

    version artırılır; workflow_id yoksa üretilir. Mevcut sürüm korunur
    (üzerine yazılmaz — yeni sürüm olarak kaydedilir)."""
    if "workflow_id" not in workflow or not workflow["workflow_id"]:
        workflow["workflow_id"] = str(uuid.uuid4())
    workflow["version"] = workflow.get("version", 0) + 1
    workflow["updated_at"] = datetime.now(timezone.utc).isoformat()
    if "created_at" not in workflow:
        workflow["created_at"] = workflow["updated_at"]

    path = workflow_dir() / f"{workflow['workflow_id']}_v{workflow['version']}.json"
    path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_workflow(workflow_id: str, version: int | None = None) -> dict | None:
    """Workflow'u yükler. version=None ise en yeni sürümü yükler."""
    dir_path = workflow_dir()
    if not dir_path.exists():
        return None
    if version is not None:
        path = dir_path / f"{workflow_id}_v{version}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    # En yeni sürümü bul
    pattern = f"{workflow_id}_v*.json"
    versions = []
    for f in dir_path.glob(pattern):
        m = re.search(r"_v(\d+)\.json$", f.name)
        if m:
            versions.append((int(m.group(1)), f))
    if not versions:
        return None
    versions.sort(key=lambda x: x[0], reverse=True)
    return json.loads(versions[0][1].read_text(encoding="utf-8"))


# ---------------------------------------------------------------- applicability ---

def check_applicability(workflow: dict, file_path: str, text: str = "") -> tuple[bool, str]:
    """Workflow'nin bu belgeye uygulanıp uygulanamayacağını kontrol eder.

    Returns: (applicable, reason) — applicable=False ise reason açıklama içerir."""
    cond = workflow.get("applicability_conditions", {})
    path = Path(file_path)

    # File type kontrolü
    allowed_types = cond.get("file_types", [])
    if allowed_types and path.suffix.lower().lstrip(".") not in allowed_types:
        return False, f"Dosya türü '{path.suffix}' workflow için uygun değil (izin verilen: {', '.join(allowed_types)})"

    # Sayfa sayısı kontrolü
    page_range = cond.get("page_count_range", {})
    if page_range and path.suffix.lower() == ".pdf":
        min_pages = page_range.get("min")
        max_pages = page_range.get("max")
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            page_count = len(reader.pages)
            if min_pages is not None and page_count < min_pages:
                return False, f"PDF {page_count} sayfa; workflow en az {min_pages} sayfa gerektiriyor"
            if max_pages is not None and page_count > max_pages:
                return False, f"PDF {page_count} sayfa; workflow en fazla {max_pages} sayfa destekliyor"
        except Exception:
            pass  # Sayfa sayısı okunamadırsa devam et

    # Header keywords kontrolü
    header_keywords = cond.get("header_keywords", [])
    if header_keywords and text:
        folded = fold_tr(text[:2000])  # İlk 2000 karakter yeterli
        if not any(fold_tr(kw) in folded for kw in header_keywords):
            return False, f"Belge başlığında workflow anahtar kelimeleri bulunamadı: {', '.join(header_keywords)}"

    return True, "Uygun"


# ---------------------------------------------------------------- extraction ------

def _apply_normalization(value: Any, rules: list[dict]) -> Any:
    """Normalization kurallarını uygular."""
    result = value
    for rule in rules:
        field_name = rule.get("field_name", "*")
        if field_name != "*" and field_name != "_current_field":
            continue
        transform = rule.get("transform", "")
        params = rule.get("parameters", {})
        if transform == "trim" and isinstance(result, str):
            result = result.strip()
        elif transform == "uppercase" and isinstance(result, str):
            result = result.upper()
        elif transform == "lowercase" and isinstance(result, str):
            result = result.lower()
        elif transform == "number_parse" and isinstance(result, str):
            text = result.strip()
            if params.get("decimal_separator") == ",":
                text = text.replace(".", "").replace(",", ".")
            try:
                result = Decimal(text)
            except (InvalidOperation, ValueError):
                pass
        elif transform == "currency_parse" and isinstance(result, str):
            text = result.strip()
            currency = params.get("currency", "TRY")
            text = text.replace("TL", "").replace("₺", "").replace(currency, "").strip()
            if params.get("decimal_separator") == ",":
                text = text.replace(".", "").replace(",", ".")
            try:
                result = Decimal(text)
            except (InvalidOperation, ValueError):
                pass
        elif transform == "date_parse" and isinstance(result, str):
            # Türkçe tarih formatı: DD.MM.YYYY
            m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", result)
            if m:
                result = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return result


def _extract_field(rule: dict, text: str, page_texts: dict[int, str], 
                   correction_rules: list[dict] = None, source_file: str = "") -> dict:
    """Tek bir extraction rule'u çalıştırır.

    Returns: {field_name, value, confidence, source_page, source_region, raw_text}
    """
    field_name = rule.get("field_name", "")
    method = rule.get("extraction_method", "")
    anchors = rule.get("anchor_keywords", [])
    pattern = rule.get("pattern", "")
    source_region = rule.get("source_region", "")
    threshold = rule.get("confidence_threshold", 0.7)

    value = None
    confidence = 0.0
    source_page = None
    raw_text = ""

    # Hangi sayfaları tarayacağımızı belirle
    pages_to_search = list(page_texts.values()) if page_texts else [text]

    for page_num, page_text in enumerate(pages_to_search, start=1):
        if method == "anchor_word" and anchors:
            for anchor in anchors:
                # Orijinal metinde case-insensitive ara (folded offset hatasını önler)
                pattern = re.compile(re.escape(anchor), re.IGNORECASE)
                m = pattern.search(page_text)
                if m:
                    after = page_text[m.end():].strip()
                    val_match = re.match(r"[\s:]*([^\n]+)", after)
                    if val_match:
                        value = val_match.group(1).strip()
                        confidence = 0.85
                        source_page = page_num
                        raw_text = page_text[max(0, m.start() - 20):m.end() + len(value) + 20]
                        break
            if value is not None:
                break

        elif method == "regex" and pattern:
            m = re.search(pattern, page_text, re.IGNORECASE)
            if m:
                value = m.group(1) if m.groups() else m.group(0)
                confidence = 0.75
                source_page = page_num
                raw_text = m.group(0)
                break

        elif method == "llm_prompt":
            # LLM prompt yöntemi: şimdilik uygulanmadı olarak işaretle
            confidence = 0.0
            break

    # Şablon-spesifik düzeltme kurallarını uygula (sonraki faturalara sabit değer taşıma)
    if value is not None and correction_rules:
        for corr in correction_rules:
            if corr.get("field_name") == field_name:
                # Anchor bağlamı eşleşiyorsa ve kaynak dosya deseni uyuyorsa
                anchor_ctx = corr.get("anchor_context", [])
                if anchor_ctx and any(a in anchors for a in anchor_ctx):
                    # Bu şablon için geçerli düzeltme — değeri sabit olarak değiştir
                    value = corr["new_value"]
                    confidence = max(confidence, 0.95)  # kullanıcı onaylı değer = yüksek güven
                    raw_text += f" [DÜZELTİLDİ: {corr['old_value']} -> {corr['new_value']}]"
                    break
                # Kaynak dosya deseni eşleşiyorsa (aynı şablon dosyası)
                elif corr.get("source_file_pattern") and corr["source_file_pattern"] in source_file:
                    value = corr["new_value"]
                    confidence = max(confidence, 0.95)
                    raw_text += f" [DÜZELTİLDİ: {corr['old_value']} -> {corr['new_value']}]"
                    break

    return {
        "field_name": field_name,
        "value": value,
        "confidence": confidence,
        "source_page": source_page,
        "source_region": source_region,
        "raw_text": raw_text,
        "threshold": threshold,
    }


def run_workflow(workflow: dict, file_path: str, text: str = "") -> dict:
    """Workflow'u belgede çalıştırır.

    Returns: {
        "workflow_id", "workflow_name", "version",
        "fields": {field_name: {value, confidence, source_page, ...}},
        "missing_fields": [...],
        "low_confidence_fields": [...],
        "validation_errors": [...],
        "validation_warnings": [...],
        "provenance": [...],
        "output": {sheet_data, ...},
    }
    """
    path = Path(file_path)
    extraction_rules = workflow.get("extraction_rules", [])
    normalization_rules = workflow.get("normalization_rules", [])
    validation_rules = workflow.get("validation_rules", [])
    output_schema = workflow.get("output_schema", {})
    confidence_policy = workflow.get("confidence_policy", {})
    provenance_policy = workflow.get("provenance_policy", {})

    # Sayfa bazlı metin (provenance için)
    page_texts = {}
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            for i, page in enumerate(reader.pages, start=1):
                try:
                    t = page.extract_text(extraction_mode="layout") or ""
                except TypeError:
                    t = page.extract_text() or ""
                page_texts[i] = t
        except Exception:
            pass
    if not page_texts:
        page_texts = {1: text}

    # Extraction
    # Şablon-spesifik düzeltme kurallarını al
    corrections = workflow.get("user_corrections", {})
    correction_rules = corrections.get("correction_rules", [])
    fields = {}
    missing_fields = []
    low_confidence_fields = []

    for rule in extraction_rules:
        result = _extract_field(rule, text, page_texts, correction_rules, path.name)
        field_name = result["field_name"]

        # Normalization uygula
        if result["value"] is not None:
            result["value"] = _apply_normalization(result["value"], normalization_rules)

        fields[field_name] = result

        if result["value"] is None:
            if rule.get("required", False):
                missing_fields.append(field_name)
        elif result["confidence"] < result["threshold"]:
            low_confidence_fields.append(field_name)

    # Validation
    validation_errors = []
    validation_warnings = []
    for vrule in validation_rules:
        condition = vrule.get("condition", "")
        severity = vrule.get("severity", "warning")
        # Basit validation: subtotal + tax == total
        if "subtotal + vat_amount - total_amount" in condition or "subtotal + tax == total" in condition:
            subtotal = fields.get("subtotal", {}).get("value")
            vat = fields.get("vat_amount", {}).get("value")
            total = fields.get("total_amount", {}).get("value")
            if subtotal is not None and vat is not None and total is not None:
                try:
                    s = Decimal(str(subtotal)) if not isinstance(subtotal, Decimal) else subtotal
                    v = Decimal(str(vat)) if not isinstance(vat, Decimal) else vat
                    t = Decimal(str(total)) if not isinstance(total, Decimal) else total
                    if abs(s + v - t) >= Decimal("0.02"):
                        msg = f"Toplam uyumsuzluk: {s} + {v} = {s+v} ≠ {t}"
                        if severity == "error":
                            validation_errors.append(msg)
                        else:
                            validation_warnings.append(msg)
                except (InvalidOperation, ValueError):
                    pass

    # Provenance
    provenance = [f"kaynak: {path.name}"]
    if provenance_policy.get("retain_page_number", True):
        for fname, fdata in fields.items():
            if fdata.get("source_page"):
                provenance.append(f"{fname}: sayfa {fdata['source_page']}")
    if provenance_policy.get("retain_source_file", True):
        provenance.append(f"dosya: {path.name}")

    # Output sheet data
    columns = output_schema.get("columns", list(fields.keys()))
    sheet_rows = [columns]
    row_data = []
    for col in columns:
        if col in fields:
            val = fields[col]["value"]
            row_data.append(str(val) if val is not None else "")
        elif col == "source_file":
            row_data.append(path.name)
        elif col == "page_number":
            row_data.append(str(next((f["source_page"] for f in fields.values() if f.get("source_page")), "")))
        elif col == "extraction_confidence":
            confidences = [f["confidence"] for f in fields.values() if f.get("confidence", 0) > 0]
            row_data.append(f"{min(confidences):.2f}" if confidences else "")
        elif col == "review_status":
            if missing_fields:
                row_data.append("EKSİK_ALAN")
            elif low_confidence_fields:
                row_data.append("İNCELEME_GEREKLİ")
            else:
                row_data.append("TAMAM")
        else:
            row_data.append("")
    sheet_rows.append(row_data)

    return {
        "workflow_id": workflow.get("workflow_id"),
        "workflow_name": workflow.get("name"),
        "version": workflow.get("version"),
        "fields": fields,
        "missing_fields": missing_fields,
        "low_confidence_fields": low_confidence_fields,
        "validation_errors": validation_errors,
        "validation_warnings": validation_warnings,
        "provenance": provenance,
        "output": {
            "format": output_schema.get("format", "xlsx"),
            "sheets": output_schema.get("sheets", ["Extracted"]),
            "rows": sheet_rows,
        },
    }


# ---------------------------------------------------------------- corrections -----

def apply_correction(workflow: dict, field_name: str, old_value: str, new_value: str,
                     user_id: str = "user", source_file: str = "") -> dict:
    """Kullanıcı düzeltmesini workflow'e uygular ve yeni sürüm olarak kaydeder.

    - correction_log'a ekler (kaynak dosya ve alanla ilişkilendirilir)
    - feedback_loop=True ise extraction_rule'u GÜNCELLEMEZ (şablon-spesifik düzeltme için
      correction_rules listesi kullanılır; synonyms'e sabit değer EKLENMEZ).
    - Yeni sürüm olarak kaydeder (mevcut sürüm korunur)
    """
    corrections = workflow.setdefault("user_corrections", {})
    log = corrections.setdefault("correction_log", [])
    log.append({
        "field_name": field_name,
        "old_value": old_value,
        "new_value": new_value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "source_file": source_file,
    })

    # Feedback loop: artık synonyms'e EKLEMEYİZ (global yayılmayı önler).
    # Bunun yerine correction_rules listesine şablon-spesifik kural eklenir.
    if corrections.get("feedback_loop", False):
        # Mevcut extraction rule'unu bul
        target_rule = None
        for rule in workflow.get("extraction_rules", []):
            if rule.get("field_name") == field_name:
                target_rule = rule
                break
        
        if target_rule:
            # Şablon-spesifik düzeltme kuralı oluştur
            correction_rule = {
                "field_name": field_name,
                "source_file_pattern": source_file,  # hangi dosya desenine uygulanır
                "old_value": old_value,
                "new_value": new_value,
                "anchor_context": target_rule.get("anchor_keywords", []),  # anchor bağlamı
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            corrections.setdefault("correction_rules", []).append(correction_rule)

    return workflow


def apply_correction_scoped(field_name: str, old_value: str, new_value: str,
                            workflow_ids: list[str], user_id: str = "user",
                            source_file: str = "") -> int:
    """Düzeltmeyi YALNIZCA belirtilen workflow'lara uygular (kullanıcı onayı gerektirir).

    Args:
        workflow_ids: Düzeltmenin uygulanacağı workflow ID listesi
        field_name: Düzeltilecek alan adı
        old_value: Eski değer
        new_value: Yeni değer
        user_id: Kullanıcı kimliği
        source_file: Kaynak dosya

    Returns: Güncellenen workflow sayısı.
    """
    count = 0
    for wf_id in workflow_ids:
        wf = load_workflow(wf_id)
        if wf is None:
            continue
        has_field = any(r.get("field_name") == field_name for r in wf.get("extraction_rules", []))
        if has_field:
            apply_correction(wf, field_name, old_value, new_value, user_id=user_id,
                             source_file=source_file)
            save_workflow(wf)
            count += 1
    return count


# ---------------------------------------------------------------- fallback --------

def pdf_to_excel_with_fallback(path: str, sheet_name: str = "PDF") -> dict:
    """PDF → Excel: önce pypdf (mevcut), başarısızsa pdfplumber/tabula fallback.

    Returns: DocumentResult (documents/ops.py ile uyumlu)
    """
    from documents import ops

    # 1) Mevcut pypdf yolu
    result = ops.pdf_to_excel(path, sheet_name=sheet_name)
    if result.ok:
        return {"method": "pypdf", "result": result}

    # 2) Fallback: pdfplumber + tabula (LAB adapter mantığı, lazy import)
    try:
        import pdfplumber
    except ImportError:
        return {
            "method": "pypdf",
            "result": result,  # Orijinal hata korunur
            "fallback_error": "pdfplumber kurulu değil; fallback atlandı",
        }

    try:
        import tabula
    except ImportError:
        tabula = None

    path_obj = Path(path)
    out_rows = [["PDF Sayfa", "Sütun 1", "Sütun 2", "Sütun 3", "Sütun 4", "Sütun 5"]]
    structure_found = False

    with pdfplumber.open(str(path_obj)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # Önce pdfplumber ile tablo çıkarmayı dene
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for row in table:
                        cells = [str(c).strip() if c else "" for c in row]
                        if len(cells) >= 2:
                            structure_found = True
                        out_rows.append([f"s.{page_num}"] + cells[:5] + [""] * (5 - min(len(cells), 5)))

            # Tablo bulunamadıysa metin tabanlı dene
            if not tables:
                text = page.extract_text() or ""
                lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
                for ln in lines:
                    cells = [c.strip() for c in re.split(r"\s{2,}|\t", ln) if c.strip()]
                    if len(cells) >= 2:
                        structure_found = True
                    out_rows.append([f"s.{page_num}"] + cells[:5] + [""] * (5 - min(len(cells), 5)))

    # Tabula fallback (pdfplumber yetersizse)
    if not structure_found and tabula is not None:
        try:
            dfs = tabula.read_pdf(str(path_obj), pages="all", multiple_tables=True)
            for i, df in enumerate(dfs):
                for _, row in df.iterrows():
                    cells = [str(v).strip() for v in row.values]
                    if len(cells) >= 2:
                        structure_found = True
                    out_rows.append([f"s.tabula_{i+1}"] + cells[:5] + [""] * (5 - min(len(cells), 5)))
        except Exception:
            pass

    if len(out_rows) == 1 or not structure_found:
        return {
            "method": "pdfplumber+tabula",
            "result": result,  # Orijinal hata korunur
            "fallback_error": "pdfplumber/tabula ile de tablo yapısı çıkarılamadı",
        }

    from tools.office_tools import excel_yaz
    target = ops._fresh_output(path_obj.stem + "_tablo_fallback", ".xlsx")
    message = excel_yaz(target, out_rows, sheet=sheet_name)
    if message.startswith("Kaizen: HATA"):
        return {
            "method": "pdfplumber+tabula",
            "result": ops.DocumentResult("error", message),
            "fallback_error": message,
        }
    return {
        "method": "pdfplumber+tabula",
        "result": ops.DocumentResult(
            "ok", message,
            provenance=[f"kaynak: {path_obj.name}", "fallback: pdfplumber+tabula"],
            output_path=target,
            data={"rows": len(out_rows) - 1, "fallback": True},
        ),
    }
