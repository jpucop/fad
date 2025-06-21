#!/bin/bash

# Ensure the script is sourced, not executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Please source this script: source $0"
  exit 1
fi

# Ensure a requirements.txt exists
if [[ ! -f "requirements.txt" ]]; then
  echo "❌ Error: requirements.txt not found"
  return 1
fi

VENV_DIR="venv"

# Create virtual environment if it doesn't exist
if [[ ! -d "$VENV_DIR" ]]; then
  echo "🚀 Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# Activate the virtual environment if it's not already activated
if [[ -d "$VENV_DIR" && ! $(which python) =~ "$VENV_DIR" ]]; then
  echo "🔌 Activating virtual environment..."
  source "$VENV_DIR/bin/activate"
  echo "✅ Virtual environment activated."
fi

# Install dependencies
echo "📦 Installing dependencies from requirements.txt..."
pip install --upgrade pip  # Ensure pip is up-to-date
pip install -r requirements.txt

echo "🦍 online"
