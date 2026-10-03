"""Assembles every router under /api (unversioned) and /api/v1 (versioned)."""

from fastapi import APIRouter

from app.api.routes_health import router as health_router

v1_router = APIRouter(prefix="/v1")

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(v1_router)
