"""Fallback regulation database using hardcoded GMP knowledge.

Fallback when LightRAG knowledge graph is unavailable.
Contains key Chinese GMP (2010) regulation excerpts.
"""

# Key GMP regulation clauses for common audit scenarios
GMP_REGULATIONS = [
    # --- 第二章 质量管理 ---
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
    # --- 第三章 机构与人员 ---
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第三章 机构与人员",
        "article": "第十六条",
        "title": "关键人员资质",
        "content": "企业负责人、生产管理负责人、质量管理负责人、质量受权人应当具有相应的专业知识和实践经验。生产管理负责人和质量管理负责人不得互相兼任。",
    },
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第三章 机构与人员",
        "article": "第二十六条",
        "title": "人员培训",
        "content": "企业应当对人员进行上岗前培训和继续培训，培训内容应当与岗位要求相适应。高风险操作区（如洁净区）的工作人员应当接受专门的培训。培训应当有记录。",
    },
    # --- 第四章 厂房与设施 ---
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第四章 厂房与设施",
        "article": "第三十八条",
        "title": "洁净区级别",
        "content": "洁净区的设计应当符合相应的洁净级别要求。A级为高风险操作区，B级为无菌配制和灌装的背景区域，C级和D级为非无菌药品生产的关键区域。不同级别洁净区之间应当有适当的压差梯度。",
    },
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第四章 厂房与设施",
        "article": "第四十二条",
        "title": "人流物流分开",
        "content": "厂房应当有适当的照明、温度、湿度和通风，生产区和储存区应当有足够的空间有序地存放设备、物料、中间产品和成品。人流和物流应当合理分开，避免交叉污染。",
    },
    # --- 第五章 设备 ---
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第五章 设备",
        "article": "第七十九条",
        "title": "设备维护",
        "content": "设备应当按照操作规程进行使用、清洁和维护。设备的维护和维修应当有记录。关键设备应当进行确认和验证。",
    },
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第五章 设备",
        "article": "第七十五条",
        "title": "设备清洁",
        "content": "设备的清洁应当按照经过验证的清洁规程进行。清洁规程应当明确规定清洁方法、清洁剂、清洁频率和清洁验证要求。设备清洁后应当有状态标识。",
    },
    # --- 第六章 物料与产品 ---
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第六章 物料与产品",
        "article": "第一百零三条",
        "title": "物料接收",
        "content": "物料接收时应当检查供应商的检验报告和合格证。物料应当有明确的标识，包括名称、批号、数量、供应商、接收日期和有效期。不合格物料应当有明确的标识和隔离存放。",
    },
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第六章 物料与产品",
        "article": "第一百一十条",
        "title": "不合格品管理",
        "content": "不合格的物料、中间产品、待包装产品和成品应当有明确的标识，并存放在限制进入的区域。不合格品的处理应当经过质量管理部门的批准，并有记录。",
    },
    # --- 第七章 确认与验证 ---
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第七章 确认与验证",
        "article": "第一百三十八条",
        "title": "验证总计划",
        "content": "企业应当制定验证总计划，包括验证策略、组织机构、职责分工、验证项目、时间安排等。验证状态应当定期回顾。",
    },
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第七章 确认与验证",
        "article": "第一百三十九条",
        "title": "工艺验证",
        "content": "工艺验证应当证明工艺在预定参数范围内运行时，能够持续生产出符合预定用途和注册要求的产品。工艺验证应当采用经验证的检验方法。",
    },
    # --- 第八章 文件管理 ---
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
    # --- 第九章 生产管理 ---
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第九章 生产管理",
        "article": "第一百八十九条",
        "title": "防止污染和交叉污染",
        "content": "生产过程中应当采取措施防止污染和交叉污染。不同品种、规格的药品生产操作不得在同一生产操作间同时进行。生产区域应当有适当的清洁和消毒程序。",
    },
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第九章 生产管理",
        "article": "第二百零一条",
        "title": "物料平衡",
        "content": "每批产品完成后应当进行物料平衡计算。物料平衡应当在规定的限度内。超出限度的偏差应当进行调查。物料平衡是批记录审核的重要内容。",
    },
    # --- 第十章 质量控制与质量保证 ---
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第十章 质量控制与质量保证",
        "article": "第二百二十三条",
        "title": "QC职责",
        "content": "质量控制实验室的职责包括：取样、检验、稳定性考察、标准品管理、环境监测、偏差调查等。质量控制实验室应当有适当的操作规程和记录。",
    },
    # --- 第十三章 投诉与不良反应报告 ---
    {
        "regulation": "中国GMP（2010年修订版）",
        "chapter": "第十三章 投诉与不良反应报告",
        "article": "第二百六十三条",
        "title": "投诉处理",
        "content": "企业应当建立投诉处理程序，指定专人负责投诉的调查和处理。所有投诉都应当有记录，并进行评价。需要调查的投诉应当及时调查，并采取相应的纠正和预防措施。",
    },
    # --- ICH ---
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


def _tokenize_chinese(text: str) -> list[str]:
    """Tokenize Chinese text using jieba, with fallback to character bigrams."""
    try:
        import jieba

        return [w for w in jieba.cut(text) if len(w.strip()) > 1]
    except ImportError:
        # Fallback: character bigrams for Chinese, split by space for others
        tokens = []
        for part in text.split():
            if len(part) > 1:
                # Add the full part and character bigrams
                tokens.append(part)
                for i in range(len(part) - 1):
                    tokens.append(part[i : i + 2])
        return tokens


def search_regulations(query: str, n_results: int = 5) -> list[dict]:
    """Search regulations by keyword matching with Chinese tokenization.

    Args:
        query: Search query
        n_results: Max results to return

    Returns:
        List of matching regulation dicts
    """
    query_lower = query.lower()
    keywords = _tokenize_chinese(query_lower)

    scored = []
    for reg in GMP_REGULATIONS:
        text = f"{reg['chapter']} {reg['title']} {reg['content']}".lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, reg))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [reg for _, reg in scored[:n_results]]
