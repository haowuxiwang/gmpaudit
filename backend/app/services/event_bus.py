"""In-memory pub/sub event bus for SSE streaming.

Replaces DB-polling SSE with push-based event delivery.
TaskRunner publishes events, SSE endpoints subscribe per connection.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Max queue size per SSE connection. Slow consumers get events dropped.
_QUEUE_MAXSIZE = 256


class _DoneSentinel:
    """Marker object pushed to signal task completion."""


DONE_SENTINEL = _DoneSentinel()


class EventBus:
    """Per-task, per-connection fan-out event bus.

    Architecture:
        TaskRunner.publish(task_id, event)
            -> pushes to all Queue objects registered for that task_id
            -> each SSE connection owns one Queue
    """

    DONE_SENTINEL = DONE_SENTINEL

    def __init__(self) -> None:
        self._subscribers: dict[int, list[asyncio.Queue[Any]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, task_id: int) -> asyncio.Queue[Any]:
        """Create a queue for a new SSE connection and register it."""
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        async with self._lock:
            self._subscribers.setdefault(task_id, []).append(queue)
        logger.debug("SSE subscriber added for task %d (total: %d)", task_id, len(self._subscribers.get(task_id, [])))
        return queue

    async def unsubscribe(self, task_id: int, queue: asyncio.Queue[Any]) -> None:
        """Remove a queue when the SSE connection closes."""
        async with self._lock:
            queues = self._subscribers.get(task_id, [])
            if queue in queues:
                queues.remove(queue)
            if not queues:
                self._subscribers.pop(task_id, None)
        logger.debug("SSE subscriber removed for task %d", task_id)

    async def publish(self, task_id: int, event: dict[str, Any]) -> None:
        """Push event to all subscribers for task_id. Non-blocking."""
        async with self._lock:
            queues = list(self._subscribers.get(task_id, []))

        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("SSE queue full for task %d, dropping event", task_id)

    async def publish_done(self, task_id: int, status: str) -> None:
        """Push terminal event and DONE sentinel to all subscribers."""
        await self.publish(task_id, {"type": "done", "status": status})
        async with self._lock:
            queues = list(self._subscribers.get(task_id, []))
        for q in queues:
            try:
                q.put_nowait(DONE_SENTINEL)
            except asyncio.QueueFull:
                pass
