#!/bin/bash
# Build Windows executable for Resume Customizer GUI
# This script creates a standalone Windows executable using PyInstaller

set -e

echo "========================================"
echo "Building Resume Customizer for Windows"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.7 or higher"
    exit 1
fi

echo "[1/4] Installing/updating PyInstaller..."
python3 -m pip install --upgrade pip
python3 -m pip install pyinstaller

echo ""
echo "[2/4] Installing dependencies..."
python3 -m pip install -r requirements.txt

echo ""
echo "[3/4] Building executable with PyInstaller..."
pyinstaller --clean resume_customizer_gui.spec

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Build failed!"
    exit 1
fi

echo ""
echo "[4/4] Build complete!"
echo ""
echo "The executable is located in: dist/ResumeCustomizerGUI"
echo ""
echo "You can now distribute the executable file."
echo ""
