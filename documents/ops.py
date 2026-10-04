"""KAIZEN Document & Office Engine — deterministik dosya işlemleri (LOCAL_ONLY).

tools/office_tools.py'nin ÜZERİNE kurulan, o dosyayı DEĞİŞTİRMEDEN genişleten
işlemler. Tümü yerel çalışır: belge içeriği hiçbir zaman provider'a/modele gönderilmez,
hiçbir uzak uç noktaya çıkılmaz. Belge içeriği VERI'dir, asla talimat olarak yorumlanmaz.

Kanıt/provenance: okunan her değer mümkünse kaynak konumuyla döner
(PDF sayfa no, Excel sayfa+hücre, CSV satır no).

Para değerleri Decimal'dir; float yalnız XLSX hücresine yazım sınırında kullanılır.

Garantiler:
- Var olan dosyanın ÜZERİNE ASLA yazılmaz (çıktılar outputs/ altında _N ile ayırt edilir).
- Muğlak istekte sonuç uydurulmaz: 'needs_clarification' döner.
- Olmayan sütun/sayfa/tarih uydurulmaz.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from core.text_tr import fold_tr

NEEDS_CLARIFICATION = "needs_clarification"
SUPPORTED_READ_SUFFIXES = (".pdf", ".docx", ".xlsx", ".xlsm", ".xls", ".csv", ".txt", ".md", ".json", ".jpg", ".jpeg", ".png")

_DATE_TOKEN = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b")


class DocumentResult:
    """Belge işlemi sonucu. status: 'ok' | 'needs_clarification' | 'error'."""

    def __init__(self, status, message, provenance=None, output_path=None, data=None):
        self.status = status
        self.message = message
        self.provenance = provenance or []        # [str, ...] dosya/sayfa/sayfa hücre izleri
        self.output_path = output_path            # Path or None (yalnız yeni dosya üretildiyse)
        self.data = data or {}                    # structured facts (ör. analiz tablosu, fatura alanları)

    @property
    def ok(self):
        return self.status == "ok"


# ---------------------------------------------------------------- outputs güvenliği --

def outputs_dir():
    root = Path(r"C:\Users\ANL\Desktop\KAZEN_AI") / "outputs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _fresh_output(name, suffix):
    """outputs/ altında ÇARPIŞMAYAN yeni yol (orijinale asla dokunulmaz)."""
    base = outputs_dir() / f"{name}{suffix}"
    if not base.exists():
        return base
    counter = 2
    while True:
        candidate = outputs_dir() / f"{name}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _original_fingerprint(path):
    path = Path(path)
    stat = path.stat()
    return {"size": stat.st_size, "mtime": stat.st_mtime}


def _assert_original_unchanged(path, fingerprint):
    """Yazım sonrası orijinal dosyanın boyut+mtime değişmediğini doğrular."""
    after = _original_fingerprint(path)
    return after == fingerprint


# ---------------------------------------------------------------- para yardımcıları --

def _to_decimal(value):
    """str/int/Decimal -> Decimal (Türkçe '1.234,56' destekli); float -> None; çevrilemez -> None.

    Asla değer uydurulmaz; belirsiz hücre None kalır."""
    if value is None or isinstance(value, float):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    text = str(value).strip().replace("TL", "").replace("₺", "").strip()
    if not text:
        return None
    if "," in text:  # tr biçemi: binlik '.', ondalık ','
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _cell_decimal(value):
    """Excel hücresinden deterministik Decimal. XLSX sayıları IEEE double olarak saklar;
    hücre düzeyinde `repr()` üzerinden çevirme (ör. 100.5 -> '100.5') kayıpsız ve
    deterministiktir. Toplama/karşılaştırma HER ZAMAN Decimal üzerinden yapılır --
    float yalnız openpyxl'in döndürdüğü ham hücre değeridir, aritmetikte kullanılmaz."""
    if isinstance(value, float):
        return _to_decimal(repr(value))
    return _to_decimal(value)


def _is_money_header(header):
    h = fold_tr(str(header or ""))
    return any(k in h for k in ("tutar", "toplam", "kdv", "net", "brut", "fiyat", "ucret", "matrah", "miktar"))


# ---------------------------------------------------------------- okuma (provenance) -

