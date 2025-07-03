#!/usr/bin/env python3
"""
Data Loader for FAD Web App Models

- Copies JSON data from backend/model/ (excluding model/schema/) to backend/app/data/
- Copies static JSON definitions from backend/model/schema/ to backend/app/data/ if _schema: true present
- Loads JSON data from backend/app/data/ (app_*.json, org_*.json, group_*.json)
- Validates against Pydantic models from backend/app/models/ (AppModel, AppTopoModel, OrgModel, GroupModel)
- Uses static schemas from backend/app/data/ (e.g., deploy_profiles.json) for constraints
- Caches model instances (org, group, apps with AppModel and AppTopoModel) for app lifecycle
- Supports on-demand AppTopoModel updates
- Requires pydantic==2.10.6
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict
from pydantic import BaseModel, ValidationError

# Import generated Pydantic models
from backend.app.models.app_model import AppModel
from backend.app.models.app_topo_model import AppTopoModel
from backend.app.models.org_model import OrgModel
from backend.app.models.group_model import GroupModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def find_project_root() -> Path:
  current = Path(__file__).resolve().parent
  while current != current.parent:
    if (current / "backend").is_dir() and (current / "frontend").is_dir():
      return current
    current = current.parent
  raise RuntimeError("Project root not found")

PROJECT_ROOT = find_project_root()
MODEL_DIR = PROJECT_ROOT / "backend" / "model"
SCHEMA_DIR = MODEL_DIR / "schema"
DATA_DIR = PROJECT_ROOT / "backend" / "app" / "data"

class AppData(BaseModel):
  definition: AppModel
  topo: AppTopoModel | None = None  # Allow None for on-demand topo generation

class WebAppData(BaseModel):
  org: OrgModel
  group: GroupModel
  apps: Dict[str, AppData]

def prepare_data_dir() -> None:
  """Copy eligible JSON files into app/data/ based on _schema rules."""
  DATA_DIR.mkdir(parents=True, exist_ok=True)

  # Copy all JSON files from model/ recursively excluding schema/
  for file in MODEL_DIR.rglob("*.json"):
    if SCHEMA_DIR in file.parents:
      continue
    dest = DATA_DIR / file.relative_to(MODEL_DIR)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(file, dest)
    logger.info(f"Copied {file} to {dest}")

  # Copy static JSON files from schema/ if _schema: true present
  for file in SCHEMA_DIR.glob("*.json"):
    try:
      with open(file, "r") as f:
        content = json.load(f)
      if content.get("_schema") is True:
        dest = DATA_DIR / file.name
        shutil.copy(file, dest)
        logger.info(f"Copied static schema {file} to {dest}")
    except Exception as e:
      logger.error(f"Failed to process schema file {file}: {e}")
      raise

def load_web_app_data() -> WebAppData:
  # Load deploy_profiles.json
  deploy_profiles_file = DATA_DIR / "deploy_profiles.json"
  deploy_profiles = []
  if deploy_profiles_file.exists():
    try:
      with open(deploy_profiles_file, "r") as f:
        raw_profiles = json.load(f)
      deploy_profiles = [p["name"] for p in raw_profiles.get("deploy_profiles", [])]
      logger.info(f"Loaded deploy profiles: {deploy_profiles}")
    except Exception as e:
      logger.error(f"Failed to load deploy_profiles.json: {e}")
      raise

  # Load org_*.json
  org_file = next(DATA_DIR.glob("org_*.json"), None)
  if not org_file:
    raise FileNotFoundError("No org_*.json file found in data dir")
  try:
    with open(org_file, "r") as f:
      org_data = json.load(f)
    org_model = OrgModel(**org_data)
    logger.info(f"Loaded {org_file.name}")
  except ValidationError as e:
    logger.error(f"Validation failed for {org_file.name}: {e}")
    raise
  except Exception as e:
    logger.error(f"Failed to load {org_file.name}: {e}")
    raise

  # Load group_*.json
  group_file = next(DATA_DIR.glob("group_*.json"), None)
  if not group_file:
    raise FileNotFoundError("No group_*.json file found in data dir")
  try:
    with open(group_file, "r") as f:
      group_data = json.load(f)
    group_model = GroupModel(**group_data)
    logger.info(f"Loaded {group_file.name}")
  except ValidationError as e:
    logger.error(f"Validation failed for {group_file.name}: {e}")
    raise
  except Exception as e:
    logger.error(f"Failed to load {group_file.name}: {e}")
    raise

  # Load app_*.json files, excluding known static files like app_profiles.json
  apps = {}
  for file in DATA_DIR.glob("app_*.json"):
    if file.name == "app_profiles.json":
      continue
    try:
      with open(file, "r") as f:
        data = json.load(f)
      app_name = file.stem.replace("app_", "")

      if deploy_profiles and data.get("deploy_profile") not in deploy_profiles:
        logger.error(f"Invalid deploy_profile in {file.name}: {data.get('deploy_profile')}")
        raise ValueError(f"Invalid deploy_profile in {file.name}")

      app_model_instance = AppModel(**data)
      apps[app_name] = AppData(definition=app_model_instance, topo=None)
      logger.info(f"Loaded app definition: {app_name}")

    except ValidationError as e:
      logger.error(f"Validation failed for {file.name}: {e}")
      raise
    except Exception as e:
      logger.error(f"Failed to load {file.name}: {e}")
      raise

  return WebAppData(org=org_model, group=group_model, apps=apps)

def update_app_topo(app_name: str, topo_data: dict, data: WebAppData) -> None:
  """Update or add AppTopoModel for an app, used for on-demand generation."""
  try:
    topo_model = AppTopoModel(**topo_data)
    if app_name in data.apps:
      data.apps[app_name].topo = topo_model
    else:
      data.apps[app_name] = AppData(definition=data.apps[list(data.apps.keys())[0]].definition, topo=topo_model)
    logger.info(f"Updated topo for app: {app_name}")
  except ValidationError as e:
    logger.error(f"Validation failed for topo data of {app_name}: {e}")
    raise
  except Exception as e:
    logger.error(f"Failed to update topo for {app_name}: {e}")
    raise
