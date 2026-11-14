"""Celery 任务：心跳 + 每日重跑待审变更的兼容检测（下游登记变化后判定会变）。"""
from __future__ import annotations

import time

from sqlalchemy import select

from src.config.celery_app import TASK_DAILY, TASK_HEARTBEAT, celery_app
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("tasks")


def _redis():
    import redis

    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


@celery_app.task(name=TASK_HEARTBEAT)
def heartbeat() -> str:
    try:
        _redis().set(f"{settings.app_name}:worker:heartbeat", time.time())
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat failed: %s", exc)
        return "error"


@celery_app.task(name=TASK_DAILY)
def daily_recheck() -> dict:
    """对仍待处理的变更单重跑字段级检测，兼容级别可能因下游新增引用而变化。"""
    from src.config.database import session_scope
    from src.constants.enums import PENDING_STATUSES
    from src.models.change_request import ChangeRequest
    from src.services import audit_service, change_service

    done = 0
    scheduler = "scheduler@" + settings.app_name + ".io"
    with session_scope() as db:
        pending = db.scalars(
            select(ChangeRequest).where(ChangeRequest.status.in_(PENDING_STATUSES)).order_by(ChangeRequest.id)
        ).all()
        for request in pending:
            change_service.run_checks(db, request)
            done += 1
            audit_service.record(
                db,
                actor_email=scheduler,
                actor_role="admin",
                action="change.run",
                entity="change_request",
                entity_id=request.id,
                detail={"trigger": "schedule", "code": request.code, "gate": request.gate},
                layer="worker",
            )
    logger.info("daily recheck finished: %s change requests", done)
    return {"requests": done}
