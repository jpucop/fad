@echo off
setlocal

cd /d %USERPROFILE%\dev\fad\backend

echo Starting localhost FastAPI server..
uvicorn app.main:app --reload
