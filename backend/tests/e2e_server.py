"""Playwright-only isolated application; never used by production startup."""

import os
from pathlib import Path

from fastapi.staticfiles import StaticFiles

database_path = Path(__file__).resolve().parents[2] / "playwright-e2e.db"
database_path.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"

from app.db import models_core, models_generation, models_memory, models_role
from app.db.session import Base
from app.main import create_app


app = create_app()
Base.metadata.create_all(app.state.engine)
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
