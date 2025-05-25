from pydantic import BaseModel
from typing import List
from .org import Org
from .group import Group
from .app import App

class DashboardData(BaseModel):
    org: Org
    group: Group
    apps: List[App]