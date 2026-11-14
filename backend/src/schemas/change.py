from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.dataset import FieldIn


class ChangeRequestIn(BaseModel):
    dataset_id: int = Field(gt=0)
    base_version: int | None = Field(default=None, ge=1)
    target_fields: list[FieldIn] = Field(min_length=1, max_length=300)
    summary: str | None = Field(default=None, max_length=2000)


class DecisionIn(BaseModel):
    action: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=1000)
