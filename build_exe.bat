@echo off
setlocal

python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --onefile --windowed --name NeoCircuitRacer racer_game.py

echo.
echo Build finished. EXE is in dist\NeoCircuitRacer.exe
pause
