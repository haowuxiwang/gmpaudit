"""Tests for agent/tools/risk_matrix.py"""

from agent.tools.risk_matrix import calculate_risk_score, format_risk_summary


class TestCalculateRiskScore:
    """Test calculate_risk_score function."""

    def test_no_findings(self):
        """Empty findings returns (0, 'not_assessed')."""
        score, level = calculate_risk_score([])
        assert score == 0
        assert level == "not_assessed"

    def test_all_high_severity(self):
        """3 high findings: score=40, level='high'."""
        findings = [
            {"severity": "high"},
            {"severity": "high"},
            {"severity": "high"},
        ]
        score, level = calculate_risk_score(findings)
        assert score == 40  # 100 - (3*20)
        assert level == "high"

    def test_mixed_severity_with_high(self):
        """1 high + 2 medium + 1 low: score=55, level='high'."""
        findings = [
            {"severity": "high"},
            {"severity": "medium"},
            {"severity": "medium"},
            {"severity": "low"},
        ]
        score, level = calculate_risk_score(findings)
        assert score == 55  # 100 - (1*20 + 2*10 + 1*5)
        assert level == "high"

    def test_medium_majority(self):
        """0 high + 5 medium + 1 low: level='medium' (medium > 30% of total)."""
        findings = [
            {"severity": "medium"},
            {"severity": "medium"},
            {"severity": "medium"},
            {"severity": "medium"},
            {"severity": "medium"},
            {"severity": "low"},
        ]
        score, level = calculate_risk_score(findings)
        assert score == 45  # 100 - (5*10 + 1*5)
        assert level == "medium"

    def test_low_only(self):
        """3 low findings: score=85, level='low'."""
        findings = [
            {"severity": "low"},
            {"severity": "low"},
            {"severity": "low"},
        ]
        score, level = calculate_risk_score(findings)
        assert score == 85  # 100 - (3*5)
        assert level == "low"

    def test_score_floor_at_zero(self):
        """Extreme case: score doesn't go below 0."""
        findings = [{"severity": "high"}] * 10
        score, level = calculate_risk_score(findings)
        assert score == 0  # max(0, 100 - 200)
        assert level == "high"

    def test_missing_severity_field(self):
        """Findings without severity field treated as 'low' (not counted)."""
        findings = [
            {"title": "no severity"},
            {"severity": "high"},
        ]
        score, level = calculate_risk_score(findings)
        assert score == 80  # 100 - (1*20)
        assert level == "high"

    def test_medium_below_threshold(self):
        """Medium findings <= 30% of total: level='low'."""
        findings = [
            {"severity": "medium"},
            {"severity": "low"},
            {"severity": "low"},
            {"severity": "low"},
        ]
        score, level = calculate_risk_score(findings)
        assert score == 75  # 100 - (1*10 + 3*5)
        assert level == "low"


class TestFormatRiskSummary:
    """Test format_risk_summary function."""

    def test_no_findings(self):
        """Empty findings returns default message."""
        result = format_risk_summary([])
        assert result == "No findings identified."

    def test_single_high_finding(self):
        """Single high severity finding formatted correctly."""
        findings = [
            {
                "title": "Critical issue",
                "type": "compliance_risk",
                "severity": "high",
                "evidence": "Missing documentation",
            }
        ]
        result = format_risk_summary(findings)
        assert "Total findings: 1" in result
        assert "HIGH SEVERITY (1)" in result
        assert "Critical issue" in result
        assert "Missing documentation" in result

    def test_multiple_severity_levels(self):
        """All severity levels formatted."""
        findings = [
            {"title": "H1", "type": "t1", "severity": "high"},
            {"title": "M1", "type": "t2", "severity": "medium"},
            {"title": "L1", "type": "t3", "severity": "low"},
        ]
        result = format_risk_summary(findings)
        assert "Total findings: 3" in result
        assert "HIGH SEVERITY (1)" in result
        assert "MEDIUM SEVERITY (1)" in result
        assert "LOW SEVERITY (1)" in result

    def test_missing_fields_use_defaults(self):
        """Findings with missing fields use N/A defaults."""
        findings = [{"severity": "high"}]
        result = format_risk_summary(findings)
        assert "N/A" in result
        assert "Untitled" in result
