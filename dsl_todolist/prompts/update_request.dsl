SCRIPT TodoUpdateStage1 v1.0

SET CURRENT_TIME = "{current_time}"

SECTION USER_INSTRUCTION
"""
{instruction}
"""
END SECTION

SECTION CONTEXT
{context_block}
END SECTION

SECTION SPEC
  RULE 1: 输出 JSON 必须包含 action、data、summary。
  RULE 2: 如果用户已提供明确 id，则 action="update"，data 至少包含 id，且根据需求填入 title/details/due_at/status 中需要修改的字段。
  RULE 3: 若无法确定 id，则 action 必须为 "list"，根据描述给出筛选条件，以便下一步锁定候选。
  RULE 4: summary 控制在 20 字以内，描述当前步骤目的。
  RULE 5: 若需要调整截止时间，将相对时间换算为 YYYY-MM-DD HH:MM。
  RULE 6: 禁止输出 JSON 以外内容。
END SECTION

TASK
  1. 解析 USER_INSTRUCTION。
  2. 判断能否直接构造 update 操作。
  3. 生成符合 SPEC 的 JSON。
END TASK
