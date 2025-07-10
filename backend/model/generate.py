#!/usr/bin/env python3
"""
Webify Script: Combines Pydantic Model Generation and Data Copying

- Accepts an input argument: "schema", "data", or "all" (default)
- "schema": Generates Pydantic models from JSON files in backend/model/schema/
- "data": Copies and serializes JSON data files from org directories adjacent to schema/
- "all": Performs both schema and data operations
- Uses GenSON for schema generation with strict typing
- Ensures all properties are required (except base class properties), arrays have explicit types, and two-space indentation
- Requires datamodel-code-generator==0.31.2, pydantic==2.10.6, genson
"""

import argparse
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, List, Tuple, Dict, Set
from genson import SchemaBuilder
from datamodel_code_generator import generate, InputFileType, PythonVersion
from importlib import import_module

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCHEMA_DIR = PROJECT_ROOT / "backend" / "model" / "schema"
APP_MODELS_DIR = PROJECT_ROOT / "backend" / "app" / "models"
BASE_TYPES_FILE = SCHEMA_DIR / "base.py"
EXCLUDE_FILES = {"app_snapshot.json", "apps.json", "base.py"}
DEST_DATA_DIR = PROJECT_ROOT / "backend" / "app" / "data"
DEST_DATA_DIR.mkdir(parents=True, exist_ok=True)

def snake_to_pascal(snake_str: str) -> str:
  return ''.join(word.capitalize() for word in snake_str.split('_'))

class BaseTypeResolver:
  def __init__(self, base_types_path: Path):
    self.base_types_path = base_types_path
    self.base_schemas: Dict[str, dict] = {}
    self.base_properties: Dict[str, Set[str]] = {}
    self.class_mappings: Dict[str, Tuple[str, List[str]]] = {}
    self._load_base_types()

  def _load_base_types(self):
    if not self.base_types_path.exists():
      logger.warning(f"Base types file not found at {self.base_types_path}.")
      return
    try:
      with open(self.base_types_path, "r", encoding="utf-8") as f:
        raw_base_types = json.load(f)
      for key, data in raw_base_types.items():
        match = re.match(r"([^\[]+)(?:\[([^\]]+)\])?", key)
        if not match:
          logger.warning(f"Invalid base type key: {key}. Skipping.")
          continue
        type_name = match.group(1).strip()
        parent_names = match.group(2).split(',') if match.group(2) else []
        parent_names = [p.strip() for p in parent_names if p.strip()]
        self.class_mappings[type_name] = (snake_to_pascal(type_name), parent_names)
        builder = SchemaBuilder()
        builder.add_object(data)
        self.base_schemas[type_name] = builder.to_schema()
        self.base_properties[type_name] = set(self.base_schemas[type_name].get("properties", {}).keys())
      self._generate_base_models()
      logger.info(f"Loaded base types from {self.base_types_path}.")
    except Exception as e:
      logger.error(f"Failed to load base types: {e}")
      raise

  def _generate_base_models(self):
    output_path = APP_MODELS_DIR / "base_models.py"
    base_model_content = [
      "from pydantic import BaseModel, Field, ConfigDict\n",
      "from typing import Optional\n\n"
    ]
    for type_name, (class_name, parent_names) in self.class_mappings.items():
      parent_class = "BaseModel" if not parent_names else snake_to_pascal(parent_names[0])
      base_model_content.append(f"class {class_name}({parent_class}):\n")
      base_model_content.append("  model_config = ConfigDict(str_max_length=255, extra='forbid')\n")
      for field_name in self.base_properties.get(type_name, set()):
        base_model_content.append(
          f"  {field_name}: str = Field(..., description='{field_name.replace('_', ' ').title()}', max_length=255)\n"
        )
      base_model_content.append("\n  def custom_validation(self):\n")
      base_model_content.append("    for field_name, value in self.__dict__.items():\n")
      base_model_content.append("      if isinstance(value, str) and len(value) > 255:\n")
      base_model_content.append(f"        raise ValueError(f'Field {{field_name}} exceeds max length of 255')\n\n")
    with open(output_path, "w", encoding="utf-8") as f:
      f.writelines(base_model_content)
    logger.info(f"Generated {output_path.relative_to(PROJECT_ROOT)}")

  def get_base_schema(self, base_name: str) -> dict:
    return self.base_schemas.get(base_name, {})

  def get_base_properties(self, base_name: str) -> Set[str]:
    return self.base_properties.get(base_name, set())

  def get_class_name(self, base_name: str) -> str:
    return self.class_mappings.get(base_name, ("NamedEntity", []))[0]

