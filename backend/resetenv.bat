@echo off
setlocal

set VENV_DIR=venv

if not exist requirements.txt (
  echo Error: requirements.txt not found in %CD%.
  exit /b 1
)

echo Creating/re-pointing venv
python -m venv %VENV_DIR%

echo Installing dependencies from requirements.txt
call %VENV_DIR%\Scripts\activate && pip install -r requirements.txt

echo Activating venv..
call %VENV_DIR%\Scripts\activate

echo Virtual environment setup complete!
cmd /k
