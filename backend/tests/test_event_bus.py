"""Tests for app.services.event_bus — in-memory pub/sub event bus."""

import asyncio

import pytest

from app.services.event_bus import _QUEUE_MAXSIZE, _STALE_TTL, DONE_SENTINEL, EventBus, _DoneSentinel


class TestConstants:
    def test_queue_maxsize(self):
        assert _QUEUE_MAXSIZE == 256

    def test_stale_ttl(self):
        assert _STALE_TTL == 600

    def test_done_sentinel_type(self):
        assert isinstance(DONE_SENTINEL, _DoneSentinel)


class TestSubscribe:
    @pytest.mark.asyncio
    async def test_returns_queue(self):
        bus = EventBus()
        q = await bus.subscribe(1)
        assert isinstance(q, asyncio.Queue)
        assert q.maxsize == _QUEUE_MAXSIZE

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_task(self):
        bus = EventBus()
        q1 = await bus.subscribe(1)
        q2 = await bus.subscribe(1)
        assert q1 is not q2
        assert len(bus._subscribers[1]) == 2

    @pytest.mark.asyncio
    async def test_different_tasks(self):
        bus = EventBus()
        await bus.subscribe(1)
        await bus.subscribe(2)
        assert 1 in bus._subscribers
        assert 2 in bus._subscribers


class TestUnsubscribe:
    @pytest.mark.asyncio
    async def test_removes_queue(self):
        bus = EventBus()
        q = await bus.subscribe(1)
        await bus.unsubscribe(1, q)
        assert 1 not in bus._subscribers

    @pytest.mark.asyncio
    async def test_keeps_other_queues(self):
        bus = EventBus()
        q1 = await bus.subscribe(1)
        q2 = await bus.subscribe(1)
        await bus.unsubscribe(1, q1)
        assert len(bus._subscribers[1]) == 1
        assert bus._subscribers[1][0] is q2

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent(self):
        bus = EventBus()
        q = asyncio.Queue()
        await bus.unsubscribe(999, q)  # should not raise

    @pytest.mark.asyncio
    async def test_cleans_last_activity(self):
        bus = EventBus()
        q = await bus.subscribe(1)
        assert 1 in bus._last_activity
        await bus.unsubscribe(1, q)
        assert 1 not in bus._last_activity


class TestPublish:
    @pytest.mark.asyncio
    async def test_delivers_to_all_subscribers(self):
        bus = EventBus()
        q1 = await bus.subscribe(1)
        q2 = await bus.subscribe(1)
        event = {"type": "progress", "value": 50}
        await bus.publish(1, event)
        assert q1.get_nowait() is event
        assert q2.get_nowait() is event

    @pytest.mark.asyncio
    async def test_no_subscribers_no_error(self):
        bus = EventBus()
        await bus.publish(999, {"type": "test"})  # should not raise

    @pytest.mark.asyncio
    async def test_queue_full_drops_event(self):
        bus = EventBus()
        q = await bus.subscribe(1)
        # Fill the queue
        for i in range(_QUEUE_MAXSIZE):
            q.put_nowait({"i": i})
        assert q.full()
        # This should be dropped silently
        await bus.publish(1, {"type": "dropped"})
        assert bus._dropped_count == 1
        # Queue still has original items
        assert q.qsize() == _QUEUE_MAXSIZE

    @pytest.mark.asyncio
    async def test_updates_last_activity(self):
        bus = EventBus()
        await bus.subscribe(1)
        old_time = bus._last_activity[1]
        await asyncio.sleep(0.01)
        await bus.publish(1, {"type": "test"})
        assert bus._last_activity[1] >= old_time


class TestPublishDone:
    @pytest.mark.asyncio
    async def test_sends_done_event_and_sentinel(self):
        bus = EventBus()
        q = await bus.subscribe(1)
        await bus.publish_done(1, "completed")
        event = q.get_nowait()
        assert event["type"] == "done"
        assert event["status"] == "completed"
        sentinel = q.get_nowait()
        assert sentinel is DONE_SENTINEL

    @pytest.mark.asyncio
    async def test_drains_full_queue(self):
        bus = EventBus()
        q = await bus.subscribe(1)
        # Fill queue completely
        for i in range(_QUEUE_MAXSIZE):
            q.put_nowait({"i": i})
        assert q.full()
        await bus.publish_done(1, "completed")
        # Should have drained and pushed done + sentinel
        items = []
        while not q.empty():
            items.append(q.get_nowait())
        assert len(items) == 2
        assert items[0]["type"] == "done"
        assert items[1] is DONE_SENTINEL

    @pytest.mark.asyncio
    async def test_multiple_subscribers_all_receive(self):
        bus = EventBus()
        q1 = await bus.subscribe(1)
        q2 = await bus.subscribe(1)
        await bus.publish_done(1, "failed")
        for q in [q1, q2]:
            event = q.get_nowait()
            assert event["type"] == "done"
            assert event["status"] == "failed"
            sentinel = q.get_nowait()
            assert sentinel is DONE_SENTINEL


