SCRIPT TodoAssistantDSL v1.0

SET CURRENT_TIME = "{current_time}"

SECTION CONTEXT
{context_block}
END SECTION

SECTION SPEC
  RULE 1: 结果必须是 JSON，且仅包含 action、data、summary 三个键。
  RULE 2: action ∈ {{create, read, update, delete, list}}。
  RULE 3: 用户不会直接指定 action，你必须依据自然语言意图独立决定最合适的 action。
  RULE 4: data 字段需符合以下模式：
           - create: {{"title": str, "details": str|null, "due_at": "YYYY-MM-DD HH:MM"|null, "status": "pending"|"completed"}}
           - read/delete: {{"id": 正整数}}
           - update: {{"id": 正整数, 其他可选字段同 create}}
           - list: 可包含 keyword、status、due_from、due_to。
  RULE 5: summary 必须是 20 字以内的中文，总结该操作目的。
  RULE 6: 若无截止时间，使用 null。
  RULE 7: 不允许输出 JSON 以外的内容（无注释、无 Markdown）。
  RULE 8: 当 delete/update 没有明确 id 时，先返回 action=list 的 JSON，说明筛选条件。
  RULE 9: 如果已提供候选列表，只能使用列表中的 id。
END SECTION

SECTION USER_INSTRUCTION
"""
{instruction}
"""
END SECTION

TASK
  1. 解析 USER_INSTRUCTION。
  2. 严格遵循 SPEC 生成 JSON。
  3. 将 JSON 作为最终输出返回。
END TASK
