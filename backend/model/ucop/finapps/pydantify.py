#!/usr/bin/env python3

import json
import logging
from pathlib import Path
from typing import Dict, List
from pydantic import create_model, BaseModel, Field, validator
from pydantic.fields import FieldInfo
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent.parent.parent  # /Users/gonre/dev/fad/backend
SCHEMA_DIR = BASE_DIR / "model" / "schema"
MODEL_DIR = BASE_DIR / "model" / "ucop" / "finapps" / "models"
OUTPUT_MODELS_DIR = BASE_DIR / "app" / "models"

def load_json(file_path: Path) -> Dict:
  logger.debug(f"Loading {file_path}")
  if not file_path.exists():
    logger.error(f"File {file_path} does not exist.")
    raise FileNotFoundError(f"File {file_path} does not exist.")
  with open(file_path, "r") as f:
    return json.load(f)

def save_file(content: str, file_path: str | Path) -> None:
  file_path = Path(file_path)
  logger.debug(f"Saving {file_path}")
  file_path.parent.mkdir(parents=True, exist_ok=True)
  with open(file_path, "w") as f:
    f.write(content)

def snake_to_pascal(snake_str: str) -> str:
  return "".join(word.capitalize() for word in snake_str.split("_"))

def json_schema_to_pydantic(schema: Dict, model_name: str, parent_models: Dict = None, parent_field: str = None) -> type[BaseModel]:
  if parent_models is None:
    parent_models = {}

  fields = {}
  schema_properties = schema.get("properties", schema if isinstance(schema, dict) else {})

  for prop_name, prop_schema in schema_properties.items():
    field_type = None
    default = None
    required = prop_name == "name"  # 'name' is always required

    if isinstance(prop_schema, dict):
      prop_type = prop_schema.get("type")

      if prop_type == "object":
        nested_model_name = snake_to_pascal(prop_name)
        nested_model = json_schema_to_pydantic(
          prop_schema.get("properties", prop_schema), nested_model_name, parent_models, prop_name
        )
        parent_models[f"{model_name}.{nested_model_name}"] = nested_model
        field_type = nested_model
        default = None

      elif prop_type == "array":
        items = prop_schema.get("items", {})
        if isinstance(items, dict) and items.get("type") == "object":
          sub_model_name = snake_to_pascal(prop_name.rstrip("s"))
          sub_model = json_schema_to_pydantic(
            items.get("properties", items), sub_model_name, parent_models, prop_name
          )
          parent_models[f"{model_name}.{sub_model_name}"] = sub_model
          field_type = List[sub_model]
          default = []
          required = prop_name == "environments"  # At least one environment required for App
        elif items.get("type") == "string":
          field_type = List[str]
          default = []
        else:
          field_type = List[dict]
          default = []

      elif prop_type == "string":
        field_type = str
        default = "" if not required else ...  # Required fields use ...
      elif prop_type == "number":
        field_type = float
        default = None
      elif prop_type == "boolean":
        field_type = bool
        default = False
      else:
        field_type = str
        default = ""

    elif isinstance(prop_schema, list):
      field_type = List[str]
      default = []

    else:
      field_type = str
      default = "" if not required else ...

    fields[prop_name] = (field_type, Field(default=default, required=required))

  # Special case for Apps.defaults
  if model_name == "Apps":
    fields["defaults"] = (parent_models.get("App", BaseModel), Field(default=None))

  # Add validator for environments in App
  if model_name == "App":
    def validate_environments(cls, v: List) -> List:
      if not v:
        raise ValueError("At least one environment is required")
      return v
    return create_model(model_name, __base__=BaseModel, __validators__={"validate_environments": validator("environments")(validate_environments)}, **fields)

  return create_model(model_name, __base__=BaseModel, **fields)

def generate_model_file(model: type[BaseModel], model_name: str, model_path: Path, dependencies: List[str]):
  imports = ["from pydantic import BaseModel, Field, validator\n", "from typing import List\n"]
  if model_name == "Apps":
    imports.append("from .app import App\n")

  model_code = "".join(imports) + "\n" + f"class {model_name}(BaseModel):\n"
  for field_name, field_info in model.model_fields.items():
    field_type = field_info.annotation.__name__ if field_info.annotation else "Any"
    if getattr(field_info.annotation, "__origin__", None) is List:
      inner_type = field_info.annotation.__args__[0].__name__
      field_type = f"List[{inner_type}]"
    elif field_info.annotation.__module__ not in ["builtins", "typing"]:
      field_type = field_info.annotation.__name__
    default = field_info.default
    default_str = f" = {repr(default)}" if default is not None and default != ... else ""
    model_code += f"  {field_name}: {field_type}{default_str}\n"

  # Add validator for App.environments
  if model_name == "App":
    model_code += "\n  @validator('environments')\n"
    model_code += "  def validate_environments(cls, v):\n"
    model_code += "    if not v:\n"
    model_code += '      raise ValueError("At least one environment is required")\n'
    model_code += "    return v\n"

  save_file(model_code, model_path)
  logger.info(f"Generated Pydantic model for {model_name} at {model_path}")

def generate_init_file(model_dir: Path):
  model_files = [f.stem for f in model_dir.glob("*.py") if f.name != "__init__.py"]
  init_content = ["from pathlib import Path\n"]
  init_content.append("from . import (\n")
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
    if template_file.stem != "apps":
      template_name = template_file.stem
      template_data = load_json(template_file)
      model_name = snake_to_pascal(template_name)
      model = json_schema_to_pydantic(template_data, model_name, parent_models)
      parent_models[model_name] = model
      generate_model_file(model, model_name, MODEL_DIR / f"{template_name}.py", [])

  apps_file = SCHEMA_DIR / "apps.json"
  if apps_file.exists():
    template_data = load_json(apps_file)
    model = json_schema_to_pydantic(template_data, "Apps", parent_models)
    generate_model_file(model, "Apps", MODEL_DIR / "apps.py", ["app"])

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