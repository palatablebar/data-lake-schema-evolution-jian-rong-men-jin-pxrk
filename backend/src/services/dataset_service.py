"""表目录服务：列表 / 详情 / 版本历史 / 登记。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import DATASET_FORMAT_LABELS
from src.models.change_request import ChangeRequest
from src.models.consumer import Consumer
from src.models.dataset import Dataset
from src.models.schema_version import SchemaVersion
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc


def serialize(dataset: Dataset, *, field_count: int = 0, consumer_count: int = 0) -> dict:
    return {
        "id": dataset.id,
        "db_name": dataset.db_name,
        "table_name": dataset.table_name,
        "full_name": dataset.full_name,
        "owner": dataset.owner,
        "format": dataset.format,
        "format_label": DATASET_FORMAT_LABELS.get(dataset.format, dataset.format),
        "partition_key": dataset.partition_key,
        "current_version": dataset.current_version,
        "row_count": dataset.row_count,
        "description": dataset.description,
        "field_count": field_count,
        "consumer_count": consumer_count,
        "created_at": iso_utc(dataset.created_at),
        "updated_at": iso_utc(dataset.updated_at),
    }


def serialize_version(version: SchemaVersion) -> dict:
    return {
        "id": version.id,
        "dataset_id": version.dataset_id,
        "version": version.version,
        "fields": version.fields or [],
        "field_count": len(version.fields or []),
        "author": version.author,
        "summary": version.summary,
        "committed_at": iso_utc(version.committed_at),
    }


def list_datasets(
    db: Session,
    *,
    q: str | None = None,
    db_name: str | None = None,
    fmt: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(Dataset)
    count_stmt = select(func.count()).select_from(Dataset)
    if q:
        like = f"%{q.strip()}%"
        clause = Dataset.table_name.ilike(like) | Dataset.owner.ilike(like) | Dataset.description.ilike(like)
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    if db_name:
        stmt = stmt.where(Dataset.db_name == db_name)
        count_stmt = count_stmt.where(Dataset.db_name == db_name)
    if fmt:
        stmt = stmt.where(Dataset.format == fmt)
        count_stmt = count_stmt.where(Dataset.format == fmt)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Dataset.db_name, Dataset.table_name).limit(limit).offset(offset)).all()

    version_counts = dict(
        db.execute(select(SchemaVersion.dataset_id, func.count()).group_by(SchemaVersion.dataset_id)).all()
    )
    consumer_counts = dict(
        db.execute(select(Consumer.dataset_id, func.count()).group_by(Consumer.dataset_id)).all()
    )
    items = []
    for row in rows:
        latest = db.scalar(
            select(SchemaVersion)
            .where(SchemaVersion.dataset_id == row.id)
            .order_by(SchemaVersion.version.desc())
            .limit(1)
        )
        field_count = len(latest.fields or []) if latest else 0
        payload = serialize(row, field_count=field_count, consumer_count=consumer_counts.get(row.id, 0))
        payload["version_count"] = version_counts.get(row.id, 0)
        items.append(payload)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_dataset(db: Session, dataset_id: int) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise not_found("dataset", dataset_id)
    return dataset


def get_dataset_detail(db: Session, dataset_id: int) -> dict:
    dataset = get_dataset(db, dataset_id)
    latest = db.scalar(
        select(SchemaVersion).where(SchemaVersion.dataset_id == dataset.id).order_by(SchemaVersion.version.desc()).limit(1)
    )
    consumer_count = db.scalar(select(func.count()).select_from(Consumer).where(Consumer.dataset_id == dataset.id)) or 0
    pending = db.scalar(
        select(func.count())
        .select_from(ChangeRequest)
        .where(ChangeRequest.dataset_id == dataset.id, ChangeRequest.gate == "block")
    ) or 0
    payload = serialize(dataset, field_count=len(latest.fields or []) if latest else 0, consumer_count=consumer_count)
    payload["fields"] = latest.fields if latest else []
    payload["changes"] = db.scalar(select(func.count()).select_from(ChangeRequest).where(ChangeRequest.dataset_id == dataset.id)) or 0
    payload["blocked_changes"] = pending
    return payload


def list_versions(db: Session, dataset_id: int, limit: int = 50) -> dict:
    dataset = get_dataset(db, dataset_id)
    rows = db.scalars(
        select(SchemaVersion)
        .where(SchemaVersion.dataset_id == dataset.id)
        .order_by(SchemaVersion.version.desc())
        .limit(limit)
    ).all()
    return {"items": [serialize_version(row) for row in rows], "total": len(rows), "dataset": serialize(dataset)}


def get_version_fields(db: Session, dataset_id: int, version: int) -> list[dict]:
    row = db.scalar(
        select(SchemaVersion).where(SchemaVersion.dataset_id == dataset_id, SchemaVersion.version == version)
    )
    if row is None:
        raise AppError("NOT_FOUND", 404, {"entity": "schema_version", "dataset_id": dataset_id, "version": version})
    return row.fields or []


def current_fields(db: Session, dataset: Dataset) -> list[dict]:
    return get_version_fields(db, dataset.id, dataset.current_version)


def create_dataset(db: Session, payload: dict) -> Dataset:
    exists = db.scalar(
        select(Dataset).where(Dataset.db_name == payload["db_name"], Dataset.table_name == payload["table_name"])
    )
    if exists is not None:
        raise AppError("CONFLICT", 409, {"db_name": payload["db_name"], "table_name": payload["table_name"]})
    dataset = Dataset(
        db_name=payload["db_name"],
        table_name=payload["table_name"],
        owner=payload.get("owner") or "运联科技 · 数据平台组",
        format=payload.get("format") or "iceberg",
        partition_key=payload.get("partition_key"),
        current_version=1,
        row_count=int(payload.get("row_count") or 0),
        description=payload.get("description"),
    )
    db.add(dataset)
    db.flush()
    return dataset


def list_db_names(db: Session) -> list[str]:
    return [row for row in db.scalars(select(Dataset.db_name).distinct().order_by(Dataset.db_name)).all()]
