#!/usr/bin/env python3

"""
Model Generation Script

- Reads raw JSON files from backend/model/schema/ (e.g., app.json, org.json)
- Excludes specified files (app_snapshot.json, apps.json)
- Generates one Pydantic model file per JSON file in backend/models/
- Creates NamedEntity (for name) and NameDesc (for name, description) base classes
- Ensures strongly typed arrays (e.g., list[AwsAccount], list[str])
- Ensures no optional properties
- Sets default empty string for string properties
- Uses two-space indentation
- Logs paths relative to backend/
- Requires datamodel-code-generator==0.31.2, pydantic==2.10.6
"""

import json
import logging
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Define project structure
def find_project_root() -> Path:
  """Find project root by walking up until backend/ is found."""
  current = Path(__file__).resolve().parent
  while current != current.parent:
    if (current / "backend").is_dir():
      return current
    current = current.parent
  raise RuntimeError("Project root with backend/ not found")

PROJECT_ROOT = find_project_root()
BACKEND_DIR = PROJECT_ROOT / "backend"
SCHEMA_DIR = BACKEND_DIR / "model" / "schema"
APP_MODELS_DIR = BACKEND_DIR / "models"

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
  """Return path relative to backend/."""
  try:
    return str(path.relative_to(BACKEND_DIR))
  except ValueError:
    return str(path.relative_to(PROJECT_ROOT))

def collect_files_by_category() -> Dict[str, List[Path]]:
  """Collect raw JSON files by category, excluding specified files."""
  files_by_category = {cat: [] for cat in CATEGORY_MAP}
  if not SCHEMA_DIR.exists():
    logger.error(f"SCHEMA_DIR {SCHEMA_DIR} does not exist")
    return files_by_category
  json_files = list(SCHEMA_DIR.glob("*.json"))
  logger.info(f"Found {len(json_files)} JSON files in {relpath(SCHEMA_DIR)}: {[f.name for f in json_files]}")
  for json_file in sorted(json_files):
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

def infer_type(value) -> str:
  """Infer Python type from JSON value."""
  if isinstance(value, str):
    return "str"
  elif isinstance(value, int):
    return "int"
  elif isinstance(value, float):
    return "float"
  elif isinstance(value, bool):
    return "bool"
  elif isinstance(value, list):
    return "list"
  elif isinstance(value, dict):
    return "dict"
  return "str"  # Default to str for null or unknown types

def validate_arrays(data: dict, file_path: Path) -> bool:
  """Ensure all arrays are non-empty and have typed elements."""
  for key, value in data.items():
    if isinstance(value, list):
      if not value:
        logger.error(f"Empty array found for '{key}' in {relpath(file_path)}")
        return False
      if not isinstance(value[0], (str, dict)):
        logger.error(f"Array '{key}' in {relpath(file_path)} has invalid element type: {type(value[0])}")
        return False
  return True

def get_sub_model_base_class(data: dict, field_name: str, class_name: str) -> str:
  """Determine base class for sub-models based on JSON data."""
  if isinstance(data.get(field_name), dict):
    sub_data = data[field_name]
    has_name_desc = ("name" in sub_data and infer_type(sub_data["name"]) == "str" and
                    "description" in sub_data and infer_type(sub_data["description"]) == "str")
    has_name = "name" in sub_data and infer_type(sub_data["name"]) == "str"
    return "NameDesc" if has_name_desc else "NamedEntity" if has_name else "BaseModel"
  elif isinstance(data.get(field_name), list) and data[field_name] and isinstance(data[field_name][0], dict):
    sub_data = data[field_name][0]
    has_name_desc = ("name" in sub_data and infer_type(sub_data["name"]) == "str" and
                    "description" in sub_data and infer_type(sub_data["description"]) == "str")
    has_name = "name" in sub_data and infer_type(sub_data["name"]) == "str"
    return "NameDesc" if has_name_desc else "NamedEntity" if has_name else "BaseModel"
  return "BaseModel"

