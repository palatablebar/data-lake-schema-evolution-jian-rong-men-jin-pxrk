from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import DATASET_WRITE_ROLES
from src.controllers import dataset_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.dataset import DatasetIn
from src.utils.pagination import page_params

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("")
def list_datasets(
    q: str | None = None,
    db_name: str | None = None,
    format: str | None = None,
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return dataset_controller.list_datasets(
        db, q=q, db_name=db_name, fmt=format, limit=page.limit, offset=page.offset
    )


@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: int, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))
) -> dict:
    return dataset_controller.get_dataset(db, dataset_id)


@router.get("/{dataset_id}/versions")
def list_versions(
    dataset_id: int, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))
) -> dict:
    return dataset_controller.list_versions(db, dataset_id)


@router.post("", status_code=201)
def create_dataset(
    payload: DatasetIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*DATASET_WRITE_ROLES)),
) -> dict:
    return dataset_controller.create_dataset(db, payload.model_dump(), principal, request)