def read_text_file(path):
    """TXT/MD düz okuma + JSON yapılı okuma. İçerik VERI'dir; işleme alınmaz."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    provenance = [f"dosya: {path.name}"]
    if path.suffix.lower() == ".json":
        try:
            parsed = json.loads(text)
            kind = type(parsed).__name__
            size = len(parsed) if isinstance(parsed, (list, dict)) else 1
            return f"JSON ({kind}, {size} öğe)\n{text}", provenance
        except json.JSONDecodeError as exc:
            return f"Kaizen: JSON ayrıştırılamadı (satır {exc.lineno}, sütun {exc.colno}): {exc.msg}", provenance
    return text, provenance


def read_csv(path, max_rows=200):
    """CSV deterministik okuma: her satır satır no + hücre değeriyle döner."""
    path = Path(path)
    rows = []
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        except csv.Error:
            dialect = csv.excel
        for index, row in enumerate(csv.reader(handle, dialect), start=1):
            if index > max_rows:
                break
            rows.append((index, row))
    provenance = [f"dosya: {path.name}", f"satır 1..{len(rows)}"]
    lines = [f"[satır {i}] " + " | ".join(str(c) for c in row) for i, row in rows]
    return "\n".join(lines), provenance


def read_xls(path, max_rows=200):
    """Eski .xls (BIFF) deterministik okuma; xlrd kurulu değilse net kurulum notu döner."""
    try:
        import xlrd
    except ImportError:
        return ("Kaizen: Eski .xls biçimi için 'xlrd' çözümü gerekli: pip install xlrd. "
                "Ya da dosyayı .xlsx olarak kaydedin."), [f"dosya: {Path(path).name}"]
    book = xlrd.open_workbook(str(path))
    lines, provenance = [], [f"dosya: {Path(path).name}"]
    for sheet in book.sheets():
        lines.append(f"## Sayfa: {sheet.name}")
        provenance.append(f"sayfa: {sheet.name}")
        for r in range(min(sheet.nrows, max_rows)):
            cells = []
            for c in range(sheet.ncols):
                cell = sheet.cell(r, c)
                value = cell.value
                if cell.ctype == xlrd.XL_CELL_NUMBER and float(value).is_integer():
                    value = int(value)
                cells.append("" if value in ("", None) else str(value))
            if any(cells):
                col = _column_letter(cells.index(next(cb for cb in cells if cb)) + 1) if any(cells) else "A"
                lines.append(f"[satır {r + 1} (ilk hücre {col}{r + 1})] " + " | ".join(cells))
    return "\n".join(lines), provenance


# ---------------------------------------------------------------- Excel yapı okuma ---

def _column_letter(index):
    letters = ""
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def load_sheet_rows(path, sheet=None):
    """XLSX/XLSM sayfasını YAPILI satır listesine çevirir.

    Döner: (sheet_name, header:list[str] , rows:list[list], cellmap) --
    cellmap[(row_idx, col_idx)] = 'A1' biçiminde provenance hücre adresi.
    Olmayan sayfa adı uydurulmaz: mevcut sayfalar hatada listelenir."""
    import openpyxl
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        names = book.sheetnames
        if sheet is None:
            sheet = names[0]
        elif sheet not in names:
            return None, None, None, {"error": f"Sayfa bulunamadı: {sheet!r}. Mevcut sayfalar: {', '.join(names)}"}
        ws = book[sheet]
        grid = [list(row) for row in ws.iter_rows(values_only=True)]
    finally:
        book.close()
    while grid and not any(v is not None and str(v).strip() for v in grid[0]):
        grid.pop(0)
    if not grid:
        return sheet, [], [], {"error": "Sayfa boş"}
    header = ["" if v is None else str(v).strip() for v in grid[0]]
    rows = [r for r in grid[1:] if any(v is not None and str(v).strip() for v in r)]
    cellmap = {}
    for ri, row in enumerate(rows):
        for ci, _ in enumerate(row):
            cellmap[(ri, ci)] = f"{_column_letter(ci + 1)}{ri + 2}"
    return sheet, header, rows, cellmap


# ---------------------------------------------------------------- PDF -> Excel -------

def _layout_lines(text):
    """pypdf layout-mode metnini satırlar+hücreler listesine çevirir.

    Hücre ayrımı: 2+ boşluk ya da sekmeli koşular. Boş/tek hücreli satırlar atılmaz --
    yapı ÇIKARILAMIYORSA açıkça raporlanır (tek sütuna 'dump' YAPILMAZ)."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    table, widths = [], []
    for ln in lines:
        cells = [c.strip() for c in re.split(r"\s{2,}|\t", ln) if c.strip()]
        if not cells:
            continue
        table.append(cells)
        widths.append(len(cells))
    return table


