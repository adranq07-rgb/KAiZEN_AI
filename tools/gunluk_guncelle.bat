@echo off
REM Kaizen gunluk site guncellemesi. Windows Gorev Zamanlayicisi bu dosyayi calistirir.
cd /d "%~dp0.."
where python >nul 2>nul
if %errorlevel%==0 (
    python -m accounting.refresh --max-pages 60 >> logs\refresh_console.log 2>&1
) else (
    py -3 -m accounting.refresh --max-pages 60 >> logs\refresh_console.log 2>&1
)
