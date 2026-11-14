"""下游消费方控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.models.dataset import Dataset
from src.services import audit_service, consumer_service


def list_consumers(db: Session, **filters) -> dict:
    return consumer_service.list_consumers(db, **filters)


def create_consumer(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    row = consumer_service.create_consumer(db, payload)
    dataset = db.get(Dataset, row.dataset_id)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="consumer.create",
        entity="consumer",
        entity_id=row.id,
        detail={"name": row.name, "table": dataset.full_name if dataset else None, "columns": row.columns},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return consumer_service.serialize(row, dataset)
