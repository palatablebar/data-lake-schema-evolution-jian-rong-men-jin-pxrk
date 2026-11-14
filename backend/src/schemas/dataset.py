from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DatasetIn(BaseModel):
    db_name: str = Field(min_length=2, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    table_name: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    owner: str | None = Field(default=None, max_length=80)
    format: Literal["iceberg", "hudi", "delta", "parquet"] = "iceberg"
    partition_key: str | None = Field(default=None, max_length=120)
    row_count: int = Field(default=0, ge=0)
    description: str | None = Field(default=None, max_length=2000)


class FieldIn(BaseModel):
    """一个字段定义（表结构快照 / 变更目标结构共用）。"""

    name: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    type: str = Field(min_length=1, max_length=40)
    nullable: bool = True
    default: str | int | float | bool | None = None
    comment: str | None = Field(default=None, max_length=200)
