"""字段级检测结果控制器。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.services import check_service


def list_checks(db: Session, **filters) -> dict:
    return check_service.list_checks(db, **filters)


def summary(db: Session) -> dict:
    return check_service.summary(db)
