"""Shared fixtures for agent tests."""

import pytest


@pytest.fixture
def sample_state():
    """Standard AuditState for agent node tests."""
    return {
        "document_content": "Test document content about GMP deviation handling.",
        "document_name": "test_deviation.txt",
        "document_type": "deviation",
        "audit_focus": "GMP compliance",
        "next_agent": "",
        "supervisor_reasoning": "",
        "matched_regulations": [],
        "regulation_summary": "",
        "regulation_checked": False,
        "findings": [],
        "risk_score": 0,
        "risk_level": "",
        "risk_assessed": False,
        "report_markdown": "",
        "report_path": "",
        "report_generated": False,
        "messages": [],
        "iteration": 0,
        "status": "",
    }


@pytest.fixture
def sample_findings():
    """Sample findings with mixed severity levels."""
    return [
        {
            "title": "Missing deviation record",
            "description": "No deviation record found for batch B2024001",
            "type": "compliance_risk",
            "severity": "high",
            "evidence": "Batch record review shows no deviation documentation",
            "suggestion": "Implement deviation tracking system",
        },
        {
            "title": "Incomplete CAPA documentation",
            "description": "CAPA form missing root cause analysis",
            "type": "missing_info",
            "severity": "medium",
            "evidence": "CAPA-2024-001 lacks root cause section",
            "suggestion": "Complete root cause analysis for all CAPAs",
        },
        {
            "title": "Minor formatting issue",
            "description": "Date format inconsistent in batch record",
            "type": "best_practice",
            "severity": "low",
            "evidence": "Page 3 uses MM/DD/YYYY, page 5 uses YYYY-MM-DD",
            "suggestion": "Standardize date format across all documents",
        },
    ]


@pytest.fixture
def sample_regulations():
    """Sample regulation entries for testing."""
    return [
        {
            "regulation": "中国GMP（2010年修订版）",
            "chapter": "第二章 质量管理",
            "article": "第十条",
            "title": "偏差处理",
            "content": "企业应当建立偏差处理程序。任何偏差都应当记录并说明。",
        },
        {
            "regulation": "中国GMP（2010年修订版）",
            "chapter": "第二章 质量管理",
            "article": "第十一条",
            "title": "变更控制",
            "content": "企业应当建立变更控制系统，对可能影响产品质量的变更进行评估和管理。",
        },
    ]


@pytest.fixture
def sample_llm_response():
    """Sample LLM JSON response for mocking."""
    return [
        {
            "title": "Test finding",
            "description": "Test description",
            "type": "compliance_risk",
            "severity": "medium",
            "evidence": "Test evidence",
            "suggestion": "Test suggestion",
        }
    ]
