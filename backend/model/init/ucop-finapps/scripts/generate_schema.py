import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# app declarations (apps.json - this drives the generation of model output)
APPS_PATH = os.path.join(BASE_DIR, "apps.json")
APP_PROFILES_PATH = os.path.join(BASE_DIR, "app_profiles.json")
APP_DEPLOY_PROFILES_PATH = os.path.join(BASE_DIR, "app_deploy_profiles.json")
ORG_PATH = os.path.join(BASE_DIR, "org.json")
AWS_PATH = os.path.join(BASE_DIR, "aws.json")

APP_CONFIG_TEMPLATE_PATH = os.path.join(BASE_DIR, "templates/app.config-template.json")
APP_SNAPSHOT_TEMPLATE_PATH = os.path.join(BASE_DIR, "templates/app.snapshot-template.json")

OUT_DIR = os.path.join(BASE_DIR, "out")

# Ensure out sub-directory exists
os.makedirs(OUT_DIR, exist_ok=True)

# Load JSON data with error handling
def load_json(file_path):
  try:
    with open(file_path, "r") as f:
      return json.load(f)
  except (FileNotFoundError, json.JSONDecodeError) as e:
    raise ValueError(f"Failed to load {file_path}: {str(e)}")

# Replace placeholders in a string, dict, or list
def replace_placeholders(data, replacements):
  if isinstance(data, str):
    for key, value in replacements.items():
      data = data.replace("{" + key + "}", str(value))
    return data
  elif isinstance(data, dict):
    return {k: replace_placeholders(v, replacements) for k, v in data.items()}
  elif isinstance(data, list):
    return [replace_placeholders(item, replacements) for item in data]
  return data

# Generate app configs
def generate_app_configs():

  # Load apps.json (declaration of existing apps to manage)
  apps_data = load_json(APPS_PATH)
  app_profiles = { p["name"]: p for p in load_json(APP_PROFILES_PATH)["app_profiles"] }
  deploy_profiles = { p["name"]: p for p in load_json(APP_DEPLOY_PROFILES_PATH)["app_deploy_profiles"] }
  org_data = load_json(ORG_PATH)
  aws_data = load_json(AWS_PATH)
  aws_accounts = { p["name"]: p for p in aws_data["accounts"] }
  
  app_config_template = load_json(APP_CONFIG_TEMPLATE_PATH)
  
  timestamp = datetime.now().strftime("%Y%m%d")

  for app in apps_data:
    app_name = app["app_name"]
    
    app_profile = app.get("app_profile", default_env["app_profile"])
    if app_profile not in app_profiles:
      raise ValueError(f"Invalid app_profile '{app_profile}' for app '{app_name}'")

    # Create config from template
    config = json.loads(json.dumps(app_config_template))
    config["app_name"] = app_name
    config["app_desc"] = app.get("app_desc", "")
    config["app_profile"] = app_profile
    config["source"] = replace_placeholders(
      config["source"],
      {
        "source.project_name": app["source"]["project_name"],
        "source.git_origin_url": app["source"]["git_origin_url"],
        "source.aws.account_name": app["source"]["aws"]["account_name"],
      }
    )
    config["docs"] = app.get("docs", [])

    # Populate environments
    config["environments"] = []
    for env_name in env_list:
      env_config = json.loads(json.dumps(default_env))  # Deep copy
      env_config.update(env_overrides.get(env_name, {}))
      
      deploy_profile = app.get("deploy_profile", env_config["deploy_profile"])
      if deploy_profile not in deploy_profiles:
        raise ValueError(f"Invalid deploy_profile '{deploy_profile}' for app '{app_name}'")
      
      env_config["env"] = env_name  # Explicitly set the env name
      env_config["deploy_profile"] = deploy_profile
      replacements = {
        "app_name": app_name,
        "env": env_name,
        "aws_account_id": org_data["group"].get("aws_account_id", ""),
        "aws_region": 
      }
      env_config = replace_placeholders(env_config, replacements)
      # Align with snapshot field names
      env_config["aws"]["account_id"] = env_config["aws"].pop("aws_account_id")
      env_config["aws"]["region"] = env_config["aws"].pop("aws_region")
      config["environments"].append(env_config)

    # Add org-related fields
    config["jira"] = replace_placeholders(
      config["jira"],
      {"jira_base_url": org_data["group"]["jira_base_url"], "app_name": app_name}
    )
    config["servicenow"] = replace_placeholders(
      config["servicenow"],
      {"servicenow_base_url": org_data["group"]["servicenow_base_url"], "app_name": app_name}
    )

    # Write output
    output_file = os.path.join(OUT_DIR, f"app.config.{app_name}.{timestamp}.json")
    with open(output_file, "w") as f:
      json.dump(config, f, indent=2)
    print(f"Generated: {output_file}")

if __name__ == "__main__":
  try:
    generate_app_configs()
  except Exception as e:
    print(f"Error: {str(e)}")