"""KAIZEN Document & Office Engine — doğal dil niyet yönlendiricisi (LOCAL_ONLY).

Bir sohbet cümlesindeki YEREL dosya yolunu + işlem fiilini deterministic olarak eşler
ve documents/ops.py üzerinde çalıştırır. Kurallar:

- Belge içeriği VERI'dir; modele/provider'a ASLA gönderilmez (bu modülde model çağrısı YOK).
- Yalnız yerel dosya yolları kabul edilir; URL/belge indirme YOK (LOCAL_ONLY).
- Belge içeriğindeki metin hiçbir zaman Kaizen'e talimat olarak işlenmez
  (prompt-injection koruması: içerik yalnızca çıkış metnine 'BELGE VERİSİ' olarak konur).
- Muğlak niyetlerde needs_clarification döner; işlem uydurulmaz.

Hiçbir mevcut office_tools fonksiyonu değiştirilmemiştir; bu modül YALNIZ ekler.
"""
from __future__ import annotations

import re
from pathlib import Path

from core.text_tr import fold_tr
from documents import ops

# Yol kalıbı: 'C:\..\dosya.pdf', tırnaklı yol, ya da proje-içi göreli yol
_PATH_RE = re.compile(
    r"(?:\"([^\"]+\.(?:pdf|docx|xlsx|xlsm|xls|csv|txt|md|json|jpg|jpeg|png))\"|'([^']+\.(?:pdf|docx|xlsx|xlsm|xls|csv|txt|md|json|jpg|jpeg|png))'"
    r"|((?:[A-Za-z]:\\|\.{1,2}[\\/]|[\wçÇğĞıİöÖşŞüÜ(). \\\-]*[\\/])"
    r"[\wçÇğĞıİöÖşŞüÜ(). \\\-]+\.(?:pdf|docx|xlsx|xlsm|xls|csv|txt|md|json|jpg|jpeg|png)))",
    re.IGNORECASE,
)


def extract_document_path(message, base_dir=None):
    """Mesajdan YEREL dosya yolu çıkarır. Yoksa/URL ise None.
    Bulunan yol gerçekten var olmalı -- olmayan dosya uydurulmaz."""
    if "http://" in message.lower() or "https://" in message.lower():
        return None, "Kaizen: Belge URL'si kabul edilmez; Kaizen yalnızca yerel dosyalarla çalışır (LOCAL_ONLY)."
    match = _PATH_RE.search(message)
    if not match:
        return None, None
    raw = match.group(1) or match.group(2) or match.group(3)
    candidate = Path(raw)
    if not candidate.is_absolute():
        for root in (base_dir or Path.cwd(), Path(r"C:\Users\ANL\Desktop\KAZEN_AI"), Path.home() / "Desktop"):
            probe = (root / candidate)
            if probe.exists():
                candidate = probe
                break
    candidate = candidate.resolve()
    if not candidate.exists():
        return None, f"Kaizen: Dosya bulunamadı: {raw}"
    if candidate.suffix.lower() not in ops.SUPPORTED_READ_SUFFIXES:
        return None, f"Kaizen: Desteklenmeyen dosya türü ({candidate.suffix})."
    return candidate, None


def _wants(message_folded, *keywords):
    """Normalize edilmiş anahtar kelimeleri fold_tr ile karşılaştır."""
    folded_keywords = [fold_tr(k) for k in keywords]
    return any(k in message_folded for k in folded_keywords)


