"""Tests for report export endpoints (HTML and PDF)."""

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report, ReportType


def _make_xhtml2pdf_mock(create_pdf_side_effect=None, create_pdf_return=None):
    """Build a pair of (parent_mock, pisa_mock) for sys.modules injection."""
    mock_pisa = MagicMock()
    if create_pdf_side_effect:
        mock_pisa.CreatePDF.side_effect = create_pdf_side_effect
    elif create_pdf_return:
        mock_pisa.CreatePDF.return_value = create_pdf_return
    parent = MagicMock()
    parent.pisa = mock_pisa
    return parent, mock_pisa


@pytest.fixture
async def sample_report(db_session: AsyncSession) -> Report:
    report = Report(
        task_id=1,
        report_type=ReportType.FULL_REPORT,
        title="Test Export Report",
        content="# Test\n\nThis is a **test** report.\n\n| Item | Value |\n|------|-------|\n| A | 1 |",
        report_metadata={"report_source": "agent_report_writer"},
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    return report


@pytest.mark.asyncio
async def test_export_html_success(client: AsyncClient, sample_report: Report):
    response = await client.get(f"/api/reports/{sample_report.id}/export/html")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Test Export Report" in response.text
    assert "<strong>test</strong>" in response.text


@pytest.mark.asyncio
async def test_export_html_not_found(client: AsyncClient):
    response = await client.get("/api/reports/99999/export/html")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_export_pdf_success(client: AsyncClient, sample_report: Report):
    def fake_create_pdf(html, dest, encoding="utf-8"):
        dest.write(b"%PDF-1.4 fake pdf content")
        return MagicMock(err=False)

    parent, _ = _make_xhtml2pdf_mock(create_pdf_side_effect=fake_create_pdf)
    with patch.dict("sys.modules", {"xhtml2pdf": parent, "xhtml2pdf.pisa": parent.pisa}):
        response = await client.get(f"/api/reports/{sample_report.id}/export/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers.get("content-disposition", "")
    assert response.content == b"%PDF-1.4 fake pdf content"


@pytest.mark.asyncio
async def test_export_pdf_not_found(client: AsyncClient):
    response = await client.get("/api/reports/99999/export/pdf")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_export_pdf_generation_error(client: AsyncClient, sample_report: Report):
    parent, _ = _make_xhtml2pdf_mock(create_pdf_return=MagicMock(err=True))
    with patch.dict("sys.modules", {"xhtml2pdf": parent, "xhtml2pdf.pisa": parent.pisa}):
        response = await client.get(f"/api/reports/{sample_report.id}/export/pdf")

    assert response.status_code == 500
    assert "PDF" in response.json()["detail"]


@pytest.mark.asyncio
async def test_export_pdf_content_disposition_filename(client: AsyncClient, sample_report: Report):
    def fake_create_pdf(html, dest, encoding="utf-8"):
        dest.write(b"%PDF")
        return MagicMock(err=False)

    parent, _ = _make_xhtml2pdf_mock(create_pdf_side_effect=fake_create_pdf)
    with patch.dict("sys.modules", {"xhtml2pdf": parent, "xhtml2pdf.pisa": parent.pisa}):
        response = await client.get(f"/api/reports/{sample_report.id}/export/pdf")

    disposition = response.headers.get("content-disposition", "")
    assert "Test_Export_Report.pdf" in disposition
