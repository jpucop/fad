@echo off
setlocal

rem Set the virtual environment directory name
set VENV_DIR=venv

rem Check if requirements.txt exists
if not exist "requirements.txt" (
    echo Error: requirements.txt not found in %CD%.
    exit /b 1
)

rem Activate the virtual environment
echo Activating virtual environment...
call %VENV_DIR%\Scripts\activate
