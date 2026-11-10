@echo off
REM Builds dist\PDFuser.exe (run from the repo root on Windows)
python -m pip install -r requirements-dev.txt
python -m PyInstaller --noconfirm --onefile --windowed --name PDFuser run.py
echo.
echo Done: dist\PDFuser.exe
