"""Fallback regulation database using hardcoded GMP knowledge.

This is the Phase 2 fallback before GraphRAG integration.
Contains key Chinese GMP (2010) regulation excerpts.
"""

# Key GMP regulation clauses for common audit scenarios
GMP_REGULATIONS = [
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第二章 质量管理",
        "article": "第四条",
        "title": "质量保证",
        "content": "企业应当建立并实施质量保证体系，确保药品按照批准的工艺规程和质量标准进行生产和控制。质量保证体系应当确保：药品的设计与开发符合GMP要求；生产和控制活动有明确规定；管理职责被明确规定；安排了原材料、中间产品和成品的检测；按照要求完成了生产过程中各步骤；药品未经质量控制部门放行不得发运或使用；每批药品的生产和质量控制记录可追溯。",
    },
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第二章 质量管理",
        "article": "第十条",
        "title": "偏差处理",
        "content": "企业应当建立偏差处理程序。任何偏差都应当记录并说明。重大偏差应当进行调查，调查及其结论应当形成文件。偏差调查应当包括对产品质量影响的评估。",
    },
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第二章 质量管理",
        "article": "第十一条",
        "title": "变更控制",
        "content": "企业应当建立变更控制系统，对可能影响产品质量的变更进行评估和管理。变更实施前应当经过评估、批准。变更实施后应当进行评价，确认变更达到了预期目标。",
    },
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第二章 质量管理",
        "article": "第十二条",
        "title": "纠正和预防措施",
        "content": "企业应当建立纠正和预防措施（CAPA）系统。纠正措施应当消除已发现的不符合项的原因。预防措施应当消除潜在不符合项的原因。CAPA的方法应当与问题的严重程度相适应。",
    },
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第八章 文件管理",
        "article": "第一百五十条",
        "title": "文件要求",
        "content": "文件应当涵盖质量标准、生产处方和工艺规程、操作规程和记录等。文件的制定、修订、审核和批准应当有明确规定。文件应当定期审查和修订。",
    },
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第八章 文件管理",
        "article": "第一百五十五条",
        "title": "批记录",
        "content": "每批药品应当有批生产记录和批检验记录。批记录应当真实、完整，反映生产全过程。批记录应当由生产部门填写，质量控制部门审核。",
    },
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第七章 确认与验证",
        "article": "第一百三十八条",
        "title": "验证总计划",
        "content": "企业应当制定验证总计划，包括验证策略、组织机构、职责分工、验证项目、时间安排等。验证状态应当定期回顾。",
    },
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第五章 设备",
        "article": "第七十九条",
        "title": "设备维护",
        "content": "设备应当按照操作规程进行使用、清洁和维护。设备的维护和维修应当有记录。关键设备应当进行确认和验证。",
    },
    {
        "regulation": "ICH Q9",
        "chapter": "质量风险管理",
        "article": "第3节",
        "title": "质量风险管理流程",
        "content": "质量风险管理流程包括：风险评估（风险识别、风险分析、风险评价）、风险控制（风险降低、风险接受）、风险回顾。风险管理工具包括FMEA、FTA、HACCP等。",
    },
    {
        "regulation": "ICH Q10",
        "chapter": "药品质量体系",
        "article": "第3.2节",
        "title": "CAPA系统",
        "content": "CAPA系统应当使用调查方法确定根本原因。应当采取措施防止偏差再次发生。CAPA的有效性应当进行验证。CAPA系统应当与知识管理系统相结合。",
    },
]


def search_regulations(query: str, n_results: int = 5) -> list[dict]:
    """Search regulations by keyword matching.

    Simple fallback before GraphRAG integration.

    Args:
        query: Search query
        n_results: Max results to return

    Returns:
        List of matching regulation dicts
    """
    query_lower = query.lower()
    keywords = [kw.strip() for kw in query_lower.split() if len(kw.strip()) > 1]

    scored = []
    for reg in GMP_REGULATIONS:
        text = f"{reg['chapter']} {reg['title']} {reg['content']}".lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, reg))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [reg for _, reg in scored[:n_results]]