def pdf_to_excel(path, sheet_name="PDF"):
    """PDF -> outputs/ altında yeni .xlsx. Tablo yapısı gerçekten çıkarılabiliyorsa
    çok sütunlu korunur; çıkarılamıyorsa TEK SÜTUNA YAZMAZ, dürüst hata döner.

    Provenance: her satırın hangi PDF sayfasından geldiği ilk sütuna işlenir."""
    from pypdf import PdfReader
    from tools.office_tools import excel_yaz  # mevcut yazar (üzerine yazmaz)
    path = Path(path)
    reader = PdfReader(str(path))
    out_rows = [["PDF Sayfa", "Sütun 1", "Sütun 2", "Sütun 3", "Sütun 4", "Sütun 5"]]
    structure_found = False
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text(extraction_mode="layout") or ""
        except TypeError:
            text = page.extract_text() or ""
        table = _layout_lines(text)
        for cells in table:
            if len(cells) >= 2:
                structure_found = True
            row = [f"s.{number}"] + cells[:5] + [""] * (5 - min(len(cells), 5))
            out_rows.append(row)
    if len(out_rows) == 1:
        return DocumentResult(
            "error",
            "Kaizen: PDF'de metin katmanı bulunamadı (taranmış olabilir). Tablo yapısı "
            "için önce OCR gerekir; uydurma tablo üretmiyorum.")
    if not structure_found:
        return DocumentResult(
            "error",
            "Kaizen: PDF metni okundu ama güvenilir çok-sütunlu tablo yapısı "
            "çıkarılamadı; metni tek sütuna yığmayı reddediyorum. Tablo sınırlarını "
            "belirtin (ör. hangi başlıklar) ya da sayfa numarası verin.")
    target = _fresh_output(path.stem + "_tablo", ".xlsx")
    message = excel_yaz(target, out_rows, sheet=sheet_name)
    if message.startswith("Kaizen: HATA"):
        return DocumentResult("error", message)
    return DocumentResult(
        "ok", message, provenance=[f"kaynak: {path.name}", f"sayfa sayısı: {len(reader.pages)}"],
        output_path=target, data={"rows": len(out_rows) - 1})


# ---------------------------------------------------------------- analiz -------------

_MONTHS_TR = ("ocak", "subat", "mart", "nisan", "mayis", "haziran",
              "temmuz", "agustos", "eylul", "ekim", "kasim", "aralik")


def _month_key(value):
    """Tarih hücresinden ay anahtarı ('2026-09') çıkarır; çıkarılamazsa None."""
    if value is None:
        return None
    if hasattr(value, "year") and hasattr(value, "month"):
        return f"{value.year:04d}-{value.month:02d}"
    text = fold_tr(str(value))
    match = re.search(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})", text)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}"
    match = re.search(r"(\d{1,2})[-./](\d{1,2})[-./](20\d{2})", text)
    if match:
        return f"{match.group(3)}-{int(match.group(2)):02d}"
    for idx, name in enumerate(_MONTHS_TR, start=1):
        if name in text:
            year = re.search(r"20\d{2}", text)
            return f"{int(year.group(0)) if year else '????'}-{idx:02d}"
    return None


