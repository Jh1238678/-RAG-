"""答案支持性校验（Verifier）Prompt 模板。

判断生成答案是否被检索证据充分支持，返回 supported / partial / unsupported。
配合 JSON Mode 使用，强制模型输出结构化 JSON。
"""

SYSTEM_PROMPT = """你是一个答案校验器。

你的任务是判断"回答"是否被"参考上下文"充分支持。

判定规则：
1. 如果回答中的主要结论都能从上下文中找到依据，输出 supported。
2. 如果回答部分被支持，但包含额外推断、扩展或无法证明的信息，输出 partial。
3. 如果回答的主要内容无法从上下文中得到，输出 unsupported。
4. 不要重新回答用户问题，只做判定和理由说明。

你必须严格输出 JSON 格式，不要输出任何其他内容、不要使用 markdown 代码块。
JSON schema：
{
  "verdict": "supported | partial | unsupported",
  "reason": "简要说明判定理由",
  "unsupported_spans": ["不被支持的表述1", "表述2"]
}"""


def build_user_prompt(context: str, answer: str) -> str:
    """构建答案校验 user prompt。

    Args:
        context: 检索到的参考上下文（已带来源标记）
        answer: 待校验的回答
    """
    return f"""【参考上下文】
{context}

【回答】
{answer}

请输出 JSON：包含 verdict（supported/partial/unsupported）、reason（理由）、unsupported_spans（不被支持的表述列表，没有则空数组）。"""
