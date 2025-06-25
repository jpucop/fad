#!/usr/bin/env python3

import json
import logging
from pathlib import Path
from typing import Dict, List
from copy import deepcopy

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent  # Project root: fad/
UCOP_DIR = BASE_DIR / "model" / "ucop" / "finapps"
SCHEMA_DIR = BASE_DIR / "model" / "schema"
APPS_JSON = UCOP_DIR / "gen" / "apps.json"
ORG_UCOP_JSON = BASE_DIR / "model" / "ucop" / "org_ucop.json"
GROUP_FINAPPS_JSON = UCOP_DIR / "group_finapps.json"

def load_json(file_path: Path) -> Dict:
  """Load a JSON file and log its relative path."""
  relative_path = file_path.relative_to(BASE_DIR)
  logger.debug(f"Loading {relative_path}")
  if not file_path.exists():
    logger.error(f"File {relative_path} does not exist.")
    raise FileNotFoundError(f"File {relative_path} does not exist.")
  with open(file_path, "r") as f:
    return json.load(f)

def save_json(data: Dict, file_path: Path):
  """Save a JSON file and log its relative path."""
  relative_path = file_path.relative_to(BASE_DIR)
  logger.debug(f"Saving {relative_path}")
  file_path.parent.mkdir(parents=True, exist_ok=True)
  with open(file_path, "w") as f:
    json.dump(data, f, indent=2)
  logger.info(f"Generated {relative_path}")

def get_keys(data: Dict | List, prefix: str = "") -> set:
  """Recursively collect all keys in a JSON structure."""
  keys = set()
  if isinstance(data, dict):
    for key, value in data.items():
      keys.add(f"{prefix}{key}" if prefix else key)
      if isinstance(value, (dict, list)):
        keys.update(get_keys(value, f"{prefix}{key}."))
  elif isinstance(data, list) and data:
    keys.update(get_keys(data[0], prefix))
  return keys

def validate_defaults_against_template(defaults: Dict, template_path: Path) -> None:
  """Validate defaults.app structure against app.json template."""
  template = load_json(template_path)
  app_defaults = defaults.get("app", {})
  template_keys = get_keys(template)
  defaults_keys = get_keys(app_defaults)
  missing_keys = template_keys - defaults_keys
  if missing_keys:
    logger.warning(f"Missing keys in defaults.app: {missing_keys}")

def validate_org_against_template(org_data: Dict, template_path: Path) -> None:
  """Validate org_ucop.json structure against org.json template."""
  template = load_json(template_path)
  template_keys = get_keys(template)
  org_keys = get_keys(org_data)
  missing_keys = template_keys - org_keys
  if missing_keys:
    logger.warning(f"Missing keys in org_ucop.json: {missing_keys}")

def validate_group_against_template(group_data: Dict, template_path: Path) -> None:
  """Validate group_finapps.json structure against group.json template."""
  template = load_json(template_path)
  template_keys = get_keys(template)
  group_keys = get_keys(group_data)
  missing_keys = template_keys - group_keys
  if missing_keys:
    logger.warning(f"Missing keys in group_finapps.json: {missing_keys}")

def replace_placeholders(data: Dict | List | str, replacements: Dict) -> Dict | List | str:
  """Recursively replace placeholders in strings, lists, or dicts."""
  if isinstance(data, str):
    for key, value in replacements.items():
      data = data.replace(f"{{{key}}}", value)
    return data
  elif isinstance(data, dict):
    return {k: replace_placeholders(v, replacements) for k, v in data.items()}
  elif isinstance(data, list):
    return [replace_placeholders(item, replacements) for item in data]
  return data

def generate_app_json(app_name: str, defaults: Dict, replacements: Dict, group_data: Dict) -> Dict:
  """Generate JSON configuration for an app dynamically."""
  app_defaults = deepcopy(defaults["app"])
  app_json = replace_placeholders(app_defaults, replacements)
  app_json["name"] = app_name

  # Get ServiceNow assignment groups for the app
  sn_groups = [
    group["name"]
    for group in group_data.get("service_now", {}).get("assignment_groups", [])
    if app_name in group.get("apps", [])
  ]
  app_json["service_now"]["assignment_group_names"] = sn_groups

  # Handle database ARN replacements
  for db in app_json.get("dbs", []):
    db["aws"]["db_arn"] = db["aws"]["db_arn"].replace("{db.name}", db["name"])
    db["aws"]["db_arn"] = db["aws"]["db_arn"].replace("{aws.account_id}", replacements["account_id"])
    db["aws"]["db_arn"] = db["aws"]["db_arn"].replace("{region}", replacements["region"])

  return app_json

def regenerate():
  """Regenerate app JSON files."""
  apps_data = load_json(APPS_JSON)
  org_data = load_json(ORG_UCOP_JSON)
  group_data = load_json(GROUP_FINAPPS_JSON)
  apps = apps_data["apps"]
  defaults = apps_data["defaults"]
  
  # Validate inputs against templates
  validate_org_against_template(org_data, SCHEMA_DIR / "org.json")
  validate_group_against_template(group_data, SCHEMA_DIR / "group.json")
  validate_defaults_against_template(defaults, SCHEMA_DIR / "app.json")

  for app_name in apps:
    replacements = {
      "name": app_name,
      "app": app_name,
      "project_name": f"{app_name}Web",
      "org": org_data["name"],
      "account_id": org_data["aws_accounts"][0]["account_id"],
      "region": org_data["aws_accounts"][0]["region"]
    }
    app_json = generate_app_json(app_name, defaults, replacements, group_data)
    save_json(app_json, UCOP_DIR / f"app_{app_name}.json")

if __name__ == "__main__":
  try:
    logger.info(f"BASE_DIR: {BASE_DIR.relative_to(BASE_DIR)}")
    logger.info(f"UCOP_DIR: {UCOP_DIR.relative_to(BASE_DIR)}")
    logger.info(f"APPS_JSON: {APPS_JSON.relative_to(BASE_DIR)}")
    regenerate()
  except Exception as e:
    logger.error(f"Error: {str(e)}")
    raise