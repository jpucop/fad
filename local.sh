#!/bin/bash

# Exit on error
set -e

# Activate virtual environment
echo "Activating backend environment..."
source backend/app/venv/bin/activate || {
  echo "❌ Failed to activate virtual environment"
  exit 1
}

# Install backend dependencies
echo "Installing backend dependencies..."
pip install -r backend/requirements.txt || {
  echo "❌ Failed to install backend dependencies"
  exit 1
}

# Install watchfiles for model directory watch
echo "Installing watchfiles for model watch..."
pip install watchfiles || {
  echo "❌ Failed to install watchfiles"
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

# Initial frontend build
echo "Building frontend..."
cd frontend
npm run build || {
  echo "❌ Frontend build failed"
  exit 1
}
cd ..

# Initial Pydantic model generation
echo "Generating Pydantic models..."
cd backend/model/ucop
if [ -f gen_web_model.py ]; then
  python gen_web_model.py || {
    echo "❌ Pydantic model generation failed"
    exit 1
  }
else
  echo "⚠️ gen_web_model.py not found, skipping model generation"
fi
cd ../../..

# Initial model data copy
echo "Copying model data..."
cd backend/model/ucop
if [ -f gen_web_data.py ]; then
  python gen_web_data.py || {
    echo "❌ Model data copy failed"
    exit 1
  }
else
  echo "⚠️ gen_web_data.py not found, skipping data copy"
fi
cd ../../..

# Start frontend watch in background
echo "Starting frontend watch..."
cd frontend
npm run buildwatch &
FRONTEND_PID=$!
cd ..

# Start model watch in background
echo "Starting model watch..."
cd backend/model
watchfiles --filter "*.{json,py}" "python ucop/gen_web_model.py && python ucop/gen_web_data.py" . &
MODEL_PID=$!
cd ../..

# Start FastAPI with reload
echo "Starting FastAPI server..."
cd backend/app
fastapi dev main.py &
BACKEND_PID=$!

# Wait for background processes and handle cleanup
trap "echo 'Stopping processes...'; kill $FRONTEND_PID $MODEL_PID $BACKEND_PID 2>/dev/null; exit" INT TERM
wait