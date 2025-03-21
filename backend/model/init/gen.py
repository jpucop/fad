import json
import os
from datetime import datetime

# Define paths relative to the script location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GEN_DIR = os.path.join(BASE_DIR, "../gen")
TEMPLATE_PATH = os.path.join(BASE_DIR, "../templates/app.config-template.json")
APPS_PATH = os.path.join(BASE_DIR, "apps.json")
ENV_PATH = os.path.join(BASE_DIR, "app-environments.json")
APP_PROFILES_PATH = os.path.join(BASE_DIR, "app-profile-defs.json")
DEPLOY_PROFILES_PATH = os.path.join(BASE_DIR, "deploy-profile-defs.json")
ORG_PATH = os.path.join(BASE_DIR, "org.json")

# Ensure gen directory exists
os.makedirs(GEN_DIR, exist_ok=True)

# Load JSON data
def load_json(file_path):
  with open(file_path, "r") as f:
    return json.load(f)

# Generate timestamp
TIMESTAMP = datetime.now().strftime("%Y%m%d")  # e.g., 20250320

# Replace placeholders in a string or dict
def replace_placeholders(data, replacements):
  if isinstance(data, str):
    for key, value in replacements.items():
      data = data.replace("{" + key + "}", value)
    return data
  elif isinstance(data, dict):
    return {k: replace_placeholders(v, replacements) for k, v in data.items()}
  elif isinstance(data, list):
    return [replace_placeholders(item, replacements) for item in data]
  return data

# Main function to generate config files
def generate_app_configs():
  # Load all necessary data
  apps_data = load_json(APPS_PATH)  # List of app definitions
  env_template = load_json(ENV_PATH)[0]["environments"]  # Generic env structure
  app_profiles = {p["name"]: p for p in load_json(APP_PROFILES_PATH)["app_profiles"]}
  deploy_profiles = {p["name"]: p for p in load_json(DEPLOY_PROFILES_PATH)["deploy_profiles"]}
  template = load_json(TEMPLATE_PATH)

  for app in apps_data:
    app_name = app["app_name"]
    project_name = app["source"]["project_name"]

    # Create a copy of the template
    config = template.copy()

    # Populate top-level fields
    config["app_name"] = app_name
    config["app_desc"] = app.get("app_desc", "")
    config["app_profile"] = "tomcat-java"  # Default from env template; override if needed
    config["source"] = replace_placeholders(config["source"], {"source.project_name": project_name})
    config["source"]["git_origin_url"] = app["source"]["git_origin_url"]
    config["docs"] = app.get("docs", [])

    # Populate environments from app-environments.json
    config["environments"] = []
    for env in env_template:
      env_config = env.copy()
      replacements = {
        "app_name": app_name,
        "env": env_config["env"]
      }
      env_config = replace_placeholders(env_config, replacements)
      
      # Set deploy_profile (use app-specific if provided, else from env template)
      env_config["deploy_profile"] = app.get("deploy_profile", env_config["deploy_profile"])
      config["environments"].append(env_config)

    # Output file path
    output_file = os.path.join(GEN_DIR, f"app.config.{app_name}.{TIMESTAMP}.json")
    
    # Write the config to file
    with open(output_file, "w") as f:
      json.dump(config, f, indent=2)
    print(f"Generated: {output_file}")

if __name__ == "__main__":
  generate_app_configs()