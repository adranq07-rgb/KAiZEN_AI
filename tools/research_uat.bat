@echo off
setlocal
rem KAIZEN Research Engine -- GERCEK PC UAT calistiricisi (madde 3/28).
rem Proje kokunden TEK KOMUT: tools\research_uat.bat
rem Bu dosya hicbir ayar DEGISTIRMEZ; yalniz dogru Python ortamini bulup
rem tools\research_uat.py'yi calistirir. Cikti hem ekrana hem de
rem artifacts\research_uat_report.json / .txt dosyalarina yazilir.

cd /d "%~dp0.."

set PYTHON_EXE=
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
    ) else (
        where py >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=py"
        )
    )
)

if "%PYTHON_EXE%"=="" (
    echo Python bulunamadi: ne .venv\Scripts\python.exe ne de PATH'te python/py var.
    echo Once kurulum adimlarini tamamlayin ya da bir Python 3 kurulumu ekleyin.
    pause
    exit /b 1
)

echo ================================================================
echo KAIZEN Research Engine -- Gercek PC UAT baslatiliyor
echo Python: %PYTHON_EXE%
echo Proje kok: %CD%
echo ================================================================
echo.

"%PYTHON_EXE%" tools\research_uat.py
set UAT_EXIT_CODE=%ERRORLEVEL%

echo.
echo ================================================================
if %UAT_EXIT_CODE%==0 (
    echo SONUC: PASS
) else if %UAT_EXIT_CODE%==1 (
    echo SONUC: PARTIAL
) else if %UAT_EXIT_CODE%==2 (
    echo SONUC: FAIL
) else (
    echo SONUC: SCRIPT COKTU ^(cikis kodu %UAT_EXIT_CODE%^) -- yukaridaki hatayi inceleyin.
)
echo Ayrintili rapor: artifacts\research_uat_report.txt
echo Ayrintili rapor (JSON): artifacts\research_uat_report.json
echo ================================================================
echo.
pause
exit /b %UAT_EXIT_CODE%
