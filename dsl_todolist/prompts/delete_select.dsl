SCRIPT TodoDeleteStage2 v1.0

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
  RULE 1: CONTEXT 会提供 list_request 与 candidates（JSON 数组）。你只能从 candidates 里选择 id。
  RULE 2: 输出 JSON 必须包含 action、data、summary，且 action 固定为 "delete"。
  RULE 3: data 仅包含 {{"id": 正整数}}，不得添加其他键。
  RULE 4: summary 为 20 字以内中文，说明删除目标。
  RULE 5: 禁止输出 JSON 以外内容。
END SECTION

TASK
  1. 阅读 CONTEXT 了解候选列表。
  2. 结合 USER_INSTRUCTION 选择最匹配的候选 id。
  3. 输出符合 SPEC 的 delete 操作 JSON。
END TASK
