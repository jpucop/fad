from pydantic import BaseModel, Field, validator
from typing import List

class App(BaseModel):
  name: str = PydanticUndefined
  short_name: str = ''
  long_name: str = ''
  description: str = ''
  org: str = ''
  group: str = ''
  app_profile: str = ''
  deploy_profile: str = ''
  source: str = ''
  dbs: List = []
  confluence: str = ''
  box: str = ''
  jira: str = ''
  service_now: str = ''
  datadog: str = ''
  environments: List = []

  @validator('environments')
  def validate_environments(cls, v):
    if not v:
      raise ValueError("At least one environment is required")
    return v