def collect_raw_json() -> List[Tuple[str, dict, bool]]:
  schemas = []
  for file in sorted(SCHEMA_DIR.glob("*.json")):
    if file.name in EXCLUDE_FILES:
      continue
    try:
      data = json.loads(file.read_text("utf-8"))
      if not data:
        logger.error(f"Empty JSON file: {file}")
        raise ValueError(f"Empty JSON file: {file}")
      is_schema = data.get("_schema", False) is True or file.name != BASE_TYPES_FILE.name
      if is_schema and file.name != BASE_TYPES_FILE.name:
        data = data.copy()
        data.pop("_schema", None)
      schemas.append((file.stem, data, is_schema))
    except Exception as e:
      logger.error(f"Failed to parse {file}: {e}")
      raise
  return schemas

def infer_and_inject_base_properties(raw_schemas: List[Tuple[str, dict, bool]], base_type_resolver: BaseTypeResolver) -> List[Tuple[str, Tuple[str, dict]]]:
  modified_schemas = []
  for name, data, is_schema in raw_schemas:
    if not is_schema:
      continue
    builder = SchemaBuilder()
    builder.add_object(data)
    schema = builder.to_schema()
    data_properties = set(schema.get("properties", {}).keys())
    inferred_base = "named_entity"
    max_overlap = 0

    for base_name, base_schema in base_type_resolver.base_schemas.items():
      base_properties = set(base_schema.get("properties", {}).keys())
      overlap = len(data_properties & base_properties)
      if overlap > max_overlap:
        max_overlap = overlap
        inferred_base = base_name

    logger.info(f"Schema '{name}' inferred to inherit from: {inferred_base} (overlap: {max_overlap} properties)")
    modified_data = data.copy()
    base_data = base_type_resolver.get_base_schema(inferred_base).get("properties", {})
    for k, v in base_data.items():
      if k not in modified_data:
        modified_data[k] = ""  # Use empty string as default
        logger.debug(f"Injected property '{k}' from base '{inferred_base}' into '{name}'.")
      elif isinstance(modified_data[k], dict) and v.get("type") == "object":
        modified_data[k] = {**v.get("properties", {}), **modified_data[k]}
      elif isinstance(modified_data[k], list) and v.get("type") == "array" and v.get("items", {}) and not modified_data[k]:
        modified_data[k] = [v["items"]]
    modified_schemas.append((name, (inferred_base, modified_data)))
  return modified_schemas

def make_all_properties_required(schema: dict, base_fields: Set[str]) -> None:
  if "properties" in schema:
    schema["required"] = [prop for prop in schema["properties"].keys() if prop not in base_fields]
    for prop, prop_schema in schema["properties"].items():
      if prop in base_fields:
        continue
      if prop_schema.get("type") == "object":
        prop_schema["$id"] = f"#/definitions/{prop.title()}"
        make_all_properties_required(prop_schema, base_fields)
      elif prop_schema.get("type") == "array" and prop_schema.get("items", {}).get("type") == "object":
        prop_schema["items"]["$id"] = f"#/definitions/{prop.title()}Item"
        make_all_properties_required(prop_schema["items"], base_fields)

def transform_to_json_schema(data: dict, title: str, base_fields: Set[str]) -> dict:
  builder = SchemaBuilder()
  builder.add_object(data)
  schema = builder.to_schema()
  make_all_properties_required(schema, base_fields)
  schema["additionalProperties"] = False
  schema["title"] = title
  schema["$id"] = f"#/definitions/{title}"
  return schema

def load_pydantic_model(model_name: str) -> Any:
  module_name = f"backend.app.models.{model_name}_model"
  class_name = f"{model_name.title().replace('_','')}Model"
  try:
    module = import_module(module_name)
    return getattr(module, class_name)
  except (ImportError, AttributeError):
    logger.warning(f"Model {class_name} not found.")
    return None

