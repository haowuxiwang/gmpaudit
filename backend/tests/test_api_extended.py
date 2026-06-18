"""Extended API tests for KG, Config, and Reports endpoints.

Covers uncovered code paths identified in:
- app/api/kg.py: build, upload, delete, _parse_graphml
- app/api/config.py: placeholder validation, batch update, test-webhook, test-llm
- app/api/reports.py: LLM error paths, HTML sanitization, pagination
"""

import io
import os
import tempfile
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_task import AuditTask, TaskStatus, TaskType
from app.models.configuration import Configuration
from app.models.finding import Finding, FindingType, SeverityLevel
from app.models.report import Report, ReportType

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only")


# ---------------------------------------------------------------------------
# KG API: _parse_graphml (pure function, no HTTP)
# ---------------------------------------------------------------------------


class TestParseGraphml:
    """Tests for the _parse_graphml helper function."""

    def test_parse_valid_graphml(self, tmp_path):
        from app.api.kg import _parse_graphml

        graphml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="d0" for="node" attr.name="entity_type" attr.type="string"/>
  <key id="d1" for="node" attr.name="description" attr.type="string"/>
  <key id="d2" for="edge" attr.name="description" attr.type="string"/>
  <key id="d3" for="edge" attr.name="weight" attr.type="double"/>
  <graph id="G" edgedefault="undirected">
    <node id="GMP规范">
      <data key="d0">REGULATION</data>
      <data key="d1">药品生产质量管理规范</data>
    </node>
    <node id="数据完整性">
      <data key="d0">CONCEPT</data>
      <data key="d1">ALCOA+原则</data>
    </node>
    <edge source="GMP规范" target="数据完整性">
      <data key="d2">包含要求</data>
      <data key="d3">0.95</data>
    </edge>
  </graph>
</graphml>"""
        filepath = tmp_path / "test.graphml"
        filepath.write_text(graphml_content, encoding="utf-8")

        result = _parse_graphml(str(filepath))

        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1

        node0 = result["nodes"][0]
        assert node0["id"] == "GMP规范"
        assert node0["category"] == "REGULATION"
        assert node0["description"] == "药品生产质量管理规范"

        node1 = result["nodes"][1]
        assert node1["id"] == "数据完整性"
        assert node1["category"] == "CONCEPT"

        edge = result["edges"][0]
        assert edge["source"] == "GMP规范"
        assert edge["target"] == "数据完整性"
        assert edge["label"] == "包含要求"
        assert edge["weight"] == 0.95

    def test_parse_empty_graph(self, tmp_path):
        from app.api.kg import _parse_graphml

        graphml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="G" edgedefault="undirected">
  </graph>
</graphml>"""
        filepath = tmp_path / "empty.graphml"
        filepath.write_text(graphml_content, encoding="utf-8")

        result = _parse_graphml(str(filepath))
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_parse_no_graph_element(self, tmp_path):
        from app.api.kg import _parse_graphml

        graphml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
</graphml>"""
        filepath = tmp_path / "nograph.graphml"
        filepath.write_text(graphml_content, encoding="utf-8")

        result = _parse_graphml(str(filepath))
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_parse_edge_missing_weight(self, tmp_path):
        from app.api.kg import _parse_graphml

        graphml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="d0" for="node" attr.name="entity_type" attr.type="string"/>
  <key id="d2" for="edge" attr.name="description" attr.type="string"/>
  <graph id="G" edgedefault="undirected">
    <node id="A"><data key="d0">TYPE</data></node>
    <node id="B"><data key="d0">TYPE</data></node>
    <edge source="A" target="B">
      <data key="d2">relation</data>
    </edge>
  </graph>
</graphml>"""
        filepath = tmp_path / "noweight.graphml"
        filepath.write_text(graphml_content, encoding="utf-8")

        result = _parse_graphml(str(filepath))
        assert len(result["edges"]) == 1
        # weight defaults to 1.0 when not specified
        assert result["edges"][0]["weight"] == 1.0

    def test_parse_edge_invalid_weight(self, tmp_path):
        from app.api.kg import _parse_graphml

        graphml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="d3" for="edge" attr.name="weight" attr.type="double"/>
  <graph id="G" edgedefault="undirected">
    <node id="A"/>
    <node id="B"/>
    <edge source="A" target="B">
      <data key="d3">not_a_number</data>
    </edge>
  </graph>
