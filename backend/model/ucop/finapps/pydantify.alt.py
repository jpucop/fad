#!/usr/bin/env python3

import json
import logging
from pathlib import Path
import shutil
import libcst as cst
from libcst import CSTTransformer, ClassDef, AnnAssign
from datamodel_code_generator import generate, InputFileType, PythonVersion

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # Adjust based on script location
SCHEMA_DIR = PROJECT_ROOT / "backend" / "model" / "schema"
OUTPUT_DIR = PROJECT_ROOT / "backend" / "app" / "models"
EXCLUDE_FILES = {"app_snapshot.json", "apps.json"}

def infer_property_type(value, prop_name, file_name):
  if isinstance(value, str):
    return {"type": "string", "default": ""}
  if isinstance(value, dict):
    properties = {k: infer_property_type(v, f"{prop_name}.{k}", file_name) for k, v in value.items()}
    return {"type": "object", "properties": properties, "required": list(properties.keys())}
  raise ValueError(f"Unsupported type for {prop_name} in {file_name}")

def transform_to_json_schema(data, title, file_name):
  properties = {k: infer_property_type(v, k, file_name) for k, v in data.items()}
  return {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": title,
    "type": "object",
    "properties": properties,
    "required": list(properties.keys())
  }

def generate_base_model():
  content = """from pydantic import BaseModel

class NamedEntity(BaseModel, frozen=True):
  name: str = ""

class NameDesc(NamedEntity, frozen=True):
  description: str = ""
"""
  (OUTPUT_DIR / "base_model.py").write_text(content, encoding="utf-8")

class RedundantFieldRemover(CSTTransformer):
  def __init__(self):
    self.in_class = False
    self.base_class = None
    self.inherited_fields = {"NamedEntity": {"name"}, "NameDesc": {"name", "description"}}

  def visit_ClassDef(self, node: ClassDef):
    self.in_class = True
    if node.bases:
      self.base_class = node.bases[0].value.value
    else:
      self.base_class = None
    return True

  def leave_ClassDef(self, original_node: ClassDef, updated_node: ClassDef):
    self.in_class = False
    return updated_node

  def leave_AnnAssign(self, original_node: AnnAssign, updated_node: AnnAssign):
    if self.in_class and self.base_class in self.inherited_fields:
      field_name = original_node.target.value
      if field_name in self.inherited_fields[self.base_class]:
        return None  # Remove the redundant field
    return updated_node

def post_process_model_file(file_path):
  content = file_path.read_text(encoding="utf-8")
  tree = cst.parse_module(content)
  transformer = RedundantFieldRemover()
  modified_tree = tree.visit(transformer)
  file_path.write_text(modified_tree.code, encoding="utf-8")

def main():
  shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
  OUTPUT_DIR.mkdir(parents=True)
  generate_base_model()

  for file in SCHEMA_DIR.glob("*.json"):
    if file.name in EXCLUDE_FILES:
      continue
    name = file.stem
    data = json.loads(file.read_text("utf-8"))
    schema = transform_to_json_schema(data, name.title().replace("_", ""), name)
    output_path = OUTPUT_DIR / f"{name}_model.py"
    logger.info(f"Generating {output_path}")

    base_class = "base_model.NameDesc" if "description" in data else "base_model.NamedEntity"

    generate(
      input_=json.dumps(schema),
      input_file_type=InputFileType.JsonSchema,
      output=output_path,
      class_name=f"{name.title().replace('_','')}Model",
      base_class=base_class,
      use_double_quotes=True,
      target_python_version=PythonVersion.PY_38
    )
    post_process_model_file(output_path)

if __name__ == "__main__":
  main()