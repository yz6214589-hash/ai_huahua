from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ApiError(Exception):
    code: int
    message: str
    http_status: int = 400
    details: Any | None = None

    def __str__(self) -> str:
        return self.message

