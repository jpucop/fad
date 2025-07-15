#!/usr/bin/env python3
"""
Webify Script: Combines Pydantic Model Generation and Data Copying

- Accepts an input argument: "schema", "data", or "all" (default)
- "schema": Generates Pydantic models from JSON schemas with normalization
- "data": Copies JSON data files recursively from backend/model/ucop/ and specific schema files
- "all": Performs both schema and data operations
- Uses GenSON for JSON Schema generation with strict typing and consolidation
- Ensures all properties are required, arrays have explicit types, and two-space indentation
- Requires datamodel-code-generator==0.31.2, pydantic==2.10.6, genson
"""

import argparse
import json
import logging
import re
import shutil
from pathlib import Path
from typing import List, Tuple, Dict
from genson import SchemaBuilder
from datamodel_code_generator import generate, InputFileType, PythonVersion
from datetime import datetime

# Configure logging with timestamp
logging.basicConfig(
  level=logging.DEBUG,
  format="%(asctime)s - %(levelname)s - %(message)s",
  datefmt="%Y-%m-%d %H:%M:%S %Z"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_DIR = PROJECT_ROOT / "backend" / "model" / "schema"
APP_MODELS_DIR = PROJECT_ROOT / "backend" / "app" / "models"
BASE_TYPES_FILE = SCHEMA_DIR / "base.py"
EXCLUDE_FILES = {"app_snapshot.json", "apps.json", "base.py"}
APP_DATA_DIR = PROJECT_ROOT / "backend" / "app" / "data"

APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

def collect_raw_json() -> Dict[str, dict]:
  schemas = {}
  for file in sorted(SCHEMA_DIR.glob("*.json")):
    if file.name in EXCLUDE_FILES:
      continue
    try:
      data = json.loads(file.read_text("utf-8"))
      if not data:
        logger.error(f"Empty JSON file: {file.name}")
        raise ValueError(f"Empty JSON file: {file.name}")
      def validate_arrays(obj, path=""):
        if isinstance(obj, list):
          if not obj:
            raise ValueError(f"Empty array at {path}")
          types = {type(item) for item in obj}
          if len(types) > 1:
            raise ValueError(f"Mixed types in array at {path}: {types}")
        elif isinstance(obj, dict):
          for k, v in obj.items():
            validate_arrays(v, f"{path}.{k}" if path else k)
      validate_arrays(data)
      schemas[file.stem] = data
    except Exception as e:
      logger.error(f"Failed to parse {file}: {e}")
      raise
  return schemas

def merge_schemas(raw_schemas: Dict[str, dict]) -> dict:
  builder = SchemaBuilder()
  for name, data in raw_schemas.items():
    builder.add_object(data)
  schema = builder.to_schema()

  definitions = schema.get("definitions", {})
  properties = schema.get("properties", {})

  # Define a base Aws schema
  if "Aws" in definitions or "Aws1" in definitions or "Aws2" in definitions:
    aws_base = {
      "type": "object",
      "properties": {"account_name": {"type": "string"}},
      "required": ["account_name"],
      "$id": "#/definitions/AwsBase"
    }
    if any("db_arn" in defs.get("properties", {}) for defs in definitions.values()):
      aws_base["properties"]["db_arn"] = {"type": "string", "nullable": True}
    definitions["AwsBase"] = aws_base
    del definitions["Aws"]
    del definitions["Aws1"]
    del definitions["Aws2"]

  # Define a collaboration tool base
  collab_tools = {"Confluence", "Box", "Datadog", "Jira", "ServiceNow"}
  if any(tool in definitions for tool in collab_tools):
    collab_base = {
      "type": "object",
      "properties": {"group_web_url": {"type": "string"}},
      "required": ["group_web_url"],
      "$id": "#/definitions/CollaborationTool"
    }
    definitions["CollaborationTool"] = collab_base
    for tool in collab_tools:
      if tool in definitions:
        if tool == "Jira" and "project_keys" in definitions[tool].get("properties", {}):
          definitions[tool]["allOf"] = [{"$ref": "#/definitions/CollaborationTool"}]
        elif tool == "ServiceNow" and "assignment_group_names" in definitions[tool].get("properties", {}):
          definitions[tool]["allOf"] = [{"$ref": "#/definitions/CollaborationTool"}]
        else:
          del definitions[tool]

  # Ensure AppModel is the root
  if "App" in properties or "AppModel" in definitions:
    schema["title"] = "AppModel"
    schema["$id"] = "#/definitions/AppModel"
    schema["additionalProperties"] = False
    make_all_properties_required(schema)

  schema["definitions"] = definitions
  logger.debug(f"Merged Schema:\n{json.dumps(schema, indent=2)}")
  return schema

def make_all_properties_required(schema: dict, parent_prop: str = "") -> None:
  if "properties" in schema:
    schema["required"] = [prop for prop in schema["properties"].keys() if prop not in base_fields]
    for prop, prop_schema in schema["properties"].items():
      if prop in base_fields:
        continue
      if prop_schema.get("type") == "object":
        prop_schema["$id"] = f"#/definitions/{prop.title()}"
      make_all_properties_required(prop_schema, prop)
  elif schema.get("type") == "array" and "items" in schema:
    if schema["items"].get("type") == "object":
      schema["items"]["$id"] = f"#/definitions/{parent_prop.title()}Item"
    make_all_properties_required(schema["items"], parent_prop)

def generate_models(schema: dict) -> None:
  output_path = APP_DATA_DIR / "app_model.py"
  try:
    generate(
      input_=json.dumps(schema),
      input_file_type=InputFileType.JsonSchema,
      output=output_path,
      class_name="AppModel",
      base_class="pydantic.BaseModel",
      use_double_quotes=True,
      use_schema_description=True,
      use_field_description=True,
      reuse_model=True,
      strip_default_none=True,
      target_python_version=PythonVersion.PY_310,
      disable_appending_item_suffix=True,
    )
    logger.info(f"Generated {output_path.relative_to(PROJECT_ROOT)}")
  except Exception as e:
    logger.error(f"Failed to generate {output_path}: {e}")
    raise

def generate_schema():
  shutil.rmtree(APP_MODELS_DIR, ignore_errors=True)
  APP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
  
  # global base_type_resolver
  # base_type_resolver = BaseTypeResolver(BASE_TYPES_FILE)
  raw_schemas = collect_raw_json()
  logger.info(f"Collected {len(raw_schemas)} raw schemas.")
  if not raw_schemas:
    logger.warning("No schemas to process.")
    return
  merged_schema = merge_schemas(raw_schemas)
  generate_models(merged_schema)
  logger.info("Model generation complete.")

def copy_model_data(model_names):
  # Copy all JSON files recursively from backend/model/ucop/
  for file in SOURCE_DATA_DIR.rglob("*.json"):
    if file.name in EXCLUDE_FILES:
      logger.info(f"Skipping {rel_path}")
      continue
    try:
      data = json.loads(file.read_text("utf-8"))
      if data.get("_schema", False) is True:
        rel_path = file.relative_to(SCHEMA_DIR.parent)
        dest_file = APP_DATA_DIR / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, dest_file)
        logger.info(f"Copied {rel_path} to {dest_file}")
    except Exception as e:
      logger.error(f"Failed to copy {file.name}: {e}")
      raise

  # Copy specific schema files
  for file_name in INCLUDED_SCHEMA_FILES:
    source_file = SCHEMA_DIR / file_name
    if source_file.exists():
      try:
        shutil.copy2(source_file, APP_DATA_DIR / file_name)
        logger.info(f"Copied {file_name}")
      except Exception as e:
        logger.error(f"Failed to copy {file_name}: {e}")
        raise

def main():
  parser = argparse.ArgumentParser(description="Webify script for schema generation and data copying")
  parser.add_argument(
    "--mode",
    choices=["schema", "data", "all"],
    default="all",
    help="Operation mode: 'schema' for model generation, 'data' for copying/serializing data, 'all' for both"
  )
  args = parser.parse_args()

  model_names = {}
  if args.mode in ["schema", "all"]:
    model_names = generate_schema()
  if args.mode in ["data", "all"]:
    copy_model_data(model_names)

  logger.info("Webify script completed.")

if __name__ == "__main__":
  main()