def analyze_sheet(path, dimensions=("ay",), sheet=None):
    """Sayfayı boyutlara göre gruplar; para sütunlarını Decimal ile toplar.

    dimensions: ('ay',) ve/veya ('musteri',). İstenen boyut sütunu yoksa
    needs_clarification (mevcut sütunlar listelenir) -- uydurulmaz."""
    sheet_name, header, rows, cellmap = load_sheet_rows(path, sheet=sheet)
    if header is None:
        return DocumentResult("error", f"Kaizen: {cellmap['error']}")
    folded_header = [fold_tr(h) for h in header]

    def _find_column(*keywords, date_hint=False):
        for idx, h in enumerate(folded_header):
            if any(k in h for k in keywords):
                return idx
        if date_hint:
            for idx in range(len(header)):
                if any(_month_key(r[idx]) for r in rows[:5] if idx < len(r)):
                    return idx
        return None

    group_cols = []
    for dim in dimensions:
        if dim == "ay":
            col = _find_column("tarih", "donem", "ay", date_hint=True)
            if col is None:
                return DocumentResult(
                    NEEDS_CLARIFICATION,
                    "Kaizen: Aylık analiz için tarih/dönem sütunu bulunamadı. "
                    f"Mevcut sütunlar: {', '.join(header)}. Hangi sütun ay bilgisi?")
            group_cols.append(("ay", col))
        elif dim == "musteri":
            col = _find_column("musteri", "cari", "musteri adi", "unvan", "firma")
            if col is None:
                return DocumentResult(
                    NEEDS_CLARIFICATION,
                    "Kaizen: Müşteri bazlı analiz için müşteri/cari sütunu bulunamadı. "
                    f"Mevcut sütunlar: {', '.join(header)}. Hangi sütun müşteri?")
            group_cols.append(("musteri", col))
        else:
            col = _find_column(dim, dim + " ")
            if col is None:
                return DocumentResult(
                    NEEDS_CLARIFICATION,
                    f"Kaizen: '{dim}' boyutu için sütun bulunamadı. Mevcut sütunlar: {', '.join(header)}")
            group_cols.append((dim, col))

    money_cols = [i for i, h in enumerate(header) if _is_money_header(h)]
    if not money_cols:
        numeric = []
        for i in range(len(header)):
            if any(_cell_decimal(r[i]) is not None for r in rows[:10] if i < len(r)):
                numeric.append(i)
        if not numeric:
            return DocumentResult(
                NEEDS_CLARIFICATION,
                "Kaizen: Toplanacak tutar (para) sütunu bulunamadı. "
                f"Mevcut sütunlar: {', '.join(header)}. Hangi sütun toplansın?")
        money_cols = numeric

    groups = {}
    provenance = [f"kaynak: {Path(path).name} / sayfa: {sheet_name}"]
    for r_index, row in enumerate(rows):
        keys = []
        for dim, col in group_cols:
            raw = row[col] if col < len(row) else None
            key = _month_key(raw) if dim == "ay" else (None if raw is None else str(raw).strip())
            if key is None or key == "":
                key = "(belirtilmemiş)"
            keys.append(key)
        sums = groups.setdefault(tuple(keys), {c: Decimal("0") for c in money_cols})
        for col in money_cols:
            value = _cell_decimal(row[col] if col < len(row) else None)
            if value is not None:
                sums[col] += value
            # hücre provenance ilk katkıda
            if len(provenance) < 12 and value is not None:
                provenance.append(f"ör. hücre {cellmap[(r_index, col)]} -> {header[col]}={value}")

    out_header = [dim[0].upper() for dim in group_cols] + [f"{header[c]} TOPLAM" for c in money_cols]
    out_rows = [out_header]
    for keys in sorted(groups):
        out_rows.append(list(keys) + [groups[keys][c] for c in money_cols])
    from tools.office_tools import excel_yaz
    target = _fresh_output(Path(path).stem + "_analiz", ".xlsx")
    message = excel_yaz(target, out_rows, sheet="Analiz")
    if message.startswith("Kaizen: HATA"):
        return DocumentResult("error", message)
    return DocumentResult("ok", message,
                          provenance=provenance, output_path=target,
                          data={"groups": len(groups), "dimension_names": [d for d, _ in group_cols]})


