@echo off
REM Build Windows executable for Resume Customizer GUI
REM This script creates a standalone Windows executable

echo ========================================
echo Building Resume Customizer for Windows
echo ========================================
echo.

REM Check if Python is installed (try py -3 first on Windows, then python)
set PYEXE=python
py -3 --version >nul 2>&1
if %errorlevel% equ 0 set PYEXE=py -3
if "%PYEXE%"=="python" python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7 or higher
    pause
    exit /b 1
)

echo [1/4] Installing/updating PyInstaller...
%PYEXE% -m pip install --upgrade pip
%PYEXE% -m pip install pyinstaller

echo.
echo [2/4] Installing dependencies...
%PYEXE% -m pip install -r requirements.txt

echo.
echo [3/4] Building executable with PyInstaller...
%PYEXE% -m PyInstaller --clean resume_customizer_gui.spec

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo [4/4] Build complete!
echo.
echo The executable is located in: dist\ResumeCustomizerGUI.exe
echo.
echo You can now distribute the entire 'dist' folder or just the .exe file.
echo.
pause
