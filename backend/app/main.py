import json
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from contextlib import asynccontextmanager
from pydantic import ValidationError
from cachetools import TTLCache
from datetime import datetime
from typing import Dict, Optional
from models import Org, Group, App, DashboardData, AppTopo, AppSnapshot
from model.ucop.finapps.webify import regenerate
from .fetchers.aws_pipeline_app_fetcher import AWSPipelineFetcher  # Updated import

# Caches
dashboard_data = None  # Input model data (org, group, apps)
topology_cache = TTLCache(maxsize=100, ttl=300)  # App topology, 5-min TTL
snapshot_cache = TTLCache(maxsize=100, ttl=60)  # App snapshots, 1-min TTL

@asynccontextmanager
async def lifespan(app: FastAPI):
  global dashboard_data
  await reload_data()
  yield
  dashboard_data = None

app = FastAPI(lifespan=lifespan)

def get_dashboard_data():
  if dashboard_data is None:
    raise HTTPException(status_code=500, detail="Dashboard data not loaded")
  return dashboard_data

async def reload_data():
  global dashboard_data
  try:
    regenerate()  # Regenerate JSON files and models
    data_dir = Path(__file__).parent / "data"
    org_data = json.load(open(data_dir / "org_ucop.json"))
    group_data = json.load(open(data_dir / "group_finapps.json"))
    apps_data = [json.load(open(file)) for file in data_dir.glob("app_*.json")]
    dashboard_data = DashboardData(
      org=Org(**org_data),
      group=Group(**group_data),
      apps=[App(**app) for app in apps_data]
    )
    # Clear caches on reload
    topology_cache.clear()
    snapshot_cache.clear()
    logger.info("Dashboard data reloaded successfully")
  except (ValidationError, FileNotFoundError, json.JSONDecodeError) as e:
    logger.error(f"Error reloading data: {e}")
    raise HTTPException(status_code=500, detail=f"Error reloading data: {str(e)}")

@app.get("/dashboard")
async def get_dashboard(data: DashboardData = Depends(get_dashboard_data)):
  return data.dict()

@app.post("/reload-data")
async def reload_dashboard_data():
  await reload_data()
  return {"message": "Dashboard data reloaded successfully"}

@app.get("/apps/{app_name}/topology")
async def get_app_topology(app_name: str, env: str, data: DashboardData = Depends(get_dashboard_data)):
  cache_key = f"{app_name}:{env}"
  if cache_key in topology_cache:
    return topology_cache[cache_key].dict()

  app = next((app for app in data.apps if app.name == app_name), None)
  if not app:
    raise HTTPException(status_code=404, detail="App not found")

  env_data = next((e for e in app.environments if e.env == env), None)
  if not env_data:
    raise HTTPException(status_code=404, detail="Environment not found")

  fetcher = AWSPipelineFetcher()
  topology = fetcher.get_app_topology(app, env_data)
  if not topology:
    raise HTTPException(status_code=500, detail="Failed to fetch topology")

  topology_cache[cache_key] = topology
  return topology.dict()

@app.get("/apps/{app_name}/snapshot")
async def get_app_snapshot(app_name: str, env: str, data: DashboardData = Depends(get_dashboard_data)):
  cache_key = f"{app_name}:{env}"
  if cache_key in snapshot_cache:
    return snapshot_cache[cache_key].dict()

  app = next((app for app in data.apps if app.name == app_name), None)
  if not app:
    raise HTTPException(status_code=404, detail="App not found")

  env_data = next((e for e in app.environments if e.env == env), None)
  if not env_data:
    raise HTTPException(status_code=404, detail="Environment not found")

  # Get topology (from cache or fresh)
  topology_key = f"{app_name}:{env}"
  if topology_key not in topology_cache:
    topology_cache[topology_key] = AWSPipelineFetcher().get_app_topology(app, env_data)
  topology = topology_cache[topology_key]

  fetcher = AWSPipelineFetcher()
  snapshot = fetcher.get_app_snapshot(app, env_data, topology)
  if not snapshot:
    raise HTTPException(status_code=500, detail="Failed to fetch snapshot")

  snapshot_cache[cache_key] = snapshot
  return snapshot.dict()