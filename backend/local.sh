#!/bin/sh
set -e

echo("starting localhost fastapi server..")
fastapi dev backend/app/main.py

