"""Benchmark tests for backend services.

Measures performance of key operations to establish baselines
for production readiness. Uses manual timing.
"""

import asyncio
import time

import pytest

pytestmark = pytest.mark.benchmark

from app.services.event_bus import EventBus
from app.services.task_runner import (
    _utcnow,
    append_event,
    build_aggregate_report,
    get_execution_meta,
    set_stage,
    validate_findings,
)
from app.utils.file_utils import get_file_type


def _make_task(config=None):
    """Create a mock AuditTask."""
    from unittest.mock import MagicMock
    task = MagicMock()
    task.config = config
    task.id = 1
    task.task_name = "Benchmark Task"
    return task


class BenchmarkResult:
    """Simple benchmark result container."""
    def __init__(self, name: str, iterations: int, total_time: float):
        self.name = name
        self.iterations = iterations
        self.total_time = total_time
        self.avg_ms = (total_time / iterations) * 1000 if iterations > 0 else 0
        self.ops_per_sec = iterations / total_time if total_time > 0 else 0


def _benchmark(func, iterations=1000, name=""):
    """Run a function N times and measure performance."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    return BenchmarkResult(name or func.__name__, iterations, elapsed)


class TestBackendBenchmarks:
    """Performance benchmarks for backend pure functions."""

    def test_utcnow_performance(self):
        """_utcnow() should be fast (< 0.01ms per call)."""
        result = _benchmark(_utcnow, iterations=10000, name="utcnow")
        assert result.avg_ms < 0.01, f"utcnow too slow: {result.avg_ms:.4f}ms avg"

    def test_get_execution_meta_performance(self):
        """get_execution_meta() should be fast (< 0.05ms per call)."""
        task = _make_task()
        result = _benchmark(lambda: get_execution_meta(task), iterations=5000, name="get_execution_meta")
        assert result.avg_ms < 0.05, f"get_execution_meta too slow: {result.avg_ms:.4f}ms avg"

    def test_set_stage_performance(self):
        """set_stage() should be fast (< 0.1ms per call)."""
        task = _make_task()
        result = _benchmark(lambda: set_stage(task, "running"), iterations=5000, name="set_stage")
        assert result.avg_ms < 0.1, f"set_stage too slow: {result.avg_ms:.4f}ms avg"

    def test_append_event_performance(self):
        """append_event() should be fast (< 0.1ms per call)."""
        task = _make_task()
        result = _benchmark(lambda: append_event(task, "test event"), iterations=5000, name="append_event")
        assert result.avg_ms < 0.1, f"append_event too slow: {result.avg_ms:.4f}ms avg"

    def test_validate_findings_performance(self):
        """validate_findings() with 100 findings should be fast (< 1ms)."""
        findings = [
            {"title": f"Finding {i}", "description": f"Description {i}", "severity": "medium"}
            for i in range(100)
        ]
        result = _benchmark(lambda: validate_findings(findings), iterations=1000, name="validate_findings_100")
        assert result.avg_ms < 1.0, f"validate_findings(100) too slow: {result.avg_ms:.4f}ms avg"

    def test_validate_findings_large_performance(self):
        """validate_findings() with 1000 findings should be fast (< 10ms)."""
        findings = [
            {"title": f"Finding {i}", "description": f"Description {i}", "severity": "high"}
            for i in range(1000)
        ]
        result = _benchmark(lambda: validate_findings(findings), iterations=100, name="validate_findings_1000")
        assert result.avg_ms < 10.0, f"validate_findings(1000) too slow: {result.avg_ms:.4f}ms avg"

    def test_build_aggregate_report_performance(self):
        """build_aggregate_report() with 10 docs should be fast (< 5ms)."""
        docs = [
            {"filename": f"doc_{i}.pdf", "status": "ok", "findings_count": i, "risk_level": "medium"}
            for i in range(10)
        ]
        findings = [
            {"severity": "high", "title": f"Finding {i}", "description": f"Desc {i}", "document_id": i}
            for i in range(10)
        ]
        result = _benchmark(
            lambda: build_aggregate_report("Benchmark", docs, findings),
            iterations=1000,
            name="build_aggregate_report_10docs"
        )
        assert result.avg_ms < 5.0, f"build_aggregate_report too slow: {result.avg_ms:.4f}ms avg"

    def test_get_file_type_performance(self):
        """get_file_type() should be fast (< 0.2ms per batch of 5)."""
        filenames = ["test.pdf", "doc.docx", "image.jpg", "text.txt", "unknown.xyz"]
        result = _benchmark(
            lambda: [get_file_type(f) for f in filenames],
            iterations=10000,
            name="get_file_type_batch"
        )
        assert result.avg_ms < 0.2, f"get_file_type batch too slow: {result.avg_ms:.4f}ms avg"


@pytest.mark.asyncio
class TestEventBusBenchmarks:
    """Performance benchmarks for EventBus operations."""

    async def test_publish_performance(self):
        """publish() to 1 subscriber should be fast (< 0.1ms)."""
        bus = EventBus()
        await bus.subscribe(1)

        async def publish_one():
            await bus.publish(1, {"type": "test", "data": "benchmark"})

        start = time.perf_counter()
        for _ in range(5000):
            await publish_one()
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 5000) * 1000
        assert avg_ms < 0.1, f"publish too slow: {avg_ms:.4f}ms avg"

    async def test_publish_multi_subscriber_performance(self):
        """publish() to 10 subscribers should be fast (< 1ms)."""
        bus = EventBus()
        for i in range(10):
            await bus.subscribe(1)

        async def publish_one():
            await bus.publish(1, {"type": "test", "data": "benchmark"})

        start = time.perf_counter()
        for _ in range(1000):
            await publish_one()
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 1.0, f"publish(10 subs) too slow: {avg_ms:.4f}ms avg"

    async def test_subscribe_unsubscribe_performance(self):
        """subscribe+unsubscribe cycle should be fast (< 0.1ms)."""
        bus = EventBus()

        async def cycle():
            q = await bus.subscribe(1)
            await bus.unsubscribe(1, q)

        start = time.perf_counter()
        for _ in range(5000):
            await cycle()
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 5000) * 1000
        assert avg_ms < 0.1, f"subscribe/unsubscribe too slow: {avg_ms:.4f}ms avg"

    async def test_concurrent_publish_performance(self):
        """Concurrent publishes should not deadlock."""
        bus = EventBus()
        await bus.subscribe(1)

        async def publish_many():
            for i in range(100):
                await bus.publish(1, {"type": "test", "i": i})

        start = time.perf_counter()
        await asyncio.gather(*[publish_many() for _ in range(10)])
        elapsed = time.perf_counter() - start
        # 10 goroutines * 100 publishes = 1000 total, should complete in < 1s
        assert elapsed < 1.0, f"Concurrent publish too slow: {elapsed:.2f}s"
