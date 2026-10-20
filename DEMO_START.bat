@echo off
setlocal
cd /d "%~dp0"
set "PYEXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYEXE%" (
  where py >nul 2>&1
  if errorlevel 1 (
    echo Python 3 is required. Install Python from python.org.
    pause
    exit /b 1
  )
  py -3 -m venv .venv
  if errorlevel 1 goto :fail
  "%PYEXE%" -m pip install -r requirements.txt
  if errorlevel 1 goto :fail
)
"%PYEXE%" -m demo.run_demo
if errorlevel 1 goto :fail
exit /b 0
:fail
echo.
echo Demo failed to start. Copy the error shown above.
pause
exit /b 1
