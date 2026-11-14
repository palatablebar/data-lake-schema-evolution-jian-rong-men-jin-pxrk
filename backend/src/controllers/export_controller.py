"""导出控制器：CSV / SQL 响应 + 审计。"""
from __future__ import annotations

from fastapi import Request, Response
from sqlalchemy.orm import Session

from src.services import audit_service, export_service
from src.utils.csv_export import csv_response_headers


def checks_csv(db: Session, request_id: int | None, principal: dict, request: Request) -> Response:
    content = export_service.checks_csv(db, request_id)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="export.checks",
        entity="compat_check",
        entity_id=request_id,
        detail={"bytes": len(content)},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return Response(content=content, media_type="text/csv; charset=utf-8", headers=csv_response_headers("checks.csv"))


def migration_sql(db: Session, request_id: int, principal: dict, request: Request) -> Response:
    content, filename = export_service.migration_sql(db, request_id)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="export.migration",
        entity="change_request",
        entity_id=request_id,
        detail={"bytes": len(content.encode("utf-8")), "filename": filename},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return Response(
        content=content.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
