@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo ROHI IMS - Windows PC Build
echo ================================================

where py >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python is not installed or not in PATH.
  echo Install Python 3.11 or 3.12 from python.org and enable "Add Python to PATH".
  pause
  exit /b 1
)

py -3.11 -m venv .venv 2>nul
if errorlevel 1 (
  py -3.12 -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Could not create the Python virtual environment.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements_windows.txt

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist ROHI_IMS.spec del /q ROHI_IMS.spec

python -m PyInstaller --noconfirm --clean --onedir --windowed --name ROHI_IMS ^
  --add-data "*.kv;." ^
  --add-data "assets;assets" ^
  --add-data "templates;templates" ^
  --add-data "*.png;." ^
  --add-data "*.jpg;." ^
  main.py

if errorlevel 1 (
  echo.
  echo BUILD FAILED. Read the error above.
  pause
  exit /b 1
)

echo.
echo ================================================
echo BUILD COMPLETE
echo ================================================
echo EXE: dist\ROHI_IMS\ROHI_IMS.exe
echo.
echo Copy the entire dist\ROHI_IMS folder when moving the app to another PC.
echo.
pause
