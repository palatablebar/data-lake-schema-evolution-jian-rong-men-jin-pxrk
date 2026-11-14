"""领域实体 3：ChangeRequest（一次表结构变更申请，含 diff / 兼容判定 / 门禁 / 迁移单）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    base_version: Mapped[int] = mapped_column(Integer, default=1)
    target_fields: Mapped[list] = mapped_column(JSON, default=list)
    diff: Mapped[list] = mapped_column(JSON, default=list)
    impact: Mapped[dict] = mapped_column(JSON, default=dict)
    compat: Mapped[str] = mapped_column(String(20), default="backward", index=True)
    risk: Mapped[str] = mapped_column(String(20), default="low", index=True)
    gate: Mapped[str] = mapped_column(String(10), default="pass", index=True)
    status: Mapped[str] = mapped_column(String(20), default="submitted", index=True)
    migration_sql: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(160), default="system")
    decided_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
