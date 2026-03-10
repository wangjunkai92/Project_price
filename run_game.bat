@echo off
setlocal
cd /d %~dp0

if not exist racer_game.py (
  echo [ERROR] racer_game.py not found in current folder.
  pause
  exit /b 1
)

findstr /C:"def safe_sys_font" racer_game.py >nul
if errorlevel 1 (
  echo [ERROR] Your racer_game.py is an old version. Please run: git pull
  pause
  exit /b 1
)

python racer_game.py
if errorlevel 1 (
  echo.
  echo [ERROR] Start failed. Try:
  echo   python -m pip install -r requirements.txt
)

pause
