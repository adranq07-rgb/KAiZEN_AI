import tempfile
from pathlib import Path

from memory.learning_store import LearningStore
from memory.seed_loader import load_seeds
from tools.office_tools import (
    excel_oku, excel_yaz, gorsel_oku, gorsel_pdf, pdf_birlestir, pdf_bol, pdf_oku, word_oku, word_yaz,
)


def _text_image(text, size=(700, 160)):
    """OCR testleri için: verilen metni içeren bir PIL görseli üretir (gerçek Tesseract motoruyla
    uçtan uca okunacak -- sahte/mock bir OCR değil)."""
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    font = None
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ):
        try:
            font = ImageFont.truetype(candidate, 36)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    draw.text((10, 50), text, fill="black", font=font)
    return image


def test_office_tools():
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "rapor.xlsx"
        message = excel_yaz(target, [["Kalem", "Tutar"], ["Kira", 1000], ["KDV", "=B2*0.2"]])
        assert "oluşturuldu" in message and target.exists()
        # var olan dosyanın üzerine yazmaz
        second = excel_yaz(target, [["başka"]])
        assert "rapor_2.xlsx" in second and (Path(folder) / "rapor_2.xlsx").exists()
        text = excel_oku(target)
        assert "Kira | 1000" in text and "=B2*0.2" in text

        doc = Path(folder) / "not.docx"
        assert "oluşturuldu" in word_yaz(doc, "Başlık", ["Merhaba dünya"], [["a", "b"], [1, 2]])
        content = word_oku(doc)
        assert "Merhaba dünya" in content and "a | b" in content

        # PDF: görselden üret, birleştir, böl, oku
        from PIL import Image
        for name, color in (("a.png", "red"), ("b.png", "blue"), ("c.png", "green")):
            Image.new("RGB", (60, 40), color).save(Path(folder) / name)
        made = gorsel_pdf([Path(folder) / n for n in ("a.png", "b.png", "c.png")], Path(folder) / "gorseller.pdf")
        assert "3 görsel" in made
        joined = pdf_birlestir([Path(folder) / "gorseller.pdf", Path(folder) / "gorseller.pdf"], Path(folder) / "toplu.pdf")
        assert "6 sayfa" in joined
        parts = pdf_bol(Path(folder) / "toplu.pdf", "1-2,6", Path(folder) / "parca.pdf")
        assert "3 sayfa" in parts
        assert "geçersiz" in pdf_bol(Path(folder) / "toplu.pdf", "9", Path(folder) / "x.pdf")
        assert "Sayfa 1" in pdf_oku(Path(folder) / "parca.pdf")
        assert "en az iki" in pdf_birlestir([Path(folder) / "toplu.pdf"], Path(folder) / "y.pdf")

        assert "bulunamadı" in pdf_oku(Path(folder) / "yok.pdf")
        assert "Desteklenmeyen" in word_oku(target)
    print("KAIZEN OFIS ARACLARI TESTI: BASARILI")


def test_gorsel_oku_reads_text_via_ocr():
    """gorsel_oku: fotoğraflanmış bir fatura/makbuz gibi -- düz bir görselde yazan metni gerçek
    Tesseract OCR motoruyla (sahte/mock değil) okur. Bu ortamda Türkçe dil paketi (tur) kurulu
    değil; kod bunu 'eng'e sessizce düşerek (ya da Tesseract'ın kendi iç toleransıyla) yine de
    okuyabilmeli -- tam olarak _ocr_image'daki geri düşme (fallback) mantığının kanıtı."""
    with tempfile.TemporaryDirectory() as folder:
        image_path = Path(folder) / "fatura.png"
        _text_image("KDV ORANI YUZDE 20").save(image_path)
        text = gorsel_oku(image_path)
        assert "KDV ORANI YUZDE 20" in text.upper().replace("İ", "I")

        assert "bulunamadı" in gorsel_oku(Path(folder) / "yok.png")
        not_docx = Path(folder) / "not.docx"
        not_docx.write_text("gercek gorsel degil", encoding="utf-8")
        assert "Desteklenmeyen" in gorsel_oku(not_docx)
    print("KAIZEN GORSEL OCR TESTI: BASARILI")


