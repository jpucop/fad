from pydantic import BaseModel, Field, validator
from typing import List

class Member(BaseModel):
  name: str = PydanticUndefined
  work_email: str = ''
  title: str = ''
  web_url: str = ''
  role: str = ''
  teams: List = []
