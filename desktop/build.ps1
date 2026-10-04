# KAIZEN BUYUK GELISTIRME PAKETI #1, Faz I (madde 21): Windows EXE derlemesi (PyInstaller).
#
# ONEMLI / DURUM (durustce belgelenir -- bkz. desktop/ARCHITECTURE_DECISION.md SS5 ve
# desktop/README.md "Bilinen Alpha sinirlari"): bu betik hicbir yurutme yuzeyinde
# (bulut konteyneri, device_bash izole Linux VM) CALISTIRILAMADI/TEST EDILEMEDI --
# ikisi de gercek Windows ikili dosyalarini calistiramiyor. Bu betik EN IYI CABA
# (best-effort) ile, koda bakarak yazildi; kullanicinin GERCEK Windows makinesinde
# ILK calistirmasinda dogrulanmasi gerekir (Faz K, User Acceptance Test).
#
# BILINEN RISK (onemli): Kaizen'in veri depolari (LearningStore/SiteStore/FactRegistry/
# PrincipleRegistry/ExperienceStore/ReflectionStore/KnowledgeCardStore) varsayilan yollarini
# `Path(__file__).resolve().parent.parent / "data" / ...` seklinde COZER. PyInstaller ile
# paketlenmis (frozen) bir .exe icinde `__file__` KAYNAK agactaki gercek proje kokunu degil,
# PyInstaller'in gecici/bundle konumunu gosterir -- bu da EXE'nin, musavirin GERCEK
# data/knowledge/memory klasorleri YERINE bos/yanlis bir konuma yazmasina yol acabilir.
# Bu KESINLIKLE istenmeyen bir durumdur (KESINLIKLE YAPILMAYACAKLAR: "gercek hafizayi
# temizleme" riskiyle akraba). Bu yuzden:
#   - Kaizen Desktop Alpha'nin birincil, DOGRULANMIS teslimat yontemi hala KAYNAKTAN
#     calistirmadir (Kaizen_Baslat.bat + masaustu kisayolu, bkz. create_shortcut.ps1).
#   - Bu EXE derlemesi ISTEGE BAGLI, deneysel bir ikinci secenektir. Ilk calistirmada
#     'durum' komutuyla Kaizen'in GERCEK data/ klasorunu mu yoksa EXE'nin yaninda yeni
#     bos bir data/ klasoru mu OLUSTURDUGUNU mutlaka kontrol edin (bkz. README).
#
# CALISTIRMA (proje kokunde, PowerShell'de):
#     powershell -ExecutionPolicy Bypass -File desktop\build.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error ".venv bulunamadi ($Python). Once: python -m venv .venv ve requirements.txt kurulumu gerekir."
    exit 1
}

Write-Host "PyInstaller kontrol ediliyor / kuruluyor (yalniz bu adim icin, requirements.txt'e EKLENMEDI çünkü yalnizca paketleme zamaninda gerekir)..."
& $Python -m pip show pyinstaller *> $null
if ($LASTEXITCODE -ne 0) {
    & $Python -m pip install --disable-pip-version-check pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Error "PyInstaller kurulamadi. Internet erisimini kontrol edin."
        exit 1
    }
}

Write-Host "Kaizen Desktop deleniyor (standalone/onedir -- 'onefile' TERCIH EDILMEDI, madde 21: 'daha guvenilirse standalone tercih et')..."
& $Python -m PyInstaller `
    --name "Kaizen" `
    --windowed `
    --onedir `
    --icon "desktop\icon\kaizen.ico" `
    --distpath "dist" `
    --workpath "build" `
    --noconfirm `
    desktop_app.py

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller derlemesi basarisiz oldu. Kaynaktan calisan Kaizen_Baslat.bat ETKILENMEDI, hala kullanilabilir."
    exit 1
}

Write-Host ""
Write-Host "Derleme tamamlandi: dist\Kaizen\Kaizen.exe"
Write-Host ""
Write-Host "ONEMLI DOGRULAMA ADIMI: dist\Kaizen\Kaizen.exe'yi calistirip 'durum' yazin ve" -ForegroundColor Yellow
Write-Host "cikan ders/site sayisini bu proje kokundeki 'durum' ciktisiyla karsilastirin." -ForegroundColor Yellow
Write-Host "Farkliysa (ozellikle SIFIRSA), EXE kendi bos data/ klasorunu olusturmus olabilir --" -ForegroundColor Yellow
Write-Host "bu durumda EXE'yi SILIN ve Kaizen_Baslat.bat ile kaynaktan calistirmaya devam edin." -ForegroundColor Yellow
