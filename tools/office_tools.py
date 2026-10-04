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
    Dosya oluşmazsa hata mesajı döndürür (başarı uydurulmaz).
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
    # DOSYA GERÇEKLEN OLUŞMUŞ MU KONTROL ET
    if not target.exists():
        return f"Kaizen: HATA — Excel dosyası oluşturulamadı: {target}"
    if target.stat().st_size == 0:
        return f"Kaizen: HATA — Excel dosyası boş (0 bayt): {target}"
    return f"Kaizen: Excel dosyası oluşturuldu: {target}"


_OCR_POPPLER_MISSING = (
    "Kaizen: OCR için 'pdf2image' kütüphanesi kurulu ama Poppler (PDF sayfasını görsele "
    "çeviren motor) bulunamadı.\nWindows için: "
    "https://github.com/oschwartz10612/poppler-windows/releases adresinden indirip bir "
    "klasöre çıkarın, sonra içindeki 'Library\\bin' klasörünün tam yolunu "
    "config/Kaizen.json içindeki ocr.poppler_path alanına yazın (veya PATH'e ekleyin)."
)

_OCR_TESSERACT_MISSING = (
    "Kaizen: OCR için 'pytesseract' kütüphanesi kurulu ama Tesseract OCR motoru bulunamadı.\n"
    "Windows için: https://github.com/UB-Mannheim/tesseract/wiki adresinden kurulum "
    "dosyasını indirip çalıştırın (Türkçe dil paketini de işaretleyin), sonra "
    "tesseract.exe'nin tam yolunu config/Kaizen.json içindeki ocr.tesseract_cmd alanına "
    "yazın (veya PATH'e ekleyin)."
)


def _ocr_settings():
    """config/Kaizen.json içindeki isteğe bağlı 'ocr' bölümünü okur (poppler/tesseract yolları
    PATH'te değilse, Türkçe dil paketi kurulu değilse ya da OCR kapatılmak istenirse)."""
    try:
        from config.config_manager import ConfigManager
        manager = ConfigManager()
        return {
            "enabled": manager.get("ocr", "enabled", True),
            "language": manager.get("ocr", "language", "tur+eng"),
            "poppler_path": manager.get("ocr", "poppler_path", None),
            "tesseract_cmd": manager.get("ocr", "tesseract_cmd", None),
        }
    except Exception:
        return {"enabled": True, "language": "tur+eng", "poppler_path": None, "tesseract_cmd": None}


def _ocr_image(image, settings):
    """Tek bir görseli (PIL Image) OCR ile metne çevirir. Önce ayarlardaki dili (varsayılan
    'tur+eng') dener; Türkçe dil paketi (tur.traineddata) kurulu değilse sessizce yalnız
    İngilizce'ye ('eng') düşer -- Kaizen'in çevrimdışı çalışma ilkesi burada da geçerli:
    OCR motoru eksikse çökmez, açık bir Türkçe kurulum talimatı döner."""
    try:
        import pytesseract
    except ImportError:
        return None, _missing("pytesseract")
    tesseract_cmd = settings.get("tesseract_cmd")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    language = settings.get("language") or "tur+eng"
    try:
        text = pytesseract.image_to_string(image, lang=language)
    except pytesseract.TesseractNotFoundError:
        return None, _OCR_TESSERACT_MISSING
    except Exception:
        # dil paketi (ör. tur.traineddata) kurulu değil olabilir -- İngilizce ile bir kez daha dene
        try:
            text = pytesseract.image_to_string(image, lang="eng")
        except pytesseract.TesseractNotFoundError:
            return None, _OCR_TESSERACT_MISSING
        except Exception as exc:
            return None, f"Kaizen: OCR okuma hatası: {exc}"
    return text.strip(), None


def _ocr_pdf_page(path, page_number, settings):
    """Bir PDF sayfasını (metin katmanı boşsa, yani taranmış/resim PDF) görsele çevirip OCR ile
    okur. pdf2image + Poppler ile sayfa render edilir, ardından _ocr_image ile metne çevrilir."""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        return None, _missing("pdf2image")
    try:
        images = convert_from_path(
            str(path), first_page=page_number, last_page=page_number,
            poppler_path=settings.get("poppler_path") or None,
        )
    except Exception as exc:
        if type(exc).__name__ == "PDFInfoNotInstalledError" or "poppler" in str(exc).lower():
            return None, _OCR_POPPLER_MISSING
        return None, f"Kaizen: PDF sayfası görsele çevrilemedi: {exc}"
    if not images:
        return None, "Kaizen: PDF sayfası görsele çevrilemedi."
    return _ocr_image(images[0], settings)


def pdf_oku(path, max_pages=30, ocr=True):
    """PDF'in metin katmanını sayfa sayfa okur. Metin katmanı boş bir sayfa varsa (taranmış/
    resim PDF) ve OCR kütüphaneleri/motoru kuruluysa, o sayfayı OCR ile okumayı dener --
    kurulu değilse çökmez, tek seferlik bir kurulum notuyla birlikte normal şekilde döner."""
    path, error = _check_readable(path, (".pdf",))
    if error:
        return error
    try:
        from pypdf import PdfReader
    except ImportError:
        return _missing("pypdf")
    reader = PdfReader(str(path))
    settings = _ocr_settings() if ocr else {"enabled": False}
    out = []
    ocr_note = None
    for number, page in enumerate(reader.pages, start=1):
        if number > max_pages:
            out.append(f"... ({len(reader.pages)} sayfanın ilk {max_pages} sayfası okundu)")
            break
        text = (page.extract_text() or "").strip()
        if text:
            out.append(f"## Sayfa {number}\n{text}")
            continue
        if ocr and settings.get("enabled", True):
            ocr_text, ocr_error = _ocr_pdf_page(path, number, settings)
            if ocr_text:
                out.append(f"## Sayfa {number} (OCR)\n{ocr_text}")
                continue
            if ocr_error and ocr_note is None:
                ocr_note = ocr_error  # aynı hatayı her sayfada tekrar etmeye gerek yok
        out.append(f"## Sayfa {number}\n(metin yok - taranmış resim olabilir)")
    if ocr_note:
        out.append(ocr_note)
    return "\n\n".join(out)


def gorsel_oku(path):
    """Bir görseli (fotoğraflanmış fatura/makbuz, ekran görüntüsü...) OCR ile metne çevirir."""
    path, error = _check_readable(path, (".jpg", ".jpeg", ".png"))
    if error:
        return error
    try:
        from PIL import Image
    except ImportError:
        return _missing("Pillow", "pillow")
    settings = _ocr_settings()
    if not settings.get("enabled", True):
        return "Kaizen: OCR devre dışı (config/Kaizen.json -> ocr.enabled)."
    image = Image.open(str(path)).convert("RGB")
    text, error = _ocr_image(image, settings)
    if error:
        return error
    if not text:
        return "Kaizen: Görselde okunabilir metin bulunamadı."
    return text


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
    "gorsel_oku": gorsel_oku,
}
