@echo off
cd /d "%~dp0.."
".venv\Scripts\python.exe" tools\repair_acceptance.py > artifacts\repair_acceptance_console.txt 2>&1
echo bitti
