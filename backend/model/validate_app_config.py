from enum import Enum
from pydantic import BaseModel, HttpUrl, Field, ValidationError
from typing import List, Optional
import json
import sys

class AWSConfig(BaseModel):
  account_name: str

class Document(BaseModel):
  name: str
  type: Optional[str] = None
  url: HttpUrl
  description: Optional[str] = ""

class EnvironmentName(str, Enum):
    dev = "dev"
    qa = "qa"
    prod = "prod"

class Environment(BaseModel):
  name: EnvironmentName
  host: str = Field(..., regex="^aws$")  # Ensures "aws" is the only valid value
  git_branch = Field(..., min_length=1, max_length=50)
  app_profile: str
  deploy_profile: str
  deploy_pipeline_name: str
  aws: AWSConfig

class SourceConfig(BaseModel):
  project_name: str
  git_origin_url: HttpUrl
  aws: Optional[AWSConfig] = None

class AppConfig(BaseModel):
  app_name: str
  app_desc: str
  source: SourceConfig
  docs: List[Document]
  environments: List[Environment]

def load_json(filename: str):
  try:
    with open(filename, 'r') as file:
      return json.load(file)
  except Exception as e:
    print(f"Error loading {filename}: {e}")
    sys.exit(1)

def validate_app_config(config_file: str):
  data = load_json(config_file)
  try:
    config = AppConfig(**data)
    print(f"{config_file} is valid.")
  except ValidationError as e:
    print(f"Validation failed for {config_file}:")
    print(e.json())
    sys.exit(1)

if __name__ == "__main__":
  if len(sys.argv) != 2:
    print("Usage: python validate_app_config.py <app.config-xxx.json>")
    sys.exit(1)
  validate_app_config(sys.argv[1])
