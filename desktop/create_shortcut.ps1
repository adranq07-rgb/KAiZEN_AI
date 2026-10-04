# KAIZEN BUYUK GELISTIRME PAKETI #1, Faz J (madde 22): masaustu kisayolu.
#
# NEDEN Kaizen_Baslat.bat'a isaret ediyor (bir .exe'ye DEGIL): desktop/ARCHITECTURE_DECISION.md
# ve desktop/README.md'de aciklandigi gibi, PyInstaller ile paketlenmis bir .exe icindeki
# `Path(__file__).resolve().parent.parent / "data"` gibi yollar frozen ortamda FARKLI bir
# konuma (gecici/bundle klasoru) cozulebilir -- bu, gercek musavirlik verisinin (data/,
# knowledge/, memory/) yanlislikla BOS bir kopyaya yazilmasi riski tasir ve bu oturumda
# hicbir Windows yurutme yuzeyinde TEST EDILEMEDI (bkz. ARCHITECTURE_DECISION.md SS3/SS5).
# `Kaizen_Baslat.bat` ise ZATEN calisan, `cd /d "%~dp0"` ile proje kokunu doğru cozen,
# kaynaktan calistirma yontemidir (DURDURMA kurali: "Paketleme basarisiz -> calisan
# from-source Desktop Alpha'yi koru"). Bu yuzden kisayol GUVENLI/KANITLANMIS yolu isaret eder.
#
# CALISTIRMA: bu dosyayi KAZEN_AI proje klasorunde (Kaizen_Baslat.bat ile AYNI klasorde)
# PowerShell'de calistirin:
#     powershell -ExecutionPolicy Bypass -File desktop\create_shortcut.ps1
# Kisayol, gecerli kullanicinin masaustune "Kaizen.lnk" olarak eklenir.

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LauncherPath = Join-Path $ProjectRoot "Kaizen_Baslat.bat"
$IconPath = Join-Path $ProjectRoot "desktop\icon\kaizen.ico"
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "Kaizen.lnk"

if (-not (Test-Path $LauncherPath)) {
    Write-Error "Kaizen_Baslat.bat bulunamadi: $LauncherPath. Bu betigi proje kokundeki desktop\ klasorunden calistirdiginizdan emin olun."
    exit 1
}
if (-not (Test-Path $IconPath)) {
    Write-Warning "Simge dosyasi bulunamadi: $IconPath -- kisayol varsayilan .bat simgesiyle olusturulacak."
    $IconPath = $LauncherPath
}

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $LauncherPath
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.IconLocation = $IconPath
$Shortcut.Description = "Kaizen AI - mali musavir asistani"
$Shortcut.Save()

Write-Host "Kaizen kisayolu olusturuldu: $ShortcutPath"
Write-Host "Hedef: $LauncherPath"
Write-Host "Calisma klasoru: $ProjectRoot"
Write-Host "Simge: $IconPath"
