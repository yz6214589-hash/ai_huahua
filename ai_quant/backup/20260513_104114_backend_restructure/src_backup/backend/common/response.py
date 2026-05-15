from __future__ import annotations

from typing import Any


OK_CODE = 0
VALIDATION_ERROR_CODE = 40001
UNAUTHORIZED_CODE = 40100
FORBIDDEN_CODE = 40300
NOT_FOUND_CODE = 40400
RATE_LIMITED_CODE = 42900
INTERNAL_ERROR_CODE = 50000


def is_enveloped(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return "success" in payload and "code" in payload and "message" in payload and "data" in payload


def ok(data: Any = None, message: str = "ok", *, request_id: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"success": True, "code": OK_CODE, "message": message, "data": data}
    if request_id:
        out["requestId"] = request_id
    return out


def fail(
    code: int,
    message: str,
    *,
    data: Any = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"success": False, "code": int(code), "message": message, "data": data}
    if request_id:
        out["requestId"] = request_id
    return out

