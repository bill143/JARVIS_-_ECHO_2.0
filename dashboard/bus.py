"""In-process event bus + state snapshot for the JARVIS dashboard.

Pipeline taps and tools ``publish()`` small JSON-able events; every connected
WebSocket gets its own queue. A rolling snapshot (status, config, transcript,
last thing seen) lets a freshly opened window render the current state at once.

``publish`` is safe to call from any thread: it hops onto the bus's event loop.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any

TRANSCRIPT_LIMIT = 200
SUBSCRIBER_QUEUE_LIMIT = 500
TRANSCRIPT_TYPES = frozenset({"heard", "user", "reply", "tool", "error", "seen"})


class EventBus:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue] = set()
        self._transcript: deque[dict[str, Any]] = deque(maxlen=TRANSCRIPT_LIMIT)
        self._state: dict[str, Any] = {
            "status": "starting",
            "muted": False,
            "config": {},
            "health": {},
            "last_seen": None,
        }

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop or asyncio.get_running_loop()

    def snapshot(self) -> dict[str, Any]:
        return {**self._state, "transcript": list(self._transcript)}

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def publish(self, event_type: str, **data: Any) -> None:
        event = {"type": event_type, "ts": time.time(), **data}
        loop = self._loop
        if loop is not None and loop.is_running():
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            if running is not loop:
                loop.call_soon_threadsafe(self._dispatch, event)
                return
        self._dispatch(event)

    def _dispatch(self, event: dict[str, Any]) -> None:
        self._apply(event)
        for queue in list(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()  # drop the oldest; a slow window must not stall JARVIS
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)

    def _apply(self, event: dict[str, Any]) -> None:
        kind = event["type"]
        if kind == "status":
            self._state["status"] = event["state"]
        elif kind == "muted":
            self._state["muted"] = bool(event["muted"])
        elif kind == "config":
            self._state["config"] = {**self._state["config"], **event.get("config", {})}
        elif kind == "health":
            self._state["health"] = event.get("services", {})
        elif kind == "seen":
            self._state["last_seen"] = {k: event.get(k) for k in ("source", "description", "image", "ts", "error")}
        if kind in TRANSCRIPT_TYPES:
            entry = {k: v for k, v in event.items() if k != "image"}  # keep the transcript light
            self._transcript.append(entry)

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_LIMIT)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)
