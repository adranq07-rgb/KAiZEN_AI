"""Ofis araçları: Excel, Word ve PDF okuma; Excel ve Word yazma; PDF birleştirme/bölme; görselden PDF.

Kurallar:
- Var olan bir dosyanın ÜZERİNE YAZMAZ; yeni dosya açar (ad çakışırsa _2, _3 ekler).
- openpyxl / python-docx / pypdf yüklü değilse ne yükleneceğini söyler; çökmez.
- Okuma araçları içeriği düz metin olarak döndürür; Kaizen bunu öğrenme hafızasına ekleyebilir.
"""
from decimal import Decimal
from pathlib import Path

MAX_CELLS = 4000


def _missing(package, pip_name=None):
    return f"Kaizen: '{package}' kütüphanesi yüklü değil. Yüklemek için: pip install {pip_name or package}"


def _free_path(path):
    path = Path(path)
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _check_readable(path, suffixes):
    path = Path(path)
    if not path.exists():
        return None, f"Kaizen: Dosya bulunamadı: {path}"
    if path.suffix.lower() not in suffixes:
        return None, f"Kaizen: Desteklenmeyen dosya türü ({path.suffix}); beklenen: {', '.join(suffixes)}"
    return path, None


def excel_oku(path, sheet=None, max_rows=50):
    """Excel dosyasını metin tablosu olarak okur (formüller yerine son hesaplanan değerler)."""
    path, error = _check_readable(path, (".xlsx", ".xlsm"))
    if error:
        return error
    try:
        import openpyxl
    except ImportError:
        return _missing("openpyxl")
    values_book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    formula_book = openpyxl.load_workbook(path, read_only=True, data_only=False)
    try:
        names = [sheet] if sheet else values_book.sheetnames
        out, cells = [], 0
        for name in names:
            out.append(f"## Sayfa: {name}")
            rows = zip(values_book[name].iter_rows(values_only=True), formula_book[name].iter_rows(values_only=True))
            for row_no, (shown, raw) in enumerate(rows, start=1):
                if row_no > max_rows or cells > MAX_CELLS:
                    out.append(f"... ({max_rows} satırdan sonrası gösterilmedi)")
                    break
                # Hesaplanmış değer yoksa (dosya Excel'de hiç açılıp kaydedilmediyse) formülün kendisini göster
                values = [
                    str(v) if v is not None else ("" if r is None else str(r))
                    for v, r in zip(shown, raw)
                ]
                if any(values):
                    out.append(" | ".join(values))
                    cells += len(values)
        return "\n".join(out)
    finally:
        values_book.close()
        formula_book.close()


def excel_yaz(path, rows, sheet="Sayfa1", header=True):
    """rows: satır listesi (her satır bir liste). '=TOPLA(B2:B9)' gibi metinler formül olarak yazılır.

    Var olan dosyanın üzerine yazmaz; yazılan gerçek yolu döndürür.
    """
    try:
        import openpyxl
        from openpyxl.styles import Font
    except ImportError:
        return _missing("openpyxl")
    target = _free_path(Path(path).with_suffix(".xlsx"))
    workbook = openpyxl.Workbook()
    ws = workbook.active
    ws.title = sheet[:31]
    for row in rows:
        ws.append([float(v) if isinstance(v, Decimal) else v for v in row])
    if header and rows:
        for cell in ws[1]:
            cell.font = Font(bold=True)
    for column in ws.columns:
        width = max((len(str(c.value)) for c in column if c.value is not None), default=8)
        ws.column_dimensions[column[0].column_letter].width = min(max(width + 2, 8), 60)
    target.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(target)
    return f"Kaizen: Excel dosyası oluşturuldu: {target}"


def pdf_oku(path, max_pages=30):
    """PDF'in metin katmanını sayfa sayfa okur (taranmış/resim PDF için OCR gerekir)."""
    path, error = _check_readable(path, (".pdf",))
    if error:
        return error
    try:
        from pypdf import PdfReader
    except ImportError:
        return _missing("pypdf")
    reader = PdfReader(str(path))
    out = []
    for number, page in enumerate(reader.pages, start=1):
        if number > max_pages:
            out.append(f"... ({len(reader.pages)} sayfanın ilk {max_pages} sayfası okundu)")
            break
        text = (page.extract_text() or "").strip()
        out.append(f"## Sayfa {number}\n{text}" if text else f"## Sayfa {number}\n(metin yok - taranmış resim olabilir)")
    return "\n\n".join(out)


