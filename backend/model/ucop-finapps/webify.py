import json
import re
from pathlib import Path
from typing import Dict, List, Optional

def load_json(file_path: Path) -> dict:
  with open(file_path, 'r') as f:
    return json.load(f)

def save_file(content: str, file_path: Path):
  file_path.parent.mkdir(parents=True, exist_ok=True)
  with open(file_path, 'w') as f:
    f.write(content)

def snake_to_pascal(snake_str: str) -> str:
  """Convert snake_case to PascalCase."""
  return ''.join(word.capitalize() for word in snake_str.split('_'))

def json_schema_to_pydantic(schema: dict, model_name: str, indent: int = 4) -> str:
  """Convert a JSON Schema to a Pydantic model class."""
  lines = [f"from pydantic import BaseModel\n"]
  imports = set()
  
  # Check for complex types requiring imports
  for prop_schema in schema.get('properties', {}).values():
    if prop_schema.get('type') == 'array':
      imports.add('from typing import List')
    if prop_schema.get('type') == 'object' or 'properties' in prop_schema:
      imports.add('from typing import Optional')
    if prop_schema.get('type') == 'string' and 'enum' in prop_schema:
      imports.add('from enum import Enum')
  
  lines.extend(sorted(imports))
  lines.append("\n")

  # Generate enums for string fields with enum constraints
  for prop_name, prop_schema in schema.get('properties', {}).items():
    if prop_schema.get('type') == 'string' and 'enum' in prop_schema:
      enum_name = snake_to_pascal(f"{prop_name}_enum")
      lines.append(f"class {enum_name}(str, Enum):\n")
      for value in prop_schema['enum']:
        safe_value = re.sub(r'[^a-zA-Z0-9_]', '_', value.replace('|', '_'))
        lines.append(f"  {safe_value} = \"{value}\"\n")
      lines.append("\n")

  lines.append(f"class {model_name}(BaseModel):\n")
  
  for prop_name, prop_schema in schema.get('properties', {}).items():
    prop_type = prop_schema.get('type', 'string')
    python_type = 'str'
    
    # Map JSON Schema types to Python/Pydantic types
    if prop_type == 'string':
      if 'enum' in prop_schema:
        python_type = snake_to_pascal(f"{prop_name}_enum")
      else:
        python_type = 'str'
    elif prop_type == 'integer':
      python_type = 'int'
    elif prop_type == 'number':
      python_type = 'float'
    elif prop_type == 'boolean':
      python_type = 'bool'
    elif prop_type == 'array':
      item_schema = prop_schema.get('items', {})
      item_type = item_schema.get('type', 'string')
      if item_type == 'string':
        item_python_type = 'str'
      elif item_type == 'integer':
        item_python_type = 'int'
      elif item_type == 'number':
        item_python_type = 'float'
      elif item_type == 'boolean':
        item_python_type = 'bool'
      elif item_type == 'object':
        nested_model_name = snake_to_pascal(f"{prop_name}")
        lines.append(json_schema_to_pydantic(item_schema, nested_model_name))
        item_python_type = nested_model_name
      python_type = f"List[{item_python_type}]"
    elif prop_type == 'object':
      nested_model_name = snake_to_pascal(f"{prop_name}")
      lines.append(json_schema_to_pydantic(prop_schema, nested_model_name))
      python_type = nested_model_name
    
    # Handle required fields
    required = prop_name in schema.get('required', [])
    if not required:
      python_type = f"Optional[{python_type}]"
    
    lines.append(f"{' ' * indent}{prop_name}: {python_type}\n")
  
  return ''.join(lines)

def generate_init_file(models_dir: Path, data_dir: Path):
  """Generate __init__.py to export models and provide data loading."""
  model_files = [f.stem for f in models_dir.glob('*.py') if f.name != '__init__.py']
  data_files = [f.stem for f in data_dir.glob('*.json')]
  
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
    key = data_file.replace('app_', '').replace('_', '-')
    init_content.append(f"  '{key}': '{data_file}',\n")
  init_content.append("}\n")
  
  save_file(''.join(init_content), models_dir / '__init__.py')
  print(f"Generated {models_dir / '__init__.py'}")

def main():
  # Paths
  base_dir = Path(__file__).parent.parent.parent
  schema_dir = base_dir / 'model' / 'schema'
  ucop_dir = base_dir / 'model' / 'ucop-finapps'
  output_models_dir = base_dir / 'app' / 'models'
  output_data_dir = base_dir / 'app' / 'data'
  
  # Create output directories
  output_models_dir.mkdir(parents=True, exist_ok=True)
  output_data_dir.mkdir(parents=True, exist_ok=True)
  
  # Process schema files
  for schema_file in schema_dir.glob('*.json'):
    schema_name = schema_file.stem
    schema_data = load_json(schema_file)
    model_name = snake_to_pascal(schema_name)
    
    # Generate Pydantic model
    pydantic_model = json_schema_to_pydantic(schema_data, model_name)
    model_path = output_models_dir / f"{schema_name}.py"
    save_file(pydantic_model, model_path)
    print(f"Generated Pydantic model for {schema_name} at {model_path}")
  
  # Copy app, org, and group JSON files
  for json_file in ucop_dir.glob('*.json'):
    if json_file.name.startswith('app_') or json_file.name in ['org_ucop.json', 'group_finapps.json']:
      dest_path = output_data_dir / json_file.name
      json_data = load_json(json_file)
      save_file(json.dumps(json_data, indent=2), dest_path)
      print(f"Copied {json_file.name} to {dest_path}")
  
  # Generate __init__.py for models
  generate_init_file(output_models_dir, output_data_dir)

if __name__ == '__main__':
  main()