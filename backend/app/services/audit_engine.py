import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class AuditEngine:
    async def assess_risk(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        high_count = sum(1 for f in findings if f.get("severity") == "high")
        medium_count = sum(1 for f in findings if f.get("severity") == "medium")
        low_count = sum(1 for f in findings if f.get("severity") == "low")
        total = len(findings)

        if high_count > 0:
            risk_level = "high"
        elif medium_count > total * 0.3:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "risk_level": risk_level,
            "total_findings": total,
            "high_risk": high_count,
            "medium_risk": medium_count,
            "low_risk": low_count,
            "score": max(0, 100 - (high_count * 20 + medium_count * 10 + low_count * 5)),
        }


audit_engine = None


def get_audit_engine() -> AuditEngine:
    global audit_engine
    if audit_engine is None:
        audit_engine = AuditEngine()
    return audit_engine
