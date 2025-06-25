#!/usr/bin/env python3

import logging
import subprocess
from pathlib import Path
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
SCHEMA_DIR = BASE_DIR / "model" / "schema"
MODEL_DIR = BASE_DIR / "model" / "ucop" / "finapps" / "models"

# You can optionally set APP_MODELS_DIR if you want to copy models elsewhere
# APP_MODELS_DIR = BASE_DIR / "app" / "models"

def run_datamodel_generator(input_file: Path, output_dir: Path, class_name: str):
  cmd = [
    "datamodel-codegen",
    "--input", str(input_file),
    "--input-file-type", "json",
    "--output", str(output_dir / f"{input_file.stem}.py"),
    "--class-name", class_name,
    "--disable-timestamp",
    "--strip-default-none",
    "--use-double-quotes"
  ]
  logger.info(f"Running: {' '.join(cmd)}")
  subprocess.run(cmd, check=True)

def generate_init_py(models_dir: Path):
  model_files = [f.stem for f in models_dir.glob("*.py") if f.name != "__init__.py"]
  init_lines = [
    f"from .{model} import {''.join(word.capitalize() for word in model.split('_'))}\n"
    for model in sorted(model_files)
  ]
  init_file = models_dir / "__init__.py"
  init_file.write_text("".join(init_lines), encoding="utf-8")
  logger.info(f"Generated __init__.py with {len(model_files)} model imports at {init_file}")

def generate_models():
  logger.info(f"Generating models from {SCHEMA_DIR} to {MODEL_DIR}")
  MODEL_DIR.mkdir(parents=True, exist_ok=True)

  for json_file in sorted(SCHEMA_DIR.glob("*.json")):
    class_name = "".join(word.capitalize() for word in json_file.stem.split("_"))
    run_datamodel_generator(json_file, MODEL_DIR, class_name)

  generate_init_py(MODEL_DIR)

  # Optional: copy to app folder
  # copy_models_to_app(MODEL_DIR, APP_MODELS_DIR)

def copy_models_to_app(src_models_dir: Path, target_app_dir: Path):
  target_app_dir.mkdir(parents=True, exist_ok=True)
  for file_path in src_models_dir.glob("*.py"):
    shutil.copy(file_path, target_app_dir / file_path.name)
    logger.info(f"Copied {file_path.name} to app models dir {target_app_dir}")
  generate_init_py(target_app_dir)

if __name__ == "__main__":
  try:
    generate_models()
  except subprocess.CalledProcessError as e:
    logger.error(f"datamodel-code-generator failed with exit code {e.returncode}")
  except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
