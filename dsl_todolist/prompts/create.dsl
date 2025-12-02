SCRIPT TodoCreatePlan v1.0

SET CURRENT_TIME = "{current_time}"

SECTION CONTEXT
{context_block}
END SECTION

SECTION USER_INSTRUCTION
"""
{instruction}
"""
END SECTION

SECTION SPEC
  RULE 1: 输出 JSON 必须包含 action、data、summary。
  RULE 2: action 固定为 "create"。
  RULE 3: data 需要给出 title、details、due_at、status，其中 details 与 due_at 可为 null，status ∈ {{"pending", "completed"}}，默认 "pending"。
  RULE 4: 若用户未提供截止时间，due_at= null；若提供相对时间，基于 CURRENT_TIME 解析为 YYYY-MM-DD HH:MM。
  RULE 5: summary 为 20 字以内中文，概括创建目标。
  RULE 6: 不得输出 JSON 之外任何字符（无 Markdown、无注释）。
END SECTION

TASK
  1. 解析 USER_INSTRUCTION。
  2. 根据 SPEC 构造 create 操作 JSON。
  3. 返回 JSON 作为最终输出。
END TASK
