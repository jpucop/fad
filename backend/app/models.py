# app/models.py
from pydantic import BaseModel, HttpUrl, Field, validator
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime
import json
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_PROFILES_PATH = os.path.join(BASE_DIR, "../model/app_profiles.json")
DEPLOY_PROFILES_PATH = os.path.join(BASE_DIR, "../model/app_deploy_profiles.json")
AWS_PATH = os.path.join(BASE_DIR, "../model/aws.json")

# Load valid values for validation with defaults if files are missing
try:
    with open(APP_PROFILES_PATH, 'r') as f:
        APP_PROFILES = {p["name"] for p in json.load(f).get("app_profiles", [])}
except FileNotFoundError:
    APP_PROFILES = {"tomcat-java"}
    logger.warning(f"{APP_PROFILES_PATH} not found. Using default APP_PROFILES: {APP_PROFILES}")
try:
    with open(DEPLOY_PROFILES_PATH, 'r') as f:
        DEPLOY_PROFILES = {p["name"] for p in json.load(f).get("app_deploy_profiles", [])}
except FileNotFoundError:
    DEPLOY_PROFILES = {"aws-cicd-fargate"}
    logger.warning(f"{DEPLOY_PROFILES_PATH} not found. Using default DEPLOY_PROFILES: {DEPLOY_PROFILES}")
try:
    with open(AWS_PATH, 'r') as f:
        AWS_ACCOUNTS = {p["name"] for p in json.load(f).get("accounts", [])}
except FileNotFoundError:
    AWS_ACCOUNTS = {"finapps-dev", "finapps-prod"}
    logger.warning(f"{AWS_PATH} not found. Using default AWS_ACCOUNTS: {AWS_ACCOUNTS}")

# Shared sub-models
class Doc(BaseModel):
    name: str
    url: HttpUrl
    type: Literal["confluence", "jira"] = "confluence"
    description: Optional[str] = None

class Aws(BaseModel):
    account_name: str
    @validator('account_name')
    def validate_account_name(cls, v):
        if v not in AWS_ACCOUNTS:
            raise ValueError(f"account_name must be one of {AWS_ACCOUNTS}")
        return v

class Source(BaseModel):
    project_name: str
    git_origin_url: HttpUrl
    aws: Optional[Aws] = None  # Optional to match rems.json

# App Config Model (based on app.config-*.json and template)
class Environment(BaseModel):
    name: Literal["dev", "qa", "prod"]
    host: Literal["aws"]
    git_branch: str
    app_profile: str
    @validator('app_profile')
    def validate_app_profile(cls, v):
        if v not in APP_PROFILES:
            logger.warning(f"app_profile '{v}' not in {APP_PROFILES}. Proceeding anyway.")
        return v
    deploy_profile: str
    @validator('deploy_profile')
    def validate_deploy_profile(cls, v):
        if v not in DEPLOY_PROFILES:
            logger.warning(f"deploy_profile '{v}' not in {DEPLOY_PROFILES}. Proceeding anyway.")
        return v
    deploy_pipeline_name: str
    aws: Aws

class AppConfig(BaseModel):
    version: str = "1"
    app_name: str
    app_desc: str
    app_profile: Optional[str] = None  # Optional to match rems.json
    @validator('app_profile', allow_reuse=True)
    def validate_app_profile(cls, v):
        if v and v not in APP_PROFILES:
            logger.warning(f"app_profile '{v}' not in {APP_PROFILES}. Proceeding anyway.")
        return v
    deploy_profile: Optional[str] = None  # Optional to match rems.json
    @validator('deploy_profile', allow_reuse=True)
    def validate_deploy_profile(cls, v):
        if v and v not in DEPLOY_PROFILES:
            logger.warning(f"deploy_profile '{v}' not in {DEPLOY_PROFILES}. Proceeding anyway.")
        return v
    source: Source
    docs: List[Doc]
    environments: List[Environment]

# Snapshot Sub-Models (based on app.snapshot-template.json)
class Version(BaseModel):
    number: str
    timestamp: datetime

class Deployment(BaseModel):
    timestamp: datetime
    deploy_pipeline_execution_id: str = "?"

class DNS(BaseModel):
    A: str
    details_url: Optional[HttpUrl] = None

class Certificate(BaseModel):
    registrar: str = "AWS"
    url: HttpUrl
    expires: datetime
    name: str

class AWSEnv(BaseModel):
    account_name: str
    account_id: str
    region: str

class Cost(BaseModel):
    currency: str = "USD"
    current_monthly_total: float

class LogEntry(BaseModel):
    timestamp: datetime
    output: str
    severity: Literal["info", "warning", "error"] = "info"

class Logs(BaseModel):
    http: Dict[str, Any] = Field(default_factory=lambda: {"cloudwatch_url": "", "recent": []})
    webapp: Dict[str, Any] = Field(default_factory=lambda: {"cloudwatch_url": "", "recent": []})
    db: Dict[str, Any] = Field(default_factory=lambda: {"cloudwatch_url": "", "recent": []})

class Uptime(BaseModel):
    percentage: float
    last_downtime: datetime

class Errors(BaseModel):
    count: int
    rate: float

class Requests(BaseModel):
    total: int
    rate_per_second: float
    errors: Errors

class Latency(BaseModel):
    avg_ms: float
    p95_ms: float
    p99_ms: float

class ResourceUsage(BaseModel):
    cpu_percent: float
    memory_mb: int
    disk_gb: float

class Metrics(BaseModel):
    uptime: Uptime
    requests: Requests
    latency: Latency
    resource_usage: ResourceUsage

class Vulnerability(BaseModel):
    id: str
    severity: Literal["low", "medium", "high", "critical"]
    description: str
    reported: datetime

class Vulnerabilities(BaseModel):
    open: int
    critical: int
    latest: List[Vulnerability]

class Security(BaseModel):
    vulnerabilities: Vulnerabilities

class SnapshotEnvironment(BaseModel):
    env: str
    url: Optional[HttpUrl] = None
    status: Literal["up", "down", "unknown"]
    health: Literal["healthy", "unhealthy"]
    version: Version
    host: str = "aws"
    git_branch: str
    app_profile: str = "tomcat-java"
    deploy_profile: str = "aws-cicd-fargate"
    deploy_pipeline_name: str
    deployment: Deployment
    dns: DNS
    certificate: Certificate
    aws: AWSEnv
    cost: Cost
    logs: Logs
    metrics: Metrics
    security: Security

class Commit(BaseModel):
    id: str
    message: str
    timestamp: datetime
    branch: str

class SnapshotSource(BaseModel):
    git_origin: HttpUrl
    latest_commits: List[Commit]
    aws: Optional[Dict[str, Any]] = None

class JiraTicket(BaseModel):
    id: str
    title: str
    description: str
    status: str
    created: datetime

class Jira(BaseModel):
    url: HttpUrl
    tickets: Dict[str, Any] = Field(default_factory=lambda: {"open": 0, "latest": []})

class ServiceNowTicket(BaseModel):
    id: str
    title: str
    description: str
    created: datetime
    impact: Literal["low", "medium", "high"]
    approvers: List[str]

class ServiceNow(BaseModel):
    open: int
    overdue: int
    tickets: List[ServiceNowTicket]

class App(BaseModel):
    name: str
    desc: str
    environments: List[SnapshotEnvironment]
    source: SnapshotSource
    docs: List[Doc]
    jira: Jira
    servicenow: ServiceNow

class AppSnapshot(BaseModel):
    app_snapshot_id: str
    app_snapshot_timestamp: datetime
    app: App