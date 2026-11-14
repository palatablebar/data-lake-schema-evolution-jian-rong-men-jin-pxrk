from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import CHANGE_APPROVE_ROLES, CHANGE_CREATE_ROLES, CHANGE_RUN_ROLES
from src.controllers import change_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.change import ChangeRequestIn, DecisionIn
from src.utils.pagination import page_params

router = APIRouter(prefix="/change-requests", tags=["change_requests"])


@router.get("")
def list_changes(
    dataset_id: int | None = None,
    status: str | None = None,
    compat: str | None = None,
    gate: str | None = None,
    q: str | None = None,
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return change_controller.list_changes(
        db,
        dataset_id=dataset_id,
        status=status,
        compat=compat,
        gate=gate,
        q=q,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{request_id}")
def get_change(
    request_id: int, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))
) -> dict:
    return change_controller.get_change(db, request_id)


@router.post("", status_code=201)
def create_change(
    payload: ChangeRequestIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*CHANGE_CREATE_ROLES)),
) -> dict:
    return change_controller.create_change(db, payload.model_dump(), principal, request)


@router.post("/{request_id}/run")
def run_checks(
    request_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*CHANGE_RUN_ROLES)),
) -> dict:
    return change_controller.run_checks(db, request_id, principal, request)


@router.post("/{request_id}/decision")
def decide(
    request_id: int,
    payload: DecisionIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*CHANGE_APPROVE_ROLES)),
) -> dict:
    return change_controller.decide(db, request_id, payload.model_dump(), principal, request)
