@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Sanal ortam bulunamadi: .venv\Scripts\python.exe
    pause
    exit /b 1
)
".venv\Scripts\python.exe" kazen_desktop.py
if errorlevel 1 (
    echo.
    echo KAIZEN bir hatayla kapandi, yukaridaki mesaja bak.
    pause
)
