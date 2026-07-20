"""Query Rewrite Prompt 模板。"""


def build_rewrite_prompt(question: str, history: str) -> str:
    """构建问题改写 prompt。

    根据对话历史，将当前问题改写为可独立检索的完整问题。
    """
    return f"""根据对话历史，将用户当前问题改写为可独立检索的完整问题。

要求：
1. 消除代词歧义（如"它""这个"替换为具体指代）
2. 保留原问题意图，不增删信息
3. 直接输出改写后的问题，不要任何解释
4. 若原问题已完整无需改写，原样输出

【对话历史】
{history}

【当前问题】
{question}

【改写后问题】
"""
