# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import glob
import json
import os
from typing import List, Dict
from datetime import datetime
from app.models import AppConfig, AppSnapshot, Environment, Metrics, Uptime, Requests, Errors, Latency, ResourceUsage, SnapshotSource, Commit, Jira, JiraTicket, ServiceNow, ServiceNowTicket, Doc, Version, Deployment, DNS, Certificate, AWSEnv, Cost, Logs, LogEntry, Vulnerabilities, Vulnerability, Security

app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "../model")
TEMPLATES = Jinja2Templates(directory=os.path.join(BASE_DIR, "../web/templates"))

def load_json(file_path: str) -> dict:
    with open(file_path, "r") as f:
        return json.load(f)

def mock_snapshot(app_name: str, config: AppConfig) -> Dict:
    """Generate a mock AppSnapshot based on AppConfig (replace with AWS fetch later)."""
    now = datetime.now()
    environments = []
    for env in config.environments:
        environments.append({
            "env": env.name,
            "url": f"https://{app_name}-{env.name}.example.com",
            "status": "up",
            "health": "healthy",
            "version": {"number": "1.2.3", "timestamp": now.isoformat()},
            "host": "aws",
            "git_branch": env.git_branch,
            "app_profile": env.app_profile,
            "deploy_profile": env.deploy_profile,
            "deploy_pipeline_name": env.deploy_pipeline_name,
            "deployment": {"timestamp": now.isoformat(), "deploy_pipeline_execution_id": f"pipe-{env.name}-123"},
            "dns": {"A": "192.168.1.1", "details_url": None},  # Changed "" to None
            "certificate": {
                "registrar": "AWS",
                "url": "https://aws.com/cert123",
                "expires": "2026-03-24T12:00:00Z",
                "name": f"{app_name}-{env.name}.example.com"
            },
            "aws": {"account_name": env.aws.account_name, "account_id": "123456789012", "region": "us-west-2"},
            "cost": {"currency": "USD", "current_monthly_total": 150.75},
            "logs": {
                "http": {"cloudwatch_url": f"https://logs.aws.com/{app_name}/{env.name}/http", "recent": [
                    {"timestamp": now.isoformat(), "output": "GET /api 200 OK", "severity": "info"}
                ]},
                "webapp": {"cloudwatch_url": f"https://logs.aws.com/{app_name}/{env.name}/webapp", "recent": []},
                "db": {"cloudwatch_url": f"https://logs.aws.com/{app_name}/{env.name}/db", "recent": []}
            },
            "metrics": {
                "uptime": {"percentage": 99.95, "last_downtime": "2025-03-01T03:00:00Z"},
                "requests": {"total": 15000, "rate_per_second": 10.5, "errors": {"count": 50, "rate": 0.33}},
                "latency": {"avg_ms": 120, "p95_ms": 250, "p99_ms": 400},
                "resource_usage": {"cpu_percent": 65.5, "memory_mb": 2048, "disk_gb": 15.3}
            },
            "security": {
                "vulnerabilities": {
                    "open": 3,
                    "critical": 1,
                    "latest": [
                        {"id": "CVE-2025-1234", "severity": "critical", "description": "Buffer overflow", "reported": "2025-03-05T12:00:00Z"}
                    ]
                }
            }
        })
    
    return {
        "app_snapshot_id": f"app-snap-{app_name}-{now.strftime('%Y%m%d%H%M%S')}",
        "app_snapshot_timestamp": now.isoformat(),
        "app": {
            "name": app_name,
            "desc": config.app_desc,
            "environments": environments,
            "source": {
                "git_origin": str(config.source.git_origin_url),
                "latest_commits": [
                    {"id": "abc123", "message": "Fix bug", "timestamp": "2025-03-24T09:00:00Z", "branch": "main"}
                ]
            },
            "docs": [doc.dict() for doc in config.docs],
            "jira": {
                "url": "https://ucopedu.atlassian.net",
                "tickets": {"open": 5, "latest": [
                    {"id": "JIRA-123", "title": "Fix login", "description": "Login issue", "status": "open", "created": "2025-03-24T08:00:00Z"}
                ]}
            },
            "servicenow": {
                "open": 3,
                "overdue": 1,
                "tickets": [
                    {"id": "INC001", "title": "Server down", "description": "Prod offline", "created": "2025-03-23T14:00:00Z", "impact": "high", "approvers": ["user1@example.com"]}
                ]
            }
        }
    }

@app.on_event("startup")
async def validate_configs():
    config_files = glob.glob(os.path.join(MODEL_DIR, "app.config-*.json"))
    if not config_files:
        raise RuntimeError("No app config files found")
    validated_configs: List[AppConfig] = []
    snapshots: Dict[str, AppSnapshot] = {}
    for config_file in config_files:
        try:
            data = load_json(config_file)
            config = AppConfig(**data)
            validated_configs.append(config)
            snapshot_data = mock_snapshot(config.app_name, config)
            snapshots[config.app_name] = AppSnapshot(**snapshot_data)
            print(f"Validated: {config_file} (app: {config.app_name})")
        except Exception as e:
            raise RuntimeError(f"Validation failed for {config_file}: {e}")
    app.state.app_configs = validated_configs
    app.state.app_snapshots = snapshots

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return TEMPLATES.TemplateResponse("index.html", {"request": request})

@app.get("/app-tiles", response_class=HTMLResponse)
async def app_tiles(request: Request):
    return TEMPLATES.TemplateResponse("app-tile-grid.html", {"request": request, "configs": app.state.app_configs, "snapshots": app.state.app_snapshots})

@app.get("/configs")
async def list_configs():
    return {"configs": [{"app_name": c.app_name, "app_desc": c.app_desc} for c in app.state.app_configs]}

@app.get("/app/{app_name}", response_class=HTMLResponse)
async def app_detail(request: Request, app_name: str):
    config = next((c for c in app.state.app_configs if c.app_name == app_name), None)
    snapshot = app.state.app_snapshots.get(app_name)
    if not config or not snapshot:
        return HTMLResponse("App not found", status_code=404)
    return TEMPLATES.TemplateResponse("app-detail.html", {"request": request, "config": config, "snapshot": snapshot})