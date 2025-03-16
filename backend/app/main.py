from pathlib import Path
from typing import Union
from fastapi import FastAPI, Request, APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()
router = APIRouter()

app.mount("/static", StaticFiles(directory="backend/static"), name="static")
templates = Jinja2Templates(directory="backend/templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
  return templates.TemplateResponse("index.html", {"request": request})

@router.get("/dashboard/status")
async def get_status(request: Request):
    return templates.TemplateResponse("partials/dashboard_status.html", {"request": request, "status": "Running"})