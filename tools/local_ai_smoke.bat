@echo off
setlocal
rem KAIZEN Yerel AI (Ollama) -- GERCEK PC SMOKE TEST calistiricisi.
rem Proje kokunden TEK KOMUT: tools\local_ai_smoke.bat
rem Bu dosya hicbir ayar DEGISTIRMEZ; yalniz dogru Python ortamini bulup
rem tools\local_ai_smoke.py'yi calistirir. Cikti hem ekrana hem de
rem artifacts\local_ai_smoke_report.json / .txt dosyalarina yazilir.
rem Onkosul: Ollama calisiyor olmali ("ollama serve" / Ollama uygulamasi acik),
rem llama3.2:3b ve bge-m3 modelleri zaten indirilmis olmali (kurulum yapilmaz).

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
    pause
    exit /b 1
)

echo ================================================================
echo KAIZEN Yerel AI (Ollama) -- Gercek PC Smoke Test baslatiliyor
echo Python: %PYTHON_EXE%
echo Proje kok: %CD%
echo ================================================================
echo.

"%PYTHON_EXE%" tools\local_ai_smoke.py
set SMOKE_EXIT_CODE=%ERRORLEVEL%

echo.
echo ================================================================
if %SMOKE_EXIT_CODE%==0 (
    echo SONUC: PASS
) else if %SMOKE_EXIT_CODE%==1 (
    echo SONUC: PARTIAL
) else if %SMOKE_EXIT_CODE%==2 (
    echo SONUC: FAIL
) else (
    echo SONUC: SCRIPT COKTU ^(cikis kodu %SMOKE_EXIT_CODE%^) -- yukaridaki hatayi inceleyin.
)
echo Ayrintili rapor: artifacts\local_ai_smoke_report.txt
echo Ayrintili rapor (JSON): artifacts\local_ai_smoke_report.json
echo ================================================================
echo.
pause
exit /b %SMOKE_EXIT_CODE%
