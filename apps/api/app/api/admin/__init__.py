"""Routes reserved to administrators (/api/v1/admin/*).

`require_admin` is declared ONCE on the router: every route added below is guarded without anyone
having to remember it, and the guard runs before any path, query or body validation (SEC-02).
"""

from fastapi import APIRouter, Depends

from app.api.admin.routes_audit import router as audit_router
from app.api.admin.routes_users import router as users_router
from app.api.deps import require_admin

admin_router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
admin_router.include_router(users_router)
admin_router.include_router(audit_router)