def find_common_fields(datas: List[dict]) -> Tuple[Set[Tuple[str, str]], Set[Tuple[str, str]]]:
  """Identify common fields for NamedEntity (name) and NameDesc (name, description)."""
  all_field_sets = []
  name_desc_field_sets = []
  for data in datas:
    fields = {(key, infer_type(value)) for key, value in data.items()}
    all_field_sets.append(fields)
    if "name" in data and "description" in data and infer_type(data["name"]) == "str" and infer_type(data["description"]) == "str":
      name_desc_field_sets.append({("name", "str"), ("description", "str")})
  named_entity_fields = set.intersection(*all_field_sets) if all_field_sets else set()
  name_desc_fields = set.intersection(*name_desc_field_sets) if name_desc_field_sets else set()
  logger.info(f"Found NamedEntity fields: {list(named_entity_fields)}")
  logger.info(f"Found NameDesc fields: {list(name_desc_fields)}")
  return named_entity_fields, name_desc_fields

def generate_base_model(named_entity_fields: Set[Tuple[str, str]], name_desc_fields: Set[Tuple[str, str]]):
  """Generate base_model.py with NamedEntity and NameDesc classes."""
  output_file = APP_MODELS_DIR / "base_model.py"
  output_file.parent.mkdir(parents=True, exist_ok=True)
  lines = [
    "# Auto-generated Pydantic base models\n",
    "\n",
    "from pydantic import BaseModel\n",
    "\n",
    "class NamedEntity(BaseModel, frozen=True):\n",
  ]
  for field_name, field_type in sorted(named_entity_fields):
    default = ' = ""' if field_type == "str" else ""
    lines.append(f"  {field_name}: {field_type}{default}\n")
  if not named_entity_fields:
    lines.append("  pass\n")
  lines.append("\n")
  lines.append("class NameDesc(NamedEntity, frozen=True):\n")
  name_desc_only = name_desc_fields - named_entity_fields
  for field_name, field_type in sorted(name_desc_only):
    default = ' = ""' if field_type == "str" else ""
    lines.append(f"  {field_name}: {field_type}{default}\n")
  if not name_desc_only:
    lines.append("  pass\n")
  output_file.write_text("\n".join(lines), encoding="utf-8")
  logger.info(f"Generated base model at {relpath(output_file)} with NamedEntity: {len(named_entity_fields)}, NameDesc: {len(name_desc_only)} fields")

def generate_model_for_file(schema_file: Path, output_file: Path, named_entity_fields: Set[Tuple[str, str]], name_desc_fields: Set[Tuple[str, str]]):
  """Generate Pydantic model for a single JSON file."""
  # Validate JSON file
  try:
    with schema_file.open() as f:
      data = json.load(f)
    if not validate_arrays(data, schema_file):
      logger.error(f"Skipping {relpath(schema_file)} due to invalid arrays")
      return
  except json.JSONDecodeError as e:
    logger.error(f"Failed to parse {relpath(schema_file)}: {e}")
    return

  output_file.parent.mkdir(parents=True, exist_ok=True)
  temp_output_file = output_file.parent / f"temp_{schema_file.stem}_model.py"
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

  # Post-process the model
  post_process_model(temp_output_file, output_file, schema_file, data, named_entity_fields, name_desc_fields)
  logger.info(f"Generated {output_file.read_text().count('\n')} lines at {relpath(output_file)}")