def test_pdf_oku_falls_back_to_ocr_for_scanned_pages():
    """pdf_oku: metin katmanı boş (taranmış/resim) bir PDF sayfasını OCR ile okur -- pypdf'in
    extract_text()'i boş döndüğünde otomatik devreye girer, sayfa başlığına '(OCR)' ekler.
    ocr=False verilirse eski davranış (metin yok mesajı) hiç değişmeden korunur."""
    with tempfile.TemporaryDirectory() as folder:
        pdf_path = Path(folder) / "taranmis.pdf"
        _text_image("FATURA TUTARI 1000 TL").convert("RGB").save(pdf_path, "PDF")

        with_ocr = pdf_oku(pdf_path)
        assert "(OCR)" in with_ocr
        assert "FATURA TUTARI 1000 TL" in with_ocr.upper().replace("İ", "I")

        without_ocr = pdf_oku(pdf_path, ocr=False)
        assert "(OCR)" not in without_ocr
        assert "metin yok - taranmış resim olabilir" in without_ocr
    print("KAIZEN PDF OCR GERI DUSME TESTI: BASARILI")


def test_seed_loader():
    with tempfile.TemporaryDirectory() as folder:
        store = LearningStore(Path(folder) / "seed.sqlite3")
        first = load_seeds(store)
        assert first.get("office_excel.json", 0) >= 30
        assert load_seeds(store) == {}  # dosya değişmediyse tekrar yüklenmez
        rows = store.search("DÜŞEYARA nasıl kullanılır", domain="office", limit=3)
        assert rows and "DÜŞEYARA" in rows[0]["text"]
        rows = store.search("ticari mal alışı yevmiye kaydı KDV", domain="accounting", limit=3)
        assert rows and rows[0]["source_type"] == "curated"
    print("KAIZEN OGRETILMIS BILGI YUKLEME TESTI: BASARILI")


@__import__("unittest").skip("Retired: Cognee removed from Kaizen-1 production")
def test_status_reports_experience_memory_background_stats():
    """DÜZELTME (2026-09-23, dış inceleme madde 4): 'durum' komutu artık Cognee'ye arka planda
    yazılan deneyimlerin (yazıldı/başarısız/kuyrukta/atlandı) sayısını gösteriyor -- eskiden
    bu hiç görünmüyordu ("hafızaya gerçekten yazıldı mı?" izlenemiyordu)."""
    from core.commands import CommandHandler
    from memory.brain_manager import BrainManager
    from tests.doubles import NullExperienceMemory

    class FakeProviderManager:
        provider = object()

    class FakeLearningStore:
        def stats(self):
            return {"total": 0, "by_type": {}}

    class FakeKaizenBrainWrapper:
        def __init__(self, brain_manager):
            self.brain = brain_manager

    class Engine:
        site_store = None
        facts = None
        cards = None
        learning_store = FakeLearningStore()
        provider_manager = FakeProviderManager()

    brain_manager = BrainManager(experience_memory=NullExperienceMemory(), log_dir=tempfile.mkdtemp())
    brain_manager.remember_experience("soru", "cevap", background=False)
    Engine.brain = FakeKaizenBrainWrapper(brain_manager)

    handler = CommandHandler(Engine())
    result = handler.handle("durum")
    assert "Deneyim hafızası (Cognee, arka plan)" in result
    assert "1 yazıldı" in result

    print("KAIZEN DURUM DENEYIM HAFIZASI TESTI: BASARILI")


def test_commands():
    from core.commands import CommandHandler

    class Engine:
        site_store = None
        facts = None

        class accounting_agent:
            calls = []

            @classmethod
            def learn(cls, **kwargs):
                cls.calls.append(kwargs)
                return "Kaizen: Duzeltme kaydedildi."

    handler = CommandHandler(Engine())
    assert "Kaizen komutları" in handler.handle("yardım")
    assert handler.handle("durum bilgisi ver bana") is None      # cümle içindeki 'durum' komut sayılmaz
    assert handler.handle("Kasa hesabı kaç?") is None
    assert "Site deposu kapalı" in handler.handle("kaynaklar")
    assert "kapalı" in handler.handle("parametreler")
    assert handler.handle("düzelt: soru => cevap") == "Kaizen: Duzeltme kaydedildi."
    assert Engine.accounting_agent.calls[0]["correct_answer"] == "cevap"
    assert "Kullanım" in handler.handle("düzelt: yalnız soru =>")
    print("KAIZEN KOMUTLAR TESTI: BASARILI")


