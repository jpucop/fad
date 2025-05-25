#!/usr/bin/env python3

import json
import os
from copy import deepcopy
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.join(BASE_DIR, "../../../schema")
UCOP_DIR = os.path.join(BASE_DIR, "..")
APPS_JSON = os.path.join(BASE_DIR, "apps.json")
APP_SCHEMA = os.path.join(SCHEMA_DIR, "app.json")
GROUP_JSON = os.path.join(UCOP_DIR, "group_finapps.json")
ORG_JSON = os.path.join(UCOP_DIR, "org_ucop.json")
OUTPUT_DIR = UCOP_DIR

def load_json_file(filepath):
  """Load a JSON file and return its contents."""
  try:
    with open(filepath, "r") as f:
      return json.load(f)
  except FileNotFoundError:
    logger.error(f"File {filepath} not found.")
    raise
  except json.JSONDecodeError:
    logger.error(f"Invalid JSON in {filepath}.")
    raise

def parse_delimited_values(value):
  """Parse [|]-delimited values from schema (e.g., [dev|qa|prod])."""
  if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
    return value[1:-1].split("|")
  return [value] if value else []

def generate_environments(env_schema, app_defaults, app_name):
  """Generate environment objects based on schema and app defaults."""
  env_instances = []
  env_values = parse_delimited_values(env_schema.get("env", ""))
  name_values = parse_delimited_values(env_schema.get("name", ""))

  if len(name_values) < len(env_values):
    name_values.extend([f"{env}-env" for env in env_values[len(name_values):]])

  for env, name in zip(env_values, name_values):
    env_config = deepcopy(env_schema)
    for key, value in env_config.items():
      if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
        env_config[key] = env if key == "env" else name if key == "name" else value
      elif value:
        env_config[key] = value
      else:
        env_config[key] = ""

    for default_env in app_defaults.get("environments", []):
      for key, value in default_env.items():
        if key in env_config and value:
          env_config[key] = value.replace("{env}", env).replace("{name}", app_name)

    env_config["aws"]["account_name"] = "finapps-prod" if env == "prod" else "finapps-dev"
    env_config["deploy_pipeline_name"] = f"{app_name}-{env}-pipeline"

    env_instances.append(env_config)
  return env_instances

def generate_app_json(app_name, defaults, app_schema, group_data):
  """Generate a single app_{name}.json file based on schema and defaults."""
  app_config = deepcopy(app_schema)
  app_defaults = defaults.get("app", {})

  for key, value in app_defaults.items():
    if key in app_config and key not in ["source", "environments", "confluence", "box", "jira", "service_now", "datadog"]:
      app_config[key] = value.replace("{name}", app_name) if isinstance(value, str) else value
    elif key == "source":
      for src_key, src_value in value.items():
        if src_key == "aws":
          app_config["source"]["aws"] = src_value
        else:
          app_config["source"][src_key] = src_value.replace("{name}", app_name) if isinstance(src_value, str) else src_value

  app_config["name"] = app_name
  app_config["short_name"] = app_config.get("short_name") or app_name
  app_config["long_name"] = app_config.get("long_name") or f"{app_name.capitalize()} Application"
  app_config["description"] = app_config.get("description") or f"Financial application for {app_name}"

  app_config["environments"] = generate_environments(app_schema["environments"][0], app_defaults, app_name)

  app_config["confluence"] = deepcopy(app_defaults.get("confluence", {"group_web_url": group_data.get("confluence", {}).get("url", "")}))
  app_config["box"] = deepcopy(app_defaults.get("box", {"group_web_url": group_data.get("box", {}).get("url", "")}))
  app_config["jira"] = deepcopy(app_defaults.get("jira", {
    "project_keys": [app_name.upper()],
    "group_web_url": group_data.get("jira", {}).get("url", "")
  }))
  app_config["service_now"] = {
    "group_web_url": app_defaults.get("service_now", {}).get("group_web_url", group_data.get("service_now", {}).get("url", "")),
    "assignment_groups": [
      group for group in app_defaults.get("service_now", {}).get("assignment_groups", group_data.get("service_now", {}).get("assignment_groups", []))
      if group.get("apps") and (app_name in group["apps"] or "ALL" in group["apps"])
    ]
  }
  app_config["datadog"] = deepcopy(app_defaults.get("datadog", {"group_web_url": group_data.get("data_dog", {}).get("url", "")}))

  return app_config

def regenerate():
  """Generate app_*.json files from gen/apps.json."""
  apps_data = load_json_file(APPS_JSON)
  app_schema = load_json_file(APP_SCHEMA)
  group_data = load_json_file(GROUP_JSON)

  app_names = apps_data.get("apps", [])
  defaults = apps_data.get("defaults", {})

  for app_name in app_names:
    app_config = generate_app_json(app_name, defaults, app_schema, group_data)
    output_file = os.path.join(OUTPUT_DIR, f"app_{app_name}.json")
    with open(output_file, "w") as f:
      json.dump(app_config, f, indent=2)
    logger.info(f"Generated {output_file}")

if __name__ == "__main__":
  try:
    regenerate()
  except Exception as e:
    logger.error(f"Error: {str(e)}")
    exit(1)
