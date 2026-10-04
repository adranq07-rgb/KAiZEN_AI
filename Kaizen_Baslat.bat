@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Sanal ortam bulunamadi: .venv\Scripts\python.exe
    echo Once kurulum adimlarini tamamla.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" desktop_app.py
if errorlevel 1 (
    echo.
    echo Kaizen bir hatayla kapandi, yukaridaki mesaja bak.
    pause
)
