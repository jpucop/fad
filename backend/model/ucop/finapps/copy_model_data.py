#!/usr/bin/env python3
"""
Copy Model Data for FAD Web App
- Copies JSON from backend/model/ucop/finapps/ and backend/model/schema/ to backend/app/data/
"""
import logging
import shutil
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DATA_DIR = PROJECT_ROOT / "backend" / "model" / "ucop" / "finapps"
SOURCE_SCHEMA_DIR = PROJECT_ROOT / "backend" / "model" / "schema"
DEST_DATA_DIR = PROJECT_ROOT / "backend" / "app" / "data"
EXCLUDE_FILES = {"app_snapshot.json", "apps.json"}

def copy_model_data():
  DEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
  for file in SOURCE_DATA_DIR.glob("*.json"):
    if file.name in EXCLUDE_FILES:
      continue
    try:
      shutil.copy2(file, DEST_DATA_DIR / file.name)
      logger.info(f"Copied {file.name}")
    except Exception as e:
      logger.error(f"Failed to copy {file.name}: {e}")
      raise
  for file in SOURCE_SCHEMA_DIR.glob("*.json"):
    if file.name in EXCLUDE_FILES:
      continue
    try:
      shutil.copy2(file, DEST_DATA_DIR / file.name)
      logger.info(f"Copied {file.name}")
    except Exception as e:
      logger.error(f"Failed to copy {file.name}: {e}")
      raise

if __name__ == "__main__":
  copy_model_data()