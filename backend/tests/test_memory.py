"""Tests for app.services.memory — audit memory JSONL persistence."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.memory import append_findings, load_memory


class TestAppendFindings:
    @pytest.mark.asyncio
    async def test_appends_jsonl_line(self, tmp_path):
        memory_file = tmp_path / "audit_memory.jsonl"
        with patch("app.services.memory.MEMORY_FILE", memory_file):
            await append_findings(1, "Task A", [{"title": "F1"}], [{"filename": "a.pdf", "risk_level": "high"}])
            content = memory_file.read_text(encoding="utf-8")
            line = json.loads(content.strip())
            assert line["task_id"] == 1
            assert line["task_name"] == "Task A"
            assert line["findings_count"] == 1
            assert "a.pdf" in line["documents"]

    @pytest.mark.asyncio
    async def test_multiple_appends(self, tmp_path):
        memory_file = tmp_path / "audit_memory.jsonl"
        with patch("app.services.memory.MEMORY_FILE", memory_file):
            await append_findings(1, "T1", [], [])
            await append_findings(2, "T2", [{"title": "F"}], [])
            lines = memory_file.read_text(encoding="utf-8").strip().split("\n")
            assert len(lines) == 2

    @pytest.mark.asyncio
    async def test_risk_levels_extracted(self, tmp_path):
        memory_file = tmp_path / "audit_memory.jsonl"
        with patch("app.services.memory.MEMORY_FILE", memory_file):
            await append_findings(1, "T", [], [
                {"filename": "a.pdf", "risk_level": "high"},
                {"filename": "b.pdf", "risk_level": "low"},
            ])
            line = json.loads(memory_file.read_text(encoding="utf-8").strip())
            assert line["risk_levels"]["a.pdf"] == "high"
            assert line["risk_levels"]["b.pdf"] == "low"


class TestLoadMemory:
    @pytest.mark.asyncio
    async def test_empty_file(self, tmp_path):
        memory_file = tmp_path / "nonexistent.jsonl"
        with patch("app.services.memory.MEMORY_FILE", memory_file):
            result = await load_memory()
            assert result == []

    @pytest.mark.asyncio
    async def test_loads_entries(self, tmp_path):
        memory_file = tmp_path / "audit_memory.jsonl"
        entries = [
            {"task_id": 1, "task_name": "T1"},
            {"task_id": 2, "task_name": "T2"},
        ]
        memory_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
        with patch("app.services.memory.MEMORY_FILE", memory_file):
            result = await load_memory()
            assert len(result) == 2
            assert result[0]["task_id"] == 1

    @pytest.mark.asyncio
    async def test_limit(self, tmp_path):
        memory_file = tmp_path / "audit_memory.jsonl"
        entries = [{"task_id": i} for i in range(10)]
        memory_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
        with patch("app.services.memory.MEMORY_FILE", memory_file):
            result = await load_memory(limit=3)
            assert len(result) == 3
            assert result[0]["task_id"] == 7  # last 3

    @pytest.mark.asyncio
    async def test_malformed_line_returns_empty(self, tmp_path):
        """load_memory wraps entire read in try/except, so one bad line causes empty result."""
        memory_file = tmp_path / "audit_memory.jsonl"
        memory_file.write_text('{"task_id": 1}\nnot json\n{"task_id": 2}\n', encoding="utf-8")
        with patch("app.services.memory.MEMORY_FILE", memory_file):
            result = await load_memory()
            assert result == []
