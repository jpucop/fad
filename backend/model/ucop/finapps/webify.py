#!/usr/bin/env python3

import json
import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from gen.apps import regenerate as generate_apps

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
SCHEMA_DIR = BASE_DIR / "model" / "schema"
UCOP_DIR = BASE_DIR / "model" / "ucop" / "finapps"
OUTPUT_MODELS_DIR = BASE_DIR / "app" / "models"
OUTPUT_DATA_DIR = BASE_DIR / "app" / "data"

def load_json(file_path: Path) -> Dict:
  """Load a JSON file and return its contents."""
  try:
    with open(file_path, "r") as f:
      return json.load(f)
  except FileNotFoundError:
    logger.error(f"File {file_path} not found.")
    raise
  except json.JSONDecodeError:
    logger.error(f"Invalid JSON in {file_path}.")
    raise

def save_file(content: str, file_path: Path):
  """Save content to a file."""
  file_path.parent.mkdir(parents=True, exist_ok=True)
  with open(file_path, "w") as f:
    f.write(content)

def get_expected_type(schema_value: Any) -> str:
  """Determine the expected type from a schema value."""
  if isinstance(schema_value, dict):
    return "object"
  if isinstance(schema_value, list):
    return "array"
  if isinstance(schema_value, str):
    return "string"
  if isinstance(schema_value, bool):
    return "boolean"
  if isinstance(schema_value, (int, float)):
    return "number"
  return "null"

def validate_properties(data: Dict, schema: Dict, path: str, file_name: str) -> List[str]:
  """Recursively validate properties in data against schema."""
  discrepancies = []
  schema_properties = schema.get("properties", schema) if "properties" in schema else schema

  for key, schema_value in schema_properties.items():
    current_path = f"{path}.{key}" if path else key
    expected_type = get_expected_type(schema_value)

    if key not in data:
      discrepancies.append(f"{file_name}: Missing property '{current_path}' (expected {expected_type})")
      continue

    data_value = data[key]
    actual_type = get_expected_type(data_value)

    if actual_type != expected_type:
      discrepancies.append(
        f"{file_name}: Type mismatch for '{current_path}' (expected {expected_type}, found {actual_type})"
      )
      continue

    if expected_type == "object":
      discrepancies.extend(validate_properties(data_value, schema_value, current_path, file_name))
    elif expected_type == "array" and schema_value and isinstance(schema_value[0], dict):
      for i, item in enumerate(data_value):
        discrepancies.extend(validate_properties(item, schema_value[0], f"{current_path}[{i}]", file_name))

  for key in data:
    if key not in schema_properties:
      current_path = f"{path}.{key}" if path else key
      discrepancies.append(f"{file_name}: Unexpected property '{current_path}'")

  return discrepancies

def snake_to_pascal(snake_str: str) -> str:
  """Convert snake_case to PascalCase."""
  return "".join(word.capitalize() for word in snake_str.split("_"))

def json_schema_to_pydantic(schema: dict, model_name: str, indent: int = 4) -> str:
  """Convert a JSON Schema to a Pydantic model class."""
  lines = ["from pydantic import BaseModel\n"]
  imports = set()

  schema_properties = schema.get("properties", schema) if "properties" in schema else schema
  for prop_schema in schema_properties.values():
    if prop_schema.get("type") == "array":
      imports.add("from typing import List")
    if prop_schema.get("type") == "object" or "properties" in prop_schema:
      imports.add("from typing import Optional")
    if prop_schema.get("type") == "string" and "enum" in prop_schema:
      imports.add("from enum import Enum")

  lines.extend(sorted(imports))
  lines.append("\n")

  for prop_name, prop_schema in schema_properties.items():
    if prop_schema.get("type") == "string" and "enum" in prop_schema:
      enum_name = snake_to_pascal(f"{prop_name}_enum")
      lines.append(f"class {enum_name}(str, Enum):\n")
      for value in prop_schema["enum"]:
        safe_value = re.sub(r"[^a-zA-Z0-9_]", "_", value.replace("|", "_"))
        lines.append(f"  {safe_value} = \"{value}\"\n")
      lines.append("\n")

  lines.append(f"class {model_name}(BaseModel):\n")

  for prop_name, prop_schema in schema_properties.items():
    prop_type = prop_schema.get("type", "string")
    python_type = "str"

    if prop_type == "string":
      if "enum" in prop_schema:
        python_type = snake_to_pascal(f"{prop_name}_enum")
      else:
        python_type = "str"
    elif prop_type == "integer":
      python_type = "int"
    elif prop_type == "number":
      python_type = "float"
    elif prop_type == "boolean":
      python_type = "bool"
    elif prop_type == "array":
      item_schema = prop_schema.get("items", {})
      item_type = item_schema.get("type", "string")
      if item_type == "string":
        item_python_type = "str"
      elif item_type == "integer":
        item_python_type = "int"
      elif item_type == "number":
        item_python_type = "float"
      elif item_type == "boolean":
        item_python_type = "bool"
      elif item_type == "object":
        nested_model_name = snake_to_pascal(f"{prop_name}")
        lines.append(json_schema_to_pydantic(item_schema, nested_model_name))
        item_python_type = nested_model_name
      python_type = f"List[{item_python_type}]"
    elif prop_type == "object":
      nested_model_name = snake_to_pascal(f"{prop_name}")
      lines.append(json_schema_to_pydantic(prop_schema, nested_model_name))
      python_type = nested_model_name

    required = prop_name in schema.get("required", [])
    if not required:
      python_type = f"Optional[{python_type}]"

    lines.append(f"{' ' * indent}{prop_name}: {python_type}\n")

  return "".join(lines)

