#!/usr/bin/env python3

"""
Model Generation Script

- Reads raw JSON files from model/schema/ (e.g., app.json, org.json)
- Excludes specified files (app_snapshot.json, apps.json)
- Generates strongly typed Pydantic models in backend/app/models/
- Ensures no optional properties
- Sets default empty string for string properties
- Uses two-space indentation
- Requires datamodel-code-generator==0.31.2, pydantic==2.10.6
"""

import logging
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Define project structure
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCHEMA_DIR = PROJECT_ROOT / "model" / "schema"
APP_MODELS_DIR = PROJECT_ROOT / "backend" / "app" / "models"

# Category mapping for raw JSON files
CATEGORY_MAP = {
  "app": ["app.json", "app_profiles.json", "app_topo.json"],
  "org": ["org.json"],
  "group": ["group.json"],
  "misc": ["aws_account.json", "deploy_profiles.json", "member.json"],
}

# Files to exclude
EXCLUDE_FILES = {"app_snapshot.json", "apps.json"}

def relpath(path: Path) -> str:
  """Return path relative to project root for logging."""
  return str(path.relative_to(PROJECT_ROOT))

def collect_files_by_category() -> Dict[str, List[Path]]:
  """Collect raw JSON files by category, excluding specified files."""
  files_by_category = {cat: [] for cat in CATEGORY_MAP}
  for json_file in sorted(SCHEMA_DIR.glob("*.json")):
    if json_file.name in EXCLUDE_FILES:
      logger.debug(f"Skipping excluded file: {relpath(json_file)}")
      continue
    for category, filenames in CATEGORY_MAP.items():
      if json_file.name in filenames:
        files_by_category[category].append(json_file)
        logger.info(f"Added {relpath(json_file)} to category '{category}'")
        break
    else:
      logger.warning(f"File {relpath(json_file)} not mapped to any category")
  return files_by_category

def generate_models_for_category(category: str, schema_files: List[Path], output_file: Path):
  """Generate Pydantic models for all raw JSON files in a category."""
  output_file.parent.mkdir(parents=True, exist_ok=True)
  temp_output_dir = output_file.parent / f"temp_{category}"
  temp_output_dir.mkdir(parents=True, exist_ok=True)

  for schema_file in schema_files:
    temp_output_file = temp_output_dir / f"{schema_file.stem}_model.py"
    class_name = f"{schema_file.stem.replace('_', ' ').title().replace(' ', '')}Model"
    cmd = [
      "datamodel-codegen",
      "--input", str(schema_file),
      "--input-file-type", "json",
      "--output", str(temp_output_file),
      "--use-default",
      "--disable-timestamp",
      "--use-double-quotes",
      "--strip-default-none",
      "--class-name", class_name,
    ]
    logger.info(f"Running for {relpath(schema_file)}: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
      logger.error(f"datamodel-codegen failed for {relpath(schema_file)}: {result.stderr}")
      raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    if result.stderr:
      logger.warning(f"datamodel-codegen output: {result.stderr}")

  # Combine models into a single file
  with output_file.open("w", encoding="utf-8") as outfile:
    outfile.write("# Auto-generated Pydantic models\n\n")
    outfile.write("from pydantic import BaseModel\n\n")
    for temp_file in sorted(temp_output_dir.glob("*.py")):
      content = temp_file.read_text(encoding="utf-8")
      outfile.write(content + "\n\n")
      logger.info(f"Included models from {relpath(temp_file)} in {relpath(output_file)}")

  shutil.rmtree(temp_output_dir)
  post_process_models(output_file)
  logger.info(f"Generated {output_file.read_text().count('\n')} lines at {relpath(output_file)}")

def post_process_models(output_file: Path):
  """Post-process models to enforce frozen=True, default strings, and no Optional types."""
  content = output_file.read_text(encoding="utf-8")
  lines = content.split("\n")
  new_lines = []
  in_class = False
  for line in lines:
    stripped = line.strip()
    if stripped.startswith("class ") and "BaseModel" in stripped:
      in_class = True
      new_lines.append(line.replace("BaseModel", "BaseModel, frozen=True"))
    elif in_class and ":" in stripped:
      # Remove Optional[...] and add default="" for strings
      if "Optional[" in stripped:
        line = line.replace("Optional[", "").replace("]", "")
      if "str" in stripped and " = " not in stripped:
        line = line + ' = ""'
      new_lines.append(line)
    elif in_class and stripped.startswith("class "):
      in_class = False
      new_lines.append(line)
    else:
      new_lines.append(line)
  # Ensure two-space indentation
  final_lines = []
  for line in new_lines:
    indent_count = len(line) - len(line.lstrip())
    new_indent = "  " * (indent_count // 2)
    final_lines.append(new_indent + line.lstrip())
  output_file.write_text("\n".join(final_lines), encoding="utf-8")
  logger.info(f"Post-processed {relpath(output_file)} to add frozen=True, string defaults, and remove Optional")

def generate_init_py(categories: List[str]):
  """Generate __init__.py with imports for all model files."""
  APP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
  lines = [f"from .{cat}_models import *\n" for cat in categories]
  init_file = APP_MODELS_DIR / "__init__.py"
  init_file.write_text("".join(lines), encoding="utf-8")
  logger.info(f"Generated {relpath(init_file)} with imports for {len(categories)} files")

def clean_output_dir(output_dir: Path):
  """Clean the output directory if it exists."""
  if output_dir.exists():
    shutil.rmtree(output_dir)
    logger.info(f"Cleaned existing output directory {relpath(output_dir)}")

def main():
  """Main function to generate Pydantic models from raw JSON files."""
  try:
    logger.info(f"Collecting raw JSON files from {relpath(SCHEMA_DIR)}")
    clean_output_dir(APP_MODELS_DIR)
    files_by_category = collect_files_by_category()

    if not any(files_by_category.values()):
      logger.error("No raw JSON files found to process")
      return

    for category, schema_files in files_by_category.items():
      if not schema_files:
        logger.warning(f"No raw JSON files found for category '{category}'")
        continue
      output_file = APP_MODELS_DIR / f"{category}_models.py"
      generate_models_for_category(category, schema_files, output_file)

    generate_init_py(list(files_by_category.keys()))
    logger.info("Model generation complete")

  except subprocess.CalledProcessError as e:
    logger.error(f"Subprocess failed: {e.stderr}")
    raise
  except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise

if __name__ == "__main__":
  main()