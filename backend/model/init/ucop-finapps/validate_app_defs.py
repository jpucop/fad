import json
import os
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define paths
SCHEMA_DIR = "model/init/ucop-finapps/schema"
DATA_DIR = "model/init/ucop-finapps/data"
APP_JSON = os.path.join(SCHEMA_DIR, "app.json")

# Load app.json template
with open(APP_JSON, "r") as f:
  APP_TEMPLATE = json.load(f)

def compare_structure(template: Dict[str, Any], app_json: Dict[str, Any], path: str = "") -> list[str]:
  """
  Recursively compare the structure of app_json against template, returning a list of missing properties.
  
  Args:
    template: The reference JSON structure (app.json).
    app_json: The JSON to validate.
    path: Current path in the JSON structure for error reporting.
  
  Returns:
    List of missing property paths.
  """
  missing = []
  
  for key, value in template.items():
    current_path = f"{path}.{key}" if path else key
    
    # Check if key exists in app_json
    if key not in app_json:
      missing.append(current_path)
      continue
    
    # If value is a dict, recurse
    if isinstance(value, dict):
      if not isinstance(app_json[key], dict):
        missing.append(f"{current_path} (expected dict, got {type(app_json[key]).__name__})")
      else:
        missing.extend(compare_structure(value, app_json[key], current_path))
    
    # If value is a list, check that app_json[key] is a list and validate first item (if any)
    elif isinstance(value, list):
      if not isinstance(app_json[key], list):
        missing.append(f"{current_path} (expected list, got {type(app_json[key]).__name__})")
      elif value and app_json[key]:  # Only validate if both lists have items
        # Assume first item in list defines the structure (e.g., environments, links)
        if isinstance(value[0], dict):
          for i, item in enumerate(app_json[key]):
            if not isinstance(item, dict):
              missing.append(f"{current_path}[{i}] (expected dict, got {type(item).__name__})")
            else:
              missing.extend(compare_structure(value[0], item, f"{current_path}[{i}]"))
  
  return missing

def is_valid(app_json: Dict[str, Any]) -> bool:
  """
  Validate if app_json has the same structure as the app.json template.
  
  Args:
    app_json: Parsed JSON object from an app-specific file.
  
  Returns:
    bool: True if structure matches, False otherwise.
  """
  missing_properties = compare_structure(APP_TEMPLATE, app_json)
  if missing_properties:
    logging.error(f"Validation failed: Missing or incorrect properties: {', '.join(missing_properties)}")
    return False
  return True

def main():
  """
  Validate all JSON files in data/ directory against app.json schema.
  """
  # Ensure data directory exists
  if not os.path.exists(DATA_DIR):
    logging.error(f"Data directory {DATA_DIR} does not exist.")
    return
  
  # Get all .json files in data/
  json_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".json")]
  
  if not json_files:
    logging.warning(f"No JSON files found in {DATA_DIR}.")
    return
  
  # Validate each file
  for json_file in json_files:
    file_path = os.path.join(DATA_DIR, json_file)
    logging.info(f"Validating {file_path}...")
    
    try:
      with open(file_path, "r") as f:
        app_json = json.load(f)
      
      if is_valid(app_json):
        logging.info(f"{file_path} is valid.")
      else:
        logging.error(f"{file_path} is invalid. See errors above.")
    
    except json.JSONDecodeError as e:
      logging.error(f"Failed to parse {file_path}: {str(e)}")
    except Exception as e:
      logging.error(f"Error processing {file_path}: {str(e)}")
  
  logging.info("Validation complete.")

if __name__ == "__main__":
  main()