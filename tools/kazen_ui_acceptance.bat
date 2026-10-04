@echo off
cd /d "%~dp0.."
if not exist artifacts\kazen_ui_20261004 mkdir artifacts\kazen_ui_20261004
".venv\Scripts\python.exe" tools\kazen_ui_acceptance.py > artifacts\kazen_ui_20261004\console.txt 2>&1
type artifacts\kazen_ui_20261004\console.txt
echo.
echo bitti - bu pencereyi kapatabilirsin
pause
