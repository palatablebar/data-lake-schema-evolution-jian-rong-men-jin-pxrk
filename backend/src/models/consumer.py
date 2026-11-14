"""附加实体 1：Consumer（下游消费方：任务 + 报表引用了哪些列）。自然键 = (dataset_id, name)。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Consumer(Base):
    __tablename__ = "consumers"
    __table_args__ = (UniqueConstraint("dataset_id", "name", name="uq_consumers_dataset_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    team: Mapped[str] = mapped_column(String(80), index=True)
    owner: Mapped[str] = mapped_column(String(120), default="")
    # 引用的列名列表（算法 B 的影响传播按它算）
    columns: Mapped[list] = mapped_column(JSON, default=list)
    # 该消费方名下的调度任务名与报表名（任务/报表计数由引用列推出，不是写死的数）
    tasks: Mapped[list] = mapped_column(JSON, default=list)
    reports: Mapped[list] = mapped_column(JSON, default=list)
    refresh_cron: Mapped[str] = mapped_column(String(40), default="0 3 * * *")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
