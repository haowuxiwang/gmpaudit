"""Tests for task_runner pure functions (no DB or async dependencies)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.services.task_runner import (
    _build_node_summary,
    _utcnow,
    append_event,
    build_aggregate_report,
    choose_report_content,
    get_execution_meta,
    set_execution_meta,
    set_stage,
    validate_findings,
)


def _make_task(config=None):
    """Create a mock AuditTask with configurable config."""
    task = MagicMock()
    task.config = config
    task.id = 1
    task.task_name = "Test Task"
    return task


class TestUtcnow:
    def test_returns_iso_format(self):
        result = _utcnow()
        # Should be parseable as ISO format
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo == UTC

    def test_returns_utc(self):
        result = _utcnow()
        assert "+00:00" in result or result.endswith("Z") or "UTC" in result


class TestGetExecutionMeta:
    def test_none_config_returns_defaults(self):
        task = _make_task(config=None)
        meta = get_execution_meta(task)
        assert meta["stage"] == "pending"
        assert meta["events"] == []
        assert meta["started_at"] is None
        assert meta["completed_at"] is None
        assert meta["error"] is None

    def test_custom_execution_overrides_defaults(self):
        task = _make_task(config={"execution": {"stage": "running", "started_at": "2024-01-01T00:00:00Z"}})
        meta = get_execution_meta(task)
        assert meta["stage"] == "running"
        assert meta["started_at"] == "2024-01-01T00:00:00Z"

    def test_events_are_copies(self):
        original_events = [{"time": "t", "stage": "s", "level": "info", "message": "m"}]
        task = _make_task(config={"execution": {"events": original_events}})
        meta = get_execution_meta(task)
        meta["events"].append({"time": "t2", "stage": "s2", "level": "warn", "message": "m2"})
        assert len(original_events) == 1  # original not modified

    def test_documents_are_copies(self):
        original_docs = ["doc1.pdf"]
        task = _make_task(config={"execution": {"documents": original_docs}})
        meta = get_execution_meta(task)
        meta["documents"].append("doc2.pdf")
        assert len(original_docs) == 1


class TestSetExecutionMeta:
    def test_nests_under_execution_key(self):
        task = _make_task(config=None)
        meta = {"stage": "running", "events": []}
        set_execution_meta(task, meta)
        assert task.config["execution"] is meta

    def test_preserves_other_config_keys(self):
        task = _make_task(config={"other_key": "value"})
        meta = {"stage": "running"}
        set_execution_meta(task, meta)
        assert task.config["other_key"] == "value"
        assert task.config["execution"] is meta


class TestAppendEvent:
    def test_event_structure(self):
        task = _make_task()
        meta = append_event(task, "test message")
        events = meta["events"]
        assert len(events) == 1
        event = events[0]
        assert event["message"] == "test message"
        assert event["level"] == "info"
        assert "time" in event

    def test_stage_override(self):
        task = _make_task()
        meta = append_event(task, "msg", stage="running")
        assert meta["stage"] == "running"

    def test_level_parameter(self):
        task = _make_task()
        meta = append_event(task, "msg", level="warning")
        assert meta["events"][0]["level"] == "warning"

    def test_multiple_events_accumulate(self):
        task = _make_task()
        append_event(task, "first")
        meta = append_event(task, "second")
        assert len(meta["events"]) == 2


class TestSetStage:
    def test_sets_stage(self):
        task = _make_task()
        meta = set_stage(task, "running")
        assert meta["stage"] == "running"

    def test_sets_started_at_on_running(self):
        task = _make_task()
        meta = set_stage(task, "running")
        assert meta["started_at"] is not None

    def test_started_at_set_only_once(self):
        task = _make_task(config={"execution": {"started_at": "2024-01-01T00:00:00Z"}})
        meta = set_stage(task, "running")
        assert meta["started_at"] == "2024-01-01T00:00:00Z"

    def test_completed_at_on_completed(self):
        task = _make_task()
        meta = set_stage(task, "completed")
        assert meta["completed_at"] is not None

    def test_completed_at_on_failed(self):
        task = _make_task()
        meta = set_stage(task, "failed")
        assert meta["completed_at"] is not None

    def test_error_parameter(self):
        task = _make_task()
        meta = set_stage(task, "failed", error="something broke")
        assert meta["error"] == "something broke"

    def test_no_completed_at_on_running(self):
        task = _make_task()
        meta = set_stage(task, "running")
        assert meta["completed_at"] is None


class TestBuildAggregateReport:
    def test_empty_findings(self):
        result = build_aggregate_report(
            "Test Task", [{"filename": "a.pdf", "status": "ok", "findings_count": 0, "risk_level": "low"}], []
        )
        assert "未发现审计问题" in result
        assert "Test Task" in result

    def test_multiple_documents(self):
        docs = [
            {"filename": "a.pdf", "status": "ok", "findings_count": 1, "risk_level": "medium"},
            {"filename": "b.pdf", "status": "ok", "findings_count": 2, "risk_level": "high"},
        ]
        findings = [
            {"severity": "high", "title": "Issue 1", "description": "Desc 1", "document_id": 1},
        ]
        result = build_aggregate_report("Multi Doc", docs, findings)
        assert "文档数量: 2" in result
        assert "a.pdf" in result
        assert "b.pdf" in result
        assert "Issue 1" in result

    def test_formatting_correctness(self):
        findings = [{"severity": "high", "title": "Title", "description": "Desc", "document_id": 1}]
        result = build_aggregate_report("T", [], findings)
        assert "# 审计报告 - T" in result
        assert "## 审计发现" in result
        assert "[HIGH] Title" in result


class TestChooseReportContent:
    def test_single_doc_with_agent_report(self):
        reports = ["Agent report content"]
        content, meta = choose_report_content("T", [{"filename": "a.pdf"}], [], reports)
        assert content == "Agent report content"
        assert meta["report_source"] == "agent_report_writer"
        assert meta["report_mode"] == "single_document"

    def test_multi_doc_aggregate(self):
        docs = [
            {"filename": "a.pdf", "status": "ok", "findings_count": 1, "risk_level": "medium"},
            {"filename": "b.pdf", "status": "ok", "findings_count": 2, "risk_level": "high"},
        ]
        findings = [{"severity": "high", "title": "T", "description": "D", "document_id": 1}]
        content, meta = choose_report_content("T", docs, findings, ["", ""])
        assert "审计报告" in content
        assert meta["report_source"] == "task_runner_aggregate"
        assert meta["report_mode"] == "multi_document"

    def test_fallback_detection(self):
        reports = ["Agent report"]
        sources = ["fallback"]
        content, meta = choose_report_content("T", [{"filename": "a.pdf"}], [], reports, sources)
        assert meta["report_source"] == "fallback"
        assert meta["report_mode"] == "degraded"

    def test_empty_agent_reports_uses_aggregate(self):
        content, meta = choose_report_content(
            "T", [{"filename": "a.pdf", "status": "ok", "findings_count": 0, "risk_level": "low"}], [], []
        )
        assert meta["report_source"] == "task_runner_aggregate"


class TestBuildNodeSummary:
    def test_regulation_expert_lightrag(self):
        output = {"matched_regulations": [{"r": 1}, {"r": 2}], "regulation_summary": "from lightrag"}
        result = _build_node_summary("regulation_expert", output)
        assert "知识图谱" in result
        assert "2 条" in result

    def test_regulation_expert_fallback(self):
        output = {"matched_regulations": [{"r": 1}], "regulation_summary": "from fallback_db"}
        result = _build_node_summary("regulation_expert", output)
        assert "内置法规库" in result

    def test_risk_assessor(self):
        output = {"findings": [{"f": 1}], "risk_level": "high"}
        result = _build_node_summary("risk_assessor", output)
        assert "1 个问题" in result
        assert "high" in result

    def test_report_writer_with_path(self):
        output = {"report_path": "/path/to/report.md"}
        result = _build_node_summary("report_writer", output)
        assert "审计报告生成完成" in result

    def test_report_writer_without_path(self):
        output = {"report_path": ""}
        result = _build_node_summary("report_writer", output)
        assert "备用模板" in result

    def test_parse_doc(self):
        output = {"document_name": "test.pdf", "document_type": "pdf"}
        result = _build_node_summary("parse_doc", output)
        assert "test.pdf" in result
        assert "pdf" in result

    def test_unknown_node(self):
        result = _build_node_summary("unknown_node", {})
        assert "unknown_node" in result


class TestValidateFindings:
    def test_valid_finding_preserved(self):
        findings = [{"title": "Issue", "description": "A real issue found"}]
        result = validate_findings(findings)
        assert len(result) == 1

    def test_missing_title_dropped(self):
        findings = [{"description": "No title here"}]
        result = validate_findings(findings)
        assert len(result) == 0

    def test_missing_description_dropped(self):
        findings = [{"title": "Has title but no desc"}]
        result = validate_findings(findings)
        assert len(result) == 0

    def test_untitled_finding_dropped(self):
        findings = [{"title": "Untitled finding", "description": "Some description"}]
        result = validate_findings(findings)
        assert len(result) == 0

    def test_short_description_dropped(self):
        findings = [{"title": "Title", "description": "x"}]
        result = validate_findings(findings)
        assert len(result) == 0

    def test_mixed_valid_and_invalid(self):
        findings = [
            {"title": "Valid", "description": "Real description here"},
            {"title": "", "description": "No title"},
            {"title": "No desc"},
            {"title": "Untitled finding", "description": "Has desc"},
            {"title": "Short", "description": "x"},
        ]
        result = validate_findings(findings)
        assert len(result) == 1
        assert result[0]["title"] == "Valid"

    def test_empty_list(self):
        result = validate_findings([])
        assert result == []