def post_process_model(input_file: Path, output_file: Path, schema_file: Path, data: dict, named_entity_fields: Set[Tuple[str, str]], name_desc_fields: Set[Tuple[str, str]]):
  """Post-process a model to add frozen=True, string defaults, remove Optional, inherit NamedEntity/NameDesc, and ensure typed arrays."""
  named_entity_field_names = {field_name for field_name, _ in named_entity_fields}
  name_desc_field_names = {field_name for field_name, _ in name_desc_fields}
  has_name_desc = ("name" in data and infer_type(data["name"]) == "str" and
                  "description" in data and infer_type(data["description"]) == "str")
  main_base_class = "NameDesc" if has_name_desc else "NamedEntity" if named_entity_field_names else "BaseModel"

  content = input_file.read_text(encoding="utf-8")
  lines = content.split("\n")
  new_lines = []
  in_class = False
  current_class = None
  import_added = False
  used_base_classes = {main_base_class} if main_base_class != "BaseModel" else set()

  # Determine base classes for sub-models
  for field_name in data:
    base_class = get_sub_model_base_class(data, field_name, current_class)
    if base_class != "BaseModel":
      used_base_classes.add(base_class)

  # Add imports at the top
  if used_base_classes:
    new_lines.append(f"from .base_model import {', '.join(sorted(used_base_classes))}")
  new_lines.append("from pydantic import BaseModel")
  new_lines.append("")

  for line in lines:
    stripped = line.strip()
    if stripped.startswith("class ") and "(BaseModel" in stripped:
      in_class = True
      current_class = stripped.split(" ")[1].split("(")[0]
      # Determine base class for this class
      if current_class.endswith("Model"):
        base_class = main_base_class
      else:
        base_class = get_sub_model_base_class(data, current_class[0].lower() + current_class[1:], current_class)
      line = line.replace("BaseModel", f"{base_class}, frozen=True")
      new_lines.append(line)
    elif in_class and ":" in stripped:
      # Remove Optional[...] and add default="" for strings
      if "Optional[" in stripped:
        line = line.replace("Optional[", "").replace("]", "")
      if "str" in stripped and " = " not in stripped:
        line = line + ' = ""'
      # Replace List[...] with list[...]
      if "List[" in stripped:
        line = line.replace("List[", "list[").replace("from typing import List", "")
      # Ensure arrays are strongly typed
      if ": list" in stripped and ": list[" not in stripped:
        field_name = stripped.split(":")[0].strip()
        sub_model = f"{current_class}{field_name.title().replace('_', '')}"
        line = line.replace(": list", f": list[{sub_model}]")
      # Skip common fields for NameDesc or NamedEntity
      field_name = stripped.split(":")[0].strip()
      if field_name in (name_desc_field_names if get_sub_model_base_class(data, current_class[0].lower() + current_class[1:], current_class) == "NameDesc" else named_entity_field_names):
        continue
      new_lines.append(line)
    else:
      # Skip redundant imports
      if not (stripped.startswith("from __future__") or stripped.startswith("from typing import List")):
        new_lines.append(line)
    if in_class and stripped.startswith("class "):
      in_class = False
  # Ensure two-space indentation
  final_lines = []
  for line in new_lines:
    indent_count = len(line) - len(line.lstrip())
    new_indent = "  " * (indent_count // 2)
    final_lines.append(new_indent + line.lstrip())
  output_file.write_text("\n".join(final_lines), encoding="utf-8")
  input_file.unlink()  # Remove temp file

def generate_init_py(categories: List[str]):
  """Generate __init__.py with imports for all model files."""
  APP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
  lines = ["from .base_model import *\n"] + [f"from .{cat}_model import *\n" for cat in categories]
  init_file = APP_MODELS_DIR / "__init__.py"
  init_file.write_text("\n".join(lines), encoding="utf-8")
  logger.info(f"Generated {relpath(init_file)} with imports for {len(categories) + 1} files")

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

    # Load all JSON data to find common fields
    all_data = []
    for category, files in files_by_category.items():
      for file in files:
        try:
          with file.open() as f:
            data = json.load(f)
          if validate_arrays(data, file):
            all_data.append(data)
          else:
            logger.error(f"Skipping {relpath(file)} due to invalid arrays")
        except json.JSONDecodeError as e:
          logger.error(f"Failed to parse {relpath(file)}: {e}")
          continue

    # Find common fields
    named_entity_fields, name_desc_fields = find_common_fields(all_data)
    generate_base_model(named_entity_fields, name_desc_fields)

    # Generate models for each file
    for category, schema_files in files_by_category.items():
      if not schema_files:
        logger.warning(f"No raw JSON files found for category '{category}'")
        continue
      for schema_file in schema_files:
        output_file = APP_MODELS_DIR / f"{schema_file.stem}_model.py"
        generate_model_for_file(schema_file, output_file, named_entity_fields, name_desc_fields)

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