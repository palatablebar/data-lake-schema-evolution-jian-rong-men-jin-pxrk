"""领域实体 1：Dataset（湖仓一张表）。业务自然键 = (db_name, table_name)。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("db_name", "table_name", name="uq_datasets_natural_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    db_name: Mapped[str] = mapped_column(String(40), index=True)
    table_name: Mapped[str] = mapped_column(String(80), index=True)
    owner: Mapped[str] = mapped_column(String(80), default="运联科技 · 数据平台组")
    format: Mapped[str] = mapped_column(String(20), default="iceberg", index=True)
    partition_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    @property
    def full_name(self) -> str:
        return f"{self.db_name}.{self.table_name}"
