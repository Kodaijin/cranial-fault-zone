"""Cranial Fault Zone — FastAPI application entrypoint."""
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    crud,
    data,
    entries,
    export,
    gamification,
    good_days,
    health,
    settings,
    stats,
)
from app.db import SessionLocal, init_db
from app.seed import seed_defaults

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables (if absent) and seed default reference data once.
    init_db()
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Cranial Fault Zone", lifespan=lifespan)

# API routers.
app.include_router(health.router)
app.include_router(crud.router)
app.include_router(entries.router)
app.include_router(stats.router)
app.include_router(settings.router)
app.include_router(gamification.router)
app.include_router(good_days.router)
app.include_router(export.router)
app.include_router(data.router)

# Static SPA assets.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    # Never cache the HTML shell so versioned asset URLs always take effect and
    # layout changes show up without a manual hard refresh.
    html = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})
