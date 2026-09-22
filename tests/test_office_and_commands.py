import tempfile
from pathlib import Path

from memory.learning_store import LearningStore
from memory.seed_loader import load_seeds
from tools.office_tools import excel_oku, excel_yaz, gorsel_pdf, pdf_birlestir, pdf_bol, pdf_oku, word_oku, word_yaz


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


if __name__ == "__main__":
    test_office_tools()
    test_seed_loader()
    test_commands()
