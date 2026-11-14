"""表目录控制器：登记表时记领域审计。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, dataset_service


def list_datasets(db: Session, **filters) -> dict:
    return dataset_service.list_datasets(db, **filters)


def get_dataset(db: Session, dataset_id: int) -> dict:
    return dataset_service.get_dataset_detail(db, dataset_id)


def list_versions(db: Session, dataset_id: int) -> dict:
    return dataset_service.list_versions(db, dataset_id)


def create_dataset(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    dataset = dataset_service.create_dataset(db, payload)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="dataset.create",
        entity="dataset",
        entity_id=dataset.id,
        detail={"table": dataset.full_name, "format": dataset.format},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return dataset_service.serialize(dataset)
