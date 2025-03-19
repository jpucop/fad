from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
from pathlib import Path
import re

app = FastAPI()
app.mount("/static", StaticFiles(directory="../web/static"), name="static")
templates = Jinja2Templates(directory="../web/templates")

BASE_DIR = Path(__file__).parent.parent  # backend/
ORG_CONFIG = BASE_DIR / "model/inputs/org-info.json"
GEN_DIR = BASE_DIR / "model/gen"

with ORG_CONFIG.open() as f:
    ORG_DATA = json.load(f)

def load_app_data(app_id: str, timestamp: str = None):
    app_dir = GEN_DIR / app_id
    if not app_dir.exists():
        return {}
    if not timestamp:
        config_files = [f.name for f in app_dir.glob("app.config-*.json")]
        if not config_files:
            return {}
        timestamp = max(re.search(r"app\.config-(\d{8})\.json", f).group(1) for f in config_files)
    
    config_file = app_dir / f"app.config-{timestamp}.json"
    snapshot_file = app_dir / f"app.snapshot-{timestamp}.json"
    data = {}
    if config_file.exists():
        with config_file.open() as f:
            data.update(json.load(f))
    if snapshot_file.exists():
        with snapshot_file.open() as f:
            data.update(json.load(f))
    return data

def get_all_apps(timestamp: str = None):
    return [load_app_data(app_dir.name, timestamp) for app_dir in GEN_DIR.iterdir() if app_dir.is_dir()]

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    apps = get_all_apps()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "apps": apps,
        "org": ORG_DATA["org"]
    })
