"""字段级兼容检测结果：列表 / 统计。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import CHANGE_TYPE_LABELS
from src.models.change_request import ChangeRequest
from src.models.compat_check import CompatCheck
from src.models.dataset import Dataset
from src.services.change_service import serialize_check
from src.utils.timeutil import iso_utc


def list_checks(
    db: Session,
    *,
    request_id: int | None = None,
    change_type: str | None = None,
    breaking: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(CompatCheck)
    count_stmt = select(func.count()).select_from(CompatCheck)
    filters = []
    if request_id:
        filters.append(CompatCheck.request_id == request_id)
    if change_type:
        filters.append(CompatCheck.change_type == change_type)
    if breaking is not None:
        filters.append(CompatCheck.breaking.is_(breaking))
    for clause in filters:
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(CompatCheck.id).limit(limit).offset(offset)).all()
    requests = {row.id: row for row in db.scalars(select(ChangeRequest)).all()}
    datasets = {row.id: row for row in db.scalars(select(Dataset)).all()}
    items = []
    for row in rows:
        payload = serialize_check(row)
        request = requests.get(row.request_id)
        dataset = datasets.get(request.dataset_id) if request else None
        payload["request_code"] = request.code if request else None
        payload["dataset_name"] = dataset.full_name if dataset else None
        payload["compat"] = request.compat if request else None
        payload["gate"] = request.gate if request else None
        items.append(payload)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def summary(db: Session) -> dict:
    rows = db.execute(
        select(CompatCheck.change_type, CompatCheck.breaking, func.count()).group_by(
            CompatCheck.change_type, CompatCheck.breaking
        )
    ).all()
    by_type = {
        key: {"key": key, "label": CHANGE_TYPE_LABELS.get(key, key), "count": 0, "breaking": 0}
        for key in CHANGE_TYPE_LABELS
    }
    for change_type, breaking, count in rows:
        bucket = by_type.setdefault(
            change_type, {"key": change_type, "label": CHANGE_TYPE_LABELS.get(change_type, change_type), "count": 0, "breaking": 0}
        )
        bucket["count"] += count
        if breaking:
            bucket["breaking"] += count
    total = db.scalar(select(func.count()).select_from(CompatCheck)) or 0
    breaking_total = db.scalar(select(func.count()).select_from(CompatCheck).where(CompatCheck.breaking.is_(True))) or 0
    return {
        "total": total,
        "breaking": breaking_total,
        "safe": total - breaking_total,
        "by_type": sorted(by_type.values(), key=lambda item: -item["count"]),
    }
