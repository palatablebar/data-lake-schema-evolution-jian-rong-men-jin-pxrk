"""变更申请服务：提交 → 算 diff（算法 A）→ 兼容判定与影响传播（算法 B）→ 检测落 CompatCheck → 审批放行。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import (
    CHANGE_STATUS_LABELS,
    CHANGE_TYPE_LABELS,
    DATASET_FORMAT_LABELS,
    COMPAT_LABELS,
    GATE_LABELS,
    PENDING_STATUSES,
    RISK_LABELS,
    ChangeStatus,
    Compat,
)
from src.constants.limits import MAX_FIELDS_PER_REQUEST
from src.models.change_request import ChangeRequest
from src.models.compat_check import CompatCheck
from src.models.consumer import Consumer
from src.models.dataset import Dataset
from src.models.schema_version import SchemaVersion
from src.services import compat_engine, schema_diff
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc, local_now, utcnow


def serialize(request: ChangeRequest, dataset: Dataset | None = None) -> dict:
    impact = request.impact or {}
    return {
        "id": request.id,
        "code": request.code,
        "dataset_id": request.dataset_id,
        "dataset_name": dataset.full_name if dataset else None,
        "db_name": dataset.db_name if dataset else None,
        "table_name": dataset.table_name if dataset else None,
        "format": dataset.format if dataset else None,
        "base_version": request.base_version,
        "target_fields": request.target_fields or [],
        "diff": request.diff or [],
        "impact": impact,
        "compat": request.compat,
        "compat_label": COMPAT_LABELS.get(request.compat, request.compat),
        "risk": request.risk,
        "risk_label": RISK_LABELS.get(request.risk, request.risk),
        "gate": request.gate,
        "gate_label": GATE_LABELS.get(request.gate, request.gate),
        "status": request.status,
        "status_label": CHANGE_STATUS_LABELS.get(request.status, request.status),
        "migration_sql": request.migration_sql or "",
        "summary": request.summary,
        "author": request.author,
        "decided_by": request.decided_by,
        "decision_note": request.decision_note,
        "decided_at": iso_utc(request.decided_at),
        "checked_at": iso_utc(request.checked_at),
        "created_at": iso_utc(request.created_at),
        "breaking_count": sum(1 for item in (request.diff or []) if item.get("breaking")),
        "diff_count": len(request.diff or []),
        "affected_tasks": int(impact.get("task_count") or 0),
        "affected_reports": int(impact.get("report_count") or 0),
        "affected_consumers": int(impact.get("consumer_count") or 0),
    }


def next_code(db: Session) -> str:
    prefix = f"CR-{local_now():%Y%m%d}"
    count = db.scalar(select(func.count()).select_from(ChangeRequest).where(ChangeRequest.code.like(f"{prefix}%"))) or 0
    return f"{prefix}-{count + 1:04d}"


def dataset_dict(dataset: Dataset) -> dict:
    return {
        "id": dataset.id,
        "db_name": dataset.db_name,
        "table_name": dataset.table_name,
        "format": dataset.format,
        "format_label": DATASET_FORMAT_LABELS.get(dataset.format, dataset.format),
    }


def _consumers_of(db: Session, dataset_id: int) -> list[dict]:
    rows = db.scalars(select(Consumer).where(Consumer.dataset_id == dataset_id).order_by(Consumer.name)).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "team": row.team,
            "owner": row.owner,
            "columns": row.columns or [],
            "tasks": row.tasks or [],
            "reports": row.reports or [],
        }
        for row in rows
    ]


def analyze(
    db: Session,
    *,
    dataset: Dataset,
    base_fields: list[dict],
    target_fields: list[dict],
    code: str,
    base_version: int,
) -> dict:
    """纯计算部分：diff + 兼容判定 + 影响传播 + 迁移单。"""
    if len(target_fields or []) > MAX_FIELDS_PER_REQUEST:
        raise AppError("VALIDATION", 422, {"message": f"字段数超过上限 {MAX_FIELDS_PER_REQUEST}"})
    diff = schema_diff.diff_fields(base_fields, target_fields)
    result = compat_engine.evaluate(
        code=code,
        dataset=dataset_dict(dataset),
        base_version=base_version,
        diff=diff,
        consumers=_consumers_of(db, dataset.id),
    )
    return {"diff": diff, **result}


def create_change_request(db: Session, payload: dict, author: str) -> ChangeRequest:
    dataset = db.get(Dataset, payload["dataset_id"])
    if dataset is None:
        raise not_found("dataset", payload["dataset_id"])
    base_version = int(payload.get("base_version") or dataset.current_version)
    base_fields = _base_fields(db, dataset.id, base_version)
    code = next_code(db)
    result = analyze(
        db,
        dataset=dataset,
        base_fields=base_fields,
        target_fields=payload["target_fields"],
        code=code,
        base_version=base_version,
    )
    request = ChangeRequest(
        code=code,
        dataset_id=dataset.id,
        base_version=base_version,
        target_fields=payload["target_fields"],
        diff=result["diff"],
        impact=result["impact"],
        compat=result["compat"],
        risk=result["risk"],
        gate=result["gate"],
        status=ChangeStatus.SUBMITTED.value,
        migration_sql=result["migration_sql"],
        summary=payload.get("summary") or "",
        author=author,
    )
    db.add(request)
    db.flush()
    return request


def _base_fields(db: Session, dataset_id: int, version: int) -> list[dict]:
    row = db.scalar(select(SchemaVersion).where(SchemaVersion.dataset_id == dataset_id, SchemaVersion.version == version))
    if row is None:
        raise AppError("NOT_FOUND", 404, {"entity": "schema_version", "dataset_id": dataset_id, "version": version})
    return row.fields or []


def list_changes(
    db: Session,
    *,
    dataset_id: int | None = None,
    status: str | None = None,
    compat: str | None = None,
    gate: str | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(ChangeRequest)
    count_stmt = select(func.count()).select_from(ChangeRequest)
    filters = []
    if dataset_id:
        filters.append(ChangeRequest.dataset_id == dataset_id)
    if status:
        filters.append(ChangeRequest.status == status)
    if compat:
        filters.append(ChangeRequest.compat == compat)
    if gate:
        filters.append(ChangeRequest.gate == gate)
    if q:
        like = f"%{q.strip()}%"
        filters.append(ChangeRequest.code.ilike(like) | ChangeRequest.summary.ilike(like))
    for clause in filters:
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(ChangeRequest.id.desc()).limit(limit).offset(offset)).all()
    datasets = {row.id: row for row in db.scalars(select(Dataset)).all()}
    return {
        "items": [serialize(row, datasets.get(row.dataset_id)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_change(db: Session, request_id: int) -> ChangeRequest:
    request = db.get(ChangeRequest, request_id)
    if request is None:
        raise not_found("change_request", request_id)
    return request


def get_change_detail(db: Session, request_id: int) -> dict:
    request = get_change(db, request_id)
    dataset = db.get(Dataset, request.dataset_id)
    payload = serialize(request, dataset)
    checks = db.scalars(
        select(CompatCheck).where(CompatCheck.request_id == request.id).order_by(CompatCheck.id)
    ).all()
    payload["checks"] = [serialize_check(row) for row in checks]
    payload["base_fields"] = _base_fields(db, request.dataset_id, request.base_version)
    return payload


def run_checks(db: Session, request: ChangeRequest) -> dict:
    """重跑一次字段级检测：按最新下游登记与最新兼容判定刷新 CompatCheck。"""
    dataset = db.get(Dataset, request.dataset_id)
    if dataset is None:
        raise not_found("dataset", request.dataset_id)
    base_fields = _base_fields(db, request.dataset_id, request.base_version)
    result = analyze(
        db,
        dataset=dataset,
        base_fields=base_fields,
        target_fields=request.target_fields or [],
        code=request.code,
        base_version=request.base_version,
    )
    request.diff = result["diff"]
    request.impact = result["impact"]
    request.compat = result["compat"]
    request.risk = result["risk"]
    request.gate = result["gate"]
    request.migration_sql = result["migration_sql"]
    request.status = ChangeStatus.CHECKED.value
    request.checked_at = utcnow()

    existing = {
        row.field: row
        for row in db.scalars(select(CompatCheck).where(CompatCheck.request_id == request.id)).all()
    }
    for item in result["diff"]:
        row = existing.pop(item["field"], None)
        if row is None:
            row = CompatCheck(request_id=request.id, field=item["field"])
            db.add(row)
        row.change_type = item["change_type"]
        row.breaking = bool(item["breaking"])
        row.detail = item["detail"]
    for stale in existing.values():
        db.delete(stale)
    db.flush()
    return {"request": request, "checks": len(result["diff"])}


def decide(
    db: Session,
    request: ChangeRequest,
    *,
    action: str,
    actor: str,
    note: str | None,
) -> ChangeRequest:
    """放行 / 驳回。放行破坏性变更必须给出 override 理由（写进审计与迁移单）。"""
    if action not in {"approve", "reject"}:
        raise AppError("VALIDATION", 422, {"action": action})
    if request.status in {ChangeStatus.APPROVED.value, ChangeStatus.REJECTED.value}:
        raise AppError("CONFLICT", 409, {"status": request.status})
    if action == "approve" and request.gate == "block" and not (note or "").strip():
        raise AppError(
            "VALIDATION",
            422,
            {"reason": "gate=block 的破坏性变更必须填写放行理由", "gate": request.gate},
        )
    request.status = ChangeStatus.APPROVED.value if action == "approve" else ChangeStatus.REJECTED.value
    request.decided_by = actor
    request.decision_note = (note or "").strip() or None
    request.decided_at = utcnow()
    db.flush()
    return request


def serialize_check(row: CompatCheck) -> dict:
    return {
        "id": row.id,
        "request_id": row.request_id,
        "field": row.field,
        "change_type": row.change_type,
        "change_type_label": CHANGE_TYPE_LABELS.get(row.change_type, row.change_type),
        "breaking": bool(row.breaking),
        "detail": row.detail,
        "created_at": iso_utc(row.created_at),
    }


def pending_count(db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(ChangeRequest).where(ChangeRequest.status.in_(PENDING_STATUSES))
    ) or 0


def breaking_count(db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(ChangeRequest).where(ChangeRequest.compat == Compat.BREAKING.value)
    ) or 0
