"""领域实体 2：SchemaVersion（一次已提交的表结构快照）。自然键 = (dataset_id, version)。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class SchemaVersion(Base):
    __tablename__ = "schema_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version", name="uq_schema_versions_dataset_version"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    fields: Mapped[list] = mapped_column(JSON, default=list)
    author: Mapped[str] = mapped_column(String(160), default="data@yunlian.io")
    summary: Mapped[str] = mapped_column(Text, default="")
    committed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
