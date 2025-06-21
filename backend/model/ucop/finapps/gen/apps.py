#!/usr/bin/env python3

import json
import logging
from pathlib import Path
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent  # /Users/gonre/dev/fad/backend
UCOP_DIR = BASE_DIR / "model" / "ucop" / "finapps"
SCHEMA_DIR = BASE_DIR / "model" / "schema"
APPS_JSON = UCOP_DIR / "gen" / "apps.json"
GROUP_JSON = UCOP_DIR / "group_finapps.json"

def load_json(file_path: Path) -> Dict:
    """Load a JSON file."""
    logger.debug(f"Loading {file_path}")
    if not file_path.exists():
        logger.error(f"File {file_path} does not exist.")
        raise FileNotFoundError(f"File {file_path} does not exist.")
    with open(file_path, "r") as f:
        return json.load(f)

def save_json(data: Dict, file_path: Path):
    """Save a JSON file."""
    logger.debug(f"Saving {file_path}")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Generated {file_path}")

def generate_environments(app_name: str, defaults: List[Dict]) -> List[Dict]:
    """Generate environment configurations."""
    environments = []
    for env in defaults:
        env_copy = env.copy()
        env_copy["pipeline_name"] = env_copy["pipeline_name"].replace("[app]", app_name)
        env_copy["pipeline_url"] = env_copy["pipeline_url"]
        environments.append(env_copy)
    return environments

def generate_app_json(app_name: str, defaults: Dict) -> Dict:
    """Generate JSON configuration for an app."""
    group_data = load_json(GROUP_JSON)

    app_json = {
        "name": app_name,
        "short_name": app_name,
        "long_name": f"{app_name.upper()} Application",
        "description": f"{app_name.upper()} Application",
        "app_profile": defaults["app_profile"],
        "deploy_profile": defaults["deploy_profile"],
        "source": {
            "repo": defaults["source"]["repo"].replace("[app]", app_name),
            "path": defaults["source"]["path"],
            "branch": defaults["source"]["branch"]
        },
        "environments": generate_environments(app_name, defaults["environments"]),
        "dbs": [],  # Empty array for databases
        "confluence": {
            "space_key": app_name.upper()
        },
        "jira": {
            "project_key": app_name.upper()
        },
        "service_now": {
            "configuration_item": f"{app_name.upper()}_CI",
            "assignment_groups": [
                {
                    "name": group_data["service_now"]["assignment_groups"][0]["name"],
                    "apps": group_data["service_now"]["assignment_groups"][0]["apps"]  # Array
                },
                {
                    "name": group_data["service_now"]["assignment_groups"][1]["name"],
                    "apps": group_data["service_now"]["assignment_groups"][1]["apps"]  # Array
                }
            ]
        }
    }

    return app_json

def regenerate():
    """Regenerate app JSON files."""
    apps_data = load_json(APPS_JSON)
    apps = apps_data["apps"]
    defaults = apps_data["defaults"]

    for app_name in apps:
        app_json = generate_app_json(app_name, defaults)
        save_json(app_json, UCOP_DIR / f"app_{app_name}.json")

if __name__ == "__main__":
    try:
        logger.info(f"BASE_DIR: {BASE_DIR}")
        logger.info(f"UCOP_DIR: {UCOP_DIR}")
        logger.info(f"APPS_JSON: {APPS_JSON}")
        logger.debug(f"Checking {APPS_JSON} -> {'exists' if APPS_JSON.exists() else 'missing'}")
        regenerate()
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise