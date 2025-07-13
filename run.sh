#!/bin/bash

set -e

# Activate virtual environment
echo "Activating backend environment..."
source venv/bin/activate || {
  echo "❌ Failed to activate virtual environment"
  exit 1
}

# verify app static assets
echo "Validating app static web files..."
if [ ! -d backend/app/static ] || [ -z "$(ls -A backend/app/static)" ]; then
  echo "❌ No app static assets found."
  exit 1
fi

# verify app models
echo "Validating app models..."
if [ ! -d backend/app/models ] || [ -z "$(ls -A backend/app/models)" ]; then
  echo "❌ No app models found."
  exit 1
fi

# Start frontend watch in background
echo "Starting frontend watch..."
cd frontend
npm run watch &
FRONTEND_PID=$!
cd ..

# Start model watch in background
echo "Starting model watch..."
cd backend/model
watchfiles --filter "*.{json,py}" "python gen_app_models.py --mode all" . &
MODEL_PID=$!
cd ../..

# Verify Uvicorn installation
echo "Verifying Uvicorn installation..."
python -c "import uvicorn" || {
  echo "❌ Uvicorn not installed correctly"
  exit 1
}

# Start FastAPI with Uvicorn
echo "Starting app server..."
cd backend/app
uvicorn main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# Wait for background processes and handle cleanup
trap "echo 'Stopping processes...'; kill $FRONTEND_PID $MODEL_PID $BACKEND_PID 2>/dev/null; exit" INT TERM
wait