class TestCleanupStale:
    @pytest.mark.asyncio
    async def test_removes_old_entries(self, monkeypatch):
        bus = EventBus()
        await bus.subscribe(1)
        # Simulate old activity
        bus._last_activity[1] = 0.0
        # Mock time.monotonic to return a time > _STALE_TTL
        monkeypatch.setattr("app.services.event_bus.time.monotonic", lambda: _STALE_TTL + 1)
        # Remove subscriber first (cleanup only works on entries without subscribers)
        bus._subscribers.pop(1, None)
        removed = await bus.cleanup_stale()
        assert removed == 1
        assert 1 not in bus._last_activity

    @pytest.mark.asyncio
    async def test_keeps_active_entries(self, monkeypatch):
        bus = EventBus()
        await bus.subscribe(1)
        bus._last_activity[1] = 0.0
        monkeypatch.setattr("app.services.event_bus.time.monotonic", lambda: _STALE_TTL + 1)
        # Still has subscriber, should NOT be removed
        removed = await bus.cleanup_stale()
        assert removed == 0
        assert 1 in bus._subscribers

    @pytest.mark.asyncio
    async def test_keeps_recent_entries(self, monkeypatch):
        bus = EventBus()
        await bus.subscribe(1)
        bus._subscribers.pop(1, None)
        bus._last_activity[1] = 100.0
        monkeypatch.setattr("app.services.event_bus.time.monotonic", lambda: 100.0 + _STALE_TTL - 1)
        removed = await bus.cleanup_stale()
        assert removed == 0

    @pytest.mark.asyncio
    async def test_cleanup_stale_empty_bus(self):
        """cleanup_stale on an empty bus returns 0."""
        bus = EventBus()
        removed = await bus.cleanup_stale()
        assert removed == 0

    @pytest.mark.asyncio
    async def test_cleanup_stale_removes_multiple(self, monkeypatch):
        """Multiple stale entries are all removed."""
        bus = EventBus()
        await bus.subscribe(1)
        await bus.subscribe(2)
        await bus.subscribe(3)
        # Remove all subscribers so they become eligible for cleanup
        bus._subscribers.clear()
        bus._last_activity[1] = 0.0
        bus._last_activity[2] = 0.0
        bus._last_activity[3] = 0.0
        monkeypatch.setattr("app.services.event_bus.time.monotonic", lambda: _STALE_TTL + 100)
        removed = await bus.cleanup_stale()
        assert removed == 3
        assert len(bus._last_activity) == 0

    @pytest.mark.asyncio
    async def test_cleanup_stale_mixed_fresh_and_stale(self, monkeypatch):
        """Only stale entries are removed; fresh ones are kept."""
        bus = EventBus()
        await bus.subscribe(1)
        await bus.subscribe(2)
        bus._subscribers.clear()
        bus._last_activity[1] = 0.0  # stale
        bus._last_activity[2] = _STALE_TTL + 100  # fresh (set to current time)
        monkeypatch.setattr("app.services.event_bus.time.monotonic", lambda: _STALE_TTL + 100)
        removed = await bus.cleanup_stale()
        assert removed == 1
        assert 2 in bus._last_activity
        assert 1 not in bus._last_activity


class TestPublishDoneEdgeCases:
    @pytest.mark.asyncio
    async def test_publish_done_no_subscribers(self):
        """publish_done with no subscribers does not raise."""
        bus = EventBus()
        await bus.publish_done(999, "completed")  # should not raise

    @pytest.mark.asyncio
    async def test_publish_done_sentinel_push_fails(self):
        """When queue is still full after drain, sentinel push logs warning."""
        bus = EventBus()
        q = await bus.subscribe(1)
        # Make queue appear full, but drain leaves it empty
        # Fill queue, then drain should empty it
        for i in range(_QUEUE_MAXSIZE):
            q.put_nowait({"i": i})
        assert q.full()
        # publish_done should drain and push done + sentinel
        await bus.publish_done(1, "completed")
        items = []
        while not q.empty():
            items.append(q.get_nowait())
        assert len(items) == 2
        assert items[0]["type"] == "done"
        assert items[1] is DONE_SENTINEL


class TestEventBusClassAttributes:
    def test_class_has_done_sentinel(self):
        assert EventBus.DONE_SENTINEL is DONE_SENTINEL


class TestPublishDroppedCount:
    @pytest.mark.asyncio
    async def test_multiple_drops_increment_count(self):
        """Multiple dropped events increment _dropped_count correctly."""
        bus = EventBus()
        q = await bus.subscribe(1)
        for i in range(_QUEUE_MAXSIZE):
            q.put_nowait({"i": i})
        # Drop 15 events
        for i in range(15):
            await bus.publish(1, {"type": "dropped", "i": i})
        assert bus._dropped_count == 15