def generate_init_file(models_dir: Path, data_dir: Path):
  """Generate __init__.py to export models and provide data loading."""
  model_files = [f.stem for f in models_dir.glob("*.py") if f.name != "__init__.py"]
  data_files = [f.stem for f in data_dir.glob("*.json")]

  init_content = ["from pathlib import Path\n"]
  init_content.append("from . import (\n")
  init_content.extend(f"  {model},\n" for model in model_files)
  init_content.append(")\n\n")

  init_content.append("# Data loading\n")
  init_content.append("DATA_DIR = Path(__file__).parent / 'data'\n")
  init_content.append("def load_data(file_name: str) -> dict:\n")
  init_content.append("  with open(DATA_DIR / f'{file_name}.json') as f:\n")
  init_content.append("    return json.load(f)\n\n")

  init_content.append("# Available data files\n")
  init_content.append("DATA_FILES = {\n")
  for data_file in data_files:
    key = data_file.replace("app_", "").replace("_", "-")
    init_content.append(f"  '{key}': '{data_file}',\n")
  init_content.append("}\n")

  save_file("".join(init_content), models_dir / "__init__.py")
  logger.info(f"Generated {models_dir / '__init__.py'}")

def validate_models():
  """Validate org_ucop.json, group_finapps.json, and app_*.json against schemas."""
  discrepancies = []

  # Validate org_ucop.json
  org_data = load_json(UCOP_DIR.parent / "org_ucop.json")
  org_schema = load_json(SCHEMA_DIR / "org.json")
  discrepancies.extend(validate_properties(org_data, org_schema, "", "org_ucop.json"))

  # Validate group_finapps.json
  group_data = load_json(UCOP_DIR / "group_finapps.json")
  group_schema = load_json(SCHEMA_DIR / "group.json")
  discrepancies.extend(validate_properties(group_data, group_schema, "", "group_finapps.json"))

  # Validate app_*.json
  app_schema = load_json(SCHEMA_DIR / "app.json")
  for app_file in UCOP_DIR.glob("app_*.json"):
    app_data = load_json(app_file)
    discrepancies.extend(validate_properties(app_data, app_schema, "", app_file.name))

  return discrepancies

def copy_to_app():
  """Copy validated JSON files to app/data/."""
  OUTPUT_DATA_DIR.mkdir(parents=True, exist_ok=True)
  for json_file in UCOP_DIR.glob("*.json"):
    if json_file.name.startswith("app_") or json_file.name in ["org_ucop.json", "group_finapps.json"]:
      json_data = load_json(json_file)
      schema_file = SCHEMA_DIR / ("app.json" if json_file.name.startswith("app_") else json_file.name)
      schema_data = load_json(schema_file)
      discrepancies = validate_properties(json_data, schema_data, "", json_file.name)
      if discrepancies:
        logger.error(f"Validation errors in {json_file.name}: {discrepancies}")
        continue
      dest_path = OUTPUT_DATA_DIR / json_file.name
      save_file(json.dumps(json_data, indent=2), dest_path)
      logger.info(f"Copied {json_file.name} to {dest_path}")

def generate_models():
  """Generate Pydantic models in app/models/."""
  OUTPUT_MODELS_DIR.mkdir(parents=True, exist_ok=True)
  for schema_file in SCHEMA_DIR.glob("*.json"):
    schema_name = schema_file.stem
    schema_data = load_json(schema_file)
    if schema_name in ["app_profiles", "deploy_profiles"]:
      for profile in schema_data[f"{schema_name}"]:
        model_name = snake_to_pascal(profile["name"].replace("-", "_"))
        lines = ["from enum import Enum\n\n"]
        lines.append(f"class {model_name}(str, Enum):\n")
        lines.append(f"  {model_name.lower()} = \"{profile['name']}\"\n")
        model_path = OUTPUT_MODELS_DIR / f"{profile['name'].replace('-', '_')}.py"
        save_file("".join(lines), model_path)
        logger.info(f"Generated Pydantic model for {profile['name']} at {model_path}")
      continue
    model_name = snake_to_pascal(schema_name)
    pydantic_model = json_schema_to_pydantic(schema_data, model_name)
    model_path = OUTPUT_MODELS_DIR / f"{schema_name}.py"
    save_file(pydantic_model, model_path)
    logger.info(f"Generated Pydantic model for {schema_name} at {model_path}")

def regenerate(validate: bool = True, generate_apps_flag: bool = True, copy: bool = True, models: bool = True):
  """Regenerate app JSON files, validate, copy to app/data/, and generate Pydantic models."""
  if validate:
    discrepancies = validate_models()
    if discrepancies:
      logger.error("Validation failed:")
      for d in discrepancies:
        logger.error(d)
      raise ValueError("Validation errors detected")

  if generate_apps_flag:
    generate_apps()

  if copy:
    copy_to_app()

  if models:
    generate_models()
    generate_init_file(OUTPUT_MODELS_DIR, OUTPUT_DATA_DIR)

if __name__ == "__main__":
  try:
    regenerate()
  except Exception as e:
    logger.error(f"Error: {str(e)}")
    exit(1)