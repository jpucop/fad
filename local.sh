#!/bin/bash

# Exit on error
set -e

# Activate virtual environment
echo "Activating backend environment..."
source venv/bin/activate || {
  echo "❌ Failed to activate virtual environment"
  exit 1
}

# Install backend dependencies
echo "Installing backend dependencies..."
pip install -r backend/requirements.txt typer || {
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

# Validate static files
echo "Validating static files..."
if [ ! -d backend/app/static ] || [ -z "$(ls -A backend/app/static)" ]; then
  echo "❌ No static web files present in app/static/"
  exit 1
fi

# Initial model generation
echo "Generating models and copying data..."
cd backend/model
if [ -f generate.py ]; then
  python generate.py --mode all || {
    echo "❌ Model generation and data copy failed"
    exit 1
  }
else
  echo "❌ generate.py not found in backend/model/"
  exit 1
fi
cd ../..

# Validate models
echo "Validating models..."
if [ ! -d backend/app/models ] || [ -z "$(ls -A backend/app/models)" ]; then
  echo "❌ No models present in app -- need to run model/generate.py"
  exit 1
fi

# Start frontend watch in background
echo "Starting frontend watch..."
cd frontend
npm run buildwatch &
FRONTEND_PID=$!
cd ..

# Start model watch in background
echo "Starting model watch..."
cd backend/model
watchfiles --filter "*.{json,py}" "python generate.py --mode all" . &
MODEL_PID=$!
cd ../..

# Verify Uvicorn installation
echo "Verifying Uvicorn installation..."
python -c "import uvicorn" || {
  echo "❌ Uvicorn not installed correctly"
  exit 1
}

# Start FastAPI with Uvicorn
echo "Starting FastAPI server..."
cd backend/app
uvicorn main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# Wait for background processes and handle cleanup
trap "echo 'Stopping processes...'; kill $FRONTEND_PID $MODEL_PID $BACKEND_PID 2>/dev/null; exit" INT TERM
wait