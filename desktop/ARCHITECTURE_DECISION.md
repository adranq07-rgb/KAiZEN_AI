# Kaizen Desktop — Mimari Karar Kaydı

**Faz:** KAIZEN BÜYÜK GELİŞTİRME PAKETİ #1, Faz E (madde 16-17)
**Tarih:** 2026-09-23
**Durum:** KARAR VERİLDİ — **tkinter** (Python standart kütüphanesi)

## 1. Karar

Kaizen Desktop Alpha, **tkinter** (Python 3.13 ile birlikte gelen standart GUI kütüphanesi)
üzerine inşa edilir. **PySide6/Qt seçilmedi.** Bu, iş emrinin PySide6 için verdiği ön-kabul
("guidance, not a blind order") açıkça geçersiz kılınarak, repository/ortam incelemesinden
elde edilen somut kanıtlarla alınmış bir karardır (iş emri madde 17/E1: "Repository
incelemesinde daha iyi somut gerekçe varsa alternatif seçebilirsin. Kararı belgelemek
zorundasın.").

## 2. Değerlendirilen seçenekler

| Kriter | PySide6/Qt | Electron | Tauri | **tkinter (seçilen)** |
|---|---|---|---|---|
| Mevcut Python backend ile entegrasyon | Doğrudan (Python) | Yok (Node/JS köprüsü gerekir) | Yok (Rust köprüsü gerekir) | Doğrudan (Python, stdlib) |
| Yeni çalışma zamanı gereksinimi | Qt runtime + pip paketi | Node.js + Chromium (100+ MB) | Rust toolchain + sistem webview | **YOK** — Python kurulu olan her yerde var |
| Python 3.13 uyumluluğu | Evet (PyPI'da mevcut) | N/A | N/A | Evet (stdlib, her zaman) |
| Windows 10 uyumluluğu | Evet | Evet | Evet | Evet (Windows Python kurulumunun standart parçası) |
| Bu ortamda KURULABİLİRLİK | **HAYIR** (bkz. §3, kanıt) | HAYIR (aynı ağ kısıtı) | HAYIR (aynı ağ kısıtı) | **Zaten kurulu (stdlib)** |
| Paket boyutu (EXE) | Orta-büyük (Qt DLL'leri) | Çok büyük (Chromium gömülü) | Küçük-orta | **Küçük** (yalnız Python runtime) |
| Mevcut çalışan kod | Yok | Yok | Yok | **VAR** — `desktop_app.py` zaten gerçek backend'e bağlı, doğru threading ile çalışıyor |
| Proje felsefesi uyumu (AGENTS.md: "yeni paket ekleme") | İhlal eder (yeni bağımlılık) | İhlal eder | İhlal eder | **Uyumlu** (sıfır yeni bağımlılık) |

## 3. Ortam Kanıtı (madde 16: "Tahmin ederek ilerleme" — doğrudan test edildi)

Karardan ÖNCE, üç ayrı yürütme yüzeyinde doğrudan test edildi:

1. **Bulut konteyneri (`Bash` aracı):** `pip install PySide6` → HTTP 403 (kurumsal proxy
   politika reddi, `/root/.ccr/README.md`: "Do not retry or route around it"). `apt-get
   install python3-tk` (tkinter'ı BURADA test edebilmek için denendi) → aynı şekilde HTTP 403
   (archive.ubuntu.com). **Sonuç: bu ortamda ne PySide6 ne de sistem tkinter paketi
   kurulabiliyor.**
2. **`device_bash` (kullanıcının makinesindeki izole Linux VM):** `which cmd.exe
   powershell.exe pwsh.exe` → boş sonuç. Bu, gerçek Windows kabuğu/derleyicisi DEĞİL, ayrı
   bir Ubuntu 22.04 VM'dir (bağlı klasör salt okunur/yazılabilir bind-mount edilir ama
   Windows ikili dosyaları ÇALIŞTIRILAMAZ). **Sonuç: buradan da native Windows derlemesi/PySide6
   testi yapılamıyor.**
3. **Kullanıcının gerçek Windows venv'i (`C:\Users\ANL\Desktop\KAZEN_AI\.venv`, `device_bash`
   üzerinden salt dosya sistemi incelemesiyle):** `pyvenv.cfg` → Python 3.13.15, 340 paket
   kurulu (`Lib/site-packages/` sayımı). PySide6/PyQt6/Qt/Nuitka/pyinstaller/cx_freeze
   klasörlerinden HİÇBİRİ yok. **Sonuç: PySide6, kullanıcının GERÇEK ortamında da şu an
   kurulu değil — kurulumu, kullanıcının kendi makinesinde internet erişimiyle pip'i
   çalıştırmasını gerektirir (bu oturumdan kanıtlanamaz/garanti edilemez).**

Buna karşılık **tkinter, Python'un standart kurulumunun bir PARÇASIDIR** (Windows için
python.org yükleyicisi varsayılan olarak dahil eder) — hiçbir ek kurulum adımı, hiçbir ek
`pip install`, hiçbir ek indirme gerektirmez. Bu, hem "yeni bağımlılık ekleme" riskini hem de
"kullanıcının kurulum adımı çalışmayabilir" riskini SIFIRLAR.

## 4. Mevcut kod kanıtı (madde 17: "büyük bir yeniden yazım YASAK")

Repository incelemesinde, iş emrinden HABERSİZ, ÖNCEDEN yazılmış ve büyük ölçüde çalışan bir
`desktop_app.py` (+ `Kaizen_Baslat.bat` başlatıcı) bulundu:

- `core.engine.KaizenEngine`'i DOĞRUDAN sarmalıyor (H1: gerçek backend, sahte cevap yok).
- Arka plan `threading.Thread` + `queue.Queue` + `root.after()` polling deseniyle UI thread'i
  hiç bloklamıyor (H2: "Not Responding" olmaz).
- Türkçe karakterler, karanlık tema, Enter/Shift+Enter davranışı zaten doğru.

PySide6'ya geçmek bu ÇALIŞAN kodun TAMAMEN atılıp yeniden yazılması anlamına gelirdi — hem
"büyük yeniden yazım yasağı" hem de "gereksiz framework ekleme yasağı" ile doğrudan çelişir.
tkinter seçimi, bu kodu KORUYUP genişletmeyi (Faz F-H) mümkün kılar.

## 5. Bilinen kısıtlar (dürüstçe belgelenir)

- tkinter'ın görsel widget seti Qt kadar zengin/modern DEĞİL — Faz F4'ün ("profesyonel
  masaüstü uygulaması hissi") bir kısmı, özenli renk/boşluk/tipografi seçimleriyle elle
  karşılanmak zorunda (bkz. `desktop_app.py` içindeki BG/PANEL/renk sabitleri).
  - "yerel model kuruldu, GUI'yi de PySide6'ya taşı" gibi.
- **Bu kararın kendisi hiçbir zaman `python3-tk`'yı BU bulut ortamında ÇALIŞTIRARAK
  doğrulanamadı** (§3 madde 1) — `desktop_app.py`'nin gerçek görsel/etkileşimsel
  doğrulaması yalnızca Faz K'da, kullanıcının kendi Windows makinesinde mümkündür. Bu
  yüzden bu pakette iş mantığı (`desktop/adapter.py`) tkinter'dan TAMAMEN ayrıştırılıp bu
  ortamda gerçekten test edildi (bkz. `tests/test_desktop_adapter.py`); yalnız gerçek
  pencere/widget kodu (`desktop_app.py`) sözdizimi denetiminin (`py_compile`) ötesinde
  BURADA çalıştırılarak doğrulanamadı.

## 6. Geri dönüş / gelecekte yeniden değerlendirme

Eğer ileride (a) kullanıcının makinesine gerçekten yerel bir model/Qt kurulur VE (b) tkinter'ın
görsel sınırları somut bir engel hâline gelirse, bu karar yeniden değerlendirilebilir —
ama şu an için hem ortam kanıtı hem mevcut çalışan kod, tkinter'ı net bir şekilde daha
güvenli/doğrulanabilir seçim yapıyor.
