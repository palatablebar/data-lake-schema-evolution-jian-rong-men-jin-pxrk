from __future__ import annotations

from pydantic import BaseModel, Field


class ConsumerIn(BaseModel):
    dataset_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=120)
    team: str = Field(min_length=1, max_length=80)
    owner: str | None = Field(default=None, max_length=120)
    columns: list[str] = Field(default_factory=list, max_length=200)
    tasks: list[str] = Field(default_factory=list, max_length=100)
    reports: list[str] = Field(default_factory=list, max_length=100)
    refresh_cron: str | None = Field(default=None, max_length=40)
