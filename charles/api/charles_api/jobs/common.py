from __future__ import annotations

from dataclasses import dataclass

from ..models import DataSource


@dataclass
class JobStats:
    items_processed: int
    rows_written: int
    failed_items: list[str]
    data_source_final: DataSource
    fallback_chain: list[DataSource]
    message: str | None = None

