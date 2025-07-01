#!/usr/bin/env python3

"""
Pydantic Model Generation Script (Refactored with Common Property Extraction)

- Reads raw JSON files from backend/model/schema/ (e.g., app.json, org.json)
- Excludes specified files (app_snapshot.json, apps.json)
- Transforms raw JSON to strict JSON Schema with no Optional or Any types
- Post-processes schemas to extract common properties (e.g., name, description) into $defs
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

# Common properties to search for
COMMON_PROPERTIES = {"name", "description"}

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

###########################################
# Phase 3.5: Schema Refactoring for Common Properties #
###########################################

def refactor_schemas_for_common_properties(
  schemas: List[Tuple[str, dict, str]], common_props: Set[str]
) -> List[Tuple[str, dict, str]]:
  """
  Refactor JSON schemas to extract common properties into $defs and reference them.
  Args:
    schemas: List of (name, schema, category) tuples
    common_props: Set of property names to consider for extraction (e.g., {"name", "description"})
  Returns:
    Updated list of (name, schema, category) tuples with refactored schemas
  """
  # Step 1: Identify common properties with identical definitions
  prop_definitions = {}
  for prop in common_props:
    prop_schemas = []
    for name, schema, _ in schemas:
      if prop in schema["properties"]:
        prop_schemas.append(schema["properties"][prop])
    # Check if all schemas for this property are identical
    if prop_schemas and all(prop_schemas[0] == ps for ps in prop_schemas[1:]):
      prop_definitions[prop] = prop_schemas[0]

  # Step 2: Create $defs for common properties
  common_defs = {
    "NamedEntity": {
      "type": "object",
      "properties": {prop: prop_definitions[prop] for prop in prop_definitions if prop == "name"},
      "required": ["name"],
      "additionalProperties": False
    },
    "NameDesc": {
      "type": "object",
      "properties": {prop: prop_definitions[prop] for prop in prop_definitions},
      "required": sorted(prop_definitions.keys()),
      "additionalProperties": False,
      "allOf": [{"$ref": "#/components/schemas/NamedEntity"}]
    }
  }

  # Step 3: Update schemas to reference $defs
  updated_schemas = []
  for name, schema, category in schemas:
    new_schema = schema.copy()
    new_schema["components"] = {"schemas": common_defs}
    new_properties = new_schema["properties"].copy()
    new_required = new_schema["required"].copy()
    has_name = "name" in new_properties
    has_desc = "description" in new_properties
    # Remove common properties from properties and required
    for prop in prop_definitions:
      new_properties.pop(prop, None)
      if prop in new_required:
        new_required.remove(prop)
    # Add $ref based on category and present properties
    if category in ["app", "org", "group"] and has_name:
      new_schema["allOf"] = [{"$ref": "#/components/schemas/NameDesc" if has_desc else "#/components/schemas/NamedEntity"}]
      if new_properties:
        new_schema["properties"] = new_properties
        new_schema["required"] = new_required
      else:
        del new_schema["properties"]
        del new_schema["required"]
    else:
      new_schema["properties"] = new_properties
      new_schema["required"] = new_required
    updated_schemas.append((name, new_schema, category))
  return updated_schemas

######################################
# Phase 4: Common Fields + Base Class #
######################################

def generate_base_model():
  lines = [
    "from pydantic import BaseModel\n\n",
    "class NamedEntity(BaseModel, frozen=True):\n",
    '  name: str = ""\n',
    "\nclass NameDesc(NamedEntity, frozen=True):\n",
    '  description: str = ""\n'
  ]
  (OUTPUT_DIR / "base_model.py").write_text("".join(lines), encoding="utf-8")

#################################
# Phase 6: Final Model Generation#
#################################

def generate_models(schemas: List[Tuple[str, dict, str]]):
  for name, schema, category in schemas:
    temp_schema_path = OUTPUT_DIR / f"temp_{name}.schema.json"
    output_path = OUTPUT_DIR / f"{name}_model.py"
    temp_schema_contents = json.dumps(schema, indent=2)
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
      "--use-schema-description",
      "--use-field-description",
      "--base-class", "base_model.NamedEntity" if category in ["app", "org", "group"] else "pydantic.BaseModel"
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
  # Collect schemas
  schemas = []
  for category, entries in files.items():
    for name, data in entries:
      schema = transform_to_json_schema(data, name.title().replace("_", ""), name)
      schemas.append((name, schema, category))
  # Refactor schemas for common properties
  schemas = refactor_schemas_for_common_properties(schemas, COMMON_PROPERTIES)
  # Generate base model
  generate_base_model()
  # Generate individual models
  generate_models(schemas)
  logger.info("Model generation complete.")

if __name__ == "__main__":
  main()