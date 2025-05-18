import csv
import json
import os

# Define paths
SCHEMA_DIR = "model/init/ucop-finapps/schema"
DATA_DIR = "model/init/ucop-finapps/data"
APP_NAMES_CSV = os.path.join(SCHEMA_DIR, "app_names.csv")
APP_JSON = os.path.join(SCHEMA_DIR, "app.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Read app.json template
with open(APP_JSON, "r") as f:
    app_template = json.load(f)

# Define environment configurations
ENVIRONMENTS = [
    {
        "env": "dev",
        "name": "development",
        "git_branch": "dev",
        "aws_account_name": "finapps-dev"
    },
    {
        "env": "qa",
        "name": "staging",
        "git_branch": "qa",
        "aws_account_name": "finapps-qa"
    },
    {
        "env": "prod",
        "name": "production",
        "git_branch": "main",
        "aws_account_name": "finapps-prod"
    }
]

# Read app names from CSV
with open(APP_NAMES_CSV, "r") as f:
    reader = csv.reader(f)
    app_names = next(reader)  # Assuming single row with app names

# Generate a JSON file for each app
for app_name in app_names:
    # Copy the template
    app_config = json.deepcopy(app_template)
    
    # Update short_name and source.project_name
    app_config["short_name"] = app_name
    app_config["source"]["project_name"] = app_name
    
    # Create environment configurations
    app_config["environments"] = []
    for env in ENVIRONMENTS:
        # Copy the template environment
        env_config = json.deepcopy(app_template["environments"][0])
        # Update environment-specific fields
        env_config["env"] = env["env"]
        env_config["name"] = env["name"]
        env_config["git_branch"] = env["git_branch"]
        env_config["aws"]["account_name"] = env["aws_account_name"]
        app_config["environments"].append(env_config)
    
    # Write to data directory
    output_file = os.path.join(DATA_DIR, f"{app_name}.json")
    with open(output_file, "w") as f:
        json.dump(app_config, f, indent=2)
    
    print(f"Generated {output_file}")

print("App declaration files generated successfully.")