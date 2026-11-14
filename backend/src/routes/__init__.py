"""路由聚合：统一 /api 前缀（Nginx 反代时剥掉 /api）。"""
from fastapi import APIRouter

from src.routes.audit import router as audit_router
from src.routes.auth import router as auth_router
from src.routes.changes import router as changes_router
from src.routes.checks import router as checks_router
from src.routes.consumers import router as consumers_router
from src.routes.datasets import router as datasets_router
from src.routes.exports import router as exports_router
from src.routes.health import router as health_router
from src.routes.overview import router as overview_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(overview_router)
api_router.include_router(datasets_router)
api_router.include_router(changes_router)
api_router.include_router(consumers_router)
api_router.include_router(checks_router)
api_router.include_router(exports_router)
api_router.include_router(audit_router)
