SCRIPT TodoDeleteStage1 v1.0

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
  RULE 2: 如果用户指明了唯一 id，则 action="delete" 且 data={{"id": 正整数}}。
  RULE 3: 若无法确定 id，action 必须为 "list"，并基于用户描述提供 keyword/status/due_from/due_to 等筛选条件，以便后续查询。
  RULE 4: summary 为 20 字以内中文，描述当前步骤目的（如“筛选可能的待办”或“删除目标已确认”）。
  RULE 5: 禁止输出 JSON 以外内容。
END SECTION

TASK
  1. 解析 USER_INSTRUCTION。
  2. 判断当前能否直接删除。
  3. 生成符合 SPEC 的 JSON。
END TASK
