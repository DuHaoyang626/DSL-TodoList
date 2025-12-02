SCRIPT TodoReadPlan v1.0

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
  RULE 2: action 固定为 "read"。
  RULE 3: data 仅包含 {{"id": 正整数}}；如果无法确定 id，说明路由阶段就不该选择 read（因此视为不会发生）。
  RULE 4: summary 为 20 字以内中文。
  RULE 5: 禁止输出 JSON 以外内容。
END SECTION

TASK
  1. 分析 USER_INSTRUCTION。
  2. 根据 SPEC 生成 read 操作 JSON。
  3. 输出 JSON。
END TASK
