import logging
from typing import List, Dict, Any
from dataclasses import dataclass

from app.services.llm_engine import get_llm_engine

logger = logging.getLogger(__name__)

@dataclass
class AuditConfig:
    check_logic_flaws: bool = True
    check_compliance: bool = True
    check_consistency: bool = True
    check_missing_info: bool = True
    risk_threshold: str = "medium"
    max_findings: int = 50

class AuditEngine:
    def __init__(self):
        self.llm = get_llm_engine()

    async def analyze_deviation(self, document: str, config: AuditConfig) -> List[Dict[str, Any]]:
        prompt = """你是一个资深的GMP审计员。请分析以下偏差报告，识别：

1. 逻辑漏洞：偏差原因分析是否合理、调查过程是否完整、根本原因是否明确
2. 合规性风险：是否符合GMP要求、CAPA措施是否充分、是否有遗漏的关键步骤
3. 不一致之处：描述与结论是否一致、时间线是否合理、数据引用是否准确

请以JSON格式输出发现，每个发现包含：type, severity, title, description, evidence, suggestion"""

        response = await self.llm.analyze(document, prompt)
        return self._parse_findings(response.content)

    async def analyze_sop(self, document: str, config: AuditConfig) -> List[Dict[str, Any]]:
        prompt = """你是一个资深的GMP审计员。请分析以下SOP文档，检查：

1. SOP完整性：是否包含所有必要的步骤、职责分工是否明确、是否有关键控制点
2. 合规性检查：是否符合GMP要求、是否有法规引用、是否有版本控制
3. 可执行性：步骤是否清晰可执行、是否有歧义描述、是否有缺失的资源说明

请以JSON格式输出发现，每个发现包含：type, severity, title, description, location, suggestion"""

        response = await self.llm.analyze(document, prompt)
        return self._parse_findings(response.content)

    async def check_consistency(self, documents: List[str], config: AuditConfig) -> List[Dict[str, Any]]:
        if len(documents) < 2:
            return []

        docs_text = "\n\n---\n\n".join([f"文档{i+1}:\n{doc[:2000]}" for i, doc in enumerate(documents)])

        prompt = f"""你是一个资深的GMP审计员。请检查以下文档之间的一致性：

{docs_text}

检查要点：逻辑一致性、时间一致性、数据一致性、流程一致性

请以JSON格式输出发现，每个发现包含：type, severity, title, description, evidence, suggestion"""

        response = await self.llm.analyze(docs_text, prompt)
        return self._parse_findings(response.content)

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
            "score": max(0, 100 - (high_count * 20 + medium_count * 10 + low_count * 5))
        }

    def _parse_findings(self, content: str) -> List[Dict[str, Any]]:
        import json
        import re

        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return [{
            "type": "logic_flaw",
            "severity": "medium",
            "title": "需要人工审核",
            "description": content[:500],
            "evidence": "",
            "suggestion": "请人工审核此内容"
        }]

audit_engine = None

def get_audit_engine() -> AuditEngine:
    global audit_engine
    if audit_engine is None:
        audit_engine = AuditEngine()
    return audit_engine
