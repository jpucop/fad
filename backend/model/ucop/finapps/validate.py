#!/usr/bin/env python3

import json
import os
import logging
import glob
from typing import Any, Dict, List

# Configure logging
logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Define paths relative to the script's location (ucop-finapps/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.join(BASE_DIR, "../schema")
APP_SCHEMA = os.path.join(SCHEMA_DIR, "app.json")
APP_FILES_GLOB = os.path.join(BASE_DIR, "app_*.json")

def load_json_file(filepath: str) -> Dict:
  """Load a JSON file and return its contents."""
  try:
    with open(filepath, 'r') as f:
      return json.load(f)
  except FileNotFoundError:
    logger.error(f"File {filepath} not found.")
    raise
  except json.JSONDecodeError:
    logger.error(f"Invalid JSON in {filepath}.")
    raise

def get_expected_type(schema_value: Any) -> str:
  """Determine the expected type from a schema value."""
  if isinstance(schema_value, dict):
    return "object"
  if isinstance(schema_value, list):
    return "array"
  if isinstance(schema_value, str):
    return "string"
  if isinstance(schema_value, bool):
    return "boolean"
  if isinstance(schema_value, (int, float)):
    return "number"
  return "null"

def validate_properties(data: Dict, schema: Dict, path: str, file_name: str) -> List[str]:
  """Recursively validate properties in data against schema, returning discrepancies."""
  discrepancies = []

  # Check for missing or type-mismatched properties
  for key, schema_value in schema.items():
    current_path = f"{path}.{key}" if path else key
    expected_type = get_expected_type(schema_value)

    if key not in data:
      discrepancies.append(f"{file_name}: Missing property '{current_path}' (expected {expected_type})")
      continue

    data_value = data[key]
    actual_type = get_expected_type(data_value)

    # Type mismatch check
    if actual_type != expected_type:
      discrepancies.append(
        f"{file_name}: Type mismatch for '{current_path}' (expected {expected_type}, found {actual_type})"
      )
      continue

    # Recursive check for objects and arrays
    if expected_type == "object":
      discrepancies.extend(validate_properties(data_value, schema_value, current_path, file_name))
    elif expected_type == "array" and schema_value and isinstance(schema_value[0], dict):
      for i, item in enumerate(data_value):
        discrepancies.extend(validate_properties(item, schema_value[0], f"{current_path}[{i}]", file_name))

  # Check for unexpected properties
  for key in data:
    if key not in schema:
      current_path = f"{path}.{key}" if path else key
      discrepancies.append(f"{file_name}: Unexpected property '{current_path}'")

  return discrepancies

def main():
  """Validate all app_*.json files against schema/app.json."""
  try:
    # Load schema
    app_schema = load_json_file(APP_SCHEMA)

    # Find all app_*.json files
    app_files = glob.glob(APP_FILES_GLOB)
    if not app_files:
      logger.warning("No app_*.json files found in %s", BASE_DIR)
      return

    # Validate each file
    all_valid = True
    for app_file in app_files:
      file_name = os.path.basename(app_file)
      logger.info("Validating %s...", file_name)
      app_data = load_json_file(app_file)

      # Validate properties
      discrepancies = validate_properties(app_data, app_schema, "", file_name)
      if discrepancies:
        all_valid = False
        for discrepancy in discrepancies:
          logger.error(discrepancy)
      else:
        logger.info("%s: Valid", file_name)

    # Summary
    if all_valid:
      logger.info("All app files are valid!")
    else:
      logger.error("Validation failed for one or more app files.")

  except Exception as e:
    logger.error("Error: %s", str(e))
    exit(1)

if __name__ == "__main__":
  main()