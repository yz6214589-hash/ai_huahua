from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class WsHub:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._by_channel: dict[str, set[WebSocket]] = {}

    async def connect(self, channel: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._by_channel.setdefault(channel, set()).add(ws)

    async def disconnect(self, channel: str, ws: WebSocket) -> None:
        async with self._lock:
            s = self._by_channel.get(channel)
            if not s:
                return
            s.discard(ws)
            if not s:
                self._by_channel.pop(channel, None)

    async def broadcast(self, channel: str, payload: Any) -> None:
        async with self._lock:
            targets = list(self._by_channel.get(channel, set()))
        if not targets:
            return
        msg = json.dumps(payload, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                s = self._by_channel.get(channel)
                if not s:
                    return
                for ws in dead:
                    s.discard(ws)
                if not s:
                    self._by_channel.pop(channel, None)

