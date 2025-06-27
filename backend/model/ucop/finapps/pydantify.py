#!/usr/bin/env python3

"""
Pydantic Model Generation Script (Refactored)

- Reads raw JSON files from backend/model/schema/ (e.g., app.json, org.json)
- Excludes specified files (app_snapshot.json, apps.json)
- Transforms raw JSON to strict JSON Schema with no Optional or Any types
- Generates one strongly typed Pydantic model file per JSON file in backend/app/models/
- Creates common base classes for shared fields (e.g., NamedEntity, NameDesc)
- Ensures:
  - All arrays have explicitly typed elements
  - All string fields default to ""
  - Fails fast on type ambiguity or empty arrays
  - Uses double quotes in generated model classes
  - No Optional types; all properties required
- Uses two-space indentation
- Requires datamodel-code-generator==0.31.2, pydantic==2.10.6
"""

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

#######################
# Project Root Logic  #
#######################

def find_project_root() -> Path:
  current = Path(__file__).resolve().parent
  while current != current.parent:
    if (current / "backend").is_dir() and (current / "frontend").is_dir():
      return current
    current = current.parent
  raise RuntimeError("Project root not found")

PROJECT_ROOT = find_project_root()
SCHEMA_DIR = PROJECT_ROOT / "backend" / "model" / "schema"
OUTPUT_DIR = PROJECT_ROOT / "backend" / "app" / "models"
EXCLUDE_FILES = {"app_snapshot.json", "apps.json"}
CATEGORY_MAP = {
  "app": ["app.json", "app_profiles.json", "app_topo.json"],
  "org": ["org.json"],
  "group": ["group.json"],
  "misc": ["aws_account.json", "deploy_profiles.json", "member.json"],
}

####################################
# Phase 1: Collect + Validate Raw  #
####################################

def collect_raw_json() -> Dict[str, List[Tuple[str, dict]]]:
  files_by_category = {cat: [] for cat in CATEGORY_MAP}
  for file in sorted(SCHEMA_DIR.glob("*.json")):
    if file.name in EXCLUDE_FILES:
      continue
    try:
      data = json.loads(file.read_text("utf-8"))
      if not data:
        logger.error(f"Empty JSON file: {file.name}")
        raise ValueError(f"Empty JSON file: {file.name}")
    except Exception as e:
      logger.error(f"Failed to parse {file.name}: {e}")
      raise
    for category, names in CATEGORY_MAP.items():
      if file.name in names:
        files_by_category[category].append((file.stem, data))
        break
    else:
      logger.warning(f"Unmapped file: {file.name}")
  return files_by_category

###################################
# Phase 2: Type Inference Helpers #
###################################

def infer_property_type(value: Any, prop_name: str, file_name: str) -> Dict[str, Any]:
  if isinstance(value, str):
    return {"type": "string", "default": ""}
  if isinstance(value, int):
    return {"type": "integer"}
  if isinstance(value, float):
    return {"type": "number"}
  if isinstance(value, bool):
    return {"type": "boolean"}
  if isinstance(value, list):
    if not value:
      raise ValueError(f"Empty array for property '{prop_name}' in {file_name}")
    item_schema = infer_property_type(value[0], f"{prop_name}[]", file_name)
    return {"type": "array", "items": item_schema}
  if isinstance(value, dict):
    properties = {}
    required = []
    for k, v in value.items():
      properties[k] = infer_property_type(v, f"{prop_name}.{k}", file_name)
      required.append(k)
    return {"type": "object", "properties": properties, "required": required}
  raise ValueError(f"Ambiguous type for property '{prop_name}' in {file_name}: {value}")

###################################
# Phase 3: Raw to JSON Schema Step#
###################################

def transform_to_json_schema(data: dict, title: str, file_name: str) -> dict:
  properties = {}
  required = []
  for k, v in data.items():
    properties[k] = infer_property_type(v, k, file_name)
    required.append(k)
  return {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": title,
    "type": "object",
    "properties": properties,
    "required": required,
    "additionalProperties": False
  }

######################################
# Phase 4: Common Fields + Base Class #
######################################

def find_common_fields(all_data: List[dict]) -> Tuple[Set[str], Set[str]]:
  name_fields = []
  desc_fields = []
  for d in all_data:
    if "name" in d and isinstance(d["name"], str):
      name_fields.append(set(d.keys()))
    if "description" in d and isinstance(d.get("description"), str):
      desc_fields.append(set(d.keys()))
  named_fields = set.intersection(*name_fields) if name_fields else set()
  namedesc_fields = set.intersection(*desc_fields) if desc_fields else set()
  return named_fields, namedesc_fields

##############################
# Phase 5: Base Model Emission#
##############################

def generate_base_model(named: Set[str], namedesc: Set[str]):
  lines = ["from pydantic import BaseModel\n\n", "class NamedEntity(BaseModel, frozen=True):\n"]
  for f in sorted(named):
    lines.append(f'  {f}: str = ""\n')
  lines.append("\nclass NameDesc(NamedEntity, frozen=True):\n")
  for f in sorted(namedesc - named):
    lines.append(f'  {f}: str = ""\n')
  (OUTPUT_DIR / "base_model.py").write_text("".join(lines), encoding="utf-8")

#################################
# Phase 6: Final Model Generation#
#################################

def generate_models(all_files: Dict[str, List[Tuple[str, dict]]], named: Set[str], namedesc: Set[str]):
  for category, entries in all_files.items():
    for name, data in entries:
      schema = transform_to_json_schema(data, name.title().replace("_", ""), name)
      temp_schema_path = OUTPUT_DIR / f"temp_{name}.schema.json"
      output_path = OUTPUT_DIR / f"{name}_model.py"
      temp_schema_contents = json.dumps(schema, indent=2)
      # logger.info(f"temp_schema_contents: \n{temp_schema_contents}\n")
      temp_schema_path.write_text(temp_schema_contents, encoding="utf-8")
      cmd = [
        "datamodel-codegen",
        "--input", str(temp_schema_path),
        "--input-file-type", "jsonschema",
        "--output", str(output_path),
        "--disable-timestamp",
        "--strip-default-none",
        "--extra-fields", "allow",
        "--disable-appending-item-suffix",
        "--class-name", f"{name.title().replace('_','')}Model",
        "--use-double-quotes",
        "--base-class", "base_model.NamedEntity" if name in CATEGORY_MAP["app"] + CATEGORY_MAP["org"] + CATEGORY_MAP["group"] else "pydantic.BaseModel"
      ]
      logger.info(f"Generating {output_path.relative_to(PROJECT_ROOT)}")
      try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
      except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate {output_path}: {e.stderr}")
        raise
      temp_schema_path.unlink()

###########################
# Phase 7: Main Orchestration #
###########################

def main():
  shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
  files = collect_raw_json()
  all_data = [d for cat in files.values() for _, d in cat]
  named, namedesc = find_common_fields(all_data)
  generate_base_model(named, namedesc)
  generate_models(files, named, namedesc)
  logger.info("Model generation complete.")

if __name__ == "__main__":
  main()
