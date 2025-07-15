#!/usr/bin/env python3
"""
Generates Pydantic model classes to disk, validates and creates instances from JSON data,
and serializes them to app/data/.
Uses GenSON to convert plain JSON schemas to JSON-Schema in memory.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Type
from importlib import import_module
from genson import SchemaBuilder
from datamodel_code_generator import generate, InputFileType, PythonVersion
from pydantic import BaseModel, ValidationError

# Define project paths
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


def load_base_defs() -> Dict[str, Dict[str, Any]]:
    """Load and merge base type definitions from base.json."""
    try:
        raw = json.loads(BASE_TYPES_FILE.read_text("utf-8"))
    except FileNotFoundError:
        print(f"Warning: Base types file not found: {BASE_TYPES_FILE}")
        return {}
    defs = {}
    for key, props in raw.items():
        if not isinstance(props, dict):
            print(f"Warning: Invalid base type definition for {key} in {BASE_TYPES_FILE}")
            continue
        # Split key to handle inheritance
        name = key.split("[")[0]
        parent = key.split("[")[1].rstrip("]") if "[" in key else None
        defs[name] = {"__base__": parent, "__props__": list(props.keys()), "__total_props__": set(props.keys())}
        # Compute total properties
        p = parent
        while p and p in defs:
            defs[name]["__total_props__"].update(defs[p]["__props__"])
            p = defs[p]["__base__"]
    # Merge identical types
    merged = {}
    seen_shapes = {}
    for name, info in defs.items():
        shape = tuple(sorted(info["__total_props__"]))
        if shape not in seen_shapes:
            seen_shapes[shape] = name
            merged[name] = info
    return merged


def validate_model_against_schema(model_data: Any, schema_data: Dict[str, Any], file_path: str) -> None:
    """Validate model data against its JSON-Schema, ensuring required properties and types."""
    def check_properties(model: Dict[str, Any], schema: Dict[str, Any], path: str):
        schema_props = schema.get("properties", {})
        required = set(schema.get("required", []))
        model_props = set(model.keys())

        # Check for missing required properties
        missing = required - model_props
        if missing:
            print(f"Error: Missing required properties {missing} in {path}")
            sys.exit(1)

        # Validate property types
        for prop, schema_def in schema_props.items():
            if prop in model:
                model_val = model[prop]
                schema_type = schema_def.get("type")
                if schema_type == "object" and isinstance(model_val, dict):
                    check_properties(model_val, schema_def, f"{path}.{prop}")
                elif schema_type == "array" and isinstance(model_val, list):
                    item_schema = schema_def.get("items", {})
                    for i, item in enumerate(model_val):
                        if isinstance(item, dict) and item_schema.get("type") == "object":
                            check_properties(item, item_schema, f"{path}.{prop}[{i}]")
                elif not isinstance(model_val, type_from_schema(schema_type)):
                    print(f"Error: Type mismatch for {path}.{prop}: expected {schema_type}, got {type(model_val).__name__}")
                    sys.exit(1)

    def type_from_schema(schema_type: str) -> type:
        return {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }.get(schema_type, object)

    if isinstance(model_data, list):
        for i, item in enumerate(model_data):
            check_properties(item, schema_data, f"{file_path}[{i}]")
    elif isinstance(model_data, dict):
        check_properties(model_data, schema_data, file_path)


def generate_models(schema_dir: Path, model_output_dir: Path, base_defs: dict) -> tuple[set, Dict[str, Any]]:
    """Generate Pydantic models from schemas and base definitions using GenSON."""
    generated_models = set()
    schemas = {}

    # Generate base models
    for base_name, base_info in base_defs.items():
        parent = base_info.get("__base__")
        schema = {
            "title": to_camel_case(base_name),
            "type": "object",
            "properties": {k: {"type": "string"} for k in base_info["__props__"]},
            "required": base_info["__props__"],
            "additionalProperties": True
        }
        base_class = f"backend.app.models.{parent}.{to_camel_case(parent)}" if parent else "pydantic.BaseModel"
        output_path = model_output_dir / f"{base_name}.py"
        generate(
            input_=json.dumps(schema, indent=2),
            input_file_type=InputFileType.JsonSchema,
            output=output_path,
            class_name=to_camel_case(base_name),
            base_class=base_class,
            target_python_version=PythonVersion.PY_310,
            use_double_quotes=True,
            reuse_model=True
        )
        print(f"Generated base model: {output_path.relative_to(PROJECT_ROOT)}")
        generated_models.add(base_name)

    # Load and convert schemas using GenSON
    for schema_path in schema_dir.glob("*.json"):
        if schema_path.name in EXCLUDE_FILES or schema_path.stem in base_defs:
            continue
        try:
            raw_data = json.loads(schema_path.read_text("utf-8"))
            builder = SchemaBuilder()
            builder.add_object(raw_data)
            schema = builder.to_schema()
            if not isinstance(schema, dict) or "properties" not in schema:
                print(f"Warning: Skipping {schema_path.relative_to(PROJECT_ROOT)}: Not a valid JSON schema")
                continue
            schemas[schema_path.stem] = schema
        except Exception as e:
            print(f"Warning: Failed to load or convert schema {schema_path}: {e}")
            continue

    # Generate schema-based models
    for name, schema in schemas.items():
        props = set(schema.get("properties", {}).keys())
        # Find the most specific base class, ensuring exact match or inheritance relevance
        base_class = "pydantic.BaseModel"
        base_props = set()
        for base_name, base_info in sorted(base_defs.items(), key=lambda x: len(x[1]["__total_props__"]), reverse=True):
            # Only assign base class if properties match exactly or are in inheritance chain
            if base_info["__total_props__"].issubset(props):
                # Verify the base class is relevant (e.g., not cross-wiring unrelated types)
                if name in base_defs or any(name.startswith(k) for k in base_defs):
                    base_class = f"backend.app.models.{base_name}.{to_camel_case(base_name)}"
                    base_props = base_info["__total_props__"]
                    break
        # Adjust schema to remove base properties
        schema["properties"] = {k: v for k, v in schema["properties"].items() if k not in base_props}
        schema["required"] = list(set(schema.get("required", []) + list(schema["properties"].keys())))
        schema["additionalProperties"] = True
        schema["title"] = to_camel_case(name)

        output_path = model_output_dir / f"{name}.py"
        generate(
            input_=json.dumps(schema, indent=2),
            input_file_type=InputFileType.JsonSchema,
            output=output_path,
            class_name=to_camel_case(name),
            base_class=base_class,
            target_python_version=PythonVersion.PY_310,
            use_double_quotes=True,
            reuse_model=True
        )
        print(f"Generated model: {output_path.relative_to(PROJECT_ROOT)}")
        generated_models.add(name)

    return generated_models, schemas


def load_pydantic_model(model_name: str) -> Type[BaseModel]:
    """Dynamically load a generated Pydantic model class."""
    module_name = f"backend.app.models.{model_name}"
    try:
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.append(str(PROJECT_ROOT))
        module = import_module(module_name)
        model_class = getattr(module, to_camel_case(model_name))
        if not issubclass(model_class, BaseModel):
            raise ValueError(f"{model_name} is not a Pydantic model")
        return model_class
    except (ImportError, AttributeError, ValueError) as e:
        print(f"Error: Failed to load Pydantic model {model_name}: {e}")
        sys.exit(1)


def collect_data_files(data_root: Path) -> Dict[str, Any]:
    """Collect all JSON data files from data_root into memory."""
    files = {}
    for path in data_root.rglob("*.json"):
        if "schema" in path.parts or path.name in EXCLUDE_FILES:
            continue
        try:
            content = json.loads(path.read_text("utf-8"))
            files[str(path.relative_to(data_root))] = content
        except Exception as e:
            print(f"Warning: Failed to load data file {path}: {e}")
            continue
    return files


def process_data(files: Dict[str, Any], schemas: Dict[str, Any], generated_models: set):
    """Validate, instantiate, and serialize model data."""
    for rel_path, data in files.items():
        model_name = Path(rel_path).stem.split("_")[0]
        if model_name not in generated_models:
            print(f"Warning: Skipping {rel_path}: No matching model for {model_name}")
            continue
        if model_name not in schemas:
            print(f"Warning: Skipping {rel_path}: No schema for {model_name}")
            continue

        # Validate against schema
        try:
            validate_model_against_schema(data, schemas[model_name], rel_path)
        except ValueError as e:
            print(f"Error: Validation failed for {rel_path}: {e}")
            sys.exit(1)

        # Instantiate and serialize
        try:
            model_class = load_pydantic_model(model_name)
            if isinstance(data, list):
                instances = [model_class(**item) for item in data]
                serialized = [inst.model_dump() for inst in instances]
            else:
                instance = model_class(**data)
                serialized = instance.model_dump()

            dest_path = APP_DATA_DIR / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_text(json.dumps(serialized, indent=2))
            print(f"Serialized {rel_path} to {dest_path.relative_to(PROJECT_ROOT)}")
        except ValidationError as e:
            print(f"Error: Pydantic validation failed for {rel_path}: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: Failed to process {rel_path}: {e}")
            sys.exit(1)


def main():
    """Main execution function."""
    # Load base definitions
    base_defs = load_base_defs()
    print(f"Loaded base definitions: {list(base_defs.keys())}")

    # Generate Pydantic models and collect schemas
    generated_models, schemas = generate_models(SCHEMA_DIR, APP_MODELS_DIR, base_defs)

    # Load all JSON data into memory
    data_files = collect_data_files(MODEL_DIR)
    print(f"Loaded {len(data_files)} data files")

    # Process data
    process_data(data_files, schemas, generated_models)


if __name__ == "__main__":
    main()