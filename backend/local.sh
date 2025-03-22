#!/bin/sh
set -e

cd ~/dev/fad/backend
echo("running from <project_root>/backend/")

echo("starting localhost fastapi server..")
# fastapi dev backend/app/main.py
uvicorn main:app --reload
