# FAD - FastAPI AWS Dashboard

## Overview

Financial Applications UCOP group aggregate dashboard widget.

## Setup

1. Navigate to the **backend** dir and make that the cwd for fastapi app startup.

3. Create a python virtual environment

  ```sh
  TODO
  ```

2. Install dependencies:

   ```sh
   pip install -r requirements.txt
   ```

3. Run the app:

   ```sh
   fastapi dev app/main.py
   ```
   OR

   ```sh
   uvicorn main:app --reload
   ```

## Features

tree -I "venv|.git|.gitignore|.gitmodules"

## re-generate requirements.txt and requirements-test.txt

pip-compile requirements.in
pip-compile requirements-test.in

pip-sync
