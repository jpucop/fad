from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
from pathlib import Path
import re
from app.models import AppConfig

app = FastAPI()

BASE_DIR = Path(__file__).parent.parent  # ~/dev/fad/backend/
STATIC_DIR = BASE_DIR / "web/static"
TEMPLATES_DIR = BASE_DIR / "web/templates"
ORG_CONFIG = BASE_DIR / "model/init/org.json"
GEN_DIR = BASE_DIR / "model/gen"

# Mount static files and templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Load org and profile data
with ORG_CONFIG.open() as f:
    ORG_DATA = json.load(f)

def load_app_config(filename: str) -> AppConfig:
    """Load and validate an app config file."""
    file_path = GEN_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Config file {filename} not found")
    
    with file_path.open() as f:
        data = json.load(f)
    
    try:
        return AppConfig(**data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid config {filename}: {str(e)}")

def get_all_apps(timestamp: str = None) -> list[AppConfig]:
    """Load all app configs, optionally filtered by timestamp."""
    configs = []
    for filename in GEN_DIR.glob("app.config.*.json"):
        if timestamp and timestamp not in filename.name:
            continue
        configs.append(load_app_config(filename.name))
    return configs

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    apps = get_all_apps()
    enriched_apps = [enrich_config(app) for app in apps]
    return templates.TemplateResponse("index.html", {
        "request": request,
        "apps": enriched_apps,
        "org": ORG_DATA["group"]
    })

@app.get("/config", response_class=HTMLResponse)
async def config(request: Request):
    apps = get_all_apps()
    enriched_apps = [enrich_config(app) for app in apps]
    return templates.TemplateResponse("config/index.html", {
        "request": request,
        "apps": enriched_apps,
        "org": ORG_DATA["group"]
    })

@app.get("/configs/{app_name}")
async def get_config(app_name: str, timestamp: str = None):
    """Get a specific app config by name and optional timestamp."""
    pattern = f"app.config.{app_name}.*.json" if not timestamp else f"app.config.{app_name}.{timestamp}.json"
    for filename in GEN_DIR.glob(pattern):
        config = load_app_config(filename.name)
        return enrich_config(config)
    raise HTTPException(status_code=404, detail=f"No config found for {app_name}")