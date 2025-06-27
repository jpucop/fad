from pydantic import BaseModel

class NamedEntity(BaseModel, frozen=True):
  name: str = ""

class NameDesc(NamedEntity, frozen=True):
  description: str = ""
