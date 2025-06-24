#!/usr/bin/env python3

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import create_model, BaseModel, Field
import shutil
import inflect
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Pluralizer for singularization
inflector = inflect.engine()

# Paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
SCHEMA_DIR = BASE_DIR / "model" / "schema"
MODEL_DIR = BASE_DIR / "model" / "ucop" / "finapps" / "models"
OUTPUT_MODELS_DIR = BASE_DIR / "app" / "models"

def load_json(file_path: Path) -> Dict:
  logger.debug(f"Loading {file_path}")
  if not file_path.exists():
    raise FileNotFoundError(f"File {file_path} does not exist.")
  with open(file_path, "r") as f:
    return json.load(f)

def save_file(content: str, file_path: Path) -> None:
  logger.debug(f"Saving {file_path}")
  file_path.parent.mkdir(parents=True, exist_ok=True)
  with open(file_path, "w") as f:
    f.write(content)

def snake_to_pascal(snake_str: str) -> str:
  return "".join(word.capitalize() for word in snake_str.split("_"))

def pascal_to_snake(name: str) -> str:
  return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

def singularize(name: str) -> str:
  singular = inflector.singular_noun(name)
  return singular if singular else name

def json_schema_to_pydantic(schema: Dict, model_name: str, parent_models: Dict = None) -> type[BaseModel]:
  if parent_models is None:
    parent_models = {}

  fields = {}

  for prop_name, prop_value in schema.items():
    field_type = str
    default = ""

    if isinstance(prop_value, dict):
      nested_model_name = snake_to_pascal(f"{model_name}_{prop_name}")
      nested_model = json_schema_to_pydantic(prop_value, nested_model_name, parent_models)
      parent_models[nested_model_name] = nested_model
      field_type = nested_model
      default = None
    elif isinstance(prop_value, list):
      singular = singularize(prop_name)
      element_model_name = snake_to_pascal(singular)

      if prop_value and isinstance(prop_value[0], dict):
        sub_model = json_schema_to_pydantic(prop_value[0], element_model_name, parent_models)
        parent_models[element_model_name] = sub_model
        field_type = List[sub_model]
      else:
        field_type = List[str]
      default = []
    else:
      field_type = str
      default = ""

    fields[prop_name] = (field_type, Field(default=default))

  return create_model(model_name, __base__=BaseModel, **fields)

def generate_model_file(model: type[BaseModel], model_name: str, model_path: Path, parent_models: Dict):
  lines = ["from pydantic import BaseModel, Field\n", "from typing import List, Optional\n"]

  for field_info in model.model_fields.values():
    annotation = field_info.annotation
    if hasattr(annotation, "__name__") and annotation.__name__ in parent_models:
      lines.append(f"from .{pascal_to_snake(annotation.__name__)} import {annotation.__name__}\n")
    if hasattr(annotation, "__origin__") and annotation.__origin__ in (list, List):
      inner = annotation.__args__[0]
      if hasattr(inner, "__name__") and inner.__name__ in parent_models:
        lines.append(f"from .{pascal_to_snake(inner.__name__)} import {inner.__name__}\n")

  lines.append(f"\nclass {model_name}(BaseModel):\n")

  for field_name, field_info in model.model_fields.items():
    annotation = field_info.annotation
    field_type = "str"
    if hasattr(annotation, "__name__"):
      field_type = annotation.__name__
    if hasattr(annotation, "__origin__") and annotation.__origin__ in (list, List):
      inner = annotation.__args__[0]
      inner_type = inner.__name__ if hasattr(inner, "__name__") else "str"
      field_type = f"List[{inner_type}]"

    default = field_info.default
    default_str = f" = {repr(default)}" if default not in (None, ...) else ""
    lines.append(f"  {field_name}: {field_type}{default_str}\n")

  save_file("".join(lines), model_path)
  logger.info(f"Generated Pydantic model for {model_name} at {model_path}")

def generate_init_file(model_dir: Path):
  model_files = [f.stem for f in model_dir.glob("*.py") if f.name != "__init__.py"]
  init_content = ["from . import (\n"]
  init_content.extend(f"  {model},\n" for model in sorted(model_files))
  init_content.append(")\n")
  save_file("".join(init_content), model_dir / "__init__.py")
  logger.info(f"Generated {model_dir / '__init__.py'}")

def copy_models_to_app():
  OUTPUT_MODELS_DIR.mkdir(parents=True, exist_ok=True)
  for model_file in MODEL_DIR.glob("*.py"):
    shutil.copy(model_file, OUTPUT_MODELS_DIR / model_file.name)
    logger.info(f"Copied {model_file} to {OUTPUT_MODELS_DIR / model_file.name}")
  generate_init_file(OUTPUT_MODELS_DIR)

def generate_models():
  MODEL_DIR.mkdir(parents=True, exist_ok=True)
  parent_models = {}

  for template_file in sorted(SCHEMA_DIR.glob("*.json")):
    template_name = template_file.stem
    template_data = load_json(template_file)
    model_name = snake_to_pascal(template_name)
    model = json_schema_to_pydantic(template_data, model_name, parent_models)
    parent_models[model_name] = model
    generate_model_file(model, model_name, MODEL_DIR / f"{pascal_to_snake(model_name)}.py", parent_models)

  for sub_model_name, sub_model in parent_models.items():
    if sub_model_name not in [m for m in parent_models.keys() if m == sub_model_name]:
      generate_model_file(sub_model, sub_model_name, MODEL_DIR / f"{pascal_to_snake(sub_model_name)}.py", parent_models)

  generate_init_file(MODEL_DIR)
  copy_models_to_app()

if __name__ == "__main__":
  try:
    logger.info(f"BASE_DIR: {BASE_DIR}")
    logger.info(f"SCHEMA_DIR: {SCHEMA_DIR}")
    logger.info(f"MODEL_DIR: {MODEL_DIR}")
    generate_models()
  except Exception as e:
    logger.error(f"Error: {e}")
    raise
