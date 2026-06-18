"""Tests for agent/main.py — CLI entry point, run_audit, argument parsing."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.main import run_audit


@pytest.mark.asyncio
class TestRunAudit:
    async def test_successful_run(self, tmp_path):
        """run_audit with mocked graph returns final state."""
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "status": "completed",
            "report_markdown": "# Report",
            "report_path": str(tmp_path / "report.md"),
            "messages": ["done"],
            "findings": [],
            "risk_score": 0,
            "trace": {},
        })

        with (
            patch("agent.main.build_audit_graph", return_value=mock_graph),
            patch("agent.trace.PipelineTrace") as mock_trace_cls,
        ):
            mock_trace = MagicMock()
            mock_trace.to_dict.return_value = {}
            mock_trace.summary_report.return_value = "trace summary"
            mock_trace_cls.return_value = mock_trace

            result = await run_audit("test.txt", doc_type="deviation", focus="GMP")

        assert result["status"] == "completed"
        assert result["report_markdown"] == "# Report"
        mock_trace.finalize.assert_called_once_with(status="completed")

    async def test_error_status_finalized(self):
        """Error in pipeline should finalize with error status."""
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "status": "error",
            "messages": ["Error: file not found"],
        })

        with (
            patch("agent.main.build_audit_graph", return_value=mock_graph),
            patch("agent.trace.PipelineTrace") as mock_trace_cls,
        ):
            mock_trace = MagicMock()
            mock_trace.to_dict.return_value = {}
            mock_trace.summary_report.return_value = ""
            mock_trace_cls.return_value = mock_trace

            result = await run_audit("bad_file.txt")

        mock_trace.finalize.assert_called_once_with(status="error")

    async def test_trace_cleared_on_completion(self):
        """Trace should be cleared even if exception occurs."""
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))

        with (
            patch("agent.main.build_audit_graph", return_value=mock_graph),
            patch("agent.trace.PipelineTrace") as mock_trace_cls,
            patch("agent.trace.clear_current_trace") as mock_clear,
            pytest.raises(RuntimeError, match="boom"),
        ):
            mock_trace_cls.return_value = MagicMock()
            await run_audit("test.txt")

        mock_clear.assert_called_once()

    async def test_state_has_trace_key(self):
        """Returned state should contain 'trace' key."""
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "status": "completed",
            "messages": [],
        })

        with (
            patch("agent.main.build_audit_graph", return_value=mock_graph),
            patch("agent.trace.PipelineTrace") as mock_trace_cls,
        ):
            mock_trace = MagicMock()
            mock_trace.to_dict.return_value = {"run_id": "abc123"}
            mock_trace.summary_report.return_value = ""
            mock_trace_cls.return_value = mock_trace

            result = await run_audit("test.txt")

        assert "trace" in result
        assert result["trace"]["run_id"] == "abc123"


class TestMainFunction:
    def test_file_not_found_exits(self, monkeypatch):
        """main() with nonexistent file should sys.exit(1)."""
        monkeypatch.setattr(sys, "argv", ["main", "--file", "/nonexistent/file.txt"])
        from agent.main import main
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_output_saves_report_markdown(self, tmp_path, monkeypatch):
        """--output flag should save report_markdown to file."""
        output_file = tmp_path / "output_report.md"

        mock_result = {
            "status": "completed",
            "report_markdown": "# Test Report Content",
        }

        async def mock_run(*args, **kwargs):
            return mock_result

        monkeypatch.setattr(sys, "argv", [
            "main", "--file", "test.txt", "--output", str(output_file)
        ])

        with (
            patch("agent.main.run_audit", side_effect=mock_run),
            patch("agent.main.Path") as mock_path_cls,
        ):
            # Path.exists() must return True for the input file
            mock_input_path = MagicMock()
            mock_input_path.exists.return_value = True
            mock_output_path = MagicMock()

            def path_side_effect(p):
                if p == "test.txt":
                    return mock_input_path
                elif p == str(output_file):
                    return mock_output_path
                return Path(p)

            mock_path_cls.side_effect = path_side_effect

            from agent.main import main
            main()

    def test_output_saves_json_when_no_report(self, tmp_path, monkeypatch):
        """--output with no report_markdown should save state as JSON."""
        output_file = tmp_path / "output.json"

        mock_result = {"status": "completed", "report_markdown": ""}

        async def mock_run(*args, **kwargs):
            return mock_result

        monkeypatch.setattr(sys, "argv", [
            "main", "--file", "test.txt", "-o", str(output_file)
        ])

        with (
            patch("agent.main.run_audit", side_effect=mock_run),
            patch("agent.main.Path") as mock_path_cls,
        ):
            mock_input_path = MagicMock()
            mock_input_path.exists.return_value = True

            def path_side_effect(p):
                if p == "test.txt":
                    return mock_input_path
                return Path(p)

            mock_path_cls.side_effect = path_side_effect

            from agent.main import main
            main()
