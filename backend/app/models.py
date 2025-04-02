from pydantic import BaseModel, HttpUrl, Field, validator
from typing import List, Optional, Literal
import json
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_PROFILES_PATH = os.path.join(BASE_DIR, "../model/app_profiles.json")
DEPLOY_PROFILES_PATH = os.path.join(BASE_DIR, "../model/app_deploy_profiles.json")
AWS_PATH = os.path.join(BASE_DIR, "../model/aws.json")

try:
    with open(APP_PROFILES_PATH, 'r') as f:
        APP_PROFILES = {p["name"] for p in json.load(f).get("app_profiles", [])}
except FileNotFoundError:
    APP_PROFILES = {"jboss-java", "tomcat-java", "flask-sso"}
    logger.warning(f"{APP_PROFILES_PATH} not found. Using default: {APP_PROFILES}")
try:
    with open(DEPLOY_PROFILES_PATH, 'r') as f:
        DEPLOY_PROFILES = {p["name"] for p in json.load(f).get("deploy_profiles", [])}
except FileNotFoundError:
    DEPLOY_PROFILES = {"aws-cicd-fargate", "aws-cicd-lambda"}
    logger.warning(f"{DEPLOY_PROFILES_PATH} not found. Using default: {DEPLOY_PROFILES}")
try:
    with open(AWS_PATH, 'r') as f:
        AWS_ACCOUNTS = {p["name"] for p in json.load(f).get("accounts", [])}
except FileNotFoundError:
    AWS_ACCOUNTS = {"finapps-dev", "finapps-prod"}
    logger.warning(f"{AWS_PATH} not found. Using default: {AWS_ACCOUNTS}")

class Aws(BaseModel):
    account_name: str = Field(..., description="AWS account name from aws.json")
    @validator('account_name')
    def validate_account_name(cls, v):
        if v not in AWS_ACCOUNTS:
            raise ValueError(f"account_name must be one of {AWS_ACCOUNTS}")
        return v

class Source(BaseModel):
    project_name: str = Field(..., min_length=1, description="Project name in source control")
    git_origin_url: HttpUrl = Field(..., description="Git repository URL")
    aws: Optional[Aws] = None

class Doc(BaseModel):
    name: str = Field(..., min_length=1, description="Documentation name")
    desc: Optional[str] = Field(default=None, description="Documentation description")
    url: HttpUrl = Field(..., description="Documentation URL")

class Environment(BaseModel):
    name: Literal["dev", "qa", "prod"] = Field(..., description="Environment name")
    host: Literal["aws"] = Field(default="aws", description="Hosting provider")
    git_branch: str = Field(..., min_length=1, description="Git branch, defaults to name if empty")
    app_profile: str = Field(..., description="App profile from app_profiles.json")
    @validator('app_profile')
    def validate_app_profile(cls, v):
        if v not in APP_PROFILES:
            logger.warning(f"app_profile '{v}' not in {APP_PROFILES}. Proceeding anyway.")
        return v
    deploy_profile: str = Field(..., description="Deploy profile from app_deploy_profiles.json")
    @validator('deploy_profile')
    def validate_deploy_profile(cls, v):
        if v not in DEPLOY_PROFILES:
            logger.warning(f"deploy_profile '{v}' not in {DEPLOY_PROFILES}. Proceeding anyway.")
        return v
    deploy_pipeline_name: str = Field(..., min_length=1, pattern=r"^pipeline-.*", description="Pipeline name")
    aws: Aws

    @validator('git_branch', pre=True)
    def default_git_branch(cls, v, values):
        return v or values.get('name', 'main')

class AppConfig(BaseModel):
    version: str = Field(default="1", description="Config version")
    app_name: str = Field(..., min_length=1, description="Unique app name")
    app_desc: str = Field(..., min_length=1, description="App description")
    app_profile: Optional[str] = Field(default=None, description="App profile from app_profiles.json")
    @validator('app_profile', allow_reuse=True)
    def validate_app_profile(cls, v):
        if v and v not in APP_PROFILES:
            logger.warning(f"app_profile '{v}' not in {APP_PROFILES}. Proceeding anyway.")
        return v
    deploy_profile: Optional[str] = Field(default=None, description="Deploy profile from app_deploy_profiles.json")
    @validator('deploy_profile', allow_reuse=True)
    def validate_deploy_profile(cls, v):
        if v and v not in DEPLOY_PROFILES:
            logger.warning(f"deploy_profile '{v}' not in {DEPLOY_PROFILES}. Proceeding anyway.")
        return v
    source: Source
    docs: List[Doc] = Field(default_factory=list)
    environments: List[Environment] = Field(default_factory=list)