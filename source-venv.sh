#!/bin/bash

# Set the virtual environment directory name
VENV_DIR="venv"

# Check if requirements.txt exists
if [[ ! -f "requirements.txt" ]]; then
    echo "❌ Error: requirements.txt not found in $(pwd)."
    exit 1
fi

# Activate the virtual environment
echo "✅ Activating virtual environment..."
source "$VENV_DIR/bin/activate"

