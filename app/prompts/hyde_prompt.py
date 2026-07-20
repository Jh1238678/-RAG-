"""HyDE（Hypothetical Document Embeddings）Prompt 模板。

让 LLM 先根据问题生成一个假设性答案（无需真实依据），
再用该假设性答案的 embedding 去检索真实文档，
通常能大幅提升语义命中准确率。
"""


def build_hyde_prompt(question: str) -> str:
    """构建 HyDE 假设性答案生成 prompt。

    Args:
        question: 用户原始问题
    """
    return f"""请针对以下问题写一段 200-400 字的假设性答案。不需要真实依据，可以基于常识推测。
这段答案将用于向量检索，目的是让检索系统能找到相关真实文档。

要求：
1. 直接输出答案正文，不要解释、不要前后缀
2. 使用与问题相关的专业术语和表达
3. 内容连贯，像一段真实的文档片段

【问题】
{question}

【假设性答案】
"""
