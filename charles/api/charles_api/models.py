from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DataSource(str, Enum):
    qmt = "qmt"
    tushare = "tushare"
    akshare = "akshare"
    qwen_search = "qwen_search"
    file = "file"
    unknown = "unknown"


class JobDomain(str, Enum):
    stock_daily = "stock_daily"
    stock_financial = "stock_financial"
    stock_news = "stock_news"
    macro_indicator = "macro_indicator"
    rate_daily = "rate_daily"
    report_consensus = "report_consensus"
    calendar = "calendar"
    catalyst = "catalyst"


class JobRunRequest(BaseModel):
    domain: JobDomain
    mode: str | None = Field(default=None, description="test/full")
    params: dict[str, Any] | None = None


class JobRunResult(BaseModel):
    runId: str
    domain: JobDomain
    startedAt: str
    finishedAt: str | None = None
    status: str
    dataSourceFinal: DataSource
    fallbackChain: list[DataSource]
    rowsWritten: int
    itemsProcessed: int
    failedItems: list[str]
    message: str | None = None


class ExportRequest(BaseModel):
    dataset: str
    format: str
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int | None = None

