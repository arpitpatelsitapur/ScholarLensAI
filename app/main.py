from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path

from app.core.config import settings
from app.db.base import Base, PapersBase
from app.db.session import engine_users, engine_papers
from app.api import pages, auth, users

# Initialize DBs
Base.metadata.create_all(bind=engine_users)
PapersBase.metadata.create_all(bind=engine_papers)

app = FastAPI(title="ScholarLens AI")
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Mount static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# Routers
app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(users.router)


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse("<h2>Welcome to ScholarLens AI</h2>")

