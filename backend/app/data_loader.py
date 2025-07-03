#!/usr/bin/env python3
"""
Data Loader for FAD Web App Models

- Loads JSON data from backend/model/ucop/finapps/ (app_*.json, org_ucop.json, group_finapps.json)
- Loads static app definitions from backend/model/schema/app.json
- Validates against Pydantic models from backend/app/models/ (AppModel, AppTopoModel, OrgModel, GroupModel)
- Uses static schemas from backend/model/schema/ (e.g., deploy_profiles.json) for constraints
- Caches model instances (org, group, apps with AppModel and AppTopoModel) for app lifecycle
- Supports on-demand AppTopoModel updates
- Requires pydantic==2.10.6
"""

import json
import logging
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
DATA_DIR = PROJECT_ROOT / "backend" / "model" / "ucop" / "finapps"
SCHEMA_DIR = PROJECT_ROOT / "backend" / "model" / "schema"


class AppData(BaseModel):
  definition: AppModel
  topo: AppTopoModel | None = None  # Allow None for on-demand topo generation


class WebAppData(BaseModel):
  org: OrgModel
  group: GroupModel
  apps: Dict[str, AppData]


def load_web_app_data() -> WebAppData:
  # Load static schemas for validation
  deploy_profiles_file = SCHEMA_DIR / "deploy_profiles.json"
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

  # Load static app definition (app.json)
  app_file = SCHEMA_DIR / "app.json"
  try:
    with open(app_file, "r") as f:
      app_data = json.load(f)
    app_model = AppModel(**app_data)
    logger.info("Loaded app.json")
  except ValidationError as e:
    logger.error(f"Validation failed for app.json: {e}")
    raise
  except Exception as e:
    logger.error(f"Failed to load app.json: {e}")
    raise

  # Load app model definition files (app_*.json)
  apps = {}
  for file in DATA_DIR.glob("app_*.json"):
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

  # Load org_ucop.json
  org_file = DATA_DIR / "org_ucop.json"
  try:
    with open(org_file, "r") as f:
      org_data = json.load(f)
    org_model = OrgModel(**org_data)
    logger.info("Loaded org_ucop.json")
  except ValidationError as e:
    logger.error(f"Validation failed for org_ucop.json: {e}")
    raise
  except Exception as e:
    logger.error(f"Failed to load org_ucop.json: {e}")
    raise

  # Load group_finapps.json
  group_file = DATA_DIR / "group_finapps.json"
  try:
    with open(group_file, "r") as f:
      group_data = json.load(f)
    group_model = GroupModel(**group_data)
    logger.info("Loaded group_finapps.json")
  except ValidationError as e:
    logger.error(f"Validation failed for group_finapps.json: {e}")
    raise
  except Exception as e:
    logger.error(f"Failed to load group_finapps.json: {e}")
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