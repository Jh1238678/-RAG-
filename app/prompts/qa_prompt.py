"""问答 Prompt 模板。"""

QA_SYSTEM = "你是一个严谨的文档问答助手。请严格根据下方【参考资料】回答用户问题。"


def build_qa_prompt(question: str, context: str, history: str = "") -> str:
    """构建问答 prompt。

    Args:
        question: 用户当前问题
        context: 检索到的参考资料（已带来源标记）
        history: 对话历史文本（可为空）
    """
    history_section = history if history else "（无历史对话）"

    return f"""请严格根据下方【参考资料】回答用户问题。

规则：
1. 只能基于参考资料作答，不得编造或使用资料外的知识
2. 若参考资料不足以回答，请明确说"根据现有文档无法回答该问题"
3. 回答时在相关句末标注来源，格式：[来源: 文档名 第X页]
4. 若多个来源信息冲突，请分别说明
5. 回答使用中文，条理清晰

【参考资料】
{context}

【对话历史】
{history_section}

【用户问题】
{question}

【回答】
"""
