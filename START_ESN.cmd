@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 launch_esn.py
) else (
  python launch_esn.py
)
if errorlevel 1 (
  echo.
  echo ESN could not start. Python 3.11 or newer is required.
  pause
)
