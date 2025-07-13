#!/bin/bash

set -e

# Activate virtual environment
echo "Activating backend environment..."
source venv/bin/activate || {
  echo "❌ Failed to activate virtual environment"
  exit 1
}

# Install backend dependencies
echo "Installing backend dependencies..."
pip install -r requirements.txt typer || {
  echo "❌ Failed to install backend dependencies"
  exit 1
}

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend
npm install || {
  echo "❌ Failed to install frontend dependencies"
  exit 1
}
cd ..

# build frontend
echo "Building frontend..."
cd frontend
npm run build || {
  echo "❌ Frontend build failed"
  exit 1
}
