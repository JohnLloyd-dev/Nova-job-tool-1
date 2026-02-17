#!/bin/bash
# Launch the Resume Customizer GUI

# Set API key if not already set
# You can set it as an environment variable or enter it in the GUI
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Note: OPENAI_API_KEY not set. You can enter it in the GUI when it opens."
    echo "Or set it as an environment variable: export OPENAI_API_KEY='your-api-key'"
fi

# Check if PyQt6 is installed
python3 -c "import PyQt6" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "PyQt6 not found. Installing..."
    pip install PyQt6
fi

# Launch the GUI
python3 resume_customizer_gui.py
