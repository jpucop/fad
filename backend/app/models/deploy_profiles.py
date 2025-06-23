from pydantic import BaseModel, Field, validator
from typing import List

class DeployProfiles(BaseModel):
  deploy_profiles: List = []
