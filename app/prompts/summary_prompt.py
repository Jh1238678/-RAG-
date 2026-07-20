"""摘要 Prompt 模板。"""


def build_summary_prompt(text: str) -> str:
    """构建单段摘要 prompt。"""
    return f"""请为以下文档内容生成结构化摘要。

要求：
1. 总字数控制在 300-500 字
2. 按"核心主题""关键要点""适用场景"三部分组织
3. 关键要点用分点列出，每点不超过 30 字
4. 不添加文档中没有的信息

【文档内容】
{text}

【结构化摘要】
"""


def build_reduce_prompt(combined_summaries: str) -> str:
    """构建 reduce 阶段 prompt：合并多段摘要。"""
    return f"""以下是一篇长文档各分段摘要的汇总。请将它们整合为一篇完整的结构化摘要。

要求：
1. 总字数控制在 500-800 字
2. 按"核心主题""关键要点""适用场景"三部分组织
3. 去除重复信息，保留各段要点
4. 不添加原文档中没有的信息

【各段摘要汇总】
{combined_summaries}

【最终摘要】
"""
