SCRIPT TodoListPlan v1.0

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
  RULE 2: action 固定为 "list"。
  RULE 3: data 可包含 keyword、status、due_from、due_to，缺失字段不可乱填，保留与用户请求相关的过滤条件。
  RULE 4: 若包含 due_from/due_to，应转换为 YYYY-MM-DD HH:MM；若无具体时间，则省略这些字段。
  RULE 5: summary 限 20 字中文，概括筛选目的。
  RULE 6: 禁止输出 JSON 以外内容。
END SECTION

TASK
  1. 读取 USER_INSTRUCTION。
  2. 根据 SPEC 生成 list 操作 JSON。
  3. 输出 JSON。
END TASK
