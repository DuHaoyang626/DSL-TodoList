SCRIPT TodoUpdateStage2 v1.0

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
  RULE 1: CONTEXT 提供 list_request 与 candidates（JSON 数组），只能在 candidates 中选择 id。
  RULE 2: 输出 JSON 必须包含 action、data、summary，且 action 固定为 "update"。
  RULE 3: data 必须包含 {{"id": 正整数}}，并根据 USER_INSTRUCTION 提及的修改项，补充 title/details/due_at/status 中需要更新的字段；未提及的字段不要修改。
  RULE 4: 若涉及时间，请转换为 YYYY-MM-DD HH:MM。
  RULE 5: summary 控制在 20 字以内，概括更新内容。
  RULE 6: 禁止输出 JSON 以外内容。
END SECTION

TASK
  1. 结合 CONTEXT 与 USER_INSTRUCTION，确定最匹配的候选 id。
  2. 提取用户想修改的字段。
  3. 输出符合 SPEC 的 update 操作 JSON。
END TASK
