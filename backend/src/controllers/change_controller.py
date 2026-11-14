"""变更申请控制器：提交 / 检测 / 审批，每一步都留领域审计。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants.limits import MAX_FIELDS_PER_REQUEST
from src.services import audit_service, change_service
from src.utils.errors import AppError

MAX_TARGET_FIELDS = MAX_FIELDS_PER_REQUEST


def list_changes(db: Session, **filters) -> dict:
    return change_service.list_changes(db, **filters)


def get_change(db: Session, request_id: int) -> dict:
    return change_service.get_change_detail(db, request_id)


def create_change(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    target_fields = payload.get("target_fields") or []
    if len(target_fields) > MAX_TARGET_FIELDS:
        raise AppError("VALIDATION", 422, {"message": f"字段数不能超过 {MAX_TARGET_FIELDS}"})
    row = change_service.create_change_request(db, payload, author=principal["email"])
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="change.create",
        entity="change_request",
        entity_id=row.id,
        detail={
            "code": row.code,
            "compat": row.compat,
            "gate": row.gate,
            "risk": row.risk,
            "affected_tasks": int((row.impact or {}).get("task_count") or 0),
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return change_service.get_change_detail(db, row.id)


def run_checks(db: Session, request_id: int, principal: dict, request: Request) -> dict:
    row = change_service.get_change(db, request_id)
    result = change_service.run_checks(db, row)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="change.run",
        entity="change_request",
        entity_id=row.id,
        detail={"code": row.code, "checks": result["checks"], "compat": row.compat, "gate": row.gate},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return change_service.get_change_detail(db, row.id)


def decide(db: Session, request_id: int, payload: dict, principal: dict, request: Request) -> dict:
    row = change_service.get_change(db, request_id)
    gate_before = row.gate
    change_service.decide(
        db,
        row,
        action=payload["action"],
        actor=principal["email"],
        note=payload.get("note"),
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="change.approve" if payload["action"] == "approve" else "change.reject",
        entity="change_request",
        entity_id=row.id,
        detail={
            "code": row.code,
            "gate_before": gate_before,
            "status": row.status,
            "override": bool(gate_before == "block" and payload["action"] == "approve"),
            "note": row.decision_note,
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return change_service.get_change_detail(db, row.id)