def serialize_data_file(file: Path, model_name: str):
  model_class = load_pydantic_model(model_name)
  if not model_class:
    logger.info(f"Skipped serialization for {file.relative_to(PROJECT_ROOT)} (no model)")
    return
  try:
    with open(file, "r", encoding="utf-8") as f:
      data = json.load(f)
    instance = model_class.model_validate(data)
    with open(file, "w", encoding="utf-8") as f:
      f.write(instance.model_dump_json(indent=2))
    logger.info(f"Serialized {file.relative_to(PROJECT_ROOT)} using {model_name} model")
  except Exception as e:
    logger.error(f"Failed to serialize {file}: {e}")
    raise

def get_source_model_data_dirs() -> List[Path]:
  model_dir = SCHEMA_DIR.parent
  return [group_dir for org_dir in model_dir.iterdir() if org_dir.is_dir() and org_dir.name != "schema" for group_dir in org_dir.iterdir() if group_dir.is_dir()]

def generate_models(schemas: List[Tuple[str, Tuple[str, dict]]], base_type_resolver: BaseTypeResolver) -> Dict[str, str]:
  model_names = {}
  for name, (base_type, data) in schemas:
    output_path = APP_MODELS_DIR / f"{name}_model.py"
    class_name = f"{name.title().replace('_','')}Model"
    base_class = f"base_models.{base_type_resolver.get_class_name(base_type)}"
    base_fields = base_type_resolver.get_base_properties(base_type)
    schema = transform_to_json_schema(data, class_name, base_fields)
    try:
      generate(
        input_=json.dumps(schema, indent=2),
        input_file_type=InputFileType.JsonSchema,
        output=output_path,
        class_name=class_name,
        base_class=base_class,
        use_double_quotes=True,
        use_schema_description=True,
        use_field_description=True,
        reuse_model=True,
        strip_default_none=True,
        target_python_version=PythonVersion.PY_310,
        disable_appending_item_suffix=True,
      )
      logger.info(f"Generated {output_path.relative_to(PROJECT_ROOT)}")
      model_names[name] = class_name
    except Exception as e:
      logger.error(f"Failed to generate {output_path}: {e}")
      raise
  return model_names

def generate_schema():
  shutil.rmtree(APP_MODELS_DIR, ignore_errors=True)
  APP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
  
  global base_type_resolver
  base_type_resolver = BaseTypeResolver(BASE_TYPES_FILE)
  raw_schemas = collect_raw_json()
  processed_schemas = infer_and_inject_base_properties(raw_schemas, base_type_resolver)
  return generate_models(processed_schemas, base_type_resolver)

def copy_model_data(model_names: Dict[str, str]):
  for source_dir in get_source_model_data_dirs():
    org_name = source_dir.parent.name
    for file in source_dir.rglob("*.json"):
      if file.name in EXCLUDE_FILES:
        continue
      rel_path = file.relative_to(source_dir.parent)
      dest_file = DEST_DATA_DIR / org_name / rel_path
      dest_file.parent.mkdir(parents=True, exist_ok=True)
      shutil.copy2(file, dest_file)
      model_name = file.stem
      if model_name in model_names:
        serialize_data_file(dest_file, model_name)
      else:
        logger.info(f"Copied {rel_path} to {dest_file.relative_to(PROJECT_ROOT)} without serialization")

  for file in SCHEMA_DIR.glob("*.json"):
    if file.name in EXCLUDE_FILES:
      continue
    data = json.loads(file.read_text("utf-8"))
    if data.get("_schema", False) is True:
      rel_path = file.relative_to(SCHEMA_DIR.parent)
      dest_file = DEST_DATA_DIR / rel_path
      dest_file.parent.mkdir(parents=True, exist_ok=True)
      shutil.copy2(file, dest_file)
      model_name = file.stem
      if model_name in model_names:
        serialize_data_file(dest_file, model_name)
      else:
        logger.info(f"Copied {rel_path} to {dest_file.relative_to(PROJECT_ROOT)} without serialization")

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