from fastapi import APIRouter, HTTPException
from app.models import App, Org, Group, load_data, DATA_FILES

router = APIRouter(prefix="/api")

@router.get("/apps/{app_name}", response_model=App)
async def get_app(app_name: str):
    file_name = DATA_FILES.get(app_name.replace('-', '_'))
    if not file_name:
        raise HTTPException(status_code=404, detail="App not found")
    return App(**load_data(file_name))

@router.get("/org", response_model=Org)
async def get_org():
    return Org(**load_data('org_ucop'))

@router.get("/group", response_model=Group)
async def get_group():
    return Group(**load_data('group_finapps'))

@router.get("/apps")
async def list_apps():
    return [{"name": k, "file": v} for k, v in DATA_FILES.items() if not k.startswith(('org-', 'group-'))]