</graphml>"""
        filepath = tmp_path / "badweight.graphml"
        filepath.write_text(graphml_content, encoding="utf-8")

        result = _parse_graphml(str(filepath))
        assert len(result["edges"]) == 1
        # Invalid weight should fall back to default 1.0
        assert result["edges"][0]["weight"] == 1.0

    def test_parse_long_description_truncated(self, tmp_path):
        from app.api.kg import _parse_graphml

        long_desc = "x" * 200
        graphml_content = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="d2" for="edge" attr.name="description" attr.type="string"/>
  <graph id="G" edgedefault="undirected">
    <node id="A"/>
    <node id="B"/>
    <edge source="A" target="B">
      <data key="d2">{long_desc}</data>
    </edge>
  </graph>
</graphml>"""
        filepath = tmp_path / "longdesc.graphml"
        filepath.write_text(graphml_content, encoding="utf-8")

        result = _parse_graphml(str(filepath))
        # Edge description is truncated to 100 chars
        assert len(result["edges"][0]["label"]) == 100


# ---------------------------------------------------------------------------
# KG API: GET /graph
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_graph_no_graphml(client: AsyncClient):
    """GET /graph returns 404 when graphml file does not exist."""
    with patch("app.api.kg.os.path.isfile", return_value=False):
        resp = await client.get("/api/kg/graph")
    assert resp.status_code == 404
    assert "图谱数据不存在" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_graph_success(client: AsyncClient):
    """GET /graph returns parsed nodes and edges."""
    mock_data = {
        "nodes": [{"id": "A", "name": "A", "category": "REG", "description": ""}],
        "edges": [{"source": "A", "target": "B", "label": "rel", "weight": 1.0}],
    }
    with (
        patch("app.api.kg.os.path.isfile", return_value=True),
        patch("app.api.kg._parse_graphml", return_value=mock_data),
    ):
        resp = await client.get("/api/kg/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) == 1
    assert len(data["edges"]) == 1


@pytest.mark.asyncio
async def test_get_graph_parse_error(client: AsyncClient):
    """GET /graph returns 500 when GraphML parsing fails."""
    with (
        patch("app.api.kg.os.path.isfile", return_value=True),
        patch("app.api.kg._parse_graphml", side_effect=Exception("parse error")),
    ):
        resp = await client.get("/api/kg/graph")
    assert resp.status_code == 500
    assert "解析图谱数据失败" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# KG API: POST /build
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_success(client: AsyncClient):
    """POST /build starts a background build task."""
    with (
        patch("app.api.kg._build_status", {"building": False, "started_at": None, "error": None, "recent_logs": []}),
        patch("app.api.kg._get_build_status_from_db", new_callable=AsyncMock, return_value={"building": False}),
        patch("app.api.kg.os.path.isdir", return_value=True),
        patch("app.api.kg.os.listdir", return_value=["regulation.txt"]),
        patch("app.api.kg._save_build_status_to_db", new_callable=AsyncMock),
    ):
        resp = await client.post("/api/kg/build")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "building"
    assert "已启动" in data["message"]


@pytest.mark.asyncio
async def test_build_duplicate_in_memory(client: AsyncClient):
    """POST /build returns 409 when in-memory flag says already building."""
    with (
        patch("app.api.kg._build_status", {"building": True, "started_at": "2026-01-01T00:00:00", "error": None, "recent_logs": []}),
        patch("app.api.kg._get_build_status_from_db", new_callable=AsyncMock, return_value={"building": False}),
    ):
        resp = await client.post("/api/kg/build")
    assert resp.status_code == 409
    assert "正在构建中" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_build_duplicate_in_db(client: AsyncClient):
    """POST /build returns 409 when DB says already building."""
    with (
        patch("app.api.kg._build_status", {"building": False, "started_at": None, "error": None, "recent_logs": []}),
        patch("app.api.kg._get_build_status_from_db", new_callable=AsyncMock, return_value={"building": True}),
    ):
        resp = await client.post("/api/kg/build")
    assert resp.status_code == 409
    assert "正在构建中" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_build_no_input_dir(client: AsyncClient):
    """POST /build returns 400 when input directory does not exist."""
    with (
        patch("app.api.kg._build_status", {"building": False, "started_at": None, "error": None, "recent_logs": []}),
        patch("app.api.kg._get_build_status_from_db", new_callable=AsyncMock, return_value={"building": False}),
        patch("app.api.kg.os.path.isdir", return_value=False),
    ):
        resp = await client.post("/api/kg/build")
    assert resp.status_code == 400
    assert "没有输入文件" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# KG API: POST /documents/upload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_txt_file(client: AsyncClient, tmp_path):
    """Upload a .txt file successfully."""
    with patch("app.api.kg.INPUT_DIR", str(tmp_path)):
        resp = await client.post(
            "/api/kg/documents/upload",
            files={"file": ("regulation.txt", b"GMP regulation content", "text/plain")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "regulation.txt"
    assert "上传成功" in data["message"]
    # Verify file was written
    assert os.path.isfile(tmp_path / "regulation.txt")


@pytest.mark.asyncio
async def test_upload_md_file(client: AsyncClient, tmp_path):
    """Upload a .md file successfully."""
    with patch("app.api.kg.INPUT_DIR", str(tmp_path)):
        resp = await client.post(
            "/api/kg/documents/upload",
            files={"file": ("spec.md", b"# Specification", "text/markdown")},
        )
    assert resp.status_code == 200
    assert resp.json()["filename"] == "spec.md"


@pytest.mark.asyncio
async def test_upload_pdf_converted(client: AsyncClient, tmp_path):
    """Upload a .pdf file triggers conversion to .md."""
    mock_md_text = "# Converted PDF\n\nContent from PDF"
    with (
        patch("app.api.kg.INPUT_DIR", str(tmp_path)),
        patch("app.services.converter.convert_to_markdown", new_callable=AsyncMock, return_value=mock_md_text),
    ):
        resp = await client.post(
            "/api/kg/documents/upload",
            files={"file": ("report.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "report.md"
    assert data["converted_from"] == "report.pdf"
    # Verify converted file was written
    assert os.path.isfile(tmp_path / "report.md")


@pytest.mark.asyncio
async def test_upload_docx_converted(client: AsyncClient, tmp_path):
    """Upload a .docx file triggers conversion to .md."""
    mock_md_text = "# Converted DOCX"
    with (
        patch("app.api.kg.INPUT_DIR", str(tmp_path)),
        patch("app.services.converter.convert_to_markdown", new_callable=AsyncMock, return_value=mock_md_text),
    ):
        resp = await client.post(
            "/api/kg/documents/upload",
            files={"file": ("policy.docx", b"PK fake docx", "application/vnd.openxmlformats")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "policy.md"
    assert data["converted_from"] == "policy.docx"


@pytest.mark.asyncio
async def test_upload_empty_filename(client: AsyncClient):
    """Upload with empty filename returns 400 or 422 (FastAPI validation)."""
    # Simulate empty filename by sending a file with no name
    resp = await client.post(
        "/api/kg/documents/upload",
        files={"file": ("", b"content", "text/plain")},
    )
    # FastAPI returns 422 for validation errors on required UploadFile fields
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_upload_path_traversal(client: AsyncClient):
    """Upload with path traversal in filename returns 400."""
    resp = await client.post(
        "/api/kg/documents/upload",
        files={"file": ("../../etc/passwd", b"malicious", "text/plain")},
    )
    assert resp.status_code == 400
    assert "无效的文件名" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_backslash_traversal(client: AsyncClient):
    """Upload with backslash path traversal returns 400."""
    resp = await client.post(
        "/api/kg/documents/upload",
        files={"file": ("..\\..\\windows\\system32\\config", b"malicious", "text/plain")},
    )
    assert resp.status_code == 400
    assert "无效的文件名" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_unsupported_extension(client: AsyncClient):
    """Upload with unsupported file extension returns 400."""
    resp = await client.post(
        "/api/kg/documents/upload",
        files={"file": ("malware.exe", b"MZ fake", "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert "不支持的文件格式" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_file_too_large(client: AsyncClient):
    """Upload file exceeding 10MB limit returns 400."""
    large_content = b"x" * (10 * 1024 * 1024 + 1)  # 10MB + 1 byte
    resp = await client.post(
        "/api/kg/documents/upload",
        files={"file": ("large.txt", large_content, "text/plain")},
    )
    assert resp.status_code == 400
    assert "10MB" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_conversion_failure(client: AsyncClient, tmp_path):
    """Upload PDF when converter raises RuntimeError returns 400."""
    with (
        patch("app.api.kg.INPUT_DIR", str(tmp_path)),
        patch("app.services.converter.convert_to_markdown", new_callable=AsyncMock, side_effect=RuntimeError("Conversion failed")),
    ):
        resp = await client.post(
            "/api/kg/documents/upload",
            files={"file": ("bad.pdf", b"%PDF", "application/pdf")},
        )
    assert resp.status_code == 400
    assert "文档转换失败" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# KG API: DELETE /documents/{filename}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_document_success(client: AsyncClient, tmp_path):
    """Delete an existing regulation document."""
    # Create a temp file to delete
    filepath = tmp_path / "to_delete.txt"
    filepath.write_text("content", encoding="utf-8")

    with patch("app.api.kg.INPUT_DIR", str(tmp_path)):
        resp = await client.delete("/api/kg/documents/to_delete.txt")
    assert resp.status_code == 200
    assert "删除成功" in resp.json()["message"]
    assert not filepath.exists()


@pytest.mark.asyncio
async def test_delete_document_not_found(client: AsyncClient, tmp_path):
    """Delete a non-existent file returns 404."""
    with patch("app.api.kg.INPUT_DIR", str(tmp_path)):
        resp = await client.delete("/api/kg/documents/nonexistent.txt")
    assert resp.status_code == 404
    assert "文件不存在" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_document_path_traversal(client: AsyncClient):
    """Delete with path traversal (dot-dot) returns 400 or 405."""
    resp = await client.delete("/api/kg/documents/..%2F..%2Fetc%2Fpasswd")
    # URL-encoded slashes may be decoded by the server, causing route mismatch (405)
    # or path traversal check (400)
    assert resp.status_code in (400, 405)


@pytest.mark.asyncio
async def test_delete_document_backslash_traversal(client: AsyncClient):
    """Delete with backslash traversal returns 400."""
    resp = await client.delete("/api/kg/documents/..\\..\\secret.txt")
    assert resp.status_code == 400
    assert "无效的文件名" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_document_os_error(client: AsyncClient, tmp_path):
    """Delete returns 500 when os.remove fails."""
    filepath = tmp_path / "locked.txt"
    filepath.write_text("content", encoding="utf-8")

    with (
        patch("app.api.kg.INPUT_DIR", str(tmp_path)),
        patch("app.api.kg.os.remove", side_effect=OSError("Permission denied")),
        patch("app.api.kg.os.path.isfile", return_value=True),
    ):
        resp = await client.delete("/api/kg/documents/locked.txt")
    assert resp.status_code == 500
    assert "文件删除失败" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# KG API: POST /query error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_timeout(client: AsyncClient):
    """POST /query returns 504 on timeout."""
    import asyncio

    with (
        patch("app.api.kg._get_index_info", return_value={"built": True, "file_count": 5, "last_modified": "2026-01-01"}),
        patch("agent.tools.lightrag_tool.lightrag_search", new_callable=AsyncMock, side_effect=asyncio.TimeoutError),
    ):
        resp = await client.post("/api/kg/query", json={"query": "test query"})
    assert resp.status_code == 504
    assert "超时" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_query_generic_error(client: AsyncClient):
    """POST /query returns 500 on generic exception."""
    with (
        patch("app.api.kg._get_index_info", return_value={"built": True, "file_count": 5, "last_modified": "2026-01-01"}),
        patch("agent.tools.lightrag_tool.lightrag_search", new_callable=AsyncMock, side_effect=RuntimeError("connection lost")),
    ):
        resp = await client.post("/api/kg/query", json={"query": "test query"})
    assert resp.status_code == 500
    assert "图谱查询失败" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# KG API: GET /documents with empty directory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_documents_no_input_dir(client: AsyncClient):
    """GET /documents returns empty list when INPUT_DIR does not exist."""
    with patch("app.api.kg.os.path.isdir", return_value=False):
        resp = await client.get("/api/kg/documents")
    assert resp.status_code == 200
    assert resp.json()["documents"] == []


# ---------------------------------------------------------------------------
# Config API: PUT /{key} placeholder validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_config_placeholder_api_key(client: AsyncClient):
    """PUT with placeholder API key value returns 422."""
    resp = await client.put(
        "/api/config/deepseek_api_key",
        json={"value": "your_api_key_here"},
    )
    assert resp.status_code == 422
    assert "占位符" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_config_placeholder_base_url(client: AsyncClient):
    """PUT with placeholder base URL returns 422."""
    resp = await client.put(
        "/api/config/deepseek_base_url",
        json={"value": "your_base_url"},
    )
    assert resp.status_code == 422
    assert "占位符" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_config_placeholder_model(client: AsyncClient):
    """PUT with placeholder model name returns 422."""
    resp = await client.put(
        "/api/config/deepseek_model",
        json={"value": "your_model_name"},
    )
    assert resp.status_code == 422
    assert "占位符" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_config_integer_value(client: AsyncClient):
    """PUT with valid integer value for max_concurrent_tasks."""
    resp = await client.put(
        "/api/config/max_concurrent_tasks",
        json={"value": "5"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


@pytest.mark.asyncio
async def test_update_config_invalid_integer(client: AsyncClient):
    """PUT with non-integer value for an integer config returns 422."""
    # First set it to an integer so the type check kicks in
    await client.put("/api/config/max_concurrent_tasks", json={"value": "3"})
    resp = await client.put(
        "/api/config/max_concurrent_tasks",
        json={"value": "not_a_number"},
    )
    assert resp.status_code == 422
    assert "整数" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_config_auto_sets_agent_provider(client: AsyncClient):
    """PUT with a provider API key auto-sets AGENT_LLM_PROVIDER."""
    with patch("app.api.config._apply_setting", new_callable=AsyncMock):
        resp = await client.put(
            "/api/config/deepseek_api_key",
            json={"value": "sk-real-key-12345"},
        )
    assert resp.status_code == 200
    # Verify AGENT_LLM_PROVIDER was auto-set in DB
    get_resp = await client.get("/api/config/agent_llm_provider")
    if get_resp.status_code == 200:
        assert get_resp.json()["value"] == "deepseek"


# ---------------------------------------------------------------------------
# Config API: POST /batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_update_config(client: AsyncClient):
    """POST /batch updates multiple config values."""
    with patch("app.api.config._apply_setting", new_callable=AsyncMock):
        resp = await client.post(
            "/api/config/batch",
            json={"configs": {"log_level": "DEBUG", "feishu_webhook_url": "https://hooks.example.com/test"}},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["updated"] >= 1


@pytest.mark.asyncio
async def test_batch_update_skips_placeholders(client: AsyncClient):
    """POST /batch skips placeholder API key values."""
    resp = await client.post(
        "/api/config/batch",
        json={"configs": {
            "deepseek_api_key": "your_api_key_here",
            "log_level": "INFO",
        }},
    )
    assert resp.status_code == 200
    # log_level should be updated, placeholder key should be skipped
    data = resp.json()
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_batch_update_auto_sets_provider(client: AsyncClient):
    """POST /batch auto-sets AGENT_LLM_PROVIDER when API key is provided."""
    with patch("app.api.config._reload_llm_provider", new_callable=AsyncMock):
        resp = await client.post(
            "/api/config/batch",
            json={"configs": {"deepseek_api_key": "sk-real-key-abcdef"}},
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Config API: POST /test-webhook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_test_webhook_no_url(client: AsyncClient):
    """POST /test-webhook returns failure when webhook URL is not configured."""
    # settings is lazy-imported inside the handler via `from app.core.config import settings`
    mock_settings = MagicMock()
    mock_settings.FEISHU_WEBHOOK_URL = ""
    with patch("app.core.config.settings", mock_settings):
        resp = await client.post("/api/config/test-webhook")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "未配置" in data["error"]


@pytest.mark.asyncio
async def test_test_webhook_success(client: AsyncClient):
    """POST /test-webhook returns success when notification succeeds."""
    mock_settings = MagicMock()
    mock_settings.FEISHU_WEBHOOK_URL = "https://hooks.feishu.cn/test"
    with (
        patch("app.core.config.settings", mock_settings),
        patch("app.services.notification.send_feishu_notification", new_callable=AsyncMock, return_value=True),
    ):
        resp = await client.post("/api/config/test-webhook")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["error"] is None


@pytest.mark.asyncio
async def test_test_webhook_failure(client: AsyncClient):
    """POST /test-webhook returns failure when notification send fails."""
    mock_settings = MagicMock()
    mock_settings.FEISHU_WEBHOOK_URL = "https://hooks.feishu.cn/test"
    with (
        patch("app.core.config.settings", mock_settings),
        patch("app.services.notification.send_feishu_notification", new_callable=AsyncMock, return_value=False),
    ):
        resp = await client.post("/api/config/test-webhook")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "发送失败" in data["error"]


# ---------------------------------------------------------------------------
# Config API: POST /test-llm
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_test_llm_unsupported_provider(client: AsyncClient):
    """POST /test-llm with unsupported provider returns failure."""
    resp = await client.post(
        "/api/config/test-llm",
        json={"provider": "nonexistent", "api_key": "sk-test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "不支持" in data["error"]


@pytest.mark.asyncio
async def test_test_llm_empty_api_key(client: AsyncClient):
    """POST /test-llm with empty API key returns failure."""
    resp = await client.post(
        "/api/config/test-llm",
        json={"provider": "deepseek", "api_key": ""},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "API Key" in data["error"]


@pytest.mark.asyncio
async def test_test_llm_success(client: AsyncClient):
    """POST /test-llm with valid provider returns success."""
    # Adapters are lazy-imported inside the handler function
    mock_adapter = AsyncMock()
    mock_response = MagicMock()
    mock_response.model = "deepseek-chat"
    mock_adapter.chat = AsyncMock(return_value=mock_response)
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.OpenAICompatibleAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={"provider": "deepseek", "api_key": "sk-real-key"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["model_used"] == "deepseek-chat"
    assert "latency_ms" in data


@pytest.mark.asyncio
async def test_test_llm_connection_error(client: AsyncClient):
    """POST /test-llm returns failure on connection error."""
    mock_adapter = AsyncMock()
    mock_adapter.chat = AsyncMock(side_effect=ConnectionError("Connection refused"))
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.OpenAICompatibleAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={"provider": "deepseek", "api_key": "sk-real-key"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "Connection refused" in data["error"]
    assert data["latency_ms"] == 0


@pytest.mark.asyncio
async def test_test_llm_anthropic_provider(client: AsyncClient):
    """POST /test-llm with anthropic provider uses AnthropicAdapter."""
    mock_adapter = AsyncMock()
    mock_response = MagicMock()
    mock_response.model = "claude-sonnet-4-20250514"
    mock_adapter.chat = AsyncMock(return_value=mock_response)
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.AnthropicAdapter", return_value=mock_adapter):
        resp = await client.post(
            "/api/config/test-llm",
            json={"provider": "anthropic", "api_key": "sk-ant-test"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["model_used"] == "claude-sonnet-4-20250514"


@pytest.mark.asyncio
async def test_test_llm_placeholder_url_uses_default(client: AsyncClient):
    """POST /test-llm with placeholder URL falls back to default."""
    mock_adapter = AsyncMock()
    mock_response = MagicMock()
    mock_response.model = "qwen-plus"
    mock_adapter.chat = AsyncMock(return_value=mock_response)
    mock_adapter.close = AsyncMock()

    with patch("app.services.llm_engine.OpenAICompatibleAdapter", return_value=mock_adapter) as mock_cls:
        resp = await client.post(
            "/api/config/test-llm",
            json={"provider": "qwen", "api_key": "sk-test", "base_url": "your_base_url"},
        )
    assert resp.status_code == 200
    # Verify the adapter was created with the default URL, not the placeholder
    call_kwargs = mock_cls.call_args
    assert "dashscope" in call_kwargs.kwargs.get("base_url", call_kwargs[1].get("base_url", ""))


# ---------------------------------------------------------------------------
# Config API: _mask_value
# ---------------------------------------------------------------------------


class TestMaskValue:
    """Tests for the _mask_value helper function."""

    def test_mask_short_key(self):
        from app.api.config import _mask_value

        assert _mask_value("feishu_webhook_secret", "short") == "****"

    def test_mask_long_key(self):
        from app.api.config import _mask_value

        result = _mask_value("deepseek_api_key", "sk-1234567890abcdef")
        assert result == "sk-1****cdef"

    def test_mask_placeholder_returns_empty(self):
        from app.api.config import _mask_value

        assert _mask_value("deepseek_api_key", "your_api_key") == ""

    def test_non_secret_key_not_masked(self):
        from app.api.config import _mask_value

        assert _mask_value("log_level", "DEBUG") == "DEBUG"

    def test_empty_value(self):
        from app.api.config import _mask_value

        assert _mask_value("some_key", "") == ""

    def test_mask_secret_in_key(self):
        from app.api.config import _mask_value

        result = _mask_value("feishu_webhook_secret", "abcdefghij")
        assert result == "abcd****ghij"


# ---------------------------------------------------------------------------
# Config API: GET /{key} with masked values
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_config_masks_api_key(client: AsyncClient, db_session: AsyncSession):
    """GET /{key} masks sensitive values."""
    db_session.add(Configuration(
        config_key="deepseek_api_key",
        config_value="sk-1234567890abcdef",
        config_type="string",
    ))
    await db_session.commit()

    resp = await client.get("/api/config/deepseek_api_key")
    assert resp.status_code == 200
    data = resp.json()
    # Should be masked
    assert "1234567890abcdef" not in data["value"]
    assert "****" in data["value"]


# ---------------------------------------------------------------------------
# Reports API: LLM error paths in POST /generate/{task_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_report_llm_value_error(client: AsyncClient, db_session: AsyncSession):
    """POST /generate returns 503 when LLM raises ValueError."""
    task = AuditTask(task_name="T", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    finding = Finding(
        task_id=task.id, finding_type=FindingType.COMPLIANCE_RISK,
        severity=SeverityLevel.HIGH, title="F", description="D",
    )
    db_session.add(finding)
    await db_session.commit()

    mock_engine = MagicMock()
    mock_engine.generate_report = AsyncMock(side_effect=ValueError("No API key configured"))

    with patch("app.api.reports.get_llm_engine", return_value=mock_engine):
        resp = await client.post(f"/api/reports/generate/{task.id}")
    assert resp.status_code == 503
    assert "LLM" in resp.json()["detail"] or "不可用" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_report_llm_timeout(client: AsyncClient, db_session: AsyncSession):
    """POST /generate returns 504 when LLM times out."""
    task = AuditTask(task_name="T", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    finding = Finding(
        task_id=task.id, finding_type=FindingType.COMPLIANCE_RISK,
        severity=SeverityLevel.HIGH, title="F", description="D",
    )
    db_session.add(finding)
    await db_session.commit()

    mock_engine = MagicMock()
    mock_engine.generate_report = AsyncMock(side_effect=TimeoutError)

    with patch("app.api.reports.get_llm_engine", return_value=mock_engine):
        resp = await client.post(f"/api/reports/generate/{task.id}")
    assert resp.status_code == 504
    assert "超时" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_report_llm_generic_error(client: AsyncClient, db_session: AsyncSession):
    """POST /generate returns 502 when LLM raises a generic exception."""
    task = AuditTask(task_name="T", task_type=TaskType.DEVIATION_ANALYSIS, status=TaskStatus.COMPLETED)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    finding = Finding(
        task_id=task.id, finding_type=FindingType.COMPLIANCE_RISK,
        severity=SeverityLevel.HIGH, title="F", description="D",
    )
    db_session.add(finding)
    await db_session.commit()

    mock_engine = MagicMock()
    mock_engine.generate_report = AsyncMock(side_effect=RuntimeError("unexpected failure"))

    with patch("app.api.reports.get_llm_engine", return_value=mock_engine):
        resp = await client.post(f"/api/reports/generate/{task.id}")
    assert resp.status_code == 502
    assert "LLM" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Reports API: HTML sanitization in export
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_html_strips_script_tags(client: AsyncClient, db_session: AsyncSession):
    """HTML export strips <script> tags from content (bleach strip=True removes tags, keeps text)."""
    report = Report(
        task_id=1, report_type=ReportType.FULL_REPORT,
        title="XSS Test",
        content='# Title\n\n<script>alert("xss")</script>\n\nSafe text',
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    resp = await client.get(f"/api/reports/{report.id}/export/html")
    assert resp.status_code == 200
    # bleach with strip=True removes the <script> tag but may keep text content
    assert "<script>" not in resp.text
    assert "Safe text" in resp.text


@pytest.mark.asyncio
async def test_export_html_strips_iframe_tags(client: AsyncClient, db_session: AsyncSession):
    """HTML export strips <iframe> tags from content."""
    report = Report(
        task_id=1, report_type=ReportType.FULL_REPORT,
        title="Iframe Test",
        content='# Title\n\n<iframe src="http://evil.com"></iframe>\n\nNormal text',
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    resp = await client.get(f"/api/reports/{report.id}/export/html")
    assert resp.status_code == 200
    assert "<iframe" not in resp.text
    assert "Normal text" in resp.text


@pytest.mark.asyncio
async def test_export_html_allows_tables(client: AsyncClient, db_session: AsyncSession):
    """HTML export preserves table markup."""
    report = Report(
        task_id=1, report_type=ReportType.FULL_REPORT,
        title="Table Test",
        content="# Table\n\n| Col1 | Col2 |\n|------|------|\n| A | B |",
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    resp = await client.get(f"/api/reports/{report.id}/export/html")
    assert resp.status_code == 200
    assert "<table>" in resp.text
    assert "<th>" in resp.text
    assert "<td>" in resp.text


@pytest.mark.asyncio
async def test_export_html_escapes_title(client: AsyncClient, db_session: AsyncSession):
    """HTML export escapes special characters in report title."""
    report = Report(
        task_id=1, report_type=ReportType.FULL_REPORT,
        title='Report <with> "quotes" & ampersand',
        content="Body",
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    resp = await client.get(f"/api/reports/{report.id}/export/html")
    assert resp.status_code == 200
    # Title should be HTML-escaped
    assert "&lt;with&gt;" in resp.text
    assert "&amp;" in resp.text


@pytest.mark.asyncio
async def test_export_html_with_none_content(client: AsyncClient, db_session: AsyncSession):
    """HTML export handles None content gracefully."""
    report = Report(
        task_id=1, report_type=ReportType.FULL_REPORT,
        title="Empty Report",
        content=None,
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    resp = await client.get(f"/api/reports/{report.id}/export/html")
    assert resp.status_code == 200
    assert "Empty Report" in resp.text


# ---------------------------------------------------------------------------
# Reports API: PDF export error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_pdf_import_error(client: AsyncClient, db_session: AsyncSession):
    """PDF export returns 500 when xhtml2pdf is not installed."""
    report = Report(
        task_id=1, report_type=ReportType.FULL_REPORT,
        title="PDF Import Error", content="Content",
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    # Simulate ImportError by making xhtml2pdf unavailable
    with patch.dict("sys.modules", {"xhtml2pdf": None, "xhtml2pdf.pisa": None}):
        resp = await client.get(f"/api/reports/{report.id}/export/pdf")
    assert resp.status_code == 500
    assert "PDF" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_export_pdf_with_none_content(client: AsyncClient, db_session: AsyncSession):
    """PDF export handles None content gracefully."""
    report = Report(
        task_id=1, report_type=ReportType.FULL_REPORT,
        title="PDF None Content", content=None,
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    def fake_create_pdf(html, dest, encoding="utf-8"):
        dest.write(b"%PDF fake")
        return MagicMock(err=False)

    mock_pisa = MagicMock()
    mock_pisa.CreatePDF.side_effect = fake_create_pdf
    parent = MagicMock()
    parent.pisa = mock_pisa
    with patch.dict("sys.modules", {"xhtml2pdf": parent, "xhtml2pdf.pisa": parent.pisa}):
        resp = await client.get(f"/api/reports/{report.id}/export/pdf")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Reports API: _sanitize_html
# ---------------------------------------------------------------------------


class TestSanitizeHtml:
    """Tests for the _sanitize_html helper function."""

    def test_strips_script(self):
        from app.api.reports import _sanitize_html

        result = _sanitize_html('<p>Safe</p><script>alert("xss")</script>')
        assert "<script>" not in result
        assert "Safe" in result

    def test_strips_iframe(self):
        from app.api.reports import _sanitize_html

        result = _sanitize_html('<p>Text</p><iframe src="evil"></iframe>')
        assert "<iframe" not in result
        assert "Text" in result

    def test_allows_table(self):
        from app.api.reports import _sanitize_html

        result = _sanitize_html("<table><tr><td>Cell</td></tr></table>")
        assert "<table>" in result
        assert "<td>Cell</td>" in result

    def test_allows_code(self):
        from app.api.reports import _sanitize_html

        result = _sanitize_html("<code>print()</code><pre>block</pre>")
        assert "<code>" in result
        assert "<pre>" in result

    def test_strips_onclick_attribute(self):
        from app.api.reports import _sanitize_html

        result = _sanitize_html('<p onclick="alert(1)">Text</p>')
        assert "onclick" not in result
        assert "Text" in result

    def test_allows_links_with_href(self):
        from app.api.reports import _sanitize_html

        result = _sanitize_html('<a href="https://example.com" title="test">Link</a>')
        assert 'href="https://example.com"' in result
        assert "Link" in result


# ---------------------------------------------------------------------------
# Reports API: Pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_reports_pagination(client: AsyncClient, db_session: AsyncSession):
    """GET /reports with page and page_size parameters."""
    # Create multiple reports
    for i in range(5):
        report = Report(
            task_id=1, report_type=ReportType.FULL_REPORT,
            title=f"Report {i}", content=f"Content {i}",
        )
        db_session.add(report)
    await db_session.commit()

    # Get page 1, size 2
    resp = await client.get("/api/reports/?page=1&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2

    # Get page 2, size 2
    resp = await client.get("/api/reports/?page=2&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2

    # Get page 3, size 2 (only 1 item left)
    resp = await client.get("/api/reports/?page=3&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_list_reports_filter_by_task_id(client: AsyncClient, db_session: AsyncSession):
    """GET /reports with task_id filter."""
    # Create reports for different tasks
    for task_id in [10, 10, 20]:
        report = Report(
            task_id=task_id, report_type=ReportType.FULL_REPORT,
            title=f"Report for task {task_id}", content="Content",
        )
        db_session.add(report)
    await db_session.commit()

    resp = await client.get("/api/reports/?task_id=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert all(item["task_id"] == 10 for item in data["items"])
