@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run DEMO_START.bat to install the requirements.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m demo.run_demo --reset