def route_document_request(message, base_dir=None):
    """Doğal dil cümlesi -> DocumentResult ya da None (document işlemi DEĞİLSE None).

    None dönmesi normal akışın (KaizenBrain zinciri) sürmesi demektir; yalnız
    mesajda (a) mevcut bir yerel belge yolu VE (b) işlem fiili birlikte varsa devralır."""
    path, error = extract_document_path(message, base_dir=base_dir)
    if error:
        folded = fold_tr(message)
        if _wants(folded, "oku", "cevir", "analiz", "duzelt", "kontrol", "goster", "ac"):
            return ops.DocumentResult("error", error)
        return None
    if path is None:
        folded = fold_tr(message)
        doc_word = _wants(folded, "pdf", "excel", "word", "docx", "csv", "fatura", "tablo")
        action = _wants(folded, "oku", "cevir", "donustur", "analiz", "cikar", "kontrol", "duzelt", "yap")
        if doc_word and action and _wants(folded, "bu ", "sunu", "su ", "asagidaki", "asagidaki"):
            return ops.DocumentResult(
                ops.NEEDS_CLARIFICATION,
                "Kaizen: Hangi dosyayı kastettiğinizi belirtin (yerel dosya yolu verin, "
                "ör. C:\\...\\dosya.pdf). Yol olmadan belge işlemi uyduramam.")
        return None
    folded = fold_tr(message)
    suffix = path.suffix.lower()

    # --- 1) Taranmış PDF düzeltme + yeni PDF -----------------------------------
    if suffix == ".pdf" and _wants(folded, "duzelt", "degistir", "yap", "guncelle") and _wants(
            folded, "tarih", "yeni pdf", "no", "adres"):
        date_match = ops._DATE_TOKEN.search(message)
        if "tarih" in folded and date_match:
            return ops.edit_scanned_pdf_field(path, "tarih", date_match.group(0))
        return ops.DocumentResult(
            ops.NEEDS_CLARIFICATION,
            "Kaizen: Hangi alanın hangi değere değiştirileceğini netleştirin "
            "(ör. 'tarihi 12.09.2026 yap'). Muğlak düzenleme yapmam.")

    # --- 1b) Fatura muhasebe analizi (AÇIK istek: "fatura muhasebe analiz") -----
    # Bu, otomatik workflow seçiminden ÖNCE kontrol edilmeli.
    if _wants(folded, "fatura") and _wants(folded, "muhasebe", "analiz"):
        if suffix not in (".pdf", ".jpg", ".jpeg", ".png"):
            return ops.DocumentResult(ops.NEEDS_CLARIFICATION,
                                      "Kaizen: Fatura analizi şu an PDF/JPG/PNG için destekleniyor; dosya PDF mi?")
        # JPG/PNG için OCR metni çıkar, PDF ise mevcut metin katmanı kullanılır
        if suffix == ".pdf":
            from tools.office_tools import pdf_oku
            text = pdf_oku(path)
        else:
            # Görsel OCR
            from tools.office_tools import _ocr_image, _ocr_settings
            from PIL import Image
            image = Image.open(str(path))
            image.load()
            settings = _ocr_settings()
            text, ocr_error = _ocr_image(image, settings)
            if ocr_error:
                return ops.DocumentResult("error", ocr_error)
        return ops.analyze_invoice(path, text=text)

    # --- 2) Otomatik workflow seçimi (normal giriş) --------------------------------
    # Kullanıcı "aynı şekilde hazırla" derse veya belge + talimat varsa, uygun workflow'u otomatik seç.
    # PDF, JPG, PNG için çalışır. JPG/PNG için OCR metni kullanılır.
    if suffix in (".pdf", ".jpg", ".jpeg", ".png") and _wants(folded, "hazırla", "çıkar", "çikar", "excel", "excele", "analiz", "özay", "özet"):
        from documents import learned_workflow
        from tools.office_tools import pdf_oku
        # JPG/PNG için OCR ile metin çıkar
        if suffix == ".pdf":
            text = pdf_oku(path)
        else:
            # Görsel OCR
            from tools.office_tools import _ocr_image, _ocr_settings
            from PIL import Image
            image = Image.open(str(path))
            image.load()
            settings = _ocr_settings()
            text, ocr_error = _ocr_image(image, settings)
            if ocr_error:
                return ops.DocumentResult("error", ocr_error)
        if not text.startswith("Kaizen:"):
            # Uygun workflow'ları bul
            applicable_workflows = []
            for wf_info in learned_workflow.list_workflows():
                wf = learned_workflow.load_workflow(wf_info["workflow_id"])
                if wf is None:
                    continue
                applicable, _ = learned_workflow.check_applicability(wf, str(path), text)
                if applicable:
                    applicable_workflows.append(wf)
            if len(applicable_workflows) == 1:
                # Tek uygun workflow — otomatik uygula
                wf = applicable_workflows[0]
                run_result = learned_workflow.run_workflow(wf, str(path), text)
                if run_result["output"]["rows"]:
                    from tools.office_tools import excel_yaz
                    target = ops._fresh_output(Path(path).stem + "_workflow", ".xlsx")
                    msg_text = excel_yaz(target, run_result["output"]["rows"], sheet="Extracted")
                    if msg_text.startswith("Kaizen: HATA"):
                        return ops.DocumentResult("error", msg_text)
                    status = "ok" if not run_result["missing_fields"] else ops.NEEDS_CLARIFICATION
                    msg = f"Kaizen: '{wf['name']}' v{wf['version']} otomatik seçildi ve uygulandı."
                    if run_result["missing_fields"]:
                        msg += f" Eksik alanlar: {', '.join(run_result['missing_fields'])}"
                    if run_result["low_confidence_fields"]:
                        msg += f" Düşük güven: {', '.join(run_result['low_confidence_fields'])}"
                    return ops.DocumentResult(status, msg, provenance=run_result["provenance"],
                                              output_path=target, data=run_result)
            elif len(applicable_workflows) > 1:
                # Birden fazla uygun workflow — kullanıcıya kısa seçim sorusu
                lines = ["Kaizen: Birden fazla uygun workflow bulundu. Hangisini uygulayayım?"]
                for i, wf in enumerate(applicable_workflows, start=1):
                    lines.append(f"  {i}. {wf['name']} (v{wf['version']}, {wf['document_type']})")
                return ops.DocumentResult(ops.NEEDS_CLARIFICATION, "\n".join(lines))
            # Uygun workflow yok — normal okuma işlemine düş

    # --- 3) PDF -> Excel (AÇIK istek: "excele çevir", "tabloya aktar") ---------------
    # Workflow seçim anahtar kelimeleri ("hazırla", "çıkar", "analiz") ile ayrılır.
    if suffix == ".pdf" and _wants(folded, "excele cevir", "excel'e cevir", "tabloya aktar", "excele donustur", "excel donustur"):
        return ops.pdf_to_excel(path)

    # --- 3b) JPG/PNG -> Excel (AÇIK istek) ------------------------------------------
    if suffix in (".jpg", ".jpeg", ".png") and _wants(folded, "excele cevir", "excel'e cevir", "tabloya aktar", "excele donustur", "excel donustur"):
        # Önce OCR metni çıkar, sonra tablo yapısı varsa Excel'e yaz
        from tools.office_tools import _ocr_image, _ocr_settings
        from PIL import Image
        image = Image.open(str(path))
        image.load()
        settings = _ocr_settings()
        text, ocr_error = _ocr_image(image, settings)
        if ocr_error:
            return ops.DocumentResult("error", ocr_error)
        # Metin tabanlı tablo çıkarma (basit)
        from tools.office_tools import excel_yaz
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        rows = [["OCR Satır", "İçerik"]]
        for ln in lines:
            rows.append(["", ln])
        target = ops._fresh_output(Path(path).stem + "_ocr_tablo", ".xlsx")
        message = excel_yaz(target, rows, sheet="OCR")
        if message.startswith("Kaizen: HATA"):
            return ops.DocumentResult("error", message)
        return ops.DocumentResult("ok", message, provenance=[f"kaynak: {path.name}", "yöntem: OCR"],
                                  output_path=target)

    # --- 4) KDV toplam kontrolü ----------------------------------------------------
    if suffix in (".xlsx", ".xlsm", ".xls", ".csv") and _wants(folded, "kdv") and _wants(
            folded, "kontrol", "toplam", "dogrula"):
        return ops.check_kdv_totals(path)

    # --- 5) Tablo analizi -> yeni xlsx ---------------------------------------------
    if suffix in (".xlsx", ".xlsm", ".xls", ".csv") and _wants(folded, "analiz", "cikar", "ozet", "aylik"):
        dimensions = []
        if _wants(folded, "aylik"):
            dimensions.append("ay")
        if _wants(folded, "musteri"):
            dimensions.append("musteri")
        if not dimensions:
            return ops.DocumentResult(
                ops.NEEDS_CLARIFICATION,
                "Kaizen: Analiz boyutunu belirtin (ör. 'aylık', 'müşteri bazlı'). "
                "Hangi sütunların toplanacağını uydurmam.")
        return ops.analyze_sheet(path, dimensions=dimensions)

    # --- 6) LearnedWorkflow uygula ---------------------------------------------------
    if _wants(folded, "workflow", "öğretilen", "learned"):
        from documents import learned_workflow
        wf_id_match = re.search(r"workflow[:\s]+(\S+)", message, re.IGNORECASE)
        if wf_id_match:
            wf_id = wf_id_match.group(1).strip("'\"")
            workflow = learned_workflow.load_workflow(wf_id)
            if workflow is None:
                return ops.DocumentResult("error", f"Kaizen: Workflow bulunamadı: {wf_id}")
            applicable, reason = learned_workflow.check_applicability(workflow, str(path))
            if not applicable:
                return ops.DocumentResult(ops.NEEDS_CLARIFICATION, f"Kaizen: Workflow uygulanamaz — {reason}")
            # Metni çıkar (workflow için) — JPG/PNG için OCR kullan
            if suffix == ".pdf":
                from tools.office_tools import pdf_oku
                text = pdf_oku(path)
            else:
                from tools.office_tools import _ocr_image, _ocr_settings
                from PIL import Image
                image = Image.open(str(path))
                image.load()
                settings = _ocr_settings()
                text, ocr_error = _ocr_image(image, settings)
                if ocr_error:
                    return ops.DocumentResult("error", ocr_error)
            run_result = learned_workflow.run_workflow(workflow, str(path), text)
            # Sonucu Excel'e yaz
            if run_result["output"]["rows"]:
                from tools.office_tools import excel_yaz
                target = ops._fresh_output(Path(path).stem + "_workflow", ".xlsx")
                message = excel_yaz(target, run_result["output"]["rows"], sheet="Extracted")
                if message.startswith("Kaizen: HATA"):
                    return ops.DocumentResult("error", message)
                status = "ok" if not run_result["missing_fields"] else ops.NEEDS_CLARIFICATION
                msg = f"Kaizen: Workflow '{workflow['name']}' v{workflow['version']} uygulandı."
                if run_result["missing_fields"]:
                    msg += f" Eksik alanlar: {', '.join(run_result['missing_fields'])}"
                if run_result["low_confidence_fields"]:
                    msg += f" Düşük güven: {', '.join(run_result['low_confidence_fields'])}"
                if run_result["validation_errors"]:
                    msg += f" Doğrulama hataları: {'; '.join(run_result['validation_errors'])}"
                return ops.DocumentResult(status, msg, provenance=run_result["provenance"],
                                          output_path=target, data=run_result)
        else:
            # Workflow listele
            from documents import learned_workflow
            workflows = learned_workflow.list_workflows()
            if workflows:
                lines = ["Kayıtlı workflow'lar:"]
                for wf in workflows:
                    lines.append(f"  {wf['workflow_id']} — {wf['name']} (v{wf['version']}, {wf['document_type']})")
                return ops.DocumentResult("ok", "\n".join(lines))
            return ops.DocumentResult("error", "Kaizen: Kayıtlı workflow yok.")

    # --- 7) Okuma (varsayılan) ------------------------------------------------------
    if _wants(folded, "oku", "icerigini", "icerigi", "goster", "ac"):
        sheet = None
        sheet_match = re.search(r"sayfa\s*[:\-]?\s*([\wçÇğĞıİöÖşŞüÜ]+)", message, re.IGNORECASE)
        if sheet_match and suffix in (".xlsx", ".xlsm", ".xls"):
            sheet = sheet_match.group(1)
        return ops.read_document(path, sheet=sheet)

    return ops.DocumentResult(
        ops.NEEDS_CLARIFICATION,
        "Kaizen: Bu dosyayla ne yapmamı istediğinizi netleştirin "
        "(ör. oku / Excel'e çevir / analiz çıkar / KDV kontrol / tarih düzelt).")


def format_document_answer(result):
    """DocumentResult -> kullanıcı cevabı. Belge çıktıları VERİ olarak işaretlenir."""
    if result.status == ops.NEEDS_CLARIFICATION:
        return result.message
    lines = [result.message]
    if result.provenance:
        lines.append("KAYNAK KONUMU: " + " | ".join(result.provenance))
    if result.output_path:
        lines.append(f"ÇIKTI DOSYASI: {result.output_path} (orijinal dosya korunur)")
    return "\n".join(lines)
