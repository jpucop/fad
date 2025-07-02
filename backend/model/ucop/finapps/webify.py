#!/usr/bin/env python3
"""
Webify Script: Combines Pydantic Model Generation and Data Copying

- Accepts an input argument: "schema", "data", or "all" (default)
- "schema": Generates Pydantic models from JSON schemas (like pydantify.py)
- "data": Copies JSON data files recursively from backend/model/ucop/ and specific schema files (like copy_model_data.py)
- "all": Performs both schema and data operations
- Uses GenSON for JSON Schema generation with strict typing
- Ensures all properties are required, arrays have explicit types, and two-space indentation
- Requires datamodel-code-generator==0.31.2, pydantic==2.10.6, genson
"""

import argparse
import json
import logging
import shutil
from pathlib import Path
from typing import List, Tuple
from genson import SchemaBuilder
from datamodel_code_generator import generate, InputFileType, PythonVersion


logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

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
INCLUDED_SCHEMA_FILES = {"app_profiles.json", "deploy_profiles.json"}

SOURCE_DATA_DIR = PROJECT_ROOT / "backend" / "model" / "ucop"
DEST_DATA_DIR = PROJECT_ROOT / "backend" / "app" / "data"
DEST_DATA_DIR.mkdir(parents=True, exist_ok=True)

def collect_raw_json() -> List[Tuple[str, dict]]:
  schemas = []
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
      schemas.append((file.stem, data))
    except Exception as e:
      logger.error(f"Failed to parse {file.name}: {e}")
      raise
  return schemas


def make_all_properties_required(schema: dict, parent_prop: str = "") -> None:
  if "properties" in schema:
    schema["required"] = list(schema["properties"].keys())
    for prop, prop_schema in schema["properties"].items():
      if prop_schema.get("type") == "object":
        prop_schema["$id"] = f"#/definitions/{prop.title()}"
      make_all_properties_required(prop_schema, prop)
  elif schema.get("type") == "array" and "items" in schema:
    if schema["items"].get("type") == "object":
      schema["items"]["$id"] = f"#/definitions/{parent_prop.title()}Item"
    make_all_properties_required(schema["items"], parent_prop)


def transform_to_json_schema(data: dict, title: str) -> dict:
  builder = SchemaBuilder()
  builder.add_object(data)
  schema = builder.to_schema()
  make_all_properties_required(schema)
  schema["additionalProperties"] = False
  schema["title"] = title
  schema["$id"] = f"#/definitions/{title}"
  logger.debug(f"Generated JSON Schema for {title}:\n{json.dumps(schema, indent=2)}")
  logger.info(f"Schema for {title} has properties: {list(schema.get('properties', {}).keys())}")
  return schema


def generate_models(schemas: List[Tuple[str, dict]]) -> None:
  for name, schema in schemas:
    output_path = OUTPUT_DIR / f"{name}_model.py"
    logger.info(f"Generating {output_path.relative_to(PROJECT_ROOT)}")
    try:
      generate(
        input_=json.dumps(schema),
        input_file_type=InputFileType.JsonSchema,
        output=output_path,
        class_name=f"{name.title().replace('_','')}Model",
        base_class="pydantic.BaseModel",
        use_double_quotes=True,
        use_schema_description=True,
        use_field_description=True,
        reuse_model=True,
        strip_default_none=True,
        target_python_version=PythonVersion.PY_310,
        disable_appending_item_suffix=True,
      )
      with open(output_path, "r") as f:
        code = f.read()
      with open(output_path, "w") as f:
        f.write(code)
    except Exception as e:
      logger.error(f"Failed to generate {output_path}: {e}")
      raise


def generate_schema():
  shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
  raw_schemas = collect_raw_json()
  json_schemas = [(name, transform_to_json_schema(data, name.title().replace("_", "")))
          for name, data in raw_schemas]
  generate_models(json_schemas)
  logger.info("Model generation complete.")


def copy_model_data():

  # Copy all JSON files recursively from backend/model/ucop/
  for file in SOURCE_DATA_DIR.rglob("*.json"):
    if file.name in EXCLUDE_FILES:
      continue
    try:
      rel_path = file.relative_to(SOURCE_DATA_DIR)
      dest_file = DEST_DATA_DIR / rel_path
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
        shutil.copy2(source_file, DEST_DATA_DIR / file_name)
        logger.info(f"Copied {file_name}")
      except Exception as e:
        logger.error(f"Failed to copy {file_name}: {e}")
        raise


def main():
  parser = argparse.ArgumentParser(description="Webify script for schema generation and data copying to app/")
  parser.add_argument(
    "--mode",
    choices=["schema", "data", "all"],
    default="all",
    help="Operation mode: 'schema' for model generation, 'data' for copying data, 'all' for both (default)"
  )
  args = parser.parse_args()

  if args.mode in ["schema", "all"]:
    logger.info("Running schema generation")
    generate_schema()

  if args.mode in ["data", "all"]:
    logger.info("Running data copying")
    copy_model_data()

  logger.info("Webify script completed.")


if __name__ == "__main__":
  main()