def word_oku(path):
    """Word (.docx) belgesinin paragraflarını ve tablolarını düz metin olarak okur."""
    path, error = _check_readable(path, (".docx",))
    if error:
        return error
    try:
        import docx
    except ImportError:
        return _missing("python-docx", "python-docx")
    document = docx.Document(str(path))
    out = [p.text for p in document.paragraphs if p.text.strip()]
    for index, table in enumerate(document.tables, start=1):
        out.append(f"## Tablo {index}")
        for row in table.rows:
            out.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(out)


def word_yaz(path, title, paragraphs, table=None):
    """Yeni Word belgesi oluşturur: başlık, paragraflar ve isteğe bağlı tablo (satır listesi)."""
    try:
        import docx
    except ImportError:
        return _missing("python-docx", "python-docx")
    target = _free_path(Path(path).with_suffix(".docx"))
    document = docx.Document()
    document.add_heading(title, level=1)
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    if table:
        grid = document.add_table(rows=len(table), cols=max(len(r) for r in table))
        grid.style = "Table Grid"
        for i, row in enumerate(table):
            for j, value in enumerate(row):
                grid.cell(i, j).text = str(value)
    target.parent.mkdir(parents=True, exist_ok=True)
    document.save(target)
    return f"Kaizen: Word belgesi oluşturuldu: {target}"


def pdf_birlestir(paths, target):
    """Birden çok PDF'i verilen sırayla tek PDF'te birleştirir (yeni dosya; var olanın üzerine yazmaz)."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return _missing("pypdf")
    if len(paths) < 2:
        return "Kaizen: Birleştirmek için en az iki PDF gerekir."
    writer = PdfWriter()
    for path in paths:
        checked, error = _check_readable(path, (".pdf",))
        if error:
            return error
        for page in PdfReader(str(checked)).pages:
            writer.add_page(page)
    out = _free_path(Path(target).with_suffix(".pdf"))
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as handle:
        writer.write(handle)
    return f"Kaizen: {len(paths)} PDF birleştirildi ({len(writer.pages)} sayfa): {out}"


def _parse_ranges(spec, total):
    pages = []
    for part in str(spec).replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            first, last = part.split("-", 1)
            start, end = int(first), int(last)
        else:
            start = end = int(part)
        if start < 1 or end > total or start > end:
            raise ValueError(f"Sayfa aralığı geçersiz: {part} (belgede {total} sayfa var)")
        pages.extend(range(start, end + 1))
    return pages


def pdf_bol(path, ranges, target):
    """PDF'ten belirtilen sayfaları ('1-3,5') yeni bir PDF olarak ayırır."""
    path, error = _check_readable(path, (".pdf",))
    if error:
        return error
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return _missing("pypdf")
    reader = PdfReader(str(path))
    try:
        selected = _parse_ranges(ranges, len(reader.pages))
    except ValueError as exc:
        return f"Kaizen: {exc}"
    if not selected:
        return "Kaizen: Ayrılacak sayfa belirtilmedi (ör. '1-3,5')."
    writer = PdfWriter()
    for number in selected:
        writer.add_page(reader.pages[number - 1])
    out = _free_path(Path(target).with_suffix(".pdf"))
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as handle:
        writer.write(handle)
    return f"Kaizen: {len(selected)} sayfa ayrıldı: {out}"


def gorsel_pdf(paths, target):
    """JPG/PNG görselleri sırayla tek bir PDF'e çevirir."""
    try:
        from PIL import Image
    except ImportError:
        return _missing("Pillow", "pillow")
    images = []
    for path in paths:
        checked, error = _check_readable(path, (".jpg", ".jpeg", ".png"))
        if error:
            return error
        images.append(Image.open(checked).convert("RGB"))
    if not images:
        return "Kaizen: En az bir görsel gerekir."
    out = _free_path(Path(target).with_suffix(".pdf"))
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.init()  # JPEG kayıt eklentisini yükler (PDF yazımı için gerekir)
    images[0].save(out, save_all=True, append_images=images[1:])
    return f"Kaizen: {len(images)} görsel PDF'e çevrildi: {out}"


OFFICE_TOOLS = {
    "pdf_birlestir": pdf_birlestir,
    "pdf_bol": pdf_bol,
    "gorsel_pdf": gorsel_pdf,
    "excel_oku": excel_oku,
    "excel_yaz": excel_yaz,
    "pdf_oku": pdf_oku,
    "word_oku": word_oku,
    "word_yaz": word_yaz,
}
