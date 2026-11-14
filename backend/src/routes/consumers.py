from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import CONSUMER_WRITE_ROLES
from src.controllers import consumer_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.consumer import ConsumerIn
from src.services import consumer_service
from src.utils.pagination import page_params

router = APIRouter(prefix="/consumers", tags=["consumers"])


@router.get("")
def list_consumers(
    dataset_id: int | None = None,
    team: str | None = None,
    q: str | None = None,
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    payload = consumer_controller.list_consumers(
        db, dataset_id=dataset_id, team=team, q=q, limit=page.limit, offset=page.offset
    )
    payload["teams"] = consumer_service.teams(db)
    return payload


@router.post("", status_code=201)
def create_consumer(
    payload: ConsumerIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*CONSUMER_WRITE_ROLES)),
) -> dict:
    return consumer_controller.create_consumer(db, payload.model_dump(), principal, request)
