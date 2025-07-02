#!/usr/bin/env python3
"""
FastAPI App for FAD Web App Models
- Uses data_loader to cache org, group, apps
- Endpoints: /org, /group, /apps/{app_name}, /apps, POST /apps/{app_name}/topo
"""
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from backend.app.data_loader import load_web_app_data, update_app_topo, WebAppData, AppTopoModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="FAD Web App API")

try:
  WEB_APP_DATA = load_web_app_data()
except Exception as e:
  logger.error(f"Failed to initialize web app data: {e}")
  raise

@app.get("/org")
async def get_org():
  return WEB_APP_DATA.org.dict()

@app.get("/group")
async def get_group():
  return WEB_APP_DATA.group.dict()

@app.get("/apps/{app_name}")
async def get_app(app_name: str):
  if app_name not in WEB_APP_DATA.apps:
    raise HTTPException(status_code=404, detail=f"App {app_name} not found")
  app_data = WEB_APP_DATA.apps[app_name]
  return {"definition": app_data.definition.dict(), "topo": app_data.topo.dict() if app_data.topo else None}

@app.get("/apps")
async def get_all_apps():
  return {name: {"definition": app_data.definition.dict(), "topo": app_data.topo.dict() if app_data.topo else None} for name, app_data in WEB_APP_DATA.apps.items()}

@app.post("/apps/{app_name}/topo")
async def update_app_topo_endpoint(app_name: str, topo: AppTopoModel):
  update_app_topo(app_name, topo.dict(), WEB_APP_DATA)
  return {"message": f"Topo updated for {app_name}"}

if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port=8000)