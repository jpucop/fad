from pydantic import BaseModel, Field, validator
from typing import List

class Group(BaseModel):
  name: str = PydanticUndefined
  full_name: str = ''
  description: str = ''
  members: List = []
  aws_accounts: List = []
  confluence: str = ''
  box: str = ''
  jira: str = ''
  data_dog: str = ''
  service_now: str = ''
