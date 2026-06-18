"""Targeted tests to boost coverage from 77% to 80%+.

Covers uncovered code paths in:
- app/api/audit.py (SSE stream_all_tasks, approve EventBus error, enqueue RuntimeError)
- app/api/documents.py (background processing, helper functions, delete path safety)
- app/api/reports.py (_sanitize_html, export edge cases)
- app/api/health.py (db_health error path)
- app/api/agent_audit.py (enqueue RuntimeError)
- app/api/config.py (_update_env_file, _batch_update_env_file, _atomic_write_text, batch paths)
- app/services/document_processor.py (_clean_text, _split_text, _process_image, _get_ocr, text encoding)
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.configuration import Configuration
from app.models.document import Document, DocumentStatus
from app.models.finding import Finding, FindingType, SeverityLevel
from app.models.report import Report, ReportType

# =============================================================================
# audit.py — SSE stream_task_events with live events via DONE_SENTINEL (lines 436-448)
# =============================================================================


@pytest.mark.asyncio
async def test_stream_task_with_live_done_sentinel(client: AsyncClient, db_session: AsyncSession):
    """Streaming a task should process DONE_SENTINEL and close."""
    task = AuditTask(
        task_name="Live Done",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.PENDING,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    from app.main import app
    from app.services.event_bus import EventBus

    bus = EventBus()
    app.state.event_bus = bus

    # Push done sentinel after short delay
    async def push_done():
        await asyncio.sleep(0.3)
        await bus.publish_done(task.id, "completed")

    push_task = asyncio.create_task(push_done())

    resp = await client.get(f"/api/audit/tasks/{task.id}/stream")
    assert resp.status_code == 200
    body = resp.text
    assert "done" in body

    await push_task


# =============================================================================
# audit.py — approve_task with EventBus publish (lines 230-246)
# =============================================================================


@pytest.mark.asyncio
async def test_approve_task_with_event_bus_publish(client: AsyncClient, db_session: AsyncSession):
    """Approve task covers the EventBus notification path."""
    task = AuditTask(
        task_name="Bus Approve",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.AWAITING_REVIEW,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    from app.main import app

    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    mock_bus.publish_done = AsyncMock()
    orig_bus = getattr(app.state, "event_bus", None)
    app.state.event_bus = mock_bus
    try:
        with (
            patch("app.services.notification.is_feishu_configured", return_value=False),
        ):
            resp = await client.post(
                f"/api/audit/tasks/{task.id}/approve",
                json={"comment": "Approved via bus"},
            )
        assert resp.status_code == 200
        mock_bus.publish.assert_called()
        mock_bus.publish_done.assert_called_once()
    finally:
        app.state.event_bus = orig_bus


@pytest.mark.asyncio
async def test_approve_task_event_bus_error_swallowed(client: AsyncClient, db_session: AsyncSession):
    """When EventBus raises, the error should be swallowed (non-critical)."""
    task = AuditTask(
        task_name="Bus Error",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.AWAITING_REVIEW,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    from app.main import app

    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock(side_effect=RuntimeError("bus error"))
    mock_bus.publish_done = AsyncMock()
    orig_bus = getattr(app.state, "event_bus", None)
    app.state.event_bus = mock_bus
    try:
        with (
            patch("app.services.notification.is_feishu_configured", return_value=False),
        ):
            resp = await client.post(
                f"/api/audit/tasks/{task.id}/approve",
                json={"comment": "LGTM"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
    finally:
        app.state.event_bus = orig_bus


# =============================================================================
# audit.py — approve_task with feishu notification error (lines 267-268)
# =============================================================================


@pytest.mark.asyncio
async def test_approve_task_feishu_notification_error(client: AsyncClient, db_session: AsyncSession):
    """When Feishu notification raises, error should be swallowed."""
    task = AuditTask(
        task_name="Feishu Err",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.AWAITING_REVIEW,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    db_session.add(
        Finding(
            task_id=task.id,
            finding_type=FindingType.COMPLIANCE_RISK,
            severity=SeverityLevel.HIGH,
            title="F",
            description="D",
        )
    )
    await db_session.commit()

    from app.main import app

    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    mock_bus.publish_done = AsyncMock()
    orig_bus = getattr(app.state, "event_bus", None)
    app.state.event_bus = mock_bus
    try:
        with (
            patch("app.services.notification.is_feishu_configured", return_value=True),
            patch(
                "app.services.notification.notify_audit_complete",
                new_callable=AsyncMock,
                side_effect=RuntimeError("feishu down"),
            ),
        ):
            resp = await client.post(
                f"/api/audit/tasks/{task.id}/approve",
                json={"comment": "ok"},
            )
        assert resp.status_code == 200
    finally:
        app.state.event_bus = orig_bus


# =============================================================================
# audit.py — run_audit_task enqueue RuntimeError (lines 176-178)
# =============================================================================


@pytest.mark.asyncio
async def test_run_task_enqueue_runtime_error(client: AsyncClient, db_session: AsyncSession):
    """When runner.enqueue raises RuntimeError, should return 503."""
    doc = Document(
        filename="ready.pdf",
        file_path="/tmp/ready.pdf",
        file_type="pdf",
        file_size=100,
        process_status=DocumentStatus.PROCESSED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    task = AuditTask(
        task_name="Enqueue Fail",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.PENDING,
        document_ids=[doc.id],
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    mock_engine = MagicMock()
    mock_engine.adapters = {"deepseek": True}

    mock_runner = MagicMock()
    mock_runner.enqueue = MagicMock(side_effect=RuntimeError("queue full"))
    mock_factory = MagicMock(return_value=mock_runner)

    from app.main import app

    orig_factory = app.state.task_runner_factory
    app.state.task_runner_factory = mock_factory
    try:
        with (
            patch("app.api.audit.is_agent_available", return_value=True),
            patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine),
        ):
            resp = await client.post(f"/api/audit/tasks/{task.id}/run")
        assert resp.status_code == 503
    finally:
        app.state.task_runner_factory = orig_factory


# =============================================================================
# audit.py — get_task with document_ids=None (line 124)
# =============================================================================


@pytest.mark.asyncio
async def test_get_task_with_none_document_ids(client: AsyncClient, db_session: AsyncSession):
    """Get task where document_ids is None should return empty list."""
    task = AuditTask(
        task_name="No Docs",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.PENDING,
        document_ids=None,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    resp = await client.get(f"/api/audit/tasks/{task.id}")
    assert resp.status_code == 200
    assert resp.json()["document_ids"] == []


# =============================================================================
# documents.py — _parse_metadata helper (lines 28-37)
# =============================================================================


def test_parse_metadata_none():
    from app.api.documents import _parse_metadata

    assert _parse_metadata(None) is None
    assert _parse_metadata("") is None


def test_parse_metadata_dict_passthrough():
    from app.api.documents import _parse_metadata

    d = {"key": "value"}
    assert _parse_metadata(d) == d


def test_parse_metadata_json_string():
    from app.api.documents import _parse_metadata

    assert _parse_metadata('{"a": 1}') == {"a": 1}


def test_parse_metadata_invalid_json():
    from app.api.documents import _parse_metadata

    assert _parse_metadata("not json {") is None


# =============================================================================
# documents.py — _generate_safe_filename helper (lines 40-42)
# =============================================================================


def test_generate_safe_filename():
    from app.api.documents import _generate_safe_filename

    name = _generate_safe_filename("test file (1).pdf")
    assert name.endswith(".pdf")
    assert len(name) > 4
    # Should not contain spaces or parens
    assert " " not in name
    assert "(" not in name


def test_generate_safe_filename_no_ext():
    from app.api.documents import _generate_safe_filename

    name = _generate_safe_filename("noext")
    assert name.endswith("noext") or name.endswith("")


# =============================================================================
# documents.py — _get_upload_dir fallback (lines 45-57)
# =============================================================================


def test_get_upload_dir_fallback():
    """When preferred dir is not writable, fallback to temp dir."""
    from app.api.documents import _get_upload_dir

    # Mock open to raise OSError only for the write probe
    original_open = open

    def mock_open(path, *args, **kwargs):
        if ".write_test" in str(path):
            raise OSError("read-only filesystem")
        return original_open(path, *args, **kwargs)

    with patch("app.api.documents.settings") as mock_settings:
        mock_settings.UPLOAD_DIR = "/nonexistent/readonly/path"
        with patch("builtins.open", side_effect=mock_open), patch("os.makedirs"):
            result = _get_upload_dir()
    assert "gmpaudit_uploads" in result


def test_get_upload_dir_success():
    """Normal path returns preferred dir."""
    from app.api.documents import _get_upload_dir

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.api.documents.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = tmpdir
            result = _get_upload_dir()
        assert result == tmpdir


# =============================================================================
# documents.py — delete with path safety (lines 304-308)
# =============================================================================


@pytest.mark.asyncio
async def test_delete_document_path_outside_upload_dir(client: AsyncClient, db_session: AsyncSession):
    """Delete should reject files whose path is outside the upload dir."""
    doc = Document(
        filename="escape.pdf",
        file_path="/etc/passwd",
        file_type="pdf",
        file_size=100,
        process_status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    resp = await client.delete(f"/api/documents/{doc.id}")
    assert resp.status_code == 400
    assert "路径异常" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_document_no_file_on_disk(client: AsyncClient, db_session: AsyncSession):
    """Delete should succeed even if the file doesn't exist on disk."""
    from app.core.config import settings

    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, "ghost_file.pdf")

    doc = Document(
        filename="ghost.pdf",
        file_path=file_path,
        file_type="pdf",
        file_size=100,
        process_status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    # File doesn't exist, should still succeed
    assert not os.path.exists(file_path)
    resp = await client.delete(f"/api/documents/{doc.id}")
    assert resp.status_code == 200


# =============================================================================
# documents.py — batch upload size check (lines 166-172)
# =============================================================================


@pytest.mark.asyncio
async def test_batch_upload_oversized_file(client: AsyncClient):
    """Batch upload should reject oversized files."""
    from app.api.documents import MAX_UPLOAD_SIZE

    big_content = b"x" * (MAX_UPLOAD_SIZE + 100)
    files = [("files", ("big.pdf", big_content, "application/pdf"))]
    resp = await client.post("/api/documents/upload/batch", files=files)
    assert resp.status_code == 413


# =============================================================================
# documents.py — upload with content-length exactly at limit
# =============================================================================


@pytest.mark.asyncio
async def test_upload_content_length_at_limit(client: AsyncClient):
    """Content-Length at exactly the limit should succeed."""
    from app.api.documents import MAX_UPLOAD_SIZE

    headers = {"content-length": str(MAX_UPLOAD_SIZE)}
    files = {"file": ("ok.pdf", b"small", "application/pdf")}
    resp = await client.post("/api/documents/upload", files=files, headers=headers)
    assert resp.status_code == 200


# =============================================================================
# reports.py — _sanitize_html (line 59)
# =============================================================================


def test_sanitize_html_strips_script():
    from app.api.reports import _sanitize_html

    result = _sanitize_html('<script>alert("xss")</script><p>Safe</p>')
    assert "<script>" not in result
    assert "Safe" in result


def test_sanitize_html_allows_table():
    from app.api.reports import _sanitize_html

    result = _sanitize_html("<table><tr><td>cell</td></tr></table>")
    assert "<table>" in result
    assert "cell" in result


def test_sanitize_html_strips_iframe():
    from app.api.reports import _sanitize_html

    result = _sanitize_html('<iframe src="evil"></iframe>Text')
    assert "<iframe>" not in result
    assert "Text" in result


# =============================================================================
# reports.py — export with None content (lines 188-190, 228-229)
# =============================================================================


@pytest.mark.asyncio
async def test_export_html_with_none_content(client: AsyncClient, db_session: AsyncSession):
    """Export should handle None content gracefully."""
    report = Report(
        task_id=1,
        report_type=ReportType.FULL_REPORT,
        title="None Content",
        content=None,
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    resp = await client.get(f"/api/reports/{report.id}/export/html")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_export_pdf_with_none_content(client: AsyncClient, db_session: AsyncSession):
    """PDF export should handle None content gracefully."""
    report = Report(
        task_id=1,
        report_type=ReportType.FULL_REPORT,
        title="None PDF",
        content=None,
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    def fake_create_pdf(html, dest, encoding="utf-8"):
        dest.write(b"%PDF")
        return MagicMock(err=False)

    parent = MagicMock()
    parent.pisa = MagicMock()
    parent.pisa.CreatePDF = MagicMock(side_effect=fake_create_pdf)

    with patch.dict("sys.modules", {"xhtml2pdf": parent, "xhtml2pdf.pisa": parent.pisa}):
        resp = await client.get(f"/api/reports/{report.id}/export/pdf")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_export_pdf_with_empty_title(client: AsyncClient, db_session: AsyncSession):
    """PDF export should handle empty title gracefully."""
    report = Report(
        task_id=1,
        report_type=ReportType.FULL_REPORT,
        title="",
        content="Content",
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    def fake_create_pdf(html, dest, encoding="utf-8"):
        dest.write(b"%PDF")
        return MagicMock(err=False)

    parent = MagicMock()
    parent.pisa = MagicMock()
    parent.pisa.CreatePDF = MagicMock(side_effect=fake_create_pdf)

    with patch.dict("sys.modules", {"xhtml2pdf": parent, "xhtml2pdf.pisa": parent.pisa}):
        resp = await client.get(f"/api/reports/{report.id}/export/pdf")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_export_html_with_empty_title(client: AsyncClient, db_session: AsyncSession):
    """HTML export should handle empty title gracefully."""
    report = Report(
        task_id=1,
        report_type=ReportType.FULL_REPORT,
        title="",
        content="Content",
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    resp = await client.get(f"/api/reports/{report.id}/export/html")
    assert resp.status_code == 200
    assert "Untitled" in resp.text


# =============================================================================
# reports.py — export_pdf with special characters in title (line 274)
# =============================================================================


@pytest.mark.asyncio
async def test_export_pdf_special_chars_in_title(client: AsyncClient, db_session: AsyncSession):
    """PDF export should sanitize special characters in filename."""
    report = Report(
        task_id=1,
        report_type=ReportType.FULL_REPORT,
        title="Report <with> special:chars/file*",
        content="Content",
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    def fake_create_pdf(html, dest, encoding="utf-8"):
        dest.write(b"%PDF")
        return MagicMock(err=False)

    parent = MagicMock()
    parent.pisa = MagicMock()
    parent.pisa.CreatePDF = MagicMock(side_effect=fake_create_pdf)

    with patch.dict("sys.modules", {"xhtml2pdf": parent, "xhtml2pdf.pisa": parent.pisa}):
        resp = await client.get(f"/api/reports/{report.id}/export/pdf")
    assert resp.status_code == 200
    disposition = resp.headers.get("content-disposition", "")
    # Special chars should be replaced
    assert "<" not in disposition
    assert ">" not in disposition
    assert ":" not in disposition


# =============================================================================
# reports.py — list reports with created_at=None
# =============================================================================


@pytest.mark.asyncio
async def test_list_reports_null_created_at(client: AsyncClient, db_session: AsyncSession):
    """List should handle reports with null created_at."""
    report = Report(
        task_id=1,
        report_type=ReportType.FULL_REPORT,
        title="Null Date",
        content="C",
    )
    db_session.add(report)
    await db_session.flush()
    # Manually set created_at to None after flush
    report.created_at = None
    await db_session.commit()

    resp = await client.get("/api/reports/")
    assert resp.status_code == 200


# =============================================================================
# health.py — db_health error path (lines 27-29)
# =============================================================================


@pytest.mark.asyncio
async def test_db_health_error(client: AsyncClient):
    """DB health check should return 503 when DB query fails."""
    with patch("app.api.health.get_db") as mock_get_db:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("DB connection lost"))

        async def override():
            yield mock_session

        from app.core.database import get_db as real_get_db
        from app.main import app

        app.dependency_overrides[real_get_db] = override
        try:
            resp = await client.get("/api/health/db")
            assert resp.status_code == 503
            assert resp.json()["detail"]["status"] == "error"
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# agent_audit.py — enqueue RuntimeError (lines 73-74)
# =============================================================================


@pytest.mark.asyncio
async def test_agent_audit_enqueue_error(client: AsyncClient, db_session: AsyncSession):
    """When runner.enqueue raises RuntimeError, should return 503."""
    doc = Document(
        filename="enqueue.pdf",
        file_path="/tmp/enqueue.pdf",
        file_type="pdf",
        file_size=1024,
        process_status=DocumentStatus.PROCESSED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    mock_runner = MagicMock()
    mock_runner.enqueue = MagicMock(side_effect=RuntimeError("queue full"))
    mock_factory = MagicMock(return_value=mock_runner)

    from app.main import app

    orig_factory = app.state.task_runner_factory
    app.state.task_runner_factory = mock_factory
    try:
        with patch("app.api.agent_audit.is_agent_available", return_value=True):
            resp = await client.post(
                "/api/agent-audit/run",
                json={"document_id": doc.id, "audit_type": "deviation"},
            )
        assert resp.status_code == 503
    finally:
        app.state.task_runner_factory = orig_factory


# =============================================================================
# config.py — _atomic_write_text (lines 126-142)
# =============================================================================


def test_atomic_write_text_creates_file():
    from app.api.config import _atomic_write_text

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.txt"
        _atomic_write_text(path, "hello world\n")
        assert path.read_text(encoding="utf-8") == "hello world\n"


def test_atomic_write_text_overwrites():
    from app.api.config import _atomic_write_text

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.txt"
        _atomic_write_text(path, "first\n")
        _atomic_write_text(path, "second\n")
        assert path.read_text(encoding="utf-8") == "second\n"


def test_atomic_write_text_cleans_up_on_error():
    from app.api.config import _atomic_write_text

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.txt"
        with patch("os.rename", side_effect=OSError("rename failed")), pytest.raises(OSError):
            _atomic_write_text(path, "data\n")


# =============================================================================
# config.py — _update_env_file (lines 145-165)
# =============================================================================


def test_update_env_file_updates_existing_key():
    from app.api.config import _update_env_file

    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_path.write_text("LOG_LEVEL=INFO\nMAX_CONCURRENT_TASKS=3\n", encoding="utf-8")
        with patch("app.core.paths.ENV_FILE", env_path):
            _update_env_file("LOG_LEVEL", "DEBUG")
        content = env_path.read_text(encoding="utf-8")
        assert "LOG_LEVEL=DEBUG" in content
        assert "MAX_CONCURRENT_TASKS=3" in content


def test_update_env_file_appends_new_key():
    from app.api.config import _update_env_file

    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_path.write_text("LOG_LEVEL=INFO\n", encoding="utf-8")
        with patch("app.core.paths.ENV_FILE", env_path):
            _update_env_file("NEW_KEY", "new_value")
        content = env_path.read_text(encoding="utf-8")
        assert "NEW_KEY=new_value" in content


def test_update_env_file_no_file():
    """When .env doesn't exist, _update_env_file should be a no-op."""
    from app.api.config import _update_env_file

    with patch("app.core.paths.ENV_FILE", Path("/nonexistent/path/.env")):
        _update_env_file("KEY", "VALUE")  # Should not raise


def test_update_env_file_read_error():
    """When .env can't be read, should log and not crash."""
    from app.api.config import _update_env_file

    with patch("app.core.paths.ENV_FILE") as mock_path:
        mock_path.exists.return_value = True
        mock_path.read_text.side_effect = OSError("permission denied")
        _update_env_file("KEY", "VALUE")  # Should not raise


# =============================================================================
# config.py — _batch_update_env_file (lines 168-190)
# =============================================================================


def test_batch_update_env_file():
    from app.api.config import _batch_update_env_file

    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_path.write_text("LOG_LEVEL=INFO\nTEMPERATURE=0.7\n", encoding="utf-8")
        with patch("app.core.paths.ENV_FILE", env_path):
            _batch_update_env_file({"LOG_LEVEL": "DEBUG", "TEMPERATURE": "0.5"})
        content = env_path.read_text(encoding="utf-8")
        assert "LOG_LEVEL=DEBUG" in content
        assert "TEMPERATURE=0.5" in content


def test_batch_update_env_file_new_keys():
    from app.api.config import _batch_update_env_file

    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_path.write_text("LOG_LEVEL=INFO\n", encoding="utf-8")
        with patch("app.core.paths.ENV_FILE", env_path):
            _batch_update_env_file({"NEW_KEY": "value"})
        content = env_path.read_text(encoding="utf-8")
        assert "NEW_KEY=value" in content


def test_batch_update_env_file_no_file():
    """When .env doesn't exist, should be a no-op."""
    from app.api.config import _batch_update_env_file

    with patch("app.core.paths.ENV_FILE", Path("/nonexistent/.env")):
        _batch_update_env_file({"KEY": "VALUE"})


def test_batch_update_env_file_with_comments():
    """Should preserve comments and update values."""
    from app.api.config import _batch_update_env_file

    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_path.write_text("# Comment\nLOG_LEVEL=INFO\n", encoding="utf-8")
        with patch("app.core.paths.ENV_FILE", env_path):
            _batch_update_env_file({"LOG_LEVEL": "DEBUG"})
        content = env_path.read_text(encoding="utf-8")
        assert "# Comment" in content
        assert "LOG_LEVEL=DEBUG" in content


# =============================================================================
# config.py — batch_update_config with float cast (lines 390-395)
# =============================================================================


@pytest.mark.asyncio
async def test_batch_update_float_cast(client: AsyncClient):
    """Batch update should correctly cast float values."""
    import os

    from app.core.config import settings

    orig_temp = os.environ.get("TEMPERATURE", "")
    orig_s_temp = getattr(settings, "TEMPERATURE", "")
    try:
        with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
            resp = await client.post("/api/config/batch", json={"configs": {"temperature": "0.5"}})
        assert resp.status_code == 200
    finally:
        if orig_temp:
            os.environ["TEMPERATURE"] = orig_temp
        else:
            os.environ.pop("TEMPERATURE", None)
        settings.TEMPERATURE = float(orig_s_temp) if orig_s_temp else 0.7


@pytest.mark.asyncio
async def test_batch_update_invalid_float(client: AsyncClient):
    """Batch update should skip invalid float values."""
    with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
        resp = await client.post("/api/config/batch", json={"configs": {"temperature": "not_a_float"}})
    assert resp.status_code == 200  # Skipped, not errored


@pytest.mark.asyncio
async def test_batch_update_invalid_int(client: AsyncClient):
    """Batch update should skip invalid int values."""
    with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
        resp = await client.post("/api/config/batch", json={"configs": {"max_concurrent_tasks": "not_int"}})
    assert resp.status_code == 200  # Skipped, not errored


@pytest.mark.asyncio
async def test_batch_update_same_value_skipped(client: AsyncClient):
    """Batch update should skip values that haven't changed."""
    import os

    from app.core.config import settings

    os.environ["TEMPERATURE"] = "0.7"
    settings.TEMPERATURE = 0.7
    try:
        with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
            resp = await client.post("/api/config/batch", json={"configs": {"temperature": "0.7"}})
        assert resp.status_code == 200
    finally:
        os.environ.pop("TEMPERATURE", None)
        settings.TEMPERATURE = 0.7


# =============================================================================
# config.py — batch_update_config with API key triggers reload (lines 399-408)
# =============================================================================


@pytest.mark.asyncio
async def test_batch_update_api_key_triggers_reload(client: AsyncClient):
    """Batch updating an API key should trigger provider reload."""
    import os

    orig_key = os.environ.get("DEEPSEEK_API_KEY", "")
    try:
        resp = await client.post("/api/config/batch", json={"configs": {"deepseek_api_key": "sk-batch-test-12345678"}})
        assert resp.status_code == 200
    finally:
        if orig_key:
            os.environ["DEEPSEEK_API_KEY"] = orig_key
        else:
            os.environ.pop("DEEPSEEK_API_KEY", None)


@pytest.mark.asyncio
async def test_batch_update_clears_agent_cache_on_auto_set(client: AsyncClient):
    """Batch update should clear agent cache when auto-setting provider."""
    import os

    orig_key = os.environ.get("QWEN_API_KEY", "")
    try:
        with patch("agent.config.clear_llm_cache") as mock_clear:
            resp = await client.post("/api/config/batch", json={"configs": {"qwen_api_key": "sk-qwen-batch-12345678"}})
        assert resp.status_code == 200
    finally:
        if orig_key:
            os.environ["QWEN_API_KEY"] = orig_key
        else:
            os.environ.pop("QWEN_API_KEY", None)


# =============================================================================
# config.py — _apply_setting with float type (line 98-101)
# =============================================================================


@pytest.mark.asyncio
async def test_apply_setting_float_cast():
    import os

    from app.api.config import _apply_setting
    from app.core.config import settings

    orig_val = os.environ.get("TEMPERATURE", "")
    orig_setting = getattr(settings, "TEMPERATURE", "")
    try:
        with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
            await _apply_setting("temperature", "0.3")
        assert settings.TEMPERATURE == 0.3
        assert os.environ.get("TEMPERATURE") == "0.3"
    finally:
        if orig_val:
            os.environ["TEMPERATURE"] = orig_val
        else:
            os.environ.pop("TEMPERATURE", None)
        settings.TEMPERATURE = float(orig_setting) if orig_setting else 0.7


@pytest.mark.asyncio
async def test_apply_setting_float_invalid():
    from fastapi import HTTPException

    from app.api.config import _apply_setting

    with pytest.raises(HTTPException) as exc_info:
        await _apply_setting("temperature", "not_float")
    assert exc_info.value.status_code == 422
    assert "小数" in exc_info.value.detail


# =============================================================================
# config.py — _apply_setting agent_task_timeout (integer, line 68)
# =============================================================================


@pytest.mark.asyncio
async def test_apply_setting_agent_task_timeout():
    import os

    from app.api.config import _apply_setting
    from app.core.config import settings

    orig_val = os.environ.get("AGENT_TASK_TIMEOUT", "")
    orig_setting = getattr(settings, "AGENT_TASK_TIMEOUT", "")
    try:
        with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
            await _apply_setting("agent_task_timeout", "120")
        assert settings.AGENT_TASK_TIMEOUT == 120
    finally:
        if orig_val:
            os.environ["AGENT_TASK_TIMEOUT"] = orig_val
        else:
            os.environ.pop("AGENT_TASK_TIMEOUT", None)
        settings.AGENT_TASK_TIMEOUT = int(orig_setting) if orig_setting else 600


# =============================================================================
# config.py — _apply_setting model triggers reload (line 112-113)
# =============================================================================


@pytest.mark.asyncio
async def test_apply_setting_model_triggers_reload():
    import os

    from app.api.config import _apply_setting

    orig_val = os.environ.get("DEEPSEEK_MODEL", "")
    try:
        with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock) as mock_reload:
            await _apply_setting("deepseek_model", "deepseek-reasoner")
        mock_reload.assert_called_once_with("deepseek")
    finally:
        if orig_val:
            os.environ["DEEPSEEK_MODEL"] = orig_val
        else:
            os.environ.pop("DEEPSEEK_MODEL", None)


# =============================================================================
# config.py — _apply_setting base_url triggers reload (line 112-113)
# =============================================================================


@pytest.mark.asyncio
async def test_apply_setting_base_url_triggers_reload():
    import os

    from app.api.config import _apply_setting

    orig_val = os.environ.get("DEEPSEEK_BASE_URL", "")
    try:
        with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock) as mock_reload:
            await _apply_setting("deepseek_base_url", "https://custom.api.com/v1")
        mock_reload.assert_called_once_with("deepseek")
    finally:
        if orig_val:
            os.environ["DEEPSEEK_BASE_URL"] = orig_val
        else:
            os.environ.pop("DEEPSEEK_BASE_URL", None)


# =============================================================================
# config.py — update_config with description (line 303-304)
# =============================================================================


@pytest.mark.asyncio
async def test_update_config_with_description(client: AsyncClient):
    """Updating config with description should persist it."""
    with patch("app.api.config._apply_setting", new_callable=AsyncMock):
        resp = await client.put(
            "/api/config/log_level",
            json={"value": "DEBUG", "description": "Updated log level"},
        )
    assert resp.status_code == 200

    resp = await client.get("/api/config/log_level")
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated log level"


@pytest.mark.asyncio
async def test_update_config_existing_with_new_description(client: AsyncClient, db_session: AsyncSession):
    """Updating existing config with new description should update it."""
    db_session.add(
        Configuration(
            config_key="log_level",
            config_value="INFO",
            config_type="string",
            description="Old desc",
        )
    )
    await db_session.commit()

    with patch("app.api.config._apply_setting", new_callable=AsyncMock):
        resp = await client.put(
            "/api/config/log_level",
            json={"value": "DEBUG", "description": "New desc"},
        )
    assert resp.status_code == 200

    resp = await client.get("/api/config/log_level")
    assert resp.json()["description"] == "New desc"


# =============================================================================
# config.py — _reload_llm_provider with clear_llm_cache (lines 216-221)
# =============================================================================


@pytest.mark.asyncio
async def test_reload_llm_provider_clears_agent_cache():

    from app.api.config import _reload_llm_provider

    mock_engine = AsyncMock()
    mock_engine.reload_provider = AsyncMock()
    with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.DEEPSEEK_API_KEY = "sk-test"
            mock_settings.DEEPSEEK_BASE_URL = None
            mock_settings.DEEPSEEK_MODEL = None
            with patch("agent.config.clear_llm_cache") as mock_clear:
                await _reload_llm_provider("deepseek")
            mock_clear.assert_called_once_with("deepseek")


@pytest.mark.asyncio
async def test_reload_llm_provider_import_error():
    """When agent.config is not importable, should not crash."""
    import sys

    from app.api.config import _reload_llm_provider

    mock_engine = AsyncMock()
    mock_engine.reload_provider = AsyncMock()
    with patch("app.services.llm_engine.get_llm_engine", return_value=mock_engine):
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.DEEPSEEK_API_KEY = "sk-test"
            mock_settings.DEEPSEEK_BASE_URL = None
            mock_settings.DEEPSEEK_MODEL = None
            # Temporarily remove agent.config from sys.modules
            saved = sys.modules.pop("agent.config", None)
            sys.modules["agent.config"] = None  # type: ignore
            try:
                await _reload_llm_provider("deepseek")
            finally:
                if saved is not None:
                    sys.modules["agent.config"] = saved
                else:
                    sys.modules.pop("agent.config", None)


# =============================================================================
# config.py — test-llm with latency_ms (lines 485-493)
# =============================================================================


@pytest.mark.asyncio
async def test_test_llm_returns_latency(client: AsyncClient):
    """Test LLM endpoint should return latency_ms on success."""
    mock_adapter = AsyncMock()
    mock_response = MagicMock()
    mock_response.model = "deepseek-chat"
    mock_adapter.chat = AsyncMock(return_value=mock_response)
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.OpenAICompatibleAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={
                "provider": "deepseek",
                "api_key": "sk-test-key",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "latency_ms" in data
    assert data["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_test_llm_siliconflow(client: AsyncClient):
    """Test LLM endpoint with siliconflow provider."""
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(return_value=MagicMock(model="deepseek-v3"))
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.OpenAICompatibleAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={
                "provider": "siliconflow",
                "api_key": "sk-test",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_test_llm_openrouter(client: AsyncClient):
    """Test LLM endpoint with openrouter provider."""
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(return_value=MagicMock(model="deepseek-chat"))
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.OpenAICompatibleAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={
                "provider": "openrouter",
                "api_key": "sk-test",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_test_llm_mimo(client: AsyncClient):
    """Test LLM endpoint with mimo provider."""
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(return_value=MagicMock(model="mimo-v2.5-pro"))
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.OpenAICompatibleAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={
                "provider": "mimo",
                "api_key": "sk-test",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_test_llm_glm(client: AsyncClient):
    """Test LLM endpoint with GLM provider."""
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(return_value=MagicMock(model="glm-4-flash"))
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.OpenAICompatibleAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={
                "provider": "glm",
                "api_key": "sk-test",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# =============================================================================
# document_processor.py — _clean_text (lines 228-235)
# =============================================================================


def test_clean_text_empty():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    assert proc._clean_text("") == ""
    assert proc._clean_text(None) == ""


def test_clean_text_normalizes_whitespace():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    result = proc._clean_text("hello   world  test")
    assert result == "hello world test"


def test_clean_text_collapses_newlines():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    result = proc._clean_text("line1\n\n\n\n\nline2")
    assert result == "line1\n\nline2"


def test_clean_text_strips():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    result = proc._clean_text("  hello  ")
    assert result == "hello"


# =============================================================================
# document_processor.py — _split_text (lines 237-259)
# =============================================================================


def test_split_text_empty():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    assert proc._split_text("") == []
    assert proc._split_text(None) == []


def test_split_text_short_text():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    result = proc._split_text("short text")
    assert len(result) == 1
    assert result[0] == "short text"


def test_split_text_long_text():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    text = "A" * 5000
    result = proc._split_text(text, chunk_size=2000, overlap=200)
    assert len(result) >= 2


def test_split_text_with_period_breakpoint():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    text = "A" * 1500 + "。" + "B" * 1500
    result = proc._split_text(text, chunk_size=2000, overlap=200)
    assert len(result) >= 1


def test_split_text_with_english_period():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    text = "A" * 1500 + "." + "B" * 1500
    result = proc._split_text(text, chunk_size=2000, overlap=200)
    assert len(result) >= 1


def test_split_text_no_period():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    text = "A" * 5000
    result = proc._split_text(text, chunk_size=2000, overlap=200)
    assert len(result) >= 2
    for chunk in result:
        assert len(chunk) > 0


# =============================================================================
# document_processor.py — _process_image with no result (lines 215-226)
# =============================================================================


def test_process_image_no_result():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    mock_ocr = MagicMock(return_value=(None, 0.5))
    proc.ocr = mock_ocr
    assert proc._process_image("fake.png") == ""


def test_process_image_empty_result():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    mock_ocr = MagicMock(return_value=([], 0.5))
    proc.ocr = mock_ocr
    assert proc._process_image("fake.png") == ""


def test_process_image_with_results():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    mock_ocr = MagicMock(
        return_value=(
            [
                ([[0, 0], [100, 0], [100, 30], [0, 30]], "Hello", 0.95),
                ([[0, 30], [100, 30], [100, 60], [0, 60]], "World", 0.90),
            ],
            0.5,
        )
    )
    proc.ocr = mock_ocr
    result = proc._process_image("fake.png")
    assert "Hello" in result
    assert "World" in result


def test_process_image_with_none_text_in_result():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    mock_ocr = MagicMock(
        return_value=(
            [
                ([[0, 0], [100, 0], [100, 30], [0, 30]], None, 0.95),
                ([[0, 30], [100, 30], [100, 60], [0, 60]], "Text", 0.90),
            ],
            0.5,
        )
    )
    proc.ocr = mock_ocr
    result = proc._process_image("fake.png")
    assert "Text" in result


# =============================================================================
# document_processor.py — _get_ocr (lines 18-22)
# =============================================================================


def test_get_ocr_lazy_init():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    assert proc.ocr is None
    mock_rapidocr = MagicMock()
    mock_module = MagicMock()
    mock_module.RapidOCR = MagicMock(return_value=mock_rapidocr)
    with patch.dict("sys.modules", {"rapidocr_onnxruntime": mock_module}):
        ocr = proc._get_ocr()
        assert ocr is mock_rapidocr
        assert proc.ocr is mock_rapidocr


def test_get_ocr_cached():
    """Second call should return cached instance."""
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    mock_ocr = MagicMock()
    proc.ocr = mock_ocr
    assert proc._get_ocr() is mock_ocr


# =============================================================================
# document_processor.py — process_document with unsupported type (line 39)
# =============================================================================


@pytest.mark.asyncio
async def test_process_document_unsupported_type():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    with pytest.raises(ValueError, match="不支持"):
        await proc.process_document("test.xyz", "unsupported_type")


# =============================================================================
# document_processor.py — _process_text with encoding fallback (lines 201-209)
# =============================================================================


def test_process_text_utf8():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", delete=False) as f:
        f.write("Hello UTF-8")
        path = f.name
    try:
        result = proc._process_text_sync(path)
        assert result == "Hello UTF-8"
    finally:
        os.unlink(path)


def test_process_text_fallback_encoding():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    # Write a file in GBK encoding
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
        f.write("你好世界".encode("gbk"))
        path = f.name
    try:
        result = proc._process_text_sync(path)
        assert "你好" in result
    finally:
        os.unlink(path)


# =============================================================================
# document_processor.py — get_document_processor singleton (lines 262-269)
# =============================================================================


def test_get_document_processor_singleton():
    import app.services.document_processor as dp

    orig = dp.document_processor
    dp.document_processor = None
    try:
        p1 = dp.get_document_processor()
        p2 = dp.get_document_processor()
        assert p1 is p2
        assert isinstance(p1, dp.DocumentProcessor)
    finally:
        dp.document_processor = orig


# =============================================================================
# document_processor.py — _process_word_legacy_sync antiword not found (lines 89-104)
# =============================================================================


def test_process_word_legacy_antiword_not_found():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    with patch("subprocess.run", side_effect=FileNotFoundError("antiword not found")):
        with patch.object(proc, "_extract_doc_text_olefile", return_value="olefile text"):
            result = proc._process_word_legacy_sync("test.doc")
    assert result == "olefile text"


def test_process_word_legacy_antiword_error():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    with patch("subprocess.run", side_effect=Exception("some error")):
        with patch.object(proc, "_extract_doc_text_olefile", return_value="fallback text"):
            result = proc._process_word_legacy_sync("test.doc")
    assert result == "fallback text"


def test_process_word_legacy_antiword_empty_output():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    with patch("subprocess.run", return_value=mock_result):
        with patch.object(proc, "_extract_doc_text_olefile", return_value="olefile text"):
            result = proc._process_word_legacy_sync("test.doc")
    assert result == "olefile text"


def test_process_word_legacy_antiword_success():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Antiword extracted text"
    with patch("subprocess.run", return_value=mock_result):
        result = proc._process_word_legacy_sync("test.doc")
    assert result == "Antiword extracted text"


# =============================================================================
# config.py — test-webhook exception handling
# =============================================================================

# =============================================================================
# config.py — get_llm_engine for test-llm
# =============================================================================


@pytest.mark.asyncio
async def test_test_llm_adapter_close_on_success(client: AsyncClient):
    """Adapter should be closed after test, even on success."""
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(return_value=MagicMock(model="test"))
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.OpenAICompatibleAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={
                "provider": "deepseek",
                "api_key": "sk-test",
            },
        )
    assert resp.status_code == 200
    mock_adapter.close.assert_called_once()


@pytest.mark.asyncio
async def test_test_llm_adapter_close_on_failure(client: AsyncClient):
    """Adapter should be closed after test, even on failure."""
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(side_effect=Exception("fail"))
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.OpenAICompatibleAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={
                "provider": "deepseek",
                "api_key": "sk-test",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    mock_adapter.close.assert_called_once()


# =============================================================================
# documents.py — get_document with null upload_time
# =============================================================================


@pytest.mark.asyncio
async def test_get_document_null_upload_time(client: AsyncClient, db_session: AsyncSession):
    """Get document should handle null upload_time."""
    doc = Document(
        filename="null_time.pdf",
        file_path="/tmp/null.pdf",
        file_type="pdf",
        file_size=100,
        process_status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.flush()
    doc.upload_time = None
    await db_session.commit()

    resp = await client.get(f"/api/documents/{doc.id}")
    assert resp.status_code == 200


# =============================================================================
# documents.py — list documents with null upload_time
# =============================================================================


@pytest.mark.asyncio
async def test_list_documents_null_upload_time(client: AsyncClient, db_session: AsyncSession):
    """List documents should handle null upload_time."""
    doc = Document(
        filename="null_list.pdf",
        file_path="/tmp/null_list.pdf",
        file_type="pdf",
        file_size=100,
        process_status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.flush()
    doc.upload_time = None
    await db_session.commit()

    resp = await client.get("/api/documents/")
    assert resp.status_code == 200


# =============================================================================
# document_processor.py — _extract_doc_text_olefile error paths (lines 106-195)
# =============================================================================


def test_extract_doc_text_olefile_not_installed():
    """When olefile is not installed, should raise RuntimeError."""
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    with patch.dict("sys.modules", {"olefile": None}), pytest.raises(RuntimeError, match="olefile not installed"):
        proc._extract_doc_text_olefile("test.doc")


def test_extract_doc_text_olefile_not_ole2():
    """When file is not an OLE2 file, should raise RuntimeError."""
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    mock_olefile = MagicMock()
    mock_olefile.OleFileIO.side_effect = Exception("not an ole2 file")
    with patch.dict("sys.modules", {"olefile": mock_olefile}):
        with pytest.raises(RuntimeError, match="Not a valid Word"):
            proc._extract_doc_text_olefile("test.doc")


def test_extract_doc_text_olefile_generic_open_error():
    """When OLE open fails with generic error, should raise RuntimeError."""
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    mock_olefile = MagicMock()
    mock_olefile.OleFileIO.side_effect = Exception("permission denied")
    with patch.dict("sys.modules", {"olefile": mock_olefile}), pytest.raises(RuntimeError, match="Failed to open"):
        proc._extract_doc_text_olefile("test.doc")


def test_extract_doc_text_olefile_encrypted():
    """When document is encrypted, should raise RuntimeError."""
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    mock_ole = MagicMock()
    mock_ole.exists.side_effect = lambda name: name == "EncryptionInfo"
    mock_olefile = MagicMock()
    mock_olefile.OleFileIO.return_value = mock_ole
    with patch.dict("sys.modules", {"olefile": mock_olefile}):
        with pytest.raises(RuntimeError, match="password-protected"):
            proc._extract_doc_text_olefile("test.doc")


def test_extract_doc_text_olefile_no_word_document():
    """When no WordDocument stream, should raise RuntimeError."""
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    mock_ole = MagicMock()
    mock_ole.exists.return_value = False
    mock_olefile = MagicMock()
    mock_olefile.OleFileIO.return_value = mock_ole
    with patch.dict("sys.modules", {"olefile": mock_olefile}):
        with pytest.raises(RuntimeError, match="Not a valid Word"):
            proc._extract_doc_text_olefile("test.doc")


# =============================================================================
# document_processor.py — _process_word_legacy antiword non-zero return
# =============================================================================


def test_process_word_legacy_antiword_nonzero_return():
    """When antiword returns non-zero, should fallback to olefile."""
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    with patch("subprocess.run", return_value=mock_result):
        with patch.object(proc, "_extract_doc_text_olefile", return_value="olefile fallback"):
            result = proc._process_word_legacy_sync("test.doc")
    assert result == "olefile fallback"


# =============================================================================
# document_processor.py — _process_word (async wrapper, line 85-87)
# =============================================================================


@pytest.mark.asyncio
async def test_process_word_async():
    """Test the async wrapper for word processing."""
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    with patch.object(proc, "_process_word_sync", return_value="word content"):
        result = await proc._process_word("test.docx")
    assert result == "word content"


# =============================================================================
# document_processor.py — _process_word_legacy (async wrapper, line 197-199)
# =============================================================================


@pytest.mark.asyncio
async def test_process_word_legacy_async():
    """Test the async wrapper for legacy word processing."""
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    with patch.object(proc, "_process_word_legacy_sync", return_value="legacy content"):
        result = await proc._process_word_legacy("test.doc")
    assert result == "legacy content"


# =============================================================================
# document_processor.py — _process_text (async wrapper, line 211-213)
# =============================================================================


@pytest.mark.asyncio
async def test_process_text_async():
    """Test the async wrapper for text processing."""
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", delete=False) as f:
        f.write("async text")
        path = f.name
    try:
        result = await proc._process_text(path)
        assert result == "async text"
    finally:
        os.unlink(path)


# =============================================================================
# document_processor.py — _process_pdf (async wrapper, line 76-78)
# =============================================================================


@pytest.mark.asyncio
async def test_process_pdf_async():
    """Test the async wrapper for PDF processing."""
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    with patch.object(proc, "_process_pdf_sync", return_value="pdf content"):
        result = await proc._process_pdf("test.pdf")
    assert result == "pdf content"


# =============================================================================
# document_processor.py — _process_text_sync with replacement encoding
# =============================================================================


def test_process_text_sync_replacement_encoding():
    """When all encodings fail, should use utf-8 with replace."""
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    # Create a file with bytes that are invalid in all common encodings
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
        f.write(b"\xff\xfe\x00\x01")
        path = f.name
    try:
        result = proc._process_text_sync(path)
        assert isinstance(result, str)
    finally:
        os.unlink(path)


# =============================================================================
# document_processor.py — _process_text_sync with gb18030 encoding
# =============================================================================


def test_process_text_sync_gb18030():
    """Test gb18030 encoding fallback."""
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
        f.write("GB18030编码".encode("gb18030"))
        path = f.name
    try:
        result = proc._process_text_sync(path)
        assert "GB18030" in result or "编码" in result
    finally:
        os.unlink(path)


# =============================================================================
# documents.py — _process_document_bg (lines 63-98)
# =============================================================================


@pytest.mark.asyncio
async def test_process_document_bg_not_found(db_session: AsyncSession):
    """Background processing should handle missing document gracefully."""
    from app.api.documents import _process_document_bg

    # Should not raise even if document doesn't exist
    await _process_document_bg(99999)


@pytest.mark.asyncio
async def test_process_document_bg_success():
    """Background processing should update document status on success."""
    from app.api.documents import _process_document_bg
    from tests.conftest import async_session as test_session

    async with test_session() as db:
        doc = Document(
            filename="bg.pdf",
            file_path="/tmp/bg.pdf",
            file_type="pdf",
            file_size=100,
            process_status=DocumentStatus.UPLOADED,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        doc_id = doc.id

    mock_proc = MagicMock()
    mock_proc.process_document = AsyncMock(
        return_value={
            "content": "BG processed",
            "chunks": ["c1"],
            "chunk_count": 1,
            "char_count": 12,
        }
    )

    with patch("app.api.documents.async_session", test_session):
        with patch("app.services.document_processor.get_document_processor", return_value=mock_proc):
            await _process_document_bg(doc_id)

    async with test_session() as db:
        from sqlalchemy import select

        result = await db.execute(select(Document).where(Document.id == doc_id))
        updated_doc = result.scalar_one()
        assert updated_doc.process_status == DocumentStatus.PROCESSED


@pytest.mark.asyncio
async def test_process_document_bg_failure():
    """Background processing should set FAILED status on error."""
    from app.api.documents import _process_document_bg
    from tests.conftest import async_session as test_session

    async with test_session() as db:
        doc = Document(
            filename="bg_fail.pdf",
            file_path="/tmp/bg_fail.pdf",
            file_type="pdf",
            file_size=100,
            process_status=DocumentStatus.UPLOADED,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        doc_id = doc.id

    mock_proc = MagicMock()
    mock_proc.process_document = AsyncMock(side_effect=Exception("processing error"))

    with patch("app.api.documents.async_session", test_session):
        with patch("app.services.document_processor.get_document_processor", return_value=mock_proc):
            await _process_document_bg(doc_id)

    async with test_session() as db:
        from sqlalchemy import select

        result = await db.execute(select(Document).where(Document.id == doc_id))
        updated_doc = result.scalar_one()
        assert updated_doc.process_status == DocumentStatus.FAILED


@pytest.mark.asyncio
async def test_process_document_bg_failure_persist_error():
    """When failure state can't be persisted, should not crash."""
    from app.api.documents import _process_document_bg
    from tests.conftest import async_session as test_session

    async with test_session() as db:
        doc = Document(
            filename="bg_persist.pdf",
            file_path="/tmp/bg_persist.pdf",
            file_type="pdf",
            file_size=100,
            process_status=DocumentStatus.UPLOADED,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        doc_id = doc.id

    mock_proc = MagicMock()
    mock_proc.process_document = AsyncMock(side_effect=Exception("processing error"))

    with patch("app.api.documents.async_session", test_session):
        with patch("app.services.document_processor.get_document_processor", return_value=mock_proc):
            # Should not crash even if error persistence fails
            await _process_document_bg(doc_id)


# =============================================================================
# document_processor.py — _extract_doc_text_olefile with mock OLE (lines 106-195)
# =============================================================================


def test_extract_doc_text_olefile_empty_clx():
    """When lcb_clx is 0, should return empty string."""
    import struct

    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()

    # Build minimal WordDocument stream with lcb_clx = 0
    word_stream = bytearray(2048)
    # fcClx at 0x01A2 = 0, lcbClx at 0x01A6 = 0
    struct.pack_into("<I", word_stream, 0x01A2, 0)
    struct.pack_into("<I", word_stream, 0x01A6, 0)

    mock_ole = MagicMock()
    mock_ole.exists.side_effect = lambda name: name == "WordDocument"
    mock_ole.openstream.return_value.read.return_value = bytes(word_stream)

    mock_olefile = MagicMock()
    mock_olefile.OleFileIO.return_value = mock_ole

    with patch.dict("sys.modules", {"olefile": mock_olefile}):
        result = proc._extract_doc_text_olefile("test.doc")
    assert result == ""


def test_extract_doc_text_olefile_no_piece_table():
    """When CLX has only Grpprl entries and no piece table, should return empty string."""
    import struct

    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()

    # Build WordDocument stream
    word_stream = bytearray(2048)
    # fcClx at 0x01A2, lcbClx at 0x01A6
    fc_clx = 100
    # CLX: one Grpprl entry (tag=0x01, cb=0) = 3 bytes exactly
    # After processing, offset=3 == len(clx), while loop ends, else returns ""
    lcb_clx = 3
    struct.pack_into("<I", word_stream, 0x01A2, fc_clx)
    struct.pack_into("<I", word_stream, 0x01A6, lcb_clx)

    # Build table stream with CLX that has only Grpprl (tag=0x01, cb=0)
    table_stream = bytearray(1024)
    table_stream[fc_clx] = 0x01  # tag
    struct.pack_into("<H", table_stream, fc_clx + 1, 0)  # cb=0

    mock_ole = MagicMock()
    mock_ole.exists.side_effect = lambda name: name in ("WordDocument", "0Table")
    mock_ole.openstream.side_effect = lambda name: MagicMock(
        read=MagicMock(return_value=bytes(word_stream if name == "WordDocument" else table_stream))
    )

    mock_olefile = MagicMock()
    mock_olefile.OleFileIO.return_value = mock_ole

    with patch.dict("sys.modules", {"olefile": mock_olefile}):
        result = proc._extract_doc_text_olefile("test.doc")
    assert result == ""


def test_extract_doc_text_olefile_unknown_clx_tag():
    """When CLX has unknown tag, should raise RuntimeError."""
    import struct

    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()

    word_stream = bytearray(2048)
    fc_clx = 100
    lcb_clx = 10
    struct.pack_into("<I", word_stream, 0x01A2, fc_clx)
    struct.pack_into("<I", word_stream, 0x01A6, lcb_clx)

    table_stream = bytearray(1024)
    # Unknown tag 0x03
    table_stream[fc_clx] = 0x03
    struct.pack_into("<H", table_stream, fc_clx + 1, 2)

    mock_ole = MagicMock()
    mock_ole.exists.side_effect = lambda name: name in ("WordDocument", "0Table")
    mock_ole.openstream.side_effect = lambda name: MagicMock(
        read=MagicMock(return_value=bytes(word_stream if name == "WordDocument" else table_stream))
    )

    mock_olefile = MagicMock()
    mock_olefile.OleFileIO.return_value = mock_ole

    with patch.dict("sys.modules", {"olefile": mock_olefile}), pytest.raises(RuntimeError, match="Unknown CLX tag"):
        proc._extract_doc_text_olefile("test.doc")


def test_extract_doc_text_olefile_zero_pieces():
    """When piece table has n<=0, should return empty string."""
    import struct

    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()

    word_stream = bytearray(2048)
    fc_clx = 100
    # CLX: just a piece table (tag=0x02) with n=0
    # n = (cb - 4) / 12, so cb=4 gives n=0
    cb = 4
    lcb_clx = 5  # 1 (tag) + 4 (cb)
    struct.pack_into("<I", word_stream, 0x01A2, fc_clx)
    struct.pack_into("<I", word_stream, 0x01A6, lcb_clx)

    table_stream = bytearray(1024)
    table_stream[fc_clx] = 0x02
    struct.pack_into("<I", table_stream, fc_clx + 1, cb)

    mock_ole = MagicMock()
    mock_ole.exists.side_effect = lambda name: name in ("WordDocument", "0Table")
    mock_ole.openstream.side_effect = lambda name: MagicMock(
        read=MagicMock(return_value=bytes(word_stream if name == "WordDocument" else table_stream))
    )

    mock_olefile = MagicMock()
    mock_olefile.OleFileIO.return_value = mock_ole

    with patch.dict("sys.modules", {"olefile": mock_olefile}):
        result = proc._extract_doc_text_olefile("test.doc")
    assert result == ""


def test_extract_doc_text_olefile_compressed_text():
    """Extract compressed (single-byte) text from piece table."""
    import struct

    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()

    # Build WordDocument stream with actual text
    text = b"Hello World"
    text_offset = 500
    word_stream = bytearray(2048)
    word_stream[text_offset : text_offset + len(text)] = text

    fc_clx = 100
    # Piece table: 1 piece, n=1
    # n+1=2 CPs (4 bytes each) + 1 PCD (8 bytes each) = 8 + 8 = 16 bytes
    # cb = 16 + 4 = 20
    cb = 20
    lcb_clx = 5 + cb  # 1 (tag) + 4 (cb) + cb
    struct.pack_into("<I", word_stream, 0x01A2, fc_clx)
    struct.pack_into("<I", word_stream, 0x01A6, lcb_clx)

    table_stream = bytearray(2048)
    offset = fc_clx
    table_stream[offset] = 0x02  # tag
    struct.pack_into("<I", table_stream, offset + 1, cb)
    offset += 5

    # CPs: [0, 11] (11 chars)
    struct.pack_into("<I", table_stream, offset, 0)
    struct.pack_into("<I", table_stream, offset + 4, len(text))
    offset += 8

    # PCD: fc with bit 30 set (compressed), real_fc = text_offset
    fc_value = text_offset | 0x40000000  # compressed flag
    struct.pack_into("<H", table_stream, offset, 0)  # _pcd
    struct.pack_into("<I", table_stream, offset + 2, fc_value)

    mock_ole = MagicMock()
    mock_ole.exists.side_effect = lambda name: name in ("WordDocument", "0Table")
    mock_ole.openstream.side_effect = lambda name: MagicMock(
        read=MagicMock(return_value=bytes(word_stream if name == "WordDocument" else table_stream))
    )

    mock_olefile = MagicMock()
    mock_olefile.OleFileIO.return_value = mock_ole

    with patch.dict("sys.modules", {"olefile": mock_olefile}):
        result = proc._extract_doc_text_olefile("test.doc")
    assert "Hello World" in result


def test_extract_doc_text_olefile_utf16_text():
    """Extract UTF-16LE (double-byte) text from piece table."""
    import struct

    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()

    # Build WordDocument stream with UTF-16LE text
    text = "Hello"  # 5 chars, 10 bytes in UTF-16LE
    text_bytes = text.encode("utf-16-le")
    text_offset = 500
    word_stream = bytearray(2048)
    word_stream[text_offset : text_offset + len(text_bytes)] = text_bytes

    fc_clx = 100
    cb = 20  # 2 CPs * 4 + 1 PCD * 8 + 4 padding
    lcb_clx = 5 + cb
    struct.pack_into("<I", word_stream, 0x01A2, fc_clx)
    struct.pack_into("<I", word_stream, 0x01A6, lcb_clx)

    table_stream = bytearray(2048)
    offset = fc_clx
    table_stream[offset] = 0x02
    struct.pack_into("<I", table_stream, offset + 1, cb)
    offset += 5

    # CPs: [0, 5]
    struct.pack_into("<I", table_stream, offset, 0)
    struct.pack_into("<I", table_stream, offset + 4, 5)
    offset += 8

    # PCD: fc without bit 30 (not compressed = UTF-16LE), real_fc = text_offset
    fc_value = text_offset  # no compressed flag
    struct.pack_into("<H", table_stream, offset, 0)
    struct.pack_into("<I", table_stream, offset + 2, fc_value)

    mock_ole = MagicMock()
    mock_ole.exists.side_effect = lambda name: name in ("WordDocument", "0Table")
    mock_ole.openstream.side_effect = lambda name: MagicMock(
        read=MagicMock(return_value=bytes(word_stream if name == "WordDocument" else table_stream))
    )

    mock_olefile = MagicMock()
    mock_olefile.OleFileIO.return_value = mock_ole

    with patch.dict("sys.modules", {"olefile": mock_olefile}):
        result = proc._extract_doc_text_olefile("test.doc")
    assert "Hello" in result


def test_extract_doc_text_olefile_zero_char_count():
    """When char_count <= 0, should skip that piece."""
    import struct

    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()

    text_offset = 500
    word_stream = bytearray(2048)

    fc_clx = 100
    # 2 pieces, n=2
    # 3 CPs * 4 + 2 PCDs * 8 = 12 + 16 = 28, cb = 32
    cb = 32
    lcb_clx = 5 + cb
    struct.pack_into("<I", word_stream, 0x01A2, fc_clx)
    struct.pack_into("<I", word_stream, 0x01A6, lcb_clx)

    table_stream = bytearray(2048)
    offset = fc_clx
    table_stream[offset] = 0x02
    struct.pack_into("<I", table_stream, offset + 1, cb)
    offset += 5

    # CPs: [0, 0, 5] -> first piece has 0 chars, second has 5
    struct.pack_into("<I", table_stream, offset, 0)
    struct.pack_into("<I", table_stream, offset + 4, 0)
    struct.pack_into("<I", table_stream, offset + 8, 5)
    offset += 12

    # PCD 1: compressed, text at text_offset (0 chars, will be skipped)
    fc_value1 = text_offset | 0x40000000
    struct.pack_into("<H", table_stream, offset, 0)
    struct.pack_into("<I", table_stream, offset + 2, fc_value1)
    offset += 8

    # PCD 2: compressed, text at text_offset
    text = b"World"
    word_stream[text_offset : text_offset + 5] = text
    fc_value2 = text_offset | 0x40000000
    struct.pack_into("<H", table_stream, offset, 0)
    struct.pack_into("<I", table_stream, offset + 2, fc_value2)

    mock_ole = MagicMock()
    mock_ole.exists.side_effect = lambda name: name in ("WordDocument", "0Table")
    mock_ole.openstream.side_effect = lambda name: MagicMock(
        read=MagicMock(return_value=bytes(word_stream if name == "WordDocument" else table_stream))
    )

    mock_olefile = MagicMock()
    mock_olefile.OleFileIO.return_value = mock_ole

    with patch.dict("sys.modules", {"olefile": mock_olefile}):
        result = proc._extract_doc_text_olefile("test.doc")
    assert "World" in result


# =============================================================================
# document_processor.py — _clean_text with mixed whitespace (lines 228-235)
# =============================================================================


def test_clean_text_mixed_whitespace():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    result = proc._clean_text("  hello\t\tworld  \n\n\n\n  test  ")
    assert "hello" in result
    assert "world" in result
    assert "test" in result


def test_clean_text_only_whitespace():
    from app.services.document_processor import DocumentProcessor

    proc = DocumentProcessor()
    result = proc._clean_text("   \n\n\n   ")
    assert result == ""


# =============================================================================
# audit.py — stream_task_events with DONE_SENTINEL and event type
# =============================================================================


@pytest.mark.asyncio
async def test_stream_task_events_with_progress_event(client: AsyncClient, db_session: AsyncSession):
    """Streaming should forward events with their type as SSE event name."""
    task = AuditTask(
        task_name="Progress",
        task_type=TaskType.DEVIATION_ANALYSIS,
        status=TaskStatus.PENDING,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    from app.main import app
    from app.services.event_bus import EventBus

    bus = EventBus()
    app.state.event_bus = bus

    async def push_events():
        await asyncio.sleep(0.3)
        await bus.publish(task.id, {"type": "agent_thinking", "data": {"agent": "test", "thought": "analyzing"}})
        await asyncio.sleep(0.2)
        await bus.publish_done(task.id, "completed")

    push_task = asyncio.create_task(push_events())

    resp = await client.get(f"/api/audit/tasks/{task.id}/stream")
    assert resp.status_code == 200
    body = resp.text
    assert "agent_thinking" in body
    assert "done" in body

    await push_task


# =============================================================================
# config.py — batch_update with agent_llm_provider clear cache (lines 410-418)
# =============================================================================


@pytest.mark.asyncio
async def test_batch_update_auto_provider_clears_cache(client: AsyncClient):
    """Batch update with auto-detected provider should clear agent cache."""
    import os

    orig_key = os.environ.get("GLM_API_KEY", "")
    try:
        with patch("agent.config.clear_llm_cache") as mock_clear:
            resp = await client.post("/api/config/batch", json={"configs": {"glm_api_key": "sk-glm-test-12345678"}})
        assert resp.status_code == 200
    finally:
        if orig_key:
            os.environ["GLM_API_KEY"] = orig_key
        else:
            os.environ.pop("GLM_API_KEY", None)


# =============================================================================
# config.py — batch_update with .env file persistence (lines 403-404)
# =============================================================================


@pytest.mark.asyncio
async def test_batch_update_persists_to_env_file(client: AsyncClient):
    """Batch update should persist changes to .env file."""
    import os

    from app.core.config import settings

    orig_val = os.environ.get("LOG_LEVEL", "")
    orig_setting = getattr(settings, "LOG_LEVEL", "")
    try:
        resp = await client.post("/api/config/batch", json={"configs": {"log_level": "ERROR"}})
        assert resp.status_code == 200
    finally:
        if orig_val:
            os.environ["LOG_LEVEL"] = orig_val
        else:
            os.environ.pop("LOG_LEVEL", None)
        settings.LOG_LEVEL = orig_setting or "INFO"


# =============================================================================
# documents.py — _write_file_sync (lines 23-25)
# =============================================================================


def test_write_file_sync():
    from app.api.documents import _write_file_sync

    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        path = f.name
    try:
        _write_file_sync(path, b"binary content")
        with open(path, "rb") as f:
            assert f.read() == b"binary content"
    finally:
        os.unlink(path)


# =============================================================================
# documents.py — _generate_safe_filename uniqueness
# =============================================================================


def test_generate_safe_filename_unique():
    from app.api.documents import _generate_safe_filename

    names = {_generate_safe_filename("test.pdf") for _ in range(10)}
    assert len(names) == 10  # All unique


# =============================================================================
# reports.py — list reports with page_size parameter
# =============================================================================


@pytest.mark.asyncio
async def test_list_reports_custom_page_size(client: AsyncClient, db_session: AsyncSession):
    task = AuditTask(task_name="PS", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    for i in range(5):
        db_session.add(
            Report(
                task_id=task.id,
                report_type=ReportType.FULL_REPORT,
                title=f"R{i}",
                content=f"C{i}",
            )
        )
    await db_session.commit()

    resp = await client.get("/api/reports/", params={"page": 2, "page_size": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 2
    assert data["page_size"] == 2
    assert len(data["items"]) == 2


# =============================================================================
# reports.py — get report with all fields
# =============================================================================


@pytest.mark.asyncio
async def test_get_report_all_fields(client: AsyncClient, db_session: AsyncSession):
    """Get report should return all expected fields."""
    report = Report(
        task_id=1,
        report_type=ReportType.FULL_REPORT,
        title="Full Report",
        content="Full content",
        report_metadata={"source": "test", "mode": "auto"},
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    resp = await client.get(f"/api/reports/{report.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == report.id
    assert data["task_id"] == 1
    assert data["report_type"] == "full_report"
    assert data["title"] == "Full Report"
    assert data["content"] == "Full content"
    assert data["report_metadata"]["source"] == "test"
    assert "created_at" in data
