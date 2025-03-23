from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime

# Shared sub-models
class Doc(BaseModel):
  name: str
  url: HttpUrl
  type: str = "Confluence"

class Source(BaseModel):
  project_name: str
  git_origin_url: HttpUrl
  aws_account_id: str = "finapps-dev"
  aws_region: str = "us-west-2"

# App Config Model (app.config-template.json)
class AppConfig(BaseModel):
  version: str = "1"
  app_name: str
  app_desc: str
  source: Source
  docs: List[Doc]
  environments: List[Dict[str, Any]] = []  # Empty list by default, can be populated later

# Snapshot Sub-Models (app.snapshot-template.json)
class Version(BaseModel):
  number: str
  timestamp: datetime

class Deployment(BaseModel):
  timestamp: datetime
  deploy_pipeline_execution_id: str = "?"

class DNS(BaseModel):
  A: str
  details_url: Optional[HttpUrl] = ""

class Certificate(BaseModel):
  registrar: str = "AWS"
  url: HttpUrl
  expires: datetime
  name: str

class AWSEnv(BaseModel):
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

class Environment(BaseModel):
  env: str
  url: Optional[HttpUrl] = ""
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

# App Snapshot Model (app.snapshot-template.json)
class AppSnapshot(BaseModel):
  app_snapshot_id: str
  app_snapshot_timestamp: datetime
  app: dict = Field(default_factory=dict)  # Temporary, will refine below

  class Config:
    arbitrary_types_allowed = True  # Allow dict for initial flexibility

# Refined App model within Snapshot
class App(BaseModel):
  name: str
  desc: str
  environments: List[Environment]
  source: SnapshotSource
  docs: List[Doc]
  jira: Jira
  servicenow: ServiceNow

# Update AppSnapshot to use refined App
class AppSnapshotRefined(AppSnapshot):
  app: App