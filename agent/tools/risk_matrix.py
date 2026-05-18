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

    high = sum(1 for f in findings if f.get("severity") == "high")
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
    """Format findings into a readable summary.

    Args:
        findings: List of finding dicts

    Returns:
        Formatted summary string
    """
    if not findings:
        return "No findings identified."

    high = [f for f in findings if f.get("severity") == "high"]
    medium = [f for f in findings if f.get("severity") == "medium"]
    low = [f for f in findings if f.get("severity") == "low"]

    parts = [f"Total findings: {len(findings)}"]

    if high:
        parts.append(f"\n--- HIGH SEVERITY ({len(high)}) ---")
        for f in high:
            parts.append(f"  [{f.get('type', 'N/A')}] {f.get('title', 'Untitled')}")
            parts.append(f"    Evidence: {f.get('evidence', 'N/A')}")

    if medium:
        parts.append(f"\n--- MEDIUM SEVERITY ({len(medium)}) ---")
        for f in medium:
            parts.append(f"  [{f.get('type', 'N/A')}] {f.get('title', 'Untitled')}")

    if low:
        parts.append(f"\n--- LOW SEVERITY ({len(low)}) ---")
        for f in low:
            parts.append(f"  [{f.get('type', 'N/A')}] {f.get('title', 'Untitled')}")

    return "\n".join(parts)
