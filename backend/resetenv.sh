#!/bin/bash

# Set the virtual environment directory name
VENV_DIR=".venv"

# Check if requirements.txt exists
if [[ ! -f "requirements.txt" ]]; then
    echo "❌ Error: requirements.txt not found in $(pwd)."
    exit 1
fi

# Remove old virtual environment if it exists
if [[ -d "$VENV_DIR" ]]; then
    echo "🗑️  Removing existing virtual environment ($VENV_DIR)..."
    rm -rf "$VENV_DIR"
fi

# Create a new virtual environment
echo "🚀 Creating new virtual environment ($VENV_DIR)..."
python3 -m venv "$VENV_DIR"

# Activate the virtual environment
echo "✅ Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Install dependencies from requirements.txt
echo "📦 Installing dependencies from requirements.txt..."
pip install -r requirements.txt

echo "🎉 Virtual environment setup complete!"
