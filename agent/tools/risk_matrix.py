"""Risk matrix calculation for GMP audit findings."""


def calculate_risk_score(findings: list[dict]) -> tuple[int, str]:
    """Calculate overall risk score and level from findings.

    Args:
        findings: List of finding dicts with 'severity' field

    Returns:
        Tuple of (risk_score, risk_level)
    """
    if not findings:
        return 0, "not_assessed"

    high = sum(1 for f in findings if f.get("severity") in ("high", "critical"))
    medium = sum(1 for f in findings if f.get("severity") == "medium")
    low = sum(1 for f in findings if f.get("severity") == "low")

    # Score starts at 100, deduct per finding
    score = max(0, 100 - (high * 20 + medium * 10 + low * 5))

    if high > 0:
        level = "high"
    elif medium > len(findings) * 0.3:
        level = "medium"
    else:
        level = "low"

    return score, level


def format_risk_summary(findings: list[dict]) -> str:
    """Format findings into a readable summary grouped by severity."""
    if not findings:
        return "No findings identified."

    high = [f for f in findings if f.get("severity") in ("high", "critical")]
    medium = [f for f in findings if f.get("severity") == "medium"]
    low = [f for f in findings if f.get("severity") == "low"]

    lines = [f"Total findings: {len(findings)}"]
    for label, group in [("HIGH SEVERITY", high), ("MEDIUM SEVERITY", medium), ("LOW SEVERITY", low)]:
        if group:
            lines.append(f"\n{label} ({len(group)})")
            for f in group:
                title = f.get("title", "Untitled")
                ftype = f.get("type", "N/A")
                lines.append(f"  - [{ftype}] {title}")
                evidence = f.get("evidence", "")
                if evidence:
                    lines.append(f"    Evidence: {evidence}")

    return "\n".join(lines)
