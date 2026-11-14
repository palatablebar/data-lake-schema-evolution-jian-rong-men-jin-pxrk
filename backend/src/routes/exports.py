from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import EXPORT_ROLES
from src.controllers import export_controller
from src.middlewares.rbac import require_roles

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/checks.csv")
def checks_csv(
    request: Request,
    request_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*EXPORT_ROLES)),
):
    return export_controller.checks_csv(db, request_id, principal, request)


@router.get("/migrations/{request_id}.sql")
def migration_sql(
    request_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*EXPORT_ROLES)),
):
    return export_controller.migration_sql(db, request_id, principal, request)
