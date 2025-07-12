@echo off
setlocal

cd /d %USERPROFILE%\dev\workspaces\finapps\aws\fad

echo Starting localhost FastAPI server..
uvicorn backend.app.main:app --reload --use-colors --reload-dir backend/app
