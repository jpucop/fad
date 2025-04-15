#!/bin/sh
set -e

cd backend

echo "starting localhost fastapi server.."
# fastapi dev backend/app/main.py
uvicorn app.main:app --reload
