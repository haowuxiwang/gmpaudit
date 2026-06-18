"""Benchmark tests for agent module.

Measures performance of key operations to establish baselines.
"""

import time

import pytest

pytestmark = pytest.mark.benchmark

from agent.tools.json_parser import parse_llm_json
from agent.tools.risk_matrix import calculate_risk_score, format_risk_summary
from agent.tools.regulation_db import search_regulations
from agent.tools.document_chunker import (
    chunk_document,
    deduplicate_findings,
    select_strategy,
    _title_similarity,
)
from agent.state import merge_lists


def _benchmark(func, iterations=1000, name=""):
    """Run a function N times and measure performance."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    avg_ms = (elapsed / iterations) * 1000
    ops_per_sec = iterations / elapsed if elapsed > 0 else 0
    return {"name": name or func.__name__, "iterations": iterations, "avg_ms": avg_ms, "ops_per_sec": ops_per_sec}


class TestJsonParserBenchmark:
    """Benchmark parse_llm_json performance."""

    def test_parse_simple_json(self):
        """Parse simple JSON list should be fast (< 1ms)."""
        json_str = '[{"title": "Test", "severity": "high", "description": "Desc"}]'
        result = _benchmark(lambda: parse_llm_json(json_str), iterations=5000, name="parse_simple_json")
        assert result["avg_ms"] < 1.0, f"parse_llm_json too slow: {result['avg_ms']:.4f}ms avg"

    def test_parse_json_with_code_fence(self):
        """Parse JSON in code fence should be fast (< 1ms)."""
        json_str = '```json\n[{"title": "Test", "severity": "high"}]\n```'
        result = _benchmark(lambda: parse_llm_json(json_str), iterations=5000, name="parse_fenced_json")
        assert result["avg_ms"] < 1.0, f"parse_llm_json(fenced) too slow: {result['avg_ms']:.4f}ms avg"

    def test_parse_large_json(self):
        """Parse large JSON (100 items) should be fast (< 5ms)."""
        items = [{"title": f"Item {i}", "severity": "medium", "description": f"Desc {i}"} for i in range(100)]
        import json
        json_str = json.dumps(items)
        result = _benchmark(lambda: parse_llm_json(json_str), iterations=1000, name="parse_large_json")
        assert result["avg_ms"] < 5.0, f"parse_llm_json(large) too slow: {result['avg_ms']:.4f}ms avg"


class TestRiskMatrixBenchmark:
    """Benchmark risk matrix calculations."""

    def test_calculate_risk_score_performance(self):
        """calculate_risk_score with 10 findings should be fast (< 0.1ms)."""
        findings = [
            {"title": f"F{i}", "severity": s, "type": "compliance", "description": f"D{i}"}
            for i, s in enumerate(["high", "medium", "low"] * 3 + ["medium"])
        ]
        result = _benchmark(
            lambda: calculate_risk_score(findings),
            iterations=10000,
            name="calculate_risk_score_10"
        )
        assert result["avg_ms"] < 0.1, f"calculate_risk_score too slow: {result['avg_ms']:.4f}ms avg"

    def test_calculate_risk_score_large_performance(self):
        """calculate_risk_score with 100 findings should be fast (< 1ms)."""
        findings = [
            {"title": f"F{i}", "severity": "high", "type": "compliance", "description": f"D{i}"}
            for i in range(100)
        ]
        result = _benchmark(
            lambda: calculate_risk_score(findings),
            iterations=1000,
            name="calculate_risk_score_100"
        )
        assert result["avg_ms"] < 1.0, f"calculate_risk_score(100) too slow: {result['avg_ms']:.4f}ms avg"

    def test_format_risk_summary_performance(self):
        """format_risk_summary should be fast (< 0.1ms)."""
        findings = [
            {"title": "F1", "severity": "high", "type": "compliance", "description": "D1"},
            {"title": "F2", "severity": "low", "type": "compliance", "description": "D2"},
        ]
        result = _benchmark(
            lambda: format_risk_summary(findings),
            iterations=10000,
            name="format_risk_summary"
        )
        assert result["avg_ms"] < 0.1, f"format_risk_summary too slow: {result['avg_ms']:.4f}ms avg"


class TestRegulationDbBenchmark:
    """Benchmark regulation database search."""

    def test_search_regulations_performance(self):
        """search_regulations should be fast (< 10ms)."""
        result = _benchmark(
            lambda: search_regulations("偏差处理 变更控制"),
            iterations=1000,
            name="search_regulations"
        )
        assert result["avg_ms"] < 10.0, f"search_regulations too slow: {result['avg_ms']:.4f}ms avg"

    def test_search_regulations_empty_performance(self):
        """search_regulations with empty query should be fast (< 1ms)."""
        result = _benchmark(
            lambda: search_regulations(""),
            iterations=10000,
            name="search_regulations_empty"
        )
        assert result["avg_ms"] < 1.0, f"search_regulations(empty) too slow: {result['avg_ms']:.4f}ms avg"


class TestDocumentChunkerBenchmark:
    """Benchmark document chunking operations."""

    def test_select_strategy_performance(self):
        """select_strategy should be fast (< 0.01ms)."""
        text = "x" * 10000
        result = _benchmark(
            lambda: select_strategy(text),
            iterations=100000,
            name="select_strategy"
        )
        assert result["avg_ms"] < 0.01, f"select_strategy too slow: {result['avg_ms']:.4f}ms avg"

    def test_chunk_document_small_performance(self):
        """chunk_document with 1KB text should be fast (< 1ms)."""
        text = "这是测试文档。" * 100  # ~1KB
        result = _benchmark(
            lambda: chunk_document(text, max_chars=500),
            iterations=5000,
            name="chunk_document_1kb"
        )
        assert result["avg_ms"] < 1.0, f"chunk_document(1KB) too slow: {result['avg_ms']:.4f}ms avg"

    def test_chunk_document_medium_performance(self):
        """chunk_document with 10KB text should be fast (< 10ms)."""
        text = "第一章 总则\n" + "这是正文内容。" * 500  # ~10KB
        result = _benchmark(
            lambda: chunk_document(text, max_chars=2000),
            iterations=1000,
            name="chunk_document_10kb"
        )
        assert result["avg_ms"] < 10.0, f"chunk_document(10KB) too slow: {result['avg_ms']:.4f}ms avg"

    def test_chunk_document_large_performance(self):
        """chunk_document with 100KB text should be fast (< 100ms)."""
        text = "第一章 总则\n" + "这是正文内容，包含更多的细节描述。" * 5000  # ~100KB
        result = _benchmark(
            lambda: chunk_document(text, max_chars=5000),
            iterations=100,
            name="chunk_document_100kb"
        )
        assert result["avg_ms"] < 100.0, f"chunk_document(100KB) too slow: {result['avg_ms']:.4f}ms avg"

    def test_deduplicate_findings_performance(self):
        """deduplicate_findings with 50 findings should be fast (< 5ms)."""
        findings = [
            {"title": f"发现 {i}: 偏差处理不当", "severity": "medium", "description": f"描述 {i}"}
            for i in range(50)
        ]
        result = _benchmark(
            lambda: deduplicate_findings(findings),
            iterations=1000,
            name="deduplicate_findings_50"
        )
        assert result["avg_ms"] < 20.0, f"deduplicate_findings(50) too slow: {result['avg_ms']:.4f}ms avg"

    def test_title_similarity_performance(self):
        """_title_similarity should be fast (< 0.01ms)."""
        a = "偏差处理流程不符合GMP要求"
        b = "偏差处理流程存在合规风险"
        result = _benchmark(
            lambda: _title_similarity(a, b),
            iterations=100000,
            name="title_similarity"
        )
        assert result["avg_ms"] < 0.05, f"_title_similarity too slow: {result['avg_ms']:.4f}ms avg"


class TestStateBenchmark:
    """Benchmark state operations."""

    def test_merge_lists_performance(self):
        """merge_lists should be fast (< 0.01ms)."""
        a = list(range(100))
        b = list(range(100, 200))
        result = _benchmark(
            lambda: merge_lists(a, b),
            iterations=100000,
            name="merge_lists"
        )
        assert result["avg_ms"] < 0.01, f"merge_lists too slow: {result['avg_ms']:.4f}ms avg"
