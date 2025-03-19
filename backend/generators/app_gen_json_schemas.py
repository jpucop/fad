import json
import os
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

# Paths
BASE_DIR = Path(__file__).parent.parent
MODEL_DIR = BASE_DIR / "model"
APPS_DIR = BASE_DIR / "apps"
CONFIG_TEMPLATE = MODEL_DIR / "app.config-template.json"
SNAPSHOT_TEMPLATE = MODEL_DIR / "app.snapshot-template.json"
APPS_LIST_FILE = MODEL_DIR / "apps-list.json"

# Timestamp for filenames
TIMESTAMP = datetime.now().strftime("%Y%m%d")  # e.g., "20250316"

# Jinja2 setup
env = Environment(loader=FileSystemLoader(MODEL_DIR))

def generate_app_json_schemas():
    # Load templates
    with open(CONFIG_TEMPLATE) as f:
        config_template = env.from_string(f.read())
    with open(SNAPSHOT_TEMPLATE) as f:
        snapshot_template = env.from_string(f.read())
    
    # Load apps list
    with open(APPS_LIST_FILE) as f:
        apps = json.load(f)

    # Generate for each app
    for app in apps:
        app_id = app["id"]
        app_dir = APPS_DIR / app_id
        app_dir.mkdir(exist_ok=True)

        # Generate app.config-{timestamp}.json
        config_data = config_template.render(
            app_id=app["id"],
            app_name=app["name"],
            app_url=app["url"],
            timestamp=TIMESTAMP
        )
        config_file = app_dir / f"app.config-{TIMESTAMP}.json"
        with open(config_file, "w") as f:
            f.write(config_data)

        # Generate app.snapshot-{timestamp}.json (assuming snapshot data from input or defaults)
        snapshot_data = snapshot_template.render(
            app_id=app["id"],
            app_name=app["name"],
            timestamp=TIMESTAMP
        )
        snapshot_file = app_dir / f"app.snapshot-{TIMESTAMP}.json"
        with open(snapshot_file, "w") as f:
            f.write(snapshot_data)

        print(f"Generated configs for {app['name']} at {app_dir}")

if __name__ == "__main__":
    generate_app_json_schemas()