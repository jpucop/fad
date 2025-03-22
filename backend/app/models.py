from pydantic import BaseModel, HttpUrl
from typing import List, Optional

class Doc(BaseModel):
    name: str
    url: HttpUrl
    type: str

class AWS(BaseModel):
    aws_account_id: str
    aws_region: str

class Environment(BaseModel):
    env: str
    host: str
    git_branch: str
    app_profile: str  # Kept as str to match generated JSON
    deploy_profile: str  # Kept as str to match generated JSON
    aws: AWS

class Source(BaseModel):
    project_name: str
    git_origin_url: HttpUrl
    aws_account_id: str
    aws_region: str

class Profile(BaseModel):  # Restored for enrichment
    name: str
    description: str
    dependency_manager: Optional[str] = None  # Only in app_profile

class AppConfig(BaseModel):
    app_name: str
    app_desc: str
    environments: List[Environment]
    source: Source
    docs: List[Doc]