"""Multi-Query Retrieval Prompt 模板。

让 LLM 根据用户原问题生成多个语义等价但表述不同的变种问题，
分别检索后求并集再做 rerank，提升召回率。
"""


def build_multi_query_prompt(question: str, count: int = 3) -> str:
    """构建多查询生成 prompt。

    Args:
        question: 用户原始问题
        count: 需要生成的变种问题数
    """
    return f"""你是一个问题改写助手。请根据用户问题生成 {count} 个语义等价但表述不同的变种问题，用于多路检索提升召回率。

要求：
1. 每个变种问题单独一行，不要编号、不要解释、不要前后缀
2. 保持原问题核心意图，但使用不同的关键词和句式
3. 可以从不同角度表述（如同义词替换、句式变换、视角转换）
4. 不要生成与原问题完全相同的变种

【用户问题】
{question}

【变种问题】
"""
