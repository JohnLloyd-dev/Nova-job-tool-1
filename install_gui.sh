#!/bin/bash
# Install GUI dependencies

echo "Installing Resume Customizer GUI dependencies..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found. Please install Python 3.7 or higher."
    exit 1
fi

echo "Python version:"
python3 --version
echo ""

# Install PyQt6
echo "Installing PyQt6..."
pip install PyQt6

# Install OpenAI if not already installed
echo ""
echo "Installing OpenAI..."
pip install openai

echo ""
echo "✅ Installation complete!"
echo ""
echo "To launch the GUI, run:"
echo "  ./launch_gui.sh"
echo "  or"
echo "  python3 resume_customizer_gui.py"