def check_kdv_totals(path, sheet=None):
    """KDV/matrah/toplam sütunlarını Decimal ile YENİDEN hesaplar; dokumentteki toplam
    satırıyla karşılaştırır. Fark varsa hücre düzeyinde raporlar; uydurmaz."""
    sheet_name, header, rows, cellmap = load_sheet_rows(path, sheet=sheet)
    if header is None:
        return DocumentResult("error", f"Kaizen: {cellmap['error']}")
    folded = [fold_tr(h) for h in header]
    kdv_col = next((i for i, h in enumerate(folded) if "kdv" in h), None)
    if kdv_col is None:
        return DocumentResult(NEEDS_CLARIFICATION,
                              f"Kaizen: KDV sütunu bulunamadı. Mevcut sütunlar: {', '.join(header)}.")
    total = Decimal("0")
    counted = 0
    provenance = [f"kaynak: {Path(path).name} / sayfa: {sheet_name}"]
    claimed_total = None
    for r_index, row in enumerate(rows):
        first_cell = fold_tr(str(row[0] or ""))
        value = _cell_decimal(row[kdv_col] if kdv_col < len(row) else None)
        if any(k in first_cell for k in ("toplam", "genel toplam")) and value is not None:
            claimed_total = value
            provenance.append(f"belgedeki toplam: hücre {cellmap[(r_index, kdv_col)]}")
            continue
        if value is not None:
            total += value
            counted += 1
    lines = [f"Yeniden hesaplanan KDV toplamı: {total} ({counted} satır)"]
    status_detail = "belgede toplam satırı yok; kontrol hesaplanan değerle sınırlı"
    if claimed_total is not None:
        if claimed_total == total:
            status_detail = "UYUMLU: belgedeki toplam yeniden hesaplananla aynı"
        else:
            status_detail = f"UYUMSUZ: belge {claimed_total}, hesaplanan {total}; fark {total - claimed_total}"
    lines.append(status_detail)
    return DocumentResult("ok", "\n".join(lines), provenance=provenance,
                          data={"computed": str(total), "claimed": (str(claimed_total) if claimed_total is not None else None),
                                "consistent": (claimed_total is None or claimed_total == total)})


# ---------------------------------------------------------------- fatura analizi -----

def analyze_invoice(path, text: str = ""):
    """Faturanın metin katmanından/OCR'dan alan çıkarır ve muhasebe açısından sunar.

    Muhasebe bağlantısı: net+KDV+ödeme bilgisi eksiksizse mevcut
    accounting/journal.py şablonları (sale_goods/purchase_goods) ile KAYIT ÖNERİSİ
    üretilir (Phase-1'in kendi şablonu; yeni motor yok). Alan eksikse uydurulmaz,
    eksik alanlar açıkça listelenir."""
    from tools.office_tools import pdf_oku
    if not text:
        text = pdf_oku(path)
    if text.startswith("Kaizen:"):
        return DocumentResult("error", text)
    folded = fold_tr(text)
    vat_rates = re.findall(r"%\s*(\d{1,2})(?:[.,]\d+)?", text)
    vat_amounts = re.findall(r"kdv[^0-9]{0,15}(\d[\d.,]*)", folded)
    totals = re.findall(r"(?:genel toplam|toplam|tutar)[^0-9]{0,15}(\d[\d.,]*)", folded)
    dates = _DATE_TOKEN.findall(text)
    counter_match = re.search(r"(?:alici|musteri|unvan|sayin)\s*[:\-]?\s*([A-ZÇĞİÖŞÜa-zçğışöü .&]{3,60})", text)

    fields = {
        "tarih": [".".join(d) for d in dates[:3]] or None,
        "kdv_orani": ["%" + r for r in vat_rates] or None,
        "kdv_tutari": [_to_decimal(v) for v in vat_amounts if _to_decimal(v) is not None][:3] or None,
        "toplam": [_to_decimal(t) for t in totals if _to_decimal(t) is not None][:3] or None,
        "karsi_taraf": counter_match.group(1).strip() if counter_match else None,
    }
    missing = [k for k in ("tarih", "kdv_orani", "toplam") if not fields.get(k)]
    summary = ["FATURA ALANLARI (çıkarılan, doğrulanması gerekir):"]
    for key, value in fields.items():
        summary.append(f"  {key}: {value if value else '(bulunamadı)'}")
    suggestion = None
    if not missing and len(vat_rates) == 1:
        try:
            rate = Decimal(vat_rates[0].replace(",", "."))
            toplam = fields["toplam"][-1]
            # KDV dahil toplamdan matrah (geriye dönük hesap burada AÇIKÇA
            # belirtilir -- belgeden okunmadıysa bu bölüm hiç üretilmez)
            kdv = fields["kdv_tutari"][-1] if fields["kdv_tutari"] else None
            net = _to_decimal(str(toplam)) - (_to_decimal(str(kdv)) or Decimal("0")) if toplam else None
            if net is not None and toplam is not None and net > 0:
                if kdv is None:
                    expected_kdv = (net * rate / Decimal("100")).quantize(Decimal("0.01"))
                    if expected_kdv is not None and net + expected_kdv == _to_decimal(str(toplam)):
                        kdv = expected_kdv
            if net and kdv and net + kdv == _to_decimal(str(toplam)):
                from accounting.journal import sale_goods
                entry = sale_goods(net, rate, mode="vadeli")
                suggestion = entry.render()
        except Exception:
            suggestion = None
    if suggestion:
        summary.append("\nKAYIT ÖNERİSİ (mevcut Phase-1 şablonu sale_goods, vadeli varsayımı AÇIK):")
        summary.append(suggestion)
    elif missing:
        summary.append("\nKayıt önerisi üretilmedi -- eksik alanlar: " + ", ".join(missing)
                       + ". Bu alanlar faturala birlikte netleştirilmeli; uydurma yapılmadı.")
    return DocumentResult("ok", "\n".join(summary),
                          provenance=[f"kaynak: {Path(path).name}"],
                          data={"fields": {k: (str(v) if v is not None else None) for k, v in fields.items()},
                                "journal_suggested": bool(suggestion)})


