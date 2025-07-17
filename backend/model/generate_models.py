#!/usr/bin/env python3
"""
Generates Pydantic model classes from plain JSON files using GenSON and datamodel-code-generator.
Refines schemas with base types from base.json, handles static files with .static. in names,
and outputs instance data as JSON for static files.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Any
from genson import SchemaBuilder
from datamodel_code_generator import generate, InputFileType, PythonVersion
from inflection import singularize

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = PROJECT_ROOT / "backend" / "model" / "schema"
MODEL_DIR = PROJECT_ROOT / "backend" / "model"
APP_MODELS_DIR = PROJECT_ROOT / "backend" / "app" / "models"
APP_DATA_DIR = PROJECT_ROOT / "backend" / "app" / "data"
BASE_TYPES_FILE = SCHEMA_DIR / "base.json"
EXCLUDE_FILES = {"apps.json", "app_snapshot.json"}

# Ensure output directories exist
APP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)


def to_camel_case(snake_str: str) -> str:
  """Convert snake_case to CamelCase for class names."""
  return ''.join(word.capitalize() for word in snake_str.split('_'))


def load_json_files(directory: str) -> Tuple[Dict, List[Tuple[str, Dict]], List[Tuple[str, List]]]:
  """Load JSON files, classifying as base, regular, or static based on .static. suffix."""
  json_files = Path(directory).glob("*.json")
  base_types = {}
  regular_files = []
  static_files = []
  for file in json_files:
    if file.name in EXCLUDE_FILES:
      continue
    try:
      data = json.load(file.open())
      name = file.stem.replace(".static", "")  # Normalize static file names
      if file.name == "base.json":
        base_types = data
      elif ".static." in file.name and isinstance(data, list) and all(isinstance(item, dict) for item in data):
        static_files.append((name, data))
      else:
        regular_files.append((name, data))
    except Exception as e:
      print(f"Warning: Failed to load {file}: {e}")
  return base_types, regular_files, static_files


def process_base_types(base_data: Dict) -> Tuple[Dict[str, Dict], List[str]]:
  """Process base.json to extract schemas and build hierarchy (most specific to least)."""
  base_schemas = {}
  hierarchy = []
  for type_name, schema in base_data.items():
    if not isinstance(schema, dict):
      print(f"Warning: Invalid base type definition for {type_name} in {BASE_TYPES_FILE}")
      continue
    base_type = None
    if "[" in type_name:
      type_name, base_type = type_name.split("[", 1)
      base_type = base_type.rstrip("]")
      schema["$ref_base"] = base_type
    base_schemas[type_name] = {
      "type": "object",
      "properties": {k: {"type": "string", "default": ""} for k in schema},
    }
    hierarchy.append((type_name, len(schema)))
  
  # Sort by number of properties (most specific first)
  hierarchy.sort(key=lambda x: x[1], reverse=True)
  return base_schemas, [t[0] for t in hierarchy]


def generate_json_schema(json_data: Dict | List) -> Tuple[Dict, List | None]:
  """Generate JSON Schema from plain JSON data using GenSON. Return schema and instances for static files."""
  instances = None
  if isinstance(json_data, list):
    if not json_data:
      return {"type": "object", "properties": {}}, []
    json_data = json_data[0]  # Use first object for schema
    instances = json_data
  builder = SchemaBuilder()
  builder.add_object(json_data)
  schema = builder.to_schema()
  if "required" in schema:
    del schema["required"]
  return schema, instances


def match_base_type(obj_schema: Dict, base_schemas: Dict[str, Dict], hierarchy: List[str]) -> Tuple[str | None, Dict | None]:
  """Match object schema to the most specific base type based on properties."""
  if "properties" not in obj_schema:
    return None, None
  obj_props = obj_schema["properties"]
  for base_name in hierarchy:
    base_schema = base_schemas.get(base_name, {})
    base_props = base_schema.get("properties", {})
    if all(
      k in obj_props and obj_props[k].get("type") == base_props[k].get("type")
      for k in base_props
    ):
      extra_props = {k: v for k, v in obj_props.items() if k not in base_props}
      return base_name, extra_props
  return None, None


def refine_schema_with_base_types(
  schema: Dict, base_schemas: Dict[str, Dict], hierarchy: List[str], data_schemas: Dict[str, Dict], path: str = ""
) -> Dict:
  """Refine schema by applying base types and array element type inference."""
  if "properties" in schema:
    for prop_name, prop_schema in schema["properties"].items():
      if prop_schema.get("type") == "object":
        base_name, extra_props = match_base_type(prop_schema, base_schemas, hierarchy)
        if base_name:
          schema["properties"][prop_name] = {
            "$ref": f"#/$defs/{base_name}",
            "properties": extra_props or {}
          }
        else:
          schema["properties"][prop_name] = refine_schema_with_base_types(
            prop_schema, base_schemas, hierarchy, data_schemas, f"{path}.{prop_name}"
          )
      elif prop_schema.get("type") == "array":
        element_schema = infer_array_element_type(prop_name, data_schemas)
        if element_schema:
          schema["properties"][prop_name]["items"] = {"$ref": f"#/$defs/{singularize(prop_name)}"}
        elif prop_schema.get("items", {}).get("type") == "object":
          prop_schema["items"] = refine_schema_with_base_types(
            prop_schema["items"], base_schemas, hierarchy, data_schemas, f"{path}.{prop_name}"
          )
  return schema


def infer_array_element_type(prop_name: str, data_schemas: Dict[str, Dict]) -> Dict | None:
  """Infer array element type from singularized property name."""
  singular_name = singularize(prop_name)
  return data_schemas.get(singular_name)


def apply_conventions(schema: Dict) -> Dict:
  """Apply conventions: no optional fields, default "" for strings."""
  if "properties" in schema:
    for prop_name, prop_schema in schema["properties"].items():
      if prop_schema.get("type") == "string":
        prop_schema["default"] = ""
      elif prop_schema.get("type") == "object":
        prop_schema = apply_conventions(prop_schema)
      elif prop_schema.get("type") == "array" and prop_schema.get("items", {}).get("type") == "object":
        prop_schema["items"] = apply_conventions(prop_schema["items"])
  if "required" in schema:
    del schema["required"]
  return schema


def generate_pydantic_models(unified_schema: Dict, output_dir: Path):
  """Generate Pydantic models from unified JSON Schema using datamodel-code-generator."""
  output_path = output_dir / "models.py"
  generate(
    input_=json.dumps(unified_schema, indent=2),
    input_file_type=InputFileType.JsonSchema,
    output=output_path,
    class_name="Models",
    target_python_version=PythonVersion.PY_310,
    use_double_quotes=True,
    reuse_model=True
  )
  print(f"Generated Pydantic models: {output_path.relative_to(PROJECT_ROOT)}")


def save_static_instances(static_instances: Dict[str, List], output_dir: Path):
  """Save static file instance data as JSON for Pydantic loading."""
  for name, instances in static_instances.items():
    dest_path = output_dir / f"{name}.json"
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = [instance for instance in instances]
    dest_path.write_text(json.dumps(serialized, indent=2))
    print(f"Serialized static instances: {dest_path.relative_to(PROJECT_ROOT)}")


def main():
  """Main execution function."""
  # Load and classify files
  base_types, regular_files, static_files = load_json_files(SCHEMA_DIR)
  print(f"Loaded base types: {list(base_types.keys())}")
  print(f"Loaded regular files: {[name for name, _ in regular_files]}")
  print(f"Loaded static files: {[name for name, _ in static_files]}")

  # Process base types
  base_schemas, hierarchy = process_base_types(base_types)

  # Generate schemas
  data_schemas = {}
  static_instances = {}
  for name, data in regular_files:
    schema, _ = generate_json_schema(data)
    data_schemas[name] = schema
  for name, nenhanced_data in static_files:
    schema, instances = generate_json_schema(data)
    data_schemas[name] = schema
    static_instances[name] = instances

  # Refine schemas with base types and array element types
  for name, schema in data_schemas.items():
    schema = refine_schema_with_base_types(schema, base_schemas, hierarchy, data_schemas, name)
    schema = apply_conventions(schema)
    schema["title"] = to_camel_case(name)
    data_schemas[name] = schema

  # Build unified schema
  unified_schema = {
    "type": "object",
    "$defs": {name: schema for name, schema in base_schemas.items()},
    "properties": {}
  }
  for name, schema in data_schemas.items():
    unified_schema["$defs"][name] = schema
    unified_schema["properties"][name] = {"$ref": f"#/$defs/{name}"}

  # Generate Pydantic models
  generate_pydantic_models(unified_schema, APP_MODELS_DIR)

  # Save static instances as JSON
  save_static_instances(static_instances, APP_DATA_DIR)


if __name__ == "__main__":
  main()