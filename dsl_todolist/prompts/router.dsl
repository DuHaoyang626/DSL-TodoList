SCRIPT TodoActionRouter v1.0

SET CURRENT_TIME = "{current_time}"

SECTION USER_INSTRUCTION
{instruction}
END SECTION

SECTION CONTEXT
{context_block}
END SECTION

SECTION SPEC
  RULE 1: 你必须根据用户自然语言意图推断最合适的操作类型。
  RULE 2: 可选操作集合为 {{create, update, delete, list}}。
  RULE 3: 输出 JSON 必须严格为 {{"action": "<operation>"}}，不包含其他键或文本。
  RULE 4: 当用户提出泛查询（如“查看/显示/列出”但未给出具体 ID）时，请选择 list。
  RULE 5: 只有当用户明确提供了 ID 或“第 X 条”等唯一定位信息时，才能选择 read。
  RULE 6: 当用户想新增事项，选择 create；想修改内容，选择 update；想删除事项，选择 delete。
  RULE 7: 如果上下文给出硬性指示，必须服从 CONTEXT 的约束。
  RULE 8: 如果输入明显是无意义的文字（如随机字符、垃圾文本或无法理解的短语），请输出 {{"action": "noop"}}。
END SECTION

TASK
  1. 阅读 USER_INSTRUCTION 与 CONTEXT。
  2. 选择一个满足 SPEC 的操作类型。
  3. 仅输出符合 RULE 3 的 JSON。
END TASK
