@echo off
setlocal
cd /d "%~dp0"
python scripts\run_desktop.py
if errorlevel 1 (
  echo.
  echo Enterprise RAG Workbench failed to start.
  echo Run this diagnostic command and share the output:
  echo python scripts\diagnose_desktop.py
  pause
)
