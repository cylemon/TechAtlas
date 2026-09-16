from schemas.atlas import AtlasGenerateResponse

# 简单模拟规则过滤（仅用于测试流程，后续接 LLM）
NON_STEM_KEYWORDS = ["历史", "美食", "娱乐", "明星", "做饭", "配方"]


def validate_stem_domain(query: str) -> AtlasGenerateResponse:
    """
    检查用户输入是否符合 STEM 领域要求
    """
    for keyword in NON_STEM_KEYWORDS:
        if keyword in query:
            return AtlasGenerateResponse(
                is_valid_domain=False,
                query=query,
                reject_reason="TechAtlas 仅专注于 STEM（科学、技术、工程、数学）及认知心理学领域。",
            )

    return AtlasGenerateResponse(is_valid_domain=True, query=query, reject_reason=None)
