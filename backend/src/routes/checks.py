from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import check_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.utils.pagination import page_params

router = APIRouter(prefix="/compat-checks", tags=["compat_checks"])


@router.get("")
def list_checks(
    request_id: int | None = None,
    change_type: str | None = None,
    breaking: bool | None = None,
    limit: int = Query(50),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    payload = check_controller.list_checks(
        db,
        request_id=request_id,
        change_type=change_type,
        breaking=breaking,
        limit=page.limit,
        offset=page.offset,
    )
    payload["summary"] = check_controller.summary(db)
    return payload
