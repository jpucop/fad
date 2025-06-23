from pydantic import BaseModel, Field, validator
from typing import List

class AppSnapshot(BaseModel):
  snapshot_id: str = ''
  snapshot_timestamp: str = ''
  app_name: str = ''
  environment: str = ''
  source: str = ''
  aws: str = ''
  logs: str = ''
  vulnerabilities: str = ''
