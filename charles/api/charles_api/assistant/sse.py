from __future__ import annotations

import json
from typing import Any, AsyncIterator


def sse_format(*, data: dict[str, Any], event: str = "message") -> bytes:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


async def sse_iter(queue: "asyncio.Queue[dict[str, Any]]") -> AsyncIterator[bytes]:
    import asyncio

    while True:
        item = await queue.get()
        yield sse_format(data=item)
        if item.get("type") == "done":
            break

