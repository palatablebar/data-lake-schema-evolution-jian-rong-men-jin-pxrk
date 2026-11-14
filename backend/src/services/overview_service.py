"""总览：表数、待审变更、破坏性占比、门禁/风险分布、近 7 天提交趋势、worker 心跳。"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import (
    CHANGE_STATUS_LABELS,
    COMPAT_LABELS,
    RISK_LABELS,
    RISK_ORDER,
    Gate,
    PENDING_STATUSES,
)
from src.models.change_request import ChangeRequest
from src.models.compat_check import CompatCheck
from src.models.consumer import Consumer
from src.models.dataset import Dataset
from src.models.schema_version import SchemaVersion
from src.utils.timeutil import iso_utc, local_now, utcnow


def worker_alive() -> bool:
    try:
        import redis
        import time

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
        value = client.get(f"{settings.app_name}:worker:heartbeat")
        return bool(value) and (time.time() - float(value)) < 120
    except Exception:
        return False


def _distribution(rows: list[tuple[str, int]], labels: dict[str, str], order: list[str] | None = None) -> list[dict]:
    payload = [{"key": key, "label": labels.get(key, key), "count": count} for key, count in rows]
    if order:
        payload.sort(key=lambda item: order.index(item["key"]) if item["key"] in order else 99)
    else:
        payload.sort(key=lambda item: -item["count"])
    return payload


def overview(db: Session) -> dict:
    datasets_total = db.scalar(select(func.count()).select_from(Dataset)) or 0
    versions_total = db.scalar(select(func.count()).select_from(SchemaVersion)) or 0
    consumers_total = db.scalar(select(func.count()).select_from(Consumer)) or 0
    changes_total = db.scalar(select(func.count()).select_from(ChangeRequest)) or 0
    checks_total = db.scalar(select(func.count()).select_from(CompatCheck)) or 0
    checks_breaking = db.scalar(select(func.count()).select_from(CompatCheck).where(CompatCheck.breaking.is_(True))) or 0
    pending = db.scalar(
        select(func.count()).select_from(ChangeRequest).where(ChangeRequest.status.in_(PENDING_STATUSES))
    ) or 0
    breaking = db.scalar(
        select(func.count()).select_from(ChangeRequest).where(ChangeRequest.compat == "breaking")
    ) or 0
    blocked = db.scalar(
        select(func.count()).select_from(ChangeRequest).where(ChangeRequest.gate == Gate.BLOCK.value)
    ) or 0

    compat_rows = db.execute(select(ChangeRequest.compat, func.count()).group_by(ChangeRequest.compat)).all()
    risk_rows = db.execute(select(ChangeRequest.risk, func.count()).group_by(ChangeRequest.risk)).all()
    status_rows = db.execute(select(ChangeRequest.status, func.count()).group_by(ChangeRequest.status)).all()

    recent = db.scalars(select(ChangeRequest).order_by(ChangeRequest.id.desc()).limit(6)).all()
    datasets = {row.id: row for row in db.scalars(select(Dataset)).all()}

    since = utcnow() - timedelta(days=7)
    week_rows = db.scalars(select(ChangeRequest).where(ChangeRequest.created_at >= since)).all()
    today = local_now().date()
    trend = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        count = sum(
            1
            for row in week_rows
            if row.created_at
            and (row.created_at + timedelta(minutes=settings.app_timezone_offset_minutes)).date() == day
        )
        trend.append({"date": day.isoformat(), "changes": count})

    top_consumers = db.execute(
        select(Consumer.team, func.count()).group_by(Consumer.team).order_by(func.count().desc()).limit(6)
    ).all()

    return {
        "datasets_total": datasets_total,
        "versions_total": versions_total,
        "consumers_total": consumers_total,
        "changes_total": changes_total,
        "checks_total": checks_total,
        "checks_breaking": checks_breaking,
        "pending_total": pending,
        "blocked_total": blocked,
        "breaking_total": breaking,
        "breaking_ratio": round(breaking / changes_total, 4) if changes_total else 0.0,
        "worker_alive": worker_alive(),
        "compat": _distribution(compat_rows, COMPAT_LABELS),
        "risk": _distribution(risk_rows, RISK_LABELS, RISK_ORDER),
        "status": _distribution(status_rows, CHANGE_STATUS_LABELS),
        "teams": [{"key": team, "label": team, "count": count} for team, count in top_consumers],
        "trend": trend,
        "recent_changes": [
            {
                "id": row.id,
                "code": row.code,
                "dataset_name": datasets[row.dataset_id].full_name if row.dataset_id in datasets else None,
                "compat": row.compat,
                "compat_label": COMPAT_LABELS.get(row.compat, row.compat),
                "gate": row.gate,
                "risk": row.risk,
                "risk_label": RISK_LABELS.get(row.risk, row.risk),
                "status": row.status,
                "status_label": CHANGE_STATUS_LABELS.get(row.status, row.status),
                "affected_tasks": int((row.impact or {}).get("task_count") or 0),
                "created_at": iso_utc(row.created_at),
            }
            for row in recent
        ],
    }
