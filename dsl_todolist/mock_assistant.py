"""A lightweight mock assistant that produces deterministic operations.

This can be used during UI testing to avoid calling the real LLM.
The mock assistant will call whichever API handler is available (mock_api if present,
otherwise the real `dsl_todolist.api.handle_json_request`) when `apply_changes=True`.
"""
from __future__ import annotations

import json
from typing import Any, Dict

try:
    # Prefer the mock API if available
    from . import mock_api as api_module
except Exception:
    from . import api as api_module

try:
    from .assistant import AssistantResult
except Exception:  # pragma: no cover - defensive
    # fallback simple structure if import fails
    from dataclasses import dataclass

    @dataclass
    class AssistantResult:
        operation: Dict[str, Any]
        summary: str
        api_response: Dict[str, Any]


class MockAssistant:
    """Very small rule-based assistant for tests.

    It supports basic Chinese keywords to decide the action type.
    """

    def run_instruction(self, nl_text: str, *, apply_changes: bool = True) -> AssistantResult:
        text = (nl_text or "").lower()
        operation: Dict[str, Any] = {"action": "noop", "data": {}, "summary": "无意义的操作"}
        api_response = None

        if any(k in text for k in ("创建", "新建", "加一个", "add", "create")):
            # create with title equal to the instruction (shortened)
            title = nl_text.strip()
            operation = {"action": "create", "data": {"title": title}, "summary": f"创建 待办: {title}"}

        elif any(k in text for k in ("列出", "显示", "查看", "list", "show")):
            operation = {"action": "list", "data": {}, "summary": "列出待办"}

        elif any(k in text for k in ("删除", "移除", "删掉", "delete", "remove")):
            # try to detect numeric id
            import re

            m = re.search(r"(\d+)", nl_text)
            if m:
                operation = {"action": "delete", "data": {"id": int(m.group(1))}, "summary": f"删除 id {m.group(1)}"}
            else:
                operation = {"action": "list", "data": {}, "summary": "寻找候选以删除"}

        elif any(k in text for k in ("更新", "修改", "改为", "update", "modify")):
            m = None
            import re

            m = re.search(r"(\d+)", nl_text)
            if m:
                operation = {"action": "update", "data": {"id": int(m.group(1)), "title": nl_text.strip()}, "summary": f"更新 id {m.group(1)}"}
            else:
                operation = {"action": "list", "data": {}, "summary": "寻找候选以更新"}

        # Optionally apply the API changes so GUI list refresh shows the effect
        if apply_changes and operation.get("action") not in (None, "noop", "list"):
            payload = json.dumps({"action": operation["action"], "data": operation.get("data", {})}, ensure_ascii=False)
            try:
                api_resp_text = api_module.handle_json_request(payload)
                api_response = json.loads(api_resp_text)
            except Exception as exc:  # pragma: no cover - defensive
                api_response = {"status": "error", "message": str(exc)}

        return AssistantResult(operation=operation, summary=operation.get("summary", ""), api_response=api_response)
