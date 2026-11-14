"""附加实体 2：CompatCheck（一次检测在「字段级」的判定结果）。自然键 = (request_id, field)。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class CompatCheck(Base):
    __tablename__ = "compat_checks"
    __table_args__ = (UniqueConstraint("request_id", "field", name="uq_compat_checks_request_field"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("change_requests.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(120))
    change_type: Mapped[str] = mapped_column(String(30), default="add_column", index=True)
    breaking: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
