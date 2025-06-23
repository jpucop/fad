from pydantic import BaseModel, Field, validator
from typing import List

class AppProfiles(BaseModel):
  app_profiles: List = []