# ---------------------------------------------------------------- taranmış PDF edit --

def _ocr_status():
    """Tesseract motoru kurulu mu (metadata sorgusu, belge verisi değil)."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def edit_scanned_pdf_field(path, field_description, new_value):
    """Taranmış PDF'te GÖRÜNÜR alan düzeltmesi + yeni PDF (orijinale DOKUNULMAZ).

    workflow: sayfa görsele çevrilir (pdf2image/Poppler) -> OCR ile konumlandırma
    (image_to_data) -> hedef alan güçlü beyaz kutu + yeni metin ile GÖRSEL düzeyde
    değiştirilir -> sayfalar yeni PDF olarak outputs/ altına yazılır.

    - Birden çok eşleşme/emetik tarih bulunursa: needs_clarification (hangisi?).
    - OCR motoru yoksa: kurulum talimatı (asla uydurma düzeltme YOK)."""
    if not _ocr_status():
        from tools.office_tools import _OCR_TESSERACT_MISSING
        return DocumentResult("error", _OCR_TESSERACT_MISSING)
    from pdf2image import convert_from_path
    import pytesseract
    from PIL import Image, ImageDraw
    from tools.office_tools import _ocr_settings

    path = Path(path)
    original = _original_fingerprint(path)
    settings = _ocr_settings()
    lang = settings.get("language") or "tur+eng"
    images = convert_from_path(str(path), poppler_path=settings.get("poppler_path") or None)
    if not images:
        return DocumentResult("error", "Kaizen: PDF sayfaları görsele çevrilemedi.")

    target_desc = fold_tr(field_description)
    hits = []  # (page_idx, x, y, w, h, matched_text)
    for page_idx, image in enumerate(images):
        try:
            data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
        except Exception:
            # dil paketi eksik olabilir -- office_tools._ocr_image ile AYNI degrade: eng'e düş
            try:
                data = pytesseract.image_to_data(image, lang="eng", output_type=pytesseract.Output.DICT)
            except Exception as exc:
                return DocumentResult("error", f"Kaizen: OCR okuma hatası: {exc}")
        for i, token in enumerate(data["text"]):
            token_f = fold_tr(token)
            if not token_f:
                continue
            if _DATE_TOKEN.search(token) and "tarih" in target_desc:
                hits.append((page_idx, data["left"][i], data["top"][i], data["width"][i], data["height"][i], token))
            elif target_desc and target_desc in token_f:
                hits.append((page_idx, data["left"][i], data["top"][i], data["width"][i], data["height"][i], token))
    if not hits:
        return DocumentResult(
            NEEDS_CLARIFICATION,
            f"Kaizen: Belgede '{field_description}' alanı OCR ile bulunamadı. "
            "Alanı netleştirin (ör. hangi tarih? sayfa numarası?).")
    if len(hits) > 1:
        detail = "; ".join(f"sayfa {h[0] + 1} konum (x={h[1]},y={h[2]}) değer '{h[5]}'" for h in hits[:6])
        return DocumentResult(
            NEEDS_CLARIFICATION,
            f"Kaizen: '{field_description}' için {len(hits)} eşleşme var: {detail}. Hangisi düzeltilecek?")
    page_idx, x, y, w, h, old_text = hits[0]
    edited = list(images)
    image = edited[page_idx].convert("RGB")
    draw = ImageDraw.Draw(image)
    padding = 4
    draw.rectangle([x - padding, y - padding, x + w + padding, y + h + padding], fill="white")
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("arial.ttf", max(h + padding, 12))
    except Exception:
        font = ImageFont.load_default()
    draw.text((x, y), str(new_value), fill="black", font=font)
    target = _fresh_output(path.stem + "_duzeltilmis", ".pdf")
    Image.init()
    edited[0].save(target, save_all=True, append_images=edited[1:])
    if not _assert_original_unchanged(path, original):
        return DocumentResult("error", "Kaizen: HATA -- orijinal dosya değişmiş görünüyor; çıktı iptal.")
    return DocumentResult(
        "ok",
        f"Kaizen: Taranmış PDF güncellendi (sayfa {page_idx + 1}: '{old_text}' -> "
        f"'{new_value}'). Yeni dosya: {target}\nNOT: Düzeltme görsel düzeydedir; "
        "belgenin hukuki geçerliliği için aslını saklayın.",
        provenance=[f"sayfa {page_idx + 1}", f"eski değer: {old_text}"],
        output_path=target)


# ---------------------------------------------------------------- tek nokta read -----

def read_document(path, sheet=None):
    """Sona göre deterministic okuma + provenance. Desteklenmeyen türde uydurma YOK."""
    from tools.office_tools import excel_oku, pdf_oku, word_oku
    path = Path(path)
    if not path.exists():
        return DocumentResult("error", f"Kaizen: Dosya bulunamadı: {path}")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return DocumentResult("ok", pdf_oku(path), provenance=[f"dosya: {path.name} (sayfa numaralı)"])
    if suffix == ".docx":
        return DocumentResult("ok", word_oku(path), provenance=[f"dosya: {path.name}"])
    if suffix in (".xlsx", ".xlsm"):
        text = excel_oku(path, sheet=sheet, max_rows=200)
        prov = [f"dosya: {path.name}"] + ([f"sayfa: {sheet}"] if sheet else [])
        return DocumentResult("ok", text, provenance=prov)
    if suffix == ".xls":
        text, prov = read_xls(path)
        return DocumentResult("ok" if not text.startswith("Kaizen: Eski") else "error", text, provenance=prov)
    if suffix == ".csv":
        text, prov = read_csv(path)
        return DocumentResult("ok", text, provenance=prov)
    if suffix in (".txt", ".md", ".json"):
        text, prov = read_text_file(path)
        return DocumentResult("ok" if not text.startswith("Kaizen: JSON") else "error", text, provenance=prov)
    if suffix in (".jpg", ".jpeg", ".png"):
        return _read_image_with_ocr(path)
    return DocumentResult(
        "error",
        f"Kaizen: Desteklenmeyen dosya türü: {suffix}. Desteklenenler: "
        f"{', '.join(SUPPORTED_READ_SUFFIXES)}")


def _read_image_with_ocr(path):
    """JPG/PNG görselini OCR ile metne çevirir (LOCAL_ONLY, dış API YOK).

    Mevcut Tesseract + Türkçe OCR altyapısını kullanır. Düşük okunabilirlikte
    değer uydurma — OCR motoru yoksa açık kurulum talimatı döner."""
    from tools.office_tools import _ocr_image, _ocr_settings
    try:
        from PIL import Image
    except ImportError:
        return DocumentResult("error", "Kaizen: Görsel okuma için 'Pillow' kütüphanesi gerekli: pip install Pillow")
    try:
        image = Image.open(str(path))
        image.load()
    except Exception as exc:
        return DocumentResult("error", f"Kaizen: Görsel açılamadı: {exc}")
    settings = _ocr_settings()
    if not settings.get("enabled", True):
        return DocumentResult("error", "Kaizen: OCR devre dışı (config/Kaizen.json → ocr.enabled)")
    text, error = _ocr_image(image, settings)
    if error:
        return DocumentResult("error", error)
    if not text:
        return DocumentResult(
            "error",
            "Kaizen: Görselden metin çıkarılamadı (düşük okunabilirlik olabilir). "
            "Daha yüksek çözünürlüklü bir görsel deneyin.")
    provenance = [f"dosya: {path.name}", "yöntem: OCR (Tesseract, tur+eng)"]
    return DocumentResult("ok", text, provenance=provenance)