def test_document_commands():
    """'oku:' ve 'doğrula:' komutları -- tools/office_tools.py'deki pdf_oku/excel_oku/word_oku
    daha önce tool_manager'a kayıtlıydı ama sohbetten hiç çağrılamıyordu (kullanıcının
    'pdf okuma ve resimli dosyaları okuma özelliği kat' isteği); bu komutlar o boşluğu kapatır.
    'doğrula:' ise 'excel bilgisini teyit et' / 'hesaplarımı kontrol et' isteğini karşılar.
    """
    from core.commands import CommandHandler

    class FakeToolManager:
        def __init__(self):
            self.calls = []

        def run_tool(self, name, *args, **kwargs):
            self.calls.append((name, args, kwargs))
            if name == "pdf_oku":
                return "PDF ICERIK: KDV %20"
            if name == "excel_oku":
                return f"EXCEL ICERIK sheet={kwargs.get('sheet')}: Kira | 1000"
            if name == "word_oku":
                return "WORD ICERIK"
            return "Kaizen: bilinmeyen arac"

    class FakeTopic:
        def __init__(self, id, title):
            self.id, self.title = id, title

    class FakeFacts:
        topics = [FakeTopic("kdv", "KDV oranı")]

        def rows(self):
            return [{"topic": "kdv", "year": 2026, "value": "%20", "status": "verified"}]

    class FakeAccountingAgent:
        calls = []

        @classmethod
        def verify_document(cls, content, facts_context, facts_registry=None):
            cls.calls.append((content, facts_context, facts_registry))
            return "DOGRULAMA SONUCU"

    class Engine:
        site_store = None
        facts = FakeFacts()
        tool_manager = FakeToolManager()
        accounting_agent = FakeAccountingAgent

    handler = CommandHandler(Engine())

    assert "Kullanım" in handler.handle("oku:")
    assert handler.handle("oku: rapor.pdf") == "PDF ICERIK: KDV %20"
    assert handler.handle("oku: rapor.xlsx | sayfa: Ocak") == "EXCEL ICERIK sheet=Ocak: Kira | 1000"
    assert handler.handle("oku: not.docx") == "WORD ICERIK"
    assert "okuma aracım yok" in handler.handle("oku: rapor.txt")
    # 'oku:' yalnız hızlı önizleme içindir -- varsayılan (düşük) sınırlarla çağrılır, ekstra kwarg yok
    oku_excel_call = next(c for c in Engine.tool_manager.calls if c[0] == "excel_oku")
    assert "max_rows" not in oku_excel_call[2]

    result = handler.handle("doğrula: rapor.xlsx")
    assert result == "DOGRULAMA SONUCU"
    content, facts_context, facts_registry = FakeAccountingAgent.calls[0]
    assert "EXCEL ICERIK" in content
    assert "KDV oranı (2026): %20" in facts_context
    assert facts_registry is Engine.facts  # DÜZELTME (2026-09-23): kesin (kodla) katman için facts artık iletiliyor
    # DÜZELTME (2026-09-23): 'doğrula:' bir denetimdir -- 'oku:'nün aksine, Excel/PDF araçlarına
    # (varsayılan 50 satır / 30 sayfa yerine) çok daha yüksek bir satır/sayfa sınırı geçiriyor,
    # böylece büyük bir dosyanın "kontrol edilmemiş" kısmı sessizce göz ardı edilmiyor.
    verify_call = next(c for c in Engine.tool_manager.calls if c[0] == "excel_oku" and "max_rows" in c[2])
    assert verify_call[2]["max_rows"] > 50
    assert "Doğrulama için" in handler.handle("doğrula: rapor.docx")
    assert "Kullanım" in handler.handle("doğrula:")

    print("KAIZEN BELGE KOMUTLARI TESTI: BASARILI")


if __name__ == "__main__":
    test_office_tools()
    test_gorsel_oku_reads_text_via_ocr()
    test_pdf_oku_falls_back_to_ocr_for_scanned_pages()
    test_seed_loader()
    test_status_reports_experience_memory_background_stats()
    test_commands()
    test_document_commands()
