from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionChannel:
    session_id: str
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    active_generation: str | None = None
    generation_task: asyncio.Task | None = None

    async def subscribe(self, maxsize: int = 256) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        async with self.lock:
            self.subscribers.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    async def publish(self, event: dict[str, Any]) -> None:
        async with self.lock:
            subscribers = list(self.subscribers)
        for q in subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Slow consumer: drop and let caller disconnect it.
                try:
                    q.put_nowait({"event": "error", "data": {"code": "slow_consumer", "message": "Cliente lento"}})
                except Exception:
                    pass


_CHANNELS: dict[str, SessionChannel] = {}


def get_session_channel(session_id: str) -> SessionChannel:
    if session_id not in _CHANNELS:
        _CHANNELS[session_id] = SessionChannel(session_id=session_id)
    return _CHANNELS[session_id]


def reset_channels() -> None:
    _CHANNELS.clear()