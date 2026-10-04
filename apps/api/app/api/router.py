"""Assembles every router under /api (unversioned) and /api/v1 (versioned)."""

from fastapi import APIRouter

from app.api.admin import admin_router
from app.api.routes_health import router as health_router
from app.api.routes_me import router as me_router
from app.api.routes_model import router as model_router
from app.api.routes_predictions import router as predictions_router
from app.api.routes_reference import router as reference_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(me_router)
v1_router.include_router(model_router)
v1_router.include_router(reference_router)
v1_router.include_router(predictions_router)
v1_router.include_router(admin_router)

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(v1_router)
