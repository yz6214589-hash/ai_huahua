from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ReportModel(str, Enum):
    qwen_max = "qwen-max"
    deepseek = "deepseek"


class ReportTaskStatus(str, Enum):
    waiting = "waiting"
    running = "running"
    success = "success"
    failed = "failed"


class ReportTaskCreateRequest(BaseModel):
    model: ReportModel
    stock_codes: list[str] = Field(min_length=1)


class ReportTask(BaseModel):
    task_id: str
    model: ReportModel
    stock_codes: list[str]
    stock_names: list[str] = Field(default_factory=list)
    status: ReportTaskStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None

