from pydantic import BaseModel, Field, validator
from typing import List

class AppTopo(BaseModel):
  app_name: str = ''
  environment: str = ''
  deploy_profile: str = ''
  created: str = ''
  source: str = ''
  aws: str = ''
