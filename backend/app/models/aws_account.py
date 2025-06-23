from pydantic import BaseModel, Field, validator
from typing import List

class AwsAccount(BaseModel):
  name: str = PydanticUndefined
  account_id: str = ''
  region: str = ''
  description: str = ''
