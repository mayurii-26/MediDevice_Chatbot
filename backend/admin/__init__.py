# admin package — exposes the FastAPI APIRouter for inclusion in app.py
from .routes import admin_router

__all__ = ["admin_